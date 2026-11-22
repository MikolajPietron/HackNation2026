"""Where a conversation lives between requests: the `sessions` table in Supabase.

Only the backend talks to Supabase, with the secret key. Without Supabase settings, or before
the migration is applied, sessions are kept in local files so the app still works (and says so
in /api/health).
"""

import asyncio
import datetime as dt
import logging
import weakref
from pathlib import Path
from typing import Any, Protocol
from uuid import UUID, uuid4

from postgrest.exceptions import APIError
from pydantic import BaseModel, Field, ValidationError
from supabase import AsyncClient, acreate_client

from app.engine import Scenario

logger = logging.getLogger(__name__)

TABLE = "sessions"
TABLE_MISSING = "PGRST205"


class Session(BaseModel):
    scenario: Scenario = Field(default_factory=Scenario)
    history: list[dict[str, Any]] = Field(default_factory=list)
    """Pydantic AI message history, as JSON."""


_locks: "weakref.WeakValueDictionary[UUID, asyncio.Lock]" = weakref.WeakValueDictionary()


def session_lock(session_id: UUID) -> asyncio.Lock:
    """One writer per session at a time (ZADANIA B.15). A chat turn holds it from loading the
    session to saving it, so a change from the interface (`PATCH …/scenario`) cannot be lost when
    the turn saves at its end: the change is refused with 409 while the turn runs, and a turn
    that starts during a change waits for it. In-process only: one backend process, as in the
    demo; several processes would need a version column in the `sessions` table instead."""
    lock = _locks.get(session_id)
    if lock is None:
        lock = asyncio.Lock()
        _locks[session_id] = lock
    return lock


BUSY = (
    "Asystent właśnie odpowiada w tej rozmowie. Zmianę zapiszesz, gdy skończy: spróbuj ponownie "
    "za chwilę."
)
"""The 409 detail for a change from the interface while a chat turn runs."""


class SessionStore(Protocol):
    name: str

    async def load(self, session_id: UUID) -> Session: ...
    async def save(self, session_id: UUID, session: Session) -> None: ...
    async def delete(self, session_id: UUID) -> None: ...


class MemorySessionStore:
    """Sessions in this process only: lost on restart. For tests."""

    def __init__(self, name: str = "memory") -> None:
        self.name = name
        self._sessions: dict[UUID, Session] = {}

    async def load(self, session_id: UUID) -> Session:
        return self._sessions.get(session_id, Session()).model_copy(deep=True)

    async def save(self, session_id: UUID, session: Session) -> None:
        self._sessions[session_id] = session.model_copy(deep=True)

    async def delete(self, session_id: UUID) -> None:
        self._sessions.pop(session_id, None)


class FileSessionStore:
    """Sessions as JSON files in a local folder (outside git), one per session: the fallback
    without Supabase. They survive a restart of the backend: `fastapi dev` reloads on every saved
    file, and the in-memory fallback then forgot the plan the browser still showed, so the
    assistant said it did not know the due date (22.11.2026)."""

    def __init__(self, folder: Path, name: str = "file") -> None:
        self.name = name
        self._folder = folder

    def _path(self, session_id: UUID) -> Path:
        return self._folder / f"{session_id}.json"

    async def load(self, session_id: UUID) -> Session:
        try:
            raw = await asyncio.to_thread(self._path(session_id).read_text, encoding="utf-8")
        except FileNotFoundError:
            return Session()
        try:
            return Session.model_validate_json(raw)
        except ValidationError:
            logger.warning("Stored session is unreadable; starting the conversation again.")
            return Session()

    async def save(self, session_id: UUID, session: Session) -> None:
        await asyncio.to_thread(_write, self._path(session_id), session.model_dump_json())

    async def delete(self, session_id: UUID) -> None:
        await asyncio.to_thread(self._path(session_id).unlink, missing_ok=True)


def _write(path: Path, text: str) -> None:
    """Whole file or nothing: a reload in the middle of a save never leaves half a session."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.{uuid4().hex}.tmp")
    temporary.write_text(text, encoding="utf-8")
    temporary.replace(path)


class SupabaseSessionStore:
    name = "supabase"

    def __init__(self, client: AsyncClient) -> None:
        self._client = client

    async def load(self, session_id: UUID) -> Session:
        query = self._client.table(TABLE).select("scenario,history").eq("id", str(session_id))
        rows = (await query.limit(1).execute()).data
        return Session.model_validate(rows[0]) if rows else Session()

    async def save(self, session_id: UUID, session: Session) -> None:
        row = {
            "id": str(session_id),
            **session.model_dump(mode="json"),
            "updated_at": dt.datetime.now(dt.UTC).isoformat(),
        }
        await self._client.table(TABLE).upsert(row).execute()

    async def delete(self, session_id: UUID) -> None:
        await self._client.table(TABLE).delete().eq("id", str(session_id)).execute()


_supabase: dict[tuple[str, str], SupabaseSessionStore] = {}


async def open_session_store(url: str, secret_key: str, folder: Path) -> SessionStore:
    """Supabase when it is configured and the table exists, otherwise files in `folder`.

    A ready Supabase store is cached. While the table is missing we check again on every call,
    so the app switches over as soon as the migration is applied, without a restart.
    """
    if not url or not secret_key:
        return FileSessionStore(folder)
    cached = _supabase.get((url, secret_key))
    if cached is not None:
        return cached
    client = await acreate_client(url, secret_key)
    try:
        await client.table(TABLE).select("id").limit(1).execute()
    except APIError as exc:
        if exc.code != TABLE_MISSING:
            raise
        logger.warning("Supabase has no `%s` table yet; keeping sessions in files.", TABLE)
        return FileSessionStore(folder, "file (brak tabeli sessions w Supabase: zastosuj migrację)")
    store = SupabaseSessionStore(client)
    _supabase[(url, secret_key)] = store
    return store
