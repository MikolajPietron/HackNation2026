"""ZADANIA B.17 and B.16: what the chat model gets at each stage of the family's case, the
cacheable prefix, the turn's settings and measurements, retries, and the interface notes."""

import asyncio
import datetime as dt
import json
from collections.abc import AsyncIterator, Iterator
from types import SimpleNamespace
from typing import Any
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from pydantic_ai import (
    ModelConnectionError,
    ModelMessage,
    ModelQuotaExceededError,
    ModelRateLimitError,
    ModelRequest,
    ToolReturnPart,
)
from pydantic_ai.messages import InstructionPart
from pydantic_ai.models.fallback import FallbackModel
from pydantic_ai.models.function import AgentInfo, DeltaToolCall, FunctionModel
from pydantic_ai.models.google import GoogleModel
from pydantic_ai.settings import ModelSettings

from app.api.chat import _error_message
from app.api.deps import (
    _chat_model,
    get_chat_model,
    get_param_store,
    get_session_store,
    get_today,
)
from app.assistant.agent import EVENT_MAX_TOKENS, MAX_TOKENS, _turn_settings
from app.assistant.guide import guide_sections
from app.assistant.prompts import BASE_INSTRUCTIONS, EVENT_MARKER, PATCH_NOTE
from app.assistant.stage import stage_topics
from app.engine import Scenario
from app.main import app
from app.services.param_versions import MemoryParamStore
from app.services.sessions import MemorySessionStore, Session

TODAY = dt.date(2026, 11, 21)
SESSION = "5b0d4c1e-8a7f-4f1d-9d64-2e3c7a9b1f20"
EXPECTING = {
    "role": "mother",
    "child_born": False,
    "due_date": "2027-03-15",
    "children_count": 1,
    "work": "employment",
}
BORN = {**EXPECTING, "child_born": True, "birth_date": "2026-10-01", "due_date": None}
SECTIONS = guide_sections()


@pytest.fixture
def store() -> MemorySessionStore:
    return MemorySessionStore()


@pytest.fixture
def client(store: MemorySessionStore) -> Iterator[TestClient]:
    app.dependency_overrides[get_today] = lambda: TODAY
    app.dependency_overrides[get_session_store] = lambda: store
    params = MemoryParamStore()
    app.dependency_overrides[get_param_store] = lambda: params
    yield TestClient(app)
    app.dependency_overrides.clear()


def remember(store: MemorySessionStore, scenario: dict[str, Any]) -> None:
    session = Session(scenario=Scenario.model_validate(scenario))
    asyncio.run(store.save(UUID(SESSION), session))


def recording(
    seen: list[AgentInfo], call: tuple[str, dict[str, Any]] | None = None, **settings: Any
) -> FunctionModel:
    """Records what every request sent; calls `call` once, then answers."""

    async def stream(messages: list[ModelMessage], info: AgentInfo) -> AsyncIterator[Any]:
        seen.append(info)
        last = messages[-1]
        answered = isinstance(last, ModelRequest) and any(
            isinstance(p, ToolReturnPart) for p in last.parts
        )
        if call is not None and not answered:
            yield {0: DeltaToolCall(call[0], json.dumps(call[1]), tool_call_id="call-1")}
        else:
            yield "Dobrze."

    return FunctionModel(stream_function=stream, settings=ModelSettings(**settings) or None)


def turn(client: TestClient, model: FunctionModel, **body: str) -> list[dict[str, Any]]:
    app.dependency_overrides[get_chat_model] = lambda: model
    response = client.post("/api/chat", json={"session_id": SESSION, **body})
    assert response.status_code == 200, response.text
    return [json.loads(line) for line in response.text.splitlines() if line]


def tools(info: AgentInfo) -> set[str]:
    return {t.name for t in info.function_tools}


def static(info: AgentInfo) -> list[InstructionPart]:
    return [p for p in info.model_request_parameters.instruction_parts or [] if not p.dynamic]


def test_the_stage_follows_the_family() -> None:
    def topics(**answers: Any) -> set[str]:
        return set(stage_topics(Scenario.model_validate(answers)))

    assert topics(**EXPECTING) == {"core", "birth", "pregnancy", "plans"}
    assert topics(**BORN) == {"core", "birth", "born", "plans"}
    taken_in = {"taken_in": "adoption", "child_born": True, "birth_date": "2024-05-10"}
    assert topics(**taken_in) == {"core", "taken-in"}
    # A stillbirth: the loss rules, no plans to make.
    assert topics(**BORN, losses=[{"stillborn": True}]) == {"core", "birth", "born", "loss"}
    # Sick leave in pregnancy, an amount, work in parental leave, a business.
    assert {"sick", "pregnancy"} <= topics(**BORN, sick_leave=True)
    assert "money" in topics(**EXPECTING, mother_pay=8000)
    assert "money" in topics(**EXPECTING, mother_pay="unknown")  # then 81,5% is asked
    assert "pay-history" in topics(**EXPECTING, mother_pay_history={"months": []})
    work = [{"parent": "mother", "weeks": 10, "work_fraction": "1/2"}]
    assert "work" in topics(**EXPECTING, parental_parts=work)
    assert "debt" in topics(**{**EXPECTING, "work": "business"})
    assert "job-loss" in topics(**EXPECTING, job_loss={"ended_on": "2026-11-30", "reason": "other"})
    assert "mother-event" in topics(**BORN, mother_event={"kind": "death", "start": "2026-11-01"})


def test_only_the_tools_that_can_apply_are_offered(
    client: TestClient, store: MemorySessionStore
) -> None:
    seen: list[AgentInfo] = []
    remember(store, EXPECTING)
    turn(client, recording(seen), message="…")
    expecting = tools(seen[-1])
    # Before the birth nothing that needs the date of birth, nothing of adoption.
    assert not {"set_child_loss", "set_mother_situation", "set_hospital_care"} & expecting
    assert not {"set_school_postponed", "set_adoption_ruling", "set_foster_before"} & expecting
    # What the parent may say at this stage stays: the birth, a job loss, a plan, the pay.
    for name in (
        "set_birth_date",
        "set_leave_before_birth",
        "set_medical_certificate",
        "set_job_loss",
        "set_parental_plan",
        "set_monthly_pay",
        "set_pay_history",
        "set_taken_in",
        "propose_plans",
        "explain_timeline_element",
    ):
        assert name in expecting, name
    # Each of these would only fail here: no contract of mandate, no sick leave.
    assert not {"set_voluntary_insurance", "set_mother_over_50", "set_rehab_benefit"} & expecting

    remember(store, BORN)
    turn(client, recording(seen), message="…")
    born = tools(seen[-1])
    assert {"set_hospital_care", "set_child_loss", "set_mother_situation"} <= born
    assert "set_medical_certificate" not in born

    # After a stillbirth: no plans and nothing about parental leave.
    remember(store, {**BORN, "losses": [{"stillborn": True}]})
    turn(client, recording(seen), message="…")
    lost = tools(seen[-1])
    assert not {"propose_plans", "stress_test", "set_parental_plan", "set_za_zyciem"} & lost
    assert "set_child_loss" in lost  # a correction stays possible

    # A mother without work has no rate to choose and no amount to give.
    remember(store, {**EXPECTING, "work": "none"})
    turn(client, recording(seen), message="…")
    assert not {"set_rate_choice", "set_monthly_pay", "set_pay_history"} & tools(seen[-1])


def test_a_fact_recorded_in_the_turn_brings_its_tools_and_sources(
    client: TestClient, store: MemorySessionStore
) -> None:
    """The prefix is the stage of the turn's start; a tool that changes the stage adds the new
    stage's tools and literal sources before the model answers."""
    seen: list[AgentInfo] = []
    remember(store, BORN)
    turn(
        client, recording(seen, ("set_child_loss", {"losses": [{"stillborn": True}]})), message="…"
    )
    before, after = seen
    loss_rule = SECTIONS["A.3"].text
    assert loss_rule not in (before.instructions or "")
    assert loss_rule in (after.instructions or "")
    assert static(before) == static(after)  # the cached prefix stays as it was

    seen.clear()
    remember(store, EXPECTING)
    turn(client, recording(seen, ("set_birth_date", {"birth_date": "2026-11-20"})), message="…")
    assert "set_hospital_care" not in tools(seen[0])
    assert "set_hospital_care" in tools(seen[1])


def test_the_prefix_is_the_same_for_every_turn_of_a_stage(
    client: TestClient, store: MemorySessionStore
) -> None:
    seen: list[AgentInfo] = []
    remember(store, EXPECTING)
    turn(client, recording(seen), message="Pierwsze pytanie")
    turn(client, recording(seen), message="Drugie pytanie")
    first, second = seen
    assert static(first) == static(second)
    assert first.function_tools == second.function_tools
    # Literal instructions first, then the current state: the order caching needs.
    parts = first.model_request_parameters.instruction_parts or []
    kinds = [p.dynamic for p in parts]
    assert kinds == sorted(kinds) and kinds[0] is False and kinds[-1] is True
    assert parts[0].content == BASE_INSTRUCTIONS.strip()
    assert "Aktualny stan osi czasu:" in parts[-1].content

    # An amount moves the family to another stage: the prefix carries the law on amounts.
    remember(store, {**EXPECTING, "mother_pay": 8000})
    turn(client, recording(seen), message="Trzecie pytanie")
    assert static(seen[-1]) != static(first)
    assert "[Ustawa zasiłkowa, art. 31 ust. 1]" in seen[-1].instructions  # type: ignore[operator]


def test_a_tool_result_says_only_what_changed(
    client: TestClient, store: MemorySessionStore
) -> None:
    """The whole timeline is in the current state; the tool result lists the changes only, so
    the history does not carry a copy of the timeline for every answer."""
    remember(store, EXPECTING)
    returned: list[str] = []

    async def stream(messages: list[ModelMessage], info: AgentInfo) -> AsyncIterator[Any]:
        answers = [p for p in messages[-1].parts if isinstance(p, ToolReturnPart)]
        if answers:
            returned.extend(str(p.content) for p in answers)
            yield "Zapisane."
        else:
            args = json.dumps({"weeks": 0})
            yield {0: DeltaToolCall("set_leave_before_birth", args, tool_call_id="call-1")}

    turn(client, FunctionModel(stream_function=stream), message="Pracuję do porodu")
    told = returned[0]
    assert "Na osi (id w nawiasach)" not in told
    assert "- [work-until-birth] Praca do dnia porodu" in told
    assert "[paternity]" not in told  # unchanged
    assert "Zniknęły z osi: [prenatal-window]" in told
    assert told.split("\n\n")[-1].startswith("Następne pytanie wywiadu")


def test_the_welcome_thinks_little_and_answers_briefly(
    client: TestClient, store: MemorySessionStore
) -> None:
    seen: list[AgentInfo] = []
    remember(store, EXPECTING)
    turn(client, recording(seen), event="timeline_ready")
    assert (seen[-1].model_settings or {}).get("max_tokens") == EVENT_MAX_TOKENS
    turn(client, recording(seen), message="…")
    assert (seen[-1].model_settings or {}).get("max_tokens") == MAX_TOKENS

    # Thinking (the scripted model drops it as unsupported, so it is checked on the hook).
    def settings(answers_allowed: bool, model: dict[str, Any]) -> ModelSettings:
        deps = SimpleNamespace(answers_allowed=answers_allowed)
        return _turn_settings(SimpleNamespace(deps=deps, model_settings=model))  # type: ignore[arg-type]

    # Not "minimal": Gemini Flash refuses it (400 INVALID_ARGUMENT).
    assert settings(False, {})["thinking"] == "low"
    assert settings(False, {"thinking": "high"})["thinking"] == "low"
    assert settings(True, {})["thinking"] == "low"
    # LLM_THINKING (the model's own setting) still decides the answers.
    assert settings(True, {"thinking": "high"})["thinking"] == "high"


def test_the_done_event_measures_the_turn(client: TestClient, store: MemorySessionStore) -> None:
    remember(store, EXPECTING)
    out = turn(client, recording([], ("set_children_count", {"count": 2})), message="Bliźnięta")
    done = out[-1]
    assert done["type"] == "done"
    usage = done["usage"]
    assert usage["requests"] == 2
    assert usage["input_tokens"] > 0 and usage["output_tokens"] > 0
    assert usage["first_text_s"] is not None and usage["total_s"] >= usage["first_text_s"]
    assert {"cache_read_tokens", "cache_write_tokens"} <= usage.keys()
    assert usage["cost_usd"] is None  # the scripted model has no price


def test_a_rate_limit_is_retried_once_then_told_in_polish(
    client: TestClient, store: MemorySessionStore
) -> None:
    remember(store, EXPECTING)
    calls: list[int] = []

    async def busy(messages: list[ModelMessage], info: AgentInfo) -> AsyncIterator[str]:
        calls.append(1)
        raise ModelRateLimitError("test", "429", retry_after=0)
        yield ""  # pragma: no cover

    out = turn(client, FunctionModel(stream_function=busy), message="…")
    assert len(calls) == 2  # one more attempt, then the message
    assert out[-1] == {"type": "error", "message": _error_message(ModelRateLimitError("m", "x"))}
    assert "przeciążony" in out[-1]["message"]

    # A busy model that answers on the second attempt: the parent sees only the answer.
    calls.clear()

    async def busy_once(messages: list[ModelMessage], info: AgentInfo) -> AsyncIterator[str]:
        calls.append(1)
        if len(calls) == 1:
            raise ModelRateLimitError("test", "429", retry_after=0)
        yield "Dobrze."

    out = turn(client, FunctionModel(stream_function=busy_once), message="…")
    assert len(calls) == 2
    assert [e["type"] for e in out] == ["text", "text", "done"]


def test_errors_are_short_and_polish() -> None:
    assert "połączyć" in _error_message(ModelConnectionError("m", "reset"))
    assert "limit konta" in _error_message(ModelQuotaExceededError("m", "402"))


def test_a_fallback_model_of_the_same_provider() -> None:
    model = _chat_model("google", "gemini-flash-latest", "key", None, "gemini-flash-lite-latest")
    assert isinstance(model, FallbackModel)
    assert [m.model_name for m in model.models] == [
        "gemini-flash-latest",
        "gemini-flash-lite-latest",
    ]
    plain = _chat_model("google", "gemini-flash-latest", "key", None, "")
    assert isinstance(plain, GoogleModel)
    # The stable prefix is cached, the conversation after the current state is not; the
    # agent retries once, not the SDK.
    assert plain.settings == {"cache": {"messages": False}, "max_retries": 0}


def test_the_assistant_knows_the_interface_notes(
    client: TestClient, store: MemorySessionStore
) -> None:
    """B.16: the note `PATCH /scenario` leaves in the history starts the way the instructions
    describe it, and the instructions send the parent to the cards instead of asking."""
    remember(store, EXPECTING)
    client.patch(f"/api/session/{SESSION}/scenario", json={"rate_815": True})
    history = asyncio.run(store.load(UUID(SESSION))).history
    note = history[-1]["parts"][0]["content"]
    assert note.startswith(f"{EVENT_MARKER} {PATCH_NOTE}")
    assert f"„{EVENT_MARKER} {PATCH_NOTE} …”" in BASE_INSTRUCTIONS
    assert "nigdy nie zapisuj jej drugi raz" in BASE_INSTRUCTIONS
    for card in ("„Jak dzielicie urlop rodzicielski?”", "„Planach dla Was”", "„Pieniądze”"):
        assert card in BASE_INSTRUCTIONS
    assert "Nie dopytuj od zera" in BASE_INSTRUCTIONS


def test_a_key_limit_or_spend_cap_says_so() -> None:
    """Found by the eval (22.11.2026): OpenRouter's key limit came as 403 and showed "Klucz API
    modelu jest nieprawidłowy"; Google's monthly spend cap came as 429 and showed "przeciążony".
    Both mean the money ran out, and the parent is told that."""
    from pydantic_ai.exceptions import ModelAuthenticationError

    from app.api.chat import QUOTA_MESSAGE

    key_limit = ModelAuthenticationError(
        "m", "Key limit exceeded (total limit). $5.32 of $5.00 used"
    )
    spend_cap = ModelRateLimitError("m", "429 RESOURCE_EXHAUSTED: monthly spending cap")
    assert _error_message(key_limit) == QUOTA_MESSAGE
    assert _error_message(spend_cap) == QUOTA_MESSAGE
    assert _error_message(ModelAuthenticationError("m", "invalid api key")) == (
        "Klucz API modelu jest nieprawidłowy."
    )
