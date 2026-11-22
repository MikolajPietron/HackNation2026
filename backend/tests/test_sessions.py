"""The local session store used without Supabase: a conversation survives a backend restart."""

import asyncio
from pathlib import Path
from uuid import uuid4

from app.engine import Scenario
from app.services.sessions import FileSessionStore, Session, open_session_store


def test_session_survives_a_new_store(tmp_path: Path) -> None:
    """`fastapi dev` reloads on every saved file: the next process must still know the due date
    the browser shows (22.11.2026: the assistant said it did not know it)."""
    session_id = uuid4()
    scenario = Scenario.model_validate({"due_date": "2027-03-01", "children_count": 1})
    history = [{"kind": "request", "parts": []}]
    session = Session(scenario=scenario, history=history)
    asyncio.run(FileSessionStore(tmp_path).save(session_id, session))

    restored = asyncio.run(FileSessionStore(tmp_path).load(session_id))

    assert restored.scenario == scenario
    assert restored.history == history
    assert list(tmp_path.iterdir()) == [tmp_path / f"{session_id}.json"]


def test_unknown_unreadable_and_deleted_sessions_start_empty(tmp_path: Path) -> None:
    store = FileSessionStore(tmp_path)
    assert asyncio.run(store.load(uuid4())) == Session()

    broken = uuid4()
    (tmp_path / f"{broken}.json").write_text("{not json", encoding="utf-8")
    assert asyncio.run(store.load(broken)) == Session()

    session_id = uuid4()
    asyncio.run(store.save(session_id, Session(history=[{"kind": "request", "parts": []}])))
    asyncio.run(store.delete(session_id))
    asyncio.run(store.delete(session_id))  # twice: nothing to delete is fine
    assert asyncio.run(store.load(session_id)) == Session()


def test_without_supabase_sessions_go_to_files(tmp_path: Path) -> None:
    store = asyncio.run(open_session_store("", "", tmp_path))
    assert isinstance(store, FileSessionStore)
    assert store.name == "file"
