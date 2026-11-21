"""The chat and session endpoints with a scripted model and an in-memory session store."""

import asyncio
import datetime as dt
import json
from collections.abc import AsyncIterator, Iterator
from typing import Any
from uuid import UUID

import httpx
import pytest
from fastapi.testclient import TestClient
from pydantic_ai import ModelMessage, ModelRequest, ToolReturnPart
from pydantic_ai.models.function import AgentInfo, DeltaToolCall, DeltaToolCalls, FunctionModel

from app.api.deps import get_chat_model, get_session_store, get_today
from app.config import Settings, get_settings
from app.main import app
from app.services.sessions import MemorySessionStore, Session

TODAY = dt.date(2026, 11, 21)
SESSION = "7f1c8f0e-4d7a-4b52-9c35-0d8a4f1c2b11"


def scripted(tool: str, args: dict[str, Any], reply: str) -> FunctionModel:
    """First request: call `tool` with `args`. After the tool answers: `reply`."""

    async def stream(
        messages: list[ModelMessage], info: AgentInfo
    ) -> AsyncIterator[str | DeltaToolCalls]:
        last = messages[-1]
        if isinstance(last, ModelRequest) and any(
            isinstance(p, ToolReturnPart) for p in last.parts
        ):
            yield reply
        else:
            yield {0: DeltaToolCall(tool, json.dumps(args), tool_call_id="call-1")}

    return FunctionModel(stream_function=stream)


@pytest.fixture
def store() -> MemorySessionStore:
    return MemorySessionStore()


@pytest.fixture
def client(store: MemorySessionStore) -> Iterator[TestClient]:
    app.dependency_overrides[get_today] = lambda: TODAY
    app.dependency_overrides[get_session_store] = lambda: store
    yield TestClient(app)
    app.dependency_overrides.clear()


def events(response: httpx.Response) -> list[dict[str, Any]]:
    assert response.status_code == 200, response.text
    return [json.loads(line) for line in response.text.splitlines() if line]


def ask(client: TestClient, model: FunctionModel, message: str) -> list[dict[str, Any]]:
    app.dependency_overrides[get_chat_model] = lambda: model
    return events(client.post("/api/chat", json={"session_id": SESSION, "message": message}))


def remember(store: MemorySessionStore, scenario: dict[str, Any]) -> None:
    """Put answers into the stored session, as if earlier turns had collected them."""
    asyncio.run(store.save(UUID(SESSION), Session.model_validate({"scenario": scenario})))


def test_interview_is_stored_and_restored(client: TestClient) -> None:
    model = scripted("set_due_date", {"due_date": "2027-03-15"}, "Mam datę.")
    out = ask(client, model, "Termin mam na 15 marca 2027")

    assert out[0] == {
        "type": "tool-call",
        "id": "call-1",
        "name": "set_due_date",
        "args": {"due_date": "2027-03-15"},
    }
    update = next(e for e in out if e["type"] == "timeline")
    assert update["scenario"]["due_date"] == "2027-03-15"
    assert update["scenario"]["child_born"] is False
    assert update["focus"] == "due-date"
    window = update["timeline"]["segments"][0]
    assert (window["id"], window["start"], window["end"]) == (
        "prenatal-window",
        "2027-02-01",
        "2027-03-14",
    )
    assert {"type": "tool-result", "id": "call-1", "name": "set_due_date", "ok": True} in out
    assert "".join(e["delta"] for e in out if e["type"] == "text") == "Mam datę."
    assert out[-1] == {"type": "done"}

    # Next answers: the server remembers the session; the client sends only the message.
    model = scripted("set_children_count", {"count": 1}, "Jedno dziecko.")
    update = next(e for e in ask(client, model, "Jedno") if e["type"] == "timeline")
    maternity = next(s for s in update["timeline"]["segments"] if s["id"] == "maternity")
    assert (maternity["start"], maternity["end"]) == ("2027-03-15", "2027-08-01")
    assert update["changed"] == ["maternity", "personal-weeks"]

    model = scripted("set_leave_before_birth", {"weeks": 2}, "Zapisane.")
    update = next(e for e in ask(client, model, "Dwa tygodnie") if e["type"] == "timeline")
    assert update["scenario"]["leave_before_birth_weeks"] == 2
    segments = [(s["id"], s["start"], s["end"]) for s in update["timeline"]["segments"]]
    assert segments == [
        ("maternity-prenatal", "2027-03-01", "2027-03-14"),
        ("maternity", "2027-03-15", "2027-07-18"),
    ]
    assert update["timeline"]["documents"][0]["done"] is False

    model = scripted("set_medical_certificate", {"has_certificate": True}, "Świetnie.")
    update = next(e for e in ask(client, model, "Mam zaświadczenie") if e["type"] == "timeline")
    assert update["timeline"]["documents"][0]["done"] is True
    assert update["changed"] == ["medical-certificate"]

    # After a page reload the UI gets the whole conversation and the timeline back.
    restored = client.get(f"/api/session/{SESSION}").json()
    assert [m["role"] for m in restored["messages"]] == ["user", "assistant"] * 4
    assert restored["messages"][0]["parts"] == [
        {"kind": "text", "text": "Termin mam na 15 marca 2027"}
    ]
    assert restored["messages"][1]["parts"] == [
        {
            "kind": "tool",
            "id": "call-1",
            "name": "set_due_date",
            "args": {"due_date": "2027-03-15"},
            "status": "done",
        },
        {"kind": "text", "text": "Mam datę."},
    ]
    assert restored["scenario"]["has_medical_certificate"] is True
    assert restored["timeline"]["documents"][0]["done"] is True

    # "Start over" forgets it.
    assert client.delete(f"/api/session/{SESSION}").status_code == 204
    empty = client.get(f"/api/session/{SESSION}").json()
    assert (empty["messages"], empty["timeline"]) == ([], None)


def test_born_child_from_the_chat(client: TestClient) -> None:
    model = scripted("set_birth_date", {"birth_date": "2026-11-10"}, "Gratulacje!")
    update = next(
        e for e in ask(client, model, "Urodził się 10.11.2026") if e["type"] == "timeline"
    )
    assert update["focus"] == "birth"
    assert update["scenario"]["child_born"] is True
    assert update["timeline"]["birth_date"] == "2026-11-10"
    assert update["timeline"]["segments"] == []

    model = scripted("set_birth_date", {"birth_date": "2027-01-10"}, "To data z przyszłości.")
    out = ask(client, model, "Urodził się 10 stycznia 2027")
    rejected = {"type": "tool-result", "id": "call-1", "name": "set_birth_date", "ok": False}
    assert rejected in out


def test_too_many_weeks_are_rejected(client: TestClient, store: MemorySessionStore) -> None:
    remember(store, {"due_date": "2027-03-15"})
    model = scripted("set_leave_before_birth", {"weeks": 8}, "Można najwyżej 6 tygodni.")
    out = ask(client, model, "Osiem tygodni")

    rejected = {
        "type": "tool-result",
        "id": "call-1",
        "name": "set_leave_before_birth",
        "ok": False,
    }
    assert rejected in out
    assert not any(e["type"] == "timeline" for e in out)
    assert out[-1] == {"type": "done"}
    step = client.get(f"/api/session/{SESSION}").json()["messages"][1]["parts"][0]
    assert (step["name"], step["status"]) == ("set_leave_before_birth", "failed")


def test_certificate_question_only_after_choosing_leave(
    client: TestClient, store: MemorySessionStore
) -> None:
    remember(store, {"due_date": "2027-03-15", "leave_before_birth_weeks": 0})
    model = scripted("set_medical_certificate", {"has_certificate": True}, "Najpierw urlop.")
    out = ask(client, model, "Mam zaświadczenie")
    assert not any(e["type"] == "timeline" for e in out)


def test_chat_without_api_key_is_unavailable(client: TestClient) -> None:
    app.dependency_overrides[get_settings] = lambda: Settings(
        llm_provider="openrouter", openrouter_api_key=""
    )
    response = client.post("/api/chat", json={"session_id": SESSION, "message": "Cześć"})
    assert response.status_code == 503
    assert "OPENROUTER_API_KEY" in response.json()["detail"]


def test_timeline_endpoint_without_ai(client: TestClient) -> None:
    response = client.post("/api/timeline", json={"due_date": "2027-03-15"})
    assert response.status_code == 200
    assert [s["id"] for s in response.json()["segments"]] == ["prenatal-window"]
    too_long = {"due_date": "2027-03-15", "leave_before_birth_weeks": 9}
    assert client.post("/api/timeline", json=too_long).status_code == 422


def test_health_says_where_sessions_are_stored(client: TestClient) -> None:
    assert client.get("/api/health").json() == {"status": "ok", "sessions": "memory"}


ONBOARDING = {
    "role": "father",
    "child_born": False,
    "date": "2027-03-15",
    "children_count": 2,
    "work": "employment",
    "earnings": "5k-8k",
}


def test_onboarding_answers_are_saved_and_used(client: TestClient) -> None:
    started = client.put(f"/api/session/{SESSION}/onboarding", json=ONBOARDING)
    assert started.status_code == 200
    scenario = started.json()["scenario"]
    assert {k: scenario[k] for k in ("role", "work", "earnings", "children_count")} == {
        "role": "father",
        "work": "employment",
        "earnings": "5k-8k",
        "children_count": 2,
    }
    assert (scenario["due_date"], scenario["child_born"], scenario["birth_date"]) == (
        "2027-03-15",
        False,
        None,
    )
    maternity = next(s for s in started.json()["timeline"]["segments"] if s["id"] == "maternity")
    assert maternity["end"] == "2027-10-17"  # twins: 31 weeks

    # The chat continues from the saved answers, and the assistant knows them.
    seen: list[str] = []

    async def stream(messages: list[ModelMessage], info: AgentInfo) -> AsyncIterator[str]:
        seen.append(info.instructions or "")
        yield "Kolejne pytanie."

    app.dependency_overrides[get_chat_model] = lambda: FunctionModel(stream_function=stream)
    events(client.post("/api/chat", json={"session_id": SESSION, "message": "Cześć"}))
    assert "Rozmawiasz z tatą" in seen[0]
    assert "tata pracuje na etacie" in seen[0]
    assert "urlop przed porodem (ile tygodni) czy praca do dnia porodu" in seen[0]
    assert "ile dzieci" not in seen[0]

    restored = client.get(f"/api/session/{SESSION}").json()
    assert restored["scenario"]["earnings"] == "5k-8k"
    assert restored["timeline"]["children_count"] == 2


def test_onboarding_checks_the_date(client: TestClient) -> None:
    born_in_future = {**ONBOARDING, "child_born": True, "date": "2027-01-10"}
    response = client.put(f"/api/session/{SESSION}/onboarding", json=born_in_future)
    assert response.status_code == 422
    assert "w przyszłości" in response.json()["detail"]

    born = {**ONBOARDING, "child_born": True, "date": "2026-11-10", "work": "none"}
    del born["earnings"]
    started = client.put(f"/api/session/{SESSION}/onboarding", json=born).json()
    assert started["scenario"]["birth_date"] == "2026-11-10"
    assert started["scenario"]["earnings"] is None
    assert [s["id"] for s in started["timeline"]["segments"]] == ["maternity"]
