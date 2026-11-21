"""Versions of the legal parameters saved in the admin panel: the `param_versions` table.

The base version is the JSON file in the repo. A saved version is a full copy of the parameters
with some numbers changed, valid from a date. Without Supabase settings, or before the migration
is applied, versions are kept in memory (like sessions), so the panel still works in a demo.

A stored version is read onto the base file (`merge_onto_base`): its numbers win, blocks it lacks
(added to the engine after it was saved) come from the base file, and sources, notes and rules
always come from the base file: a version from the panel changes only numbers.
"""

import datetime as dt
import logging
from collections.abc import Mapping
from typing import Protocol
from uuid import UUID, uuid4

from postgrest.exceptions import APIError
from pydantic import BaseModel, Field, TypeAdapter, ValidationError, field_validator
from supabase import AsyncClient, acreate_client

from app.engine import Params
from app.services.params import load_params

logger = logging.getLogger(__name__)

TABLE = "param_versions"
TABLE_MISSING = "PGRST205"


def merge_onto_base(stored: Mapping[str, object], base: Params) -> Params:
    """A stored version over the base file, block by block (`maternity`, `money`, ...). A block
    the version lacks, or whose numbers no longer fit the model, is the base file's."""
    base_json = base.model_dump(mode="json")
    merged = dict(base_json)
    if isinstance(stored.get("version"), str):
        merged["version"] = stored["version"]
    for name, field in Params.model_fields.items():
        block = stored.get(name)
        if name in ("version", "description") or not isinstance(block, Mapping):
            continue
        candidate = _numbers_onto(base_json[name], block)
        try:
            TypeAdapter(field.annotation).validate_python(candidate)
        except ValidationError:
            logger.warning("Stored parameters: block `%s` does not fit, base file used.", name)
            continue
        merged[name] = candidate
    return Params.model_validate(merged)


def _numbers_onto(base: object, stored: object) -> object:
    """`base` with the numbers of `stored` in the same places: every parameter's `value` and
    plain numbers (e.g. the days of the hospital rule). Sources, notes and texts stay `base`'s."""
    if isinstance(base, dict):
        if not isinstance(stored, Mapping):
            return base
        merged = {}
        for key, value in base.items():
            if key == "sources" or key not in stored:
                merged[key] = value
            elif key == "value":
                merged[key] = stored[key]
            else:
                merged[key] = _numbers_onto(value, stored[key])
        return merged
    if _is_number(base) and _is_number(stored):
        return stored
    return base


def _is_number(value: object) -> bool:
    return isinstance(value, int | float) and not isinstance(value, bool)


class ParamVersion(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    version: str
    effective_from: dt.date
    note: str
    params: Params
    created_at: dt.datetime = Field(default_factory=lambda: dt.datetime.now(dt.UTC))

    @field_validator("params", mode="before")
    @classmethod
    def onto_base(cls, value: object) -> object:
        """Stored parameters (a row's JSON) are read onto the base file, so a version saved
        before a new block of parameters existed still loads."""
        if isinstance(value, Mapping):
            return merge_onto_base(value, load_params())
        return value


class ParamStore(Protocol):
    name: str

    async def list(self) -> list[ParamVersion]: ...
    async def add(self, version: ParamVersion) -> None: ...


class MemoryParamStore:
    """Versions in this process only: lost on restart. For tests and as a fallback."""

    def __init__(self, name: str = "memory") -> None:
        self.name = name
        self._versions: list[ParamVersion] = []

    async def list(self) -> list[ParamVersion]:
        return [v.model_copy(deep=True) for v in self._versions]

    async def add(self, version: ParamVersion) -> None:
        self._versions.append(version.model_copy(deep=True))


class SupabaseParamStore:
    name = "supabase"

    def __init__(self, client: AsyncClient) -> None:
        self._client = client

    async def list(self) -> list[ParamVersion]:
        rows = (await self._client.table(TABLE).select("*").execute()).data
        return [ParamVersion.model_validate(row) for row in rows]

    async def add(self, version: ParamVersion) -> None:
        await self._client.table(TABLE).insert(version.model_dump(mode="json")).execute()


def active_params(base: Params, versions: list[ParamVersion], today: dt.date) -> Params:
    """The newest version whose date has come; the base file when there is none."""
    valid = [v for v in versions if v.effective_from <= today]
    if not valid:
        return base
    return max(valid, key=lambda v: (v.effective_from, v.created_at)).params


def active_version(versions: list[ParamVersion], today: dt.date) -> ParamVersion | None:
    valid = [v for v in versions if v.effective_from <= today]
    return max(valid, key=lambda v: (v.effective_from, v.created_at)) if valid else None


_memory = MemoryParamStore()
_missing_table = MemoryParamStore(
    "memory (brak tabeli param_versions w Supabase: zastosuj migrację)"
)
_supabase: dict[tuple[str, str], SupabaseParamStore] = {}


async def open_param_store(url: str, secret_key: str) -> ParamStore:
    """Supabase when it is configured and the table exists, otherwise memory (as for sessions)."""
    if not url or not secret_key:
        return _memory
    cached = _supabase.get((url, secret_key))
    if cached is not None:
        return cached
    client = await acreate_client(url, secret_key)
    try:
        await client.table(TABLE).select("id").limit(1).execute()
    except APIError as exc:
        if exc.code != TABLE_MISSING:
            raise
        logger.warning("Supabase has no `%s` table yet; parameter versions in memory.", TABLE)
        return _missing_table
    store = SupabaseParamStore(client)
    _supabase[(url, secret_key)] = store
    return store
