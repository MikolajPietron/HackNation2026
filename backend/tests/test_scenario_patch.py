"""PATCH /api/session/{id}/scenario: the interface changes the scenario without the chat
(ZADANIA B.7). Expected dates are worked out by hand."""

import asyncio
import datetime as dt
import json
from collections.abc import AsyncIterator, Iterator
from typing import Any
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from pydantic_ai import ModelMessage, ModelRequest, UserPromptPart
from pydantic_ai.models.function import AgentInfo, FunctionModel

from app.api.deps import get_chat_model, get_param_store, get_session_store, get_today
from app.assistant.prompts import EVENT_MARKER
from app.main import app
from app.services.param_versions import MemoryParamStore
from app.services.sessions import MemorySessionStore, Session

TODAY = dt.date(2026, 11, 21)
SESSION = "2d6f0b3e-8a41-4c7e-9b15-3e7a2c9d4f60"
URL = f"/api/session/{SESSION}/scenario"
# Born 10.11.2026, one child, no leave before the birth: maternity leave 10.11.2026-29.03.2027
# (140 days, the day of birth is the first).
FAMILY: dict[str, Any] = {
    "role": "mother",
    "work": "employment",
    "father_work": "employment",
    "child_born": True,
    "birth_date": "2026-11-10",
    "children_count": 1,
    "leave_before_birth_weeks": 0,
    "hospital_care": False,
}


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
    asyncio.run(store.save(UUID(SESSION), Session.model_validate({"scenario": scenario})))


def segment(body: dict[str, Any], segment_id: str) -> tuple[str, str]:
    found = next(s for s in body["timeline"]["segments"] if s["id"] == segment_id)
    return found["start"], found["end"]


def test_the_parental_plan_from_the_interface_recalculates_the_timeline(
    client: TestClient, store: MemorySessionStore
) -> None:
    """The mother takes 20 weeks of parental leave from 30.03.2027 working half time all along:
    the part is longer by 20 × 1/2 = 10 weeks (KP art. 182¹ᶠ § 2), 30 weeks = 210 days, so it
    ends on 25.10.2027 (30.03 is day 1; 1.10 is day 186, 25.10 day 210)."""
    remember(store, FAMILY)
    plan = [{"parent": "mother", "weeks": 20, "work_fraction": "1/2"}]
    response = client.patch(URL, json={"parental_parts": plan})
    assert response.status_code == 200, response.text
    body = response.json()
    assert segment(body, "maternity") == ("2026-11-10", "2027-03-29")
    assert segment(body, "parental-mother-1") == ("2027-03-30", "2027-10-25")
    assert body["scenario"]["parental_parts"][0]["weeks"] == 20
    assert set(body) == {"scenario", "timeline", "question"}
    # Saved: a reload gets the same plan, and the chat history has a hidden note of the change.
    restored = client.get(f"/api/session/{SESSION}").json()
    assert restored["scenario"]["parental_parts"] == body["scenario"]["parental_parts"]
    assert restored["messages"] == []  # the note is not the user's words: hidden in the UI
    history = asyncio.run(store.load(UUID(SESSION))).history
    note = history[-1]["parts"][0]["content"]
    assert note.startswith(EVENT_MARKER)
    assert "parental_parts = " in note

    # Null clears a field: no plan, the mother's share is an option again.
    body = client.patch(URL, json={"parental_parts": []}).json()
    assert "parental" in {s["id"] for s in body["timeline"]["segments"]}


def test_the_rate_choice_and_unchanged_fields(
    client: TestClient, store: MemorySessionStore
) -> None:
    remember(store, FAMILY | {"mother_pay": 8000})
    body = client.patch(URL, json={"rate_815": True}).json()
    assert body["scenario"]["rate_815"] is True
    parental = next(p for p in body["timeline"]["payments"] if p["segment_id"] == "parental")
    assert parental["rate"] == 81.5
    # Sending the same value again changes nothing and adds no second note.
    before = len(asyncio.run(store.load(UUID(SESSION))).history)
    client.patch(URL, json={"rate_815": True})
    assert len(asyncio.run(store.load(UUID(SESSION))).history) == before


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        # More than half of full time: refused by the engine with its Polish message.
        (
            {"parental_parts": [{"parent": "mother", "weeks": 20, "work_fraction": "3/4"}]},
            "etatu",
        ),
        ({"rate_815": "może"}, "Nieprawidłowa wartość pola „rate_815”"),
        ({"favourite_colour": "zielony"}, "Nieznane pola scenariusza: favourite_colour"),
    ],
)
def test_wrong_changes_are_refused_in_polish(
    client: TestClient, store: MemorySessionStore, changes: dict[str, Any], message: str
) -> None:
    remember(store, FAMILY)
    response = client.patch(URL, json=changes)
    assert response.status_code == 422
    assert message in response.json()["detail"]
    # Nothing was saved.
    assert asyncio.run(store.load(UUID(SESSION))).scenario.parental_parts == []


def test_a_scenario_without_a_date_is_refused(client: TestClient) -> None:
    response = client.patch(URL, json={"children_count": 2})
    assert response.status_code == 422
    assert "Najpierw potrzebna jest data" in response.json()["detail"]


def test_the_next_chat_turn_sees_the_note(client: TestClient, store: MemorySessionStore) -> None:
    """The hidden note is merged with the next message, so the model knows what the interface
    changed and does not ask or record it again."""
    remember(store, FAMILY)
    client.patch(URL, json={"rate_815": False})
    seen: list[str] = []

    async def stream(messages: list[ModelMessage], info: AgentInfo) -> AsyncIterator[str]:
        for message in messages:
            if isinstance(message, ModelRequest):
                seen.extend(
                    p.content
                    for p in message.parts
                    if isinstance(p, UserPromptPart) and isinstance(p.content, str)
                )
        yield "Dobrze."

    app.dependency_overrides[get_chat_model] = lambda: FunctionModel(stream_function=stream)
    response = client.post("/api/chat", json={"session_id": SESSION, "message": "Co dalej?"})
    lines = [json.loads(line) for line in response.text.splitlines() if line]
    assert lines[-1]["type"] == "done"
    assert any(text.startswith(EVENT_MARKER) and "rate_815 = false" in text for text in seen)
    assert "Co dalej?" in seen
