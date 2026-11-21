"""The chat endpoint with a scripted model (no API key, no network)."""

import datetime as dt
import json
from collections.abc import AsyncIterator, Iterator
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient
from pydantic_ai import ModelMessage, ModelRequest, ToolReturnPart
from pydantic_ai.models.function import AgentInfo, DeltaToolCall, DeltaToolCalls, FunctionModel

from app.api.deps import get_chat_model, get_today
from app.config import Settings, get_settings
from app.main import app

TODAY = dt.date(2026, 11, 21)


def scripted(tool_args: dict[str, Any], reply: str) -> FunctionModel:
    """First request: call set_birth_date with `tool_args`. After the tool answers: `reply`."""

    async def stream(
        messages: list[ModelMessage], info: AgentInfo
    ) -> AsyncIterator[str | DeltaToolCalls]:
        last = messages[-1]
        if isinstance(last, ModelRequest) and any(
            isinstance(p, ToolReturnPart) for p in last.parts
        ):
            yield reply
        else:
            yield {0: DeltaToolCall("set_birth_date", json.dumps(tool_args), tool_call_id="call-1")}

    return FunctionModel(stream_function=stream)


@pytest.fixture
def client() -> Iterator[TestClient]:
    app.dependency_overrides[get_today] = lambda: TODAY
    yield TestClient(app)
    app.dependency_overrides.clear()


def events(response: httpx.Response) -> list[dict[str, Any]]:
    assert response.status_code == 200, response.text
    return [json.loads(line) for line in response.text.splitlines() if line]


def test_birth_date_from_chat_builds_the_timeline(client: TestClient) -> None:
    model = scripted({"birth_date": "2027-03-15", "child_born": False}, "Gotowe — oto oś czasu.")
    app.dependency_overrides[get_chat_model] = lambda: model
    out = events(client.post("/api/chat", json={"message": "Termin mam na 15 marca 2027"}))

    assert out[0] == {
        "type": "tool-call",
        "id": "call-1",
        "name": "set_birth_date",
        "args": {"birth_date": "2027-03-15", "child_born": False},
    }
    update = next(e for e in out if e["type"] == "timeline")
    assert update["scenario"]["birth_date"] == "2027-03-15"
    assert update["focus"] == "birth"
    maternity = next(s for s in update["timeline"]["segments"] if s["id"] == "maternity")
    assert (maternity["start"], maternity["end"]) == ("2027-03-15", "2027-08-01")
    assert {"type": "tool-result", "id": "call-1", "name": "set_birth_date", "ok": True} in out
    assert "".join(e["delta"] for e in out if e["type"] == "text") == "Gotowe — oto oś czasu."
    assert out[-1]["type"] == "done"

    # Next turn: the client sends back history + scenario; the run continues from there.
    next_model = scripted({"birth_date": "2027-03-20", "child_born": False}, "Przesunięte.")
    app.dependency_overrides[get_chat_model] = lambda: next_model
    body = {
        "message": "Jednak 20 marca",
        "history": out[-1]["history"],
        "scenario": update["scenario"],
    }
    update2 = next(
        e for e in events(client.post("/api/chat", json=body)) if e["type"] == "timeline"
    )
    assert "maternity" in update2["changed"]
    assert update2["timeline"]["birth_date"] == "2027-03-20"


def test_future_birth_of_a_born_child_is_rejected(client: TestClient) -> None:
    model = scripted({"birth_date": "2027-01-10", "child_born": True}, "Czy to termin porodu?")
    app.dependency_overrides[get_chat_model] = lambda: model
    out = events(client.post("/api/chat", json={"message": "Urodził się 10 stycznia 2027"}))

    assert {"type": "tool-result", "id": "call-1", "name": "set_birth_date", "ok": False} in out
    assert not any(e["type"] == "timeline" for e in out)
    assert out[-1]["type"] == "done"


def test_chat_without_api_key_is_unavailable(client: TestClient) -> None:
    app.dependency_overrides[get_settings] = lambda: Settings(
        llm_provider="openrouter", openrouter_api_key=""
    )
    response = client.post("/api/chat", json={"message": "Cześć"})
    assert response.status_code == 503
    assert "OPENROUTER_API_KEY" in response.json()["detail"]


def test_timeline_endpoint_without_ai(client: TestClient) -> None:
    response = client.post("/api/timeline", json={"birth_date": "2027-03-15", "children_count": 2})
    assert response.status_code == 200
    assert {s["id"] for s in response.json()["segments"]} == {
        "maternity",
        "parental-mother",
        "paternity",
        "parental-father",
    }
    bad = client.post(
        "/api/timeline", json={"birth_date": "2027-03-15", "maternity_weeks_before_birth": 9}
    )
    assert bad.status_code == 422
