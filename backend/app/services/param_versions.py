"""Versions of the legal parameters saved in the admin panel: the `param_versions` table.

The base version is the JSON file in the repo. A saved version is a full copy of the parameters
with some numbers changed, valid from a date. Without Supabase settings, or before the migration
is applied, versions are kept in memory (like sessions), so the panel still works in a demo.
"""

import datetime as dt
import logging
from typing import Protocol
from uuid import UUID, uuid4

from postgrest.exceptions import APIError
from pydantic import BaseModel, Field
from supabase import AsyncClient, acreate_client

from app.engine import Params

logger = logging.getLogger(__name__)

TABLE = "param_versions"
TABLE_MISSING = "PGRST205"


class ParamVersion(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    version: str
    effective_from: dt.date
    note: str
    params: Params
    created_at: dt.datetime = Field(default_factory=lambda: dt.datetime.now(dt.UTC))


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
