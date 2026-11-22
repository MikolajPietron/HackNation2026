"""Share the plan with the other parent (api/share.py): a read-only copy under a random token.

Born 10.11.2026, one child, no leave before the birth: maternity leave 10.11.2026-29.03.2027
(10.11.2026 + 139 days)."""

import asyncio
import datetime as dt
from collections.abc import Iterator
from typing import Any
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_param_store, get_session_store, get_today
from app.api.share import shared_id
from app.main import app
from app.services.param_versions import MemoryParamStore
from app.services.sessions import MemorySessionStore, Session

TODAY = dt.date(2026, 11, 21)
SESSION = "8b3d6c1a-2f47-4e09-9c5d-7a1e3b2f6d84"
FAMILY: dict[str, Any] = {
    "role": "mother",
    "work": "employment",
    "father_work": "employment",
    "child_born": True,
    "birth_date": "2026-11-10",
    "children_count": 1,
    "leave_before_birth_weeks": 0,
    "mother_pay": 8000,
}
HISTORY = [{"kind": "request", "parts": [{"part_kind": "user-prompt", "content": "Cześć"}]}]


@pytest.fixture
def store() -> MemorySessionStore:
    return MemorySessionStore()


@pytest.fixture
def client(store: MemorySessionStore) -> Iterator[TestClient]:
    params = MemoryParamStore()
    app.dependency_overrides[get_today] = lambda: TODAY
    app.dependency_overrides[get_session_store] = lambda: store
    app.dependency_overrides[get_param_store] = lambda: params
    yield TestClient(app)
    app.dependency_overrides.clear()


def remember(store: MemorySessionStore, scenario: dict[str, Any]) -> None:
    session = Session.model_validate({"scenario": scenario, "history": HISTORY})
    asyncio.run(store.save(UUID(SESSION), session))


def load(store: MemorySessionStore, session_id: UUID) -> Session:
    return asyncio.run(store.load(session_id))


def test_the_other_parent_sees_the_plan_read_only(
    client: TestClient, store: MemorySessionStore
) -> None:
    """The copy has the scenario and no conversation; the timeline is rebuilt from it."""
    remember(store, FAMILY)
    response = client.post(f"/api/session/{SESSION}/share")
    assert response.status_code == 200
    token = UUID(response.json()["token"])
    assert token != UUID(SESSION)

    shared = client.get(f"/api/shared/{token}")
    assert shared.status_code == 200
    body = shared.json()
    assert body["shared"] is True
    assert set(body) == {"scenario", "timeline", "shared"}
    assert body["scenario"]["birth_date"] == "2026-11-10"
    maternity = next(s for s in body["timeline"]["segments"] if s["id"] == "maternity")
    assert (maternity["start"], maternity["end"]) == ("2026-11-10", "2027-03-29")
    # The copy holds no conversation; the original keeps its own.
    copy = load(store, shared_id(token))
    assert copy.history == []
    assert copy.scenario == Session.model_validate({"scenario": FAMILY}).scenario
    assert load(store, UUID(SESSION)).history == HISTORY


def test_the_token_is_not_a_session_id(client: TestClient, store: MemorySessionStore) -> None:
    """Changing a session with the token's id leaves the shared copy as it was; changing the
    original afterwards does not reach the copy either."""
    remember(store, FAMILY)
    token = client.post(f"/api/session/{SESSION}/share").json()["token"]
    changed = client.patch(f"/api/session/{token}/scenario", json={"children_count": 2})
    assert changed.status_code == 422  # an empty session under that id: no date yet
    client.patch(f"/api/session/{SESSION}/scenario", json={"children_count": 2})
    body = client.get(f"/api/shared/{token}").json()
    assert body["scenario"]["children_count"] == 1
    # Sharing again gives a new link with the plan as it is now.
    again = client.post(f"/api/session/{SESSION}/share").json()["token"]
    assert again != token
    assert client.get(f"/api/shared/{again}").json()["scenario"]["children_count"] == 2


def test_unknown_links_and_empty_sessions(client: TestClient) -> None:
    for token in ("2c0e5f4a-9b1d-4c8e-a7f3-6d2b1e9c0a57", "nie-uuid"):
        response = client.get(f"/api/shared/{token}")
        assert response.status_code == 404
        assert response.json()["detail"].startswith("Nie znaleźliśmy tego planu.")
    response = client.post(f"/api/session/{SESSION}/share")
    assert response.status_code == 422
    assert response.json()["detail"].startswith("Nie ma jeszcze planu do udostępnienia")


def test_the_shared_link_has_no_way_to_write(client: TestClient) -> None:
    """Only GET exists for a shared plan."""
    url = "/api/shared/2c0e5f4a-9b1d-4c8e-a7f3-6d2b1e9c0a57"
    for method in ("post", "put", "patch", "delete"):
        assert getattr(client, method)(url).status_code == 405
