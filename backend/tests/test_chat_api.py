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

from app.api.deps import get_chat_model, get_param_store, get_session_store, get_today
from app.assistant.prompts import STATIC_INSTRUCTIONS
from app.config import Settings, get_settings
from app.main import app
from app.services.param_versions import MemoryParamStore
from app.services.sessions import MemorySessionStore, Session

TODAY = dt.date(2026, 11, 21)
SESSION = "7f1c8f0e-4d7a-4b52-9c35-0d8a4f1c2b11"


def scripted(
    tool: str, args: dict[str, Any], reply: str, returned: list[str] | None = None
) -> FunctionModel:
    """First request: call `tool` with `args`. After the tool answers: `reply`.
    What the tool told the model goes into `returned`."""

    async def stream(
        messages: list[ModelMessage], info: AgentInfo
    ) -> AsyncIterator[str | DeltaToolCalls]:
        last = messages[-1]
        answers = (
            [p for p in last.parts if isinstance(p, ToolReturnPart)]
            if isinstance(last, ModelRequest)
            else []
        )
        if answers:
            if returned is not None:
                returned.extend(str(p.content) for p in answers)
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
    # Tests never reach the hosted Supabase: parameter versions stay in memory too.
    params = MemoryParamStore()
    app.dependency_overrides[get_param_store] = lambda: params
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
    assert update["changed"] == [
        "maternity",
        "parental",
        "paternity",
        "parental-father",
        "personal-weeks",
        "paternity-deadline",
        "parental-deadline",
    ]

    model = scripted("set_leave_before_birth", {"weeks": 2}, "Zapisane.")
    update = next(e for e in ask(client, model, "Dwa tygodnie") if e["type"] == "timeline")
    assert update["scenario"]["leave_before_birth_weeks"] == 2
    segments = [(s["id"], s["start"], s["end"]) for s in update["timeline"]["segments"]]
    assert segments == [
        ("maternity-prenatal", "2027-03-01", "2027-03-14"),
        ("maternity", "2027-03-15", "2027-07-18"),
        ("parental", "2027-07-19", "2028-02-27"),
        # The father: 14 days from the due date; his 9 weeks after the mother's parental leave
        # (28.02.2028 + 63 days - 1 = 30.04.2028, 2028 is a leap year).
        ("paternity", "2027-03-15", "2027-03-28"),
        ("parental-father", "2028-02-28", "2028-04-30"),
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
    health = client.get("/api/health").json()
    assert health == {"status": "ok", "sessions": "memory", "params": "memory"}


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
    # His own work says nothing about the mother's insurance: that is asked first.
    assert "Następne pytanie wywiadu (zadaj je dokładnie tak): „Jak pracuje mama:" in seen[0]
    assert "Potem: „Czy mama chce zacząć urlop macierzyński przed porodem" in seen[0]
    assert "Uprawnienie — Zasiłek macierzyński: potrzebne ubezpieczenie chorobowe." in seen[0]
    assert "Ułatwienie — Bliźnięta: dłuższy urlop." in seen[0]
    assert "Ile dzieci" not in seen[0]

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
    assert [s["id"] for s in started["timeline"]["segments"]] == ["maternity", "parental"]


def test_timeline_ready_event_starts_the_conversation(client: TestClient) -> None:
    client.put(f"/api/session/{SESSION}/onboarding", json=ONBOARDING)
    prompts: list[str] = []

    tools: list[list[str]] = []

    async def stream(messages: list[ModelMessage], info: AgentInfo) -> AsyncIterator[str]:
        prompts.append(str(messages[-1].parts[-1].content))  # type: ignore[union-attr]
        tools.append([t.name for t in info.function_tools])
        yield "Jako że dziecko jest w drodze, liczymy od przewidywanej daty porodu."

    app.dependency_overrides[get_chat_model] = lambda: FunctionModel(stream_function=stream)
    body = {"session_id": SESSION, "event": "timeline_ready"}
    out = events(client.post("/api/chat", json=body))
    assert prompts[0].startswith("⟦Zdarzenie z aplikacji⟧")
    assert "Wyjaśnienia sytuacji" in prompts[0]
    # The father filled in the interview: the closing question is about the mother.
    assert prompts[0].endswith(
        "Na końcu zadaj dokładnie to pytanie: „Jak pracuje mama: na etacie (umowa o pracę), na "
        "umowie zlecenia, prowadzi własną firmę czy nie pracuje?”"
    )
    assert out[-1] == {"type": "done"}
    # The parent answered nothing in this turn: the model can only point at the timeline.
    assert tools == [["explain_timeline_element"]]

    # The event is not the user's words: after a reload only the assistant's answer shows.
    restored = client.get(f"/api/session/{SESSION}").json()["messages"]
    assert [m["role"] for m in restored] == ["assistant"]
    assert restored[0]["parts"][0]["text"].startswith("Jako że dziecko jest w drodze")


def test_the_assistant_reacts_to_what_an_answer_changed(client: TestClient) -> None:
    """After a recalculation the UI and the model learn which points of the explanation changed;
    the model talks about those and asks the next question as given."""
    client.put(f"/api/session/{SESSION}/onboarding", json={**ONBOARDING, "role": "mother"})
    returned: list[str] = []
    model = scripted("set_leave_before_birth", {"weeks": 6}, "Urlop od 1 lutego 2027.", returned)
    out = ask(client, model, "Sześć tygodni przed porodem")

    timeline = next(e for e in out if e["type"] == "timeline")
    # The leave starts earlier: the protection ends earlier, the requests are due earlier.
    assert timeline["changed_notes"] == ["before-birth", "computed", "protection", "applications"]
    assert (
        "Zmienione punkty wyjaśnienia: „Urlop od 1 lutego 2027, 6 tyg. przed przewidywaną datą "
        "porodu”, "
        "„Co policzyliśmy”, „Ochrona przed zwolnieniem”, „Co złożyć i do kiedy”. Omów teraz "
        "tylko je" in returned[0]
    )
    assert (
        "„Czy masz już zaświadczenie lekarskie o przewidywanej dacie porodu?” Gdy użytkownik "
        "odpowie, najpierw zapisz odpowiedź narzędziem `set_medical_certificate`" in returned[0]
    )


def timeline_after(client: TestClient, tool: str, args: dict[str, Any]) -> dict[str, Any]:
    out = ask(client, scripted(tool, args, "Zapisane."), "…")
    return next(e for e in out if e["type"] == "timeline")


def test_the_mothers_work_and_insurance_decide_about_the_benefit(client: TestClient) -> None:
    """The father fills in: the chat asks how the mother works, then about the voluntary
    insurance; without it the benefit periods disappear and the interview ends."""
    client.put(f"/api/session/{SESSION}/onboarding", json=ONBOARDING)
    returned: list[str] = []
    model = scripted("set_mother_work", {"work": "contract"}, "Zlecenie.", returned)
    update = next(e for e in ask(client, model, "Mama ma zlecenie") if e["type"] == "timeline")
    assert update["scenario"]["mother_work"] == "contract"
    assert update["scenario"]["work"] == "employment"  # the father's own answer stays his
    # Also: no special protection for her, who pays her benefit, her ZAM (guide A.4, I).
    assert update["changed_notes"] == ["insurance", "protection", "payer", "applications"]
    assert "„Czy mama jest zgłoszona do dobrowolnego ubezpieczenia chorobowego" in returned[0]

    update = timeline_after(client, "set_voluntary_insurance", {"registered": False})
    # The mother has no benefit periods; the father, who works on a contract of employment,
    # keeps his paternity leave and parental leave (guide B.3, B.4).
    assert [s["id"] for s in update["timeline"]["segments"]] == ["paternity", "parental-father"]
    assert {s["lane"] for s in update["timeline"]["segments"]} == {"father"}
    assert [m["id"] for m in update["timeline"]["markers"]] == [
        "due-date",
        "paternity-deadline",
        "parental-deadline",
    ]
    assert [n["kind"] for n in update["timeline"]["notes"]] == [
        "situation",
        "risk",
        "right",
        "computed",
        "right",  # the employed father's protection
        "computed",  # who pays his benefit
        "computed",  # his requests
    ]
    assert update["focus"] == "due-date"

    seen: list[str] = []

    async def stream(messages: list[ModelMessage], info: AgentInfo) -> AsyncIterator[str]:
        seen.append(info.instructions or "")
        yield "Rozumiem."

    app.dependency_overrides[get_chat_model] = lambda: FunctionModel(stream_function=stream)
    events(client.post("/api/chat", json={"session_id": SESSION, "message": "Dziękuję"}))
    # Only who pays the father's benefit is left (the mother has none).
    assert (
        "„Czy Twój pracodawca zgłasza do ubezpieczenia chorobowego więcej niż 20 osób?" in (seen[0])
    )
    assert "pracodawca mamy" not in seen[0]

    # She registers after all: the timeline is back.
    update = timeline_after(client, "set_voluntary_insurance", {"registered": True})
    assert [s["id"] for s in update["timeline"]["segments"]] == [
        "prenatal-window",
        "maternity",
        "parental",
        "paternity",
        "parental-father",
    ]


def test_voluntary_insurance_is_only_for_a_contract_or_a_business(client: TestClient) -> None:
    client.put(f"/api/session/{SESSION}/onboarding", json={**ONBOARDING, "role": "mother"})
    out = ask(client, scripted("set_voluntary_insurance", {"registered": True}, "…"), "…")
    assert not any(e["type"] == "timeline" for e in out)

    # When the mother herself fills in, her work is her own onboarding answer.
    update = timeline_after(client, "set_mother_work", {"work": "business"})
    assert (update["scenario"]["work"], update["scenario"]["mother_work"]) == ("business", None)


def test_za_zyciem_from_the_chat_lengthens_parental_leave(client: TestClient) -> None:
    client.put(f"/api/session/{SESSION}/onboarding", json={**ONBOARDING, "role": "mother"})
    update = timeline_after(client, "set_za_zyciem", {"has_certificate": True})
    parental = next(s for s in update["timeline"]["segments"] if s["id"] == "parental")
    assert parental["days"] == 58 * 7  # twins: 67 weeks for both parents, minus the father's 9
    assert update["focus"] == "parental"
    assert "za-zyciem" in update["changed_notes"]


def test_hospital_stay_from_the_chat_adds_supplementary_leave(client: TestClient) -> None:
    born = {**ONBOARDING, "role": "mother", "child_born": True, "date": "2026-10-01"}
    client.put(f"/api/session/{SESSION}/onboarding", json={**born, "children_count": 1})
    update = timeline_after(client, "set_leave_before_birth", {"weeks": 0})
    assert "supplementary" not in [s["id"] for s in update["timeline"]["segments"]]

    returned: list[str] = []
    model = scripted("set_hospital_care", {"applies": True}, "Potrzebuję szczegółów.", returned)
    ask(client, model, "Tak, był w szpitalu")
    assert "„W którym tygodniu ciąży urodziło się dziecko, czy ważyło nie więcej niż" in returned[0]

    facts = {
        "applies": True,
        "birth_week": "28-37",
        "weight_up_to_1000g": False,
        "hospital_stays": [{"start": "2026-10-01", "end": "2026-10-09"}],
    }
    update = timeline_after(client, "set_hospital_care", facts)
    segments = {s["id"]: (s["start"], s["end"]) for s in update["timeline"]["segments"]}
    # 1-9.10 is 9 days, the day of birth counted: 2 weeks, right after maternity leave.
    assert segments["maternity"] == ("2026-10-01", "2027-02-17")
    assert segments["supplementary"] == ("2027-02-18", "2027-03-03")
    assert segments["parental"][0] == "2027-03-04"
    assert update["focus"] == "supplementary"

    update = timeline_after(client, "set_hospital_care", {"applies": False})
    assert "supplementary" not in [s["id"] for s in update["timeline"]["segments"]]
    assert update["scenario"]["hospital_stays"] == []


def test_hospital_stay_is_not_asked_before_the_birth(client: TestClient) -> None:
    client.put(f"/api/session/{SESSION}/onboarding", json={**ONBOARDING, "role": "mother"})
    out = ask(client, scripted("set_hospital_care", {"applies": True}, "…"), "…")
    assert {"type": "tool-result", "id": "call-1", "name": "set_hospital_care", "ok": False} in out


def test_a_user_message_has_every_tool(client: TestClient) -> None:
    client.put(f"/api/session/{SESSION}/onboarding", json=ONBOARDING)
    tools: list[str] = []

    async def stream(messages: list[ModelMessage], info: AgentInfo) -> AsyncIterator[str]:
        tools.extend(t.name for t in info.function_tools)
        yield "Dobrze."

    app.dependency_overrides[get_chat_model] = lambda: FunctionModel(stream_function=stream)
    events(client.post("/api/chat", json={"session_id": SESSION, "message": "Mama ma etat"}))
    assert {"set_mother_work", "set_children_count", "explain_timeline_element"} <= set(tools)


def test_chat_needs_a_message_or_an_event(client: TestClient) -> None:
    app.dependency_overrides[get_chat_model] = lambda: scripted("set_due_date", {}, "")
    neither = client.post("/api/chat", json={"session_id": SESSION})
    both = client.post(
        "/api/chat", json={"session_id": SESSION, "message": "Cześć", "event": "timeline_ready"}
    )
    assert (neither.status_code, both.status_code) == (422, 422)


def test_a_loss_is_recorded_only_when_the_parent_says_so(client: TestClient) -> None:
    """The interview never asks; after the loss of the only child it also stops asking about
    hospital stays."""
    born = {**ONBOARDING, "role": "mother", "child_born": True, "date": "2026-11-10"}
    client.put(f"/api/session/{SESSION}/onboarding", json={**born, "children_count": 1})
    update = timeline_after(client, "set_leave_before_birth", {"weeks": 0})
    questions = [n for n in update["timeline"]["notes"] if n["id"] == "loss"]
    assert questions == []

    returned: list[str] = []
    model = scripted("set_child_loss", {"losses": [{"stillborn": True}]}, "Przykro mi.", returned)
    update = next(
        e for e in ask(client, model, "Dziecko urodziło się martwe") if e["type"] == "timeline"
    )
    assert [s["id"] for s in update["timeline"]["segments"]] == ["maternity"]
    assert update["timeline"]["segments"][0]["end"] == "2027-01-04"
    assert "loss" in update["changed_notes"]
    assert "Wywiad: wszystko ustalone." in returned[0]
    assert "szpitalu" not in returned[0].split("Wywiad:")[1]

    # A correction removes it again.
    update = timeline_after(client, "set_child_loss", {"losses": []})
    assert "parental" in [s["id"] for s in update["timeline"]["segments"]]


def test_a_loss_needs_a_born_child(client: TestClient) -> None:
    client.put(f"/api/session/{SESSION}/onboarding", json={**ONBOARDING, "role": "mother"})
    out = ask(client, scripted("set_child_loss", {"losses": [{"stillborn": True}]}, "…"), "…")
    assert {"type": "tool-result", "id": "call-1", "name": "set_child_loss", "ok": False} in out


# Section B: the father.

FATHER_WORK = (
    "Jak pracuje tata: na etacie (umowa o pracę), na umowie zlecenia, prowadzi własną firmę "
    "czy nie pracuje?"
)
FATHER_INSURED = (
    "Czy tata jest zgłoszony do dobrowolnego ubezpieczenia chorobowego (opłaca składkę chorobową)?"
)
FATHER_INSURED_HIMSELF = (
    "Czy jesteś zgłoszony do dobrowolnego ubezpieczenia chorobowego (opłacasz składkę chorobową)?"
)
PAYER = (
    " zgłasza do ubezpieczenia chorobowego więcej niż 20 osób? Od tego zależy, czy zasiłek "
    "wypłaci on, czy ZUS. Możesz też odpowiedzieć, że nie wiesz."
)
MOTHER_PAYER_HERSELF = f"Czy Twój pracodawca{PAYER}"
FATHER_PAYER_CONTRACT = f"Czy płatnik składek z Twojej umowy zlecenia (zleceniodawca){PAYER}"


def interview(returned: str) -> str:
    """The interview part of a tool result: it comes last, after the timeline."""
    return returned.split("\n\n")[-1]


def next_question(question: str, tool: str) -> str:
    return (
        f"Następne pytanie wywiadu (zadaj je dokładnie tak): „{question}” Gdy użytkownik odpowie, "
        f"najpierw zapisz odpowiedź narzędziem {tool}, potem pisz."
    )


def rejected(tool: str) -> dict[str, Any]:
    return {"type": "tool-result", "id": "call-1", "name": tool, "ok": False}


def instructions_now(client: TestClient) -> str:
    """What the model is told about the current state at the start of the next turn."""
    seen: list[str] = []

    async def stream(messages: list[ModelMessage], info: AgentInfo) -> AsyncIterator[str]:
        seen.append(info.instructions or "")
        yield "Rozumiem."

    app.dependency_overrides[get_chat_model] = lambda: FunctionModel(stream_function=stream)
    events(client.post("/api/chat", json={"session_id": SESSION, "message": "…"}))
    return seen[0]


def test_the_fathers_questions_follow_the_mothers(client: TestClient) -> None:
    """The mother fills in: after her questions the chat asks how the father works and, on
    a contract or with a business, about his voluntary insurance. Nothing about taking over."""
    client.put(f"/api/session/{SESSION}/onboarding", json={**ONBOARDING, "role": "mother"})
    returned: list[str] = []
    ask(client, scripted("set_children_count", {"count": 2}, "Bliźnięta.", returned), "Dwoje")
    assert interview(returned[0]).startswith(
        "Następne pytanie wywiadu (zadaj je dokładnie tak): „Chcesz zacząć urlop macierzyński"
    )
    assert f"Potem: „{FATHER_WORK}” (narzędzie `set_father_work`)." in interview(returned[0])

    returned.clear()
    ask(client, scripted("set_leave_before_birth", {"weeks": 0}, "Zapisane.", returned), "Nie")
    assert interview(returned[0]).startswith(next_question(FATHER_WORK, "`set_father_work`"))

    returned.clear()
    model = scripted("set_father_work", {"work": "contract"}, "Zlecenie.", returned)
    update = next(e for e in ask(client, model, "Tata ma zlecenie") if e["type"] == "timeline")
    scenario = update["scenario"]
    assert (scenario["father_work"], scenario["work"]) == ("contract", "employment")
    assert update["focus"] in ("paternity", "maternity")
    assert interview(returned[0]).startswith(
        next_question(FATHER_INSURED, "`set_father_insurance`")
    )

    returned.clear()
    model = scripted("set_father_insurance", {"registered": True}, "Zapisane.", returned)
    update = next(e for e in ask(client, model, "Tak, płaci") if e["type"] == "timeline")
    assert update["scenario"]["father_insured"] is True
    assert interview(returned[0]).startswith(
        next_question(MOTHER_PAYER_HERSELF, '`set_payer_size` (parent: "mother")')
    )

    # A new job: the voluntary insurance no longer applies.
    update = timeline_after(client, "set_father_work", {"work": "employment"})
    assert (update["scenario"]["father_work"], update["scenario"]["father_insured"]) == (
        "employment",
        None,
    )

    state = instructions_now(client)
    assert "Wiadomo też, że tata pracuje na etacie (umowa o pracę)." in state
    assert "nie wykorzystuje" not in state


def test_the_father_answers_for_himself(client: TestClient) -> None:
    """The father fills in: his work is his own onboarding answer; the insurance question is
    addressed to him."""
    client.put(f"/api/session/{SESSION}/onboarding", json={**ONBOARDING, "work": "contract"})
    returned: list[str] = []
    ask(client, scripted("set_mother_work", {"work": "employment"}, "Etat.", returned), "Etat")
    assert f"Potem: „{FATHER_INSURED_HIMSELF}” (narzędzie `set_father_insurance`)." in interview(
        returned[0]
    )

    update = timeline_after(client, "set_father_work", {"work": "business"})
    assert (update["scenario"]["work"], update["scenario"]["father_work"]) == ("business", None)
    update = timeline_after(client, "set_father_insurance", {"registered": False})
    assert update["scenario"]["father_insured"] is False


def test_the_father_is_asked_about_even_when_the_mother_is_not_insured(
    client: TestClient,
) -> None:
    """His rights do not depend on her insurance, so the interview goes on to him."""
    client.put(f"/api/session/{SESSION}/onboarding", json={**ONBOARDING, "work": "contract"})
    returned: list[str] = []
    ask(client, scripted("set_mother_work", {"work": "none"}, "Rozumiem.", returned), "Nie")
    assert interview(returned[0]).startswith(
        next_question(FATHER_INSURED_HIMSELF, "`set_father_insurance`")
    )

    returned.clear()
    model = scripted("set_father_insurance", {"registered": True}, "Zapisane.", returned)
    update = next(e for e in ask(client, model, "Tak") if e["type"] == "timeline")
    assert update["scenario"]["father_insured"] is True
    assert interview(returned[0]) == next_question(
        FATHER_PAYER_CONTRACT, '`set_payer_size` (parent: "father")'
    )


def test_no_father_questions_once_no_child_lives(client: TestClient) -> None:
    born = {**ONBOARDING, "role": "mother", "child_born": True, "date": "2026-11-10"}
    client.put(f"/api/session/{SESSION}/onboarding", json=born)  # twins
    timeline_after(client, "set_leave_before_birth", {"weeks": 0})
    timeline_after(client, "set_hospital_care", {"applies": False})

    # One of the twins lives: the father's rights still matter.
    returned: list[str] = []
    model = scripted("set_child_loss", {"losses": [{"stillborn": True}]}, "Przykro mi.", returned)
    ask(client, model, "Jedno z dzieci urodziło się martwe")
    assert interview(returned[0]).startswith(next_question(FATHER_WORK, "`set_father_work`"))

    returned.clear()
    losses = [{"stillborn": True}, {"stillborn": True}]
    ask(client, scripted("set_child_loss", {"losses": losses}, "Przykro mi.", returned), "…")
    assert interview(returned[0]) == "Wywiad: wszystko ustalone."


def test_father_insurance_is_only_for_a_contract_or_a_business(client: TestClient) -> None:
    client.put(f"/api/session/{SESSION}/onboarding", json=ONBOARDING)  # he is employed
    out = ask(client, scripted("set_father_insurance", {"registered": True}, "…"), "…")
    assert rejected("set_father_insurance") in out
    assert not any(e["type"] == "timeline" for e in out)


def test_taking_over_maternity_leave_is_recorded_when_the_user_says_so(
    client: TestClient, store: MemorySessionStore
) -> None:
    """Before the birth too: the mother may apply for only 14 weeks straight away."""
    remember(
        store,
        {
            "role": "mother",
            "work": "employment",
            "father_work": "employment",
            "child_born": False,
            "due_date": "2027-03-15",
            "children_count": 2,
            "leave_before_birth_weeks": 0,
        },
    )
    update = timeline_after(client, "set_father_takeover", {"takes_over": True, "mother_weeks": 16})
    assert (
        update["scenario"]["father_takes_over"],
        update["scenario"]["mother_weeks_before_takeover"],
    ) == (True, 16)
    assert update["focus"] in ("maternity-father", "maternity")

    update = timeline_after(client, "set_father_takeover", {"takes_over": True})
    assert update["scenario"]["mother_weeks_before_takeover"] is None

    update = timeline_after(
        client, "set_father_takeover", {"takes_over": False, "mother_weeks": 16}
    )
    assert (
        update["scenario"]["father_takes_over"],
        update["scenario"]["mother_weeks_before_takeover"],
    ) == (False, None)

    # Fewer than 14 weeks only in the special situations.
    returned: list[str] = []
    args = {"takes_over": True, "mother_weeks": 10}
    out = ask(client, scripted("set_father_takeover", args, "…", returned), "…")
    assert rejected("set_father_takeover") in out
    assert not any(e["type"] == "timeline" for e in out)
    assert "co najmniej 14 tygodni" in returned[0]


def test_the_mothers_situation_needs_a_born_child(client: TestClient) -> None:
    client.put(f"/api/session/{SESSION}/onboarding", json=ONBOARDING)  # child on the way
    situation = {"kind": "hospital", "start": "2026-12-01"}
    out = ask(client, scripted("set_mother_situation", {"situation": situation}, "…"), "…")
    assert rejected("set_mother_situation") in out
    assert not any(e["type"] == "timeline" for e in out)


def test_the_mothers_situation_is_recorded_and_cleared(
    client: TestClient, store: MemorySessionStore
) -> None:
    remember(
        store,
        {
            "role": "father",
            "work": "employment",
            "mother_work": "employment",
            "child_born": True,
            "birth_date": "2026-08-01",
            "children_count": 1,
            "leave_before_birth_weeks": 0,
            "hospital_care": False,
        },
    )
    hospital = {"kind": "hospital", "start": "2026-10-05", "end": "2026-10-20"}
    update = timeline_after(client, "set_mother_situation", {"situation": hospital})
    assert update["scenario"]["mother_event"] == hospital
    assert update["focus"] in ("maternity-father", "maternity")

    update = timeline_after(client, "set_mother_situation", {"situation": None})
    assert update["scenario"]["mother_event"] is None

    # Only a hospital stay has an end.
    death_with_end = {"kind": "death", "start": "2026-10-05", "end": "2026-10-06"}
    out = ask(client, scripted("set_mother_situation", {"situation": death_with_end}, "…"), "…")
    assert rejected("set_mother_situation") in out
    assert not any(e["type"] == "timeline" for e in out)

    update = timeline_after(
        client, "set_mother_situation", {"situation": {"kind": "death", "start": "2026-10-05"}}
    )
    assert update["scenario"]["mother_event"] == {
        "kind": "death",
        "start": "2026-10-05",
        "end": None,
    }
    assert "Mama dziecka zmarła." in instructions_now(client)

    # A due date instead of a birth: the situation came after a birth, so it goes too.
    update = timeline_after(client, "set_due_date", {"due_date": "2027-03-15"})
    assert (update["scenario"]["child_born"], update["scenario"]["mother_event"]) == (False, None)


def test_the_fathers_leave_is_in_scope() -> None:
    scope = STATIC_INSTRUCTIONS.split("# Zakres\n")[1].split("\n")[0]
    assert "Tata: urlop ojcowski; jego część urlopu rodzicielskiego; przejęcie" in scope
    out_of_scope = next(
        line for line in STATIC_INSTRUCTIONS.splitlines() if line.startswith("- Pytania spoza")
    )
    for in_scope_now in ("ojcowski", "taty", "podział urlopu rodzicielskiego"):
        assert in_scope_now not in out_of_scope
    for still_out in ("kwoty zasiłku", "81,5%", "łączenie urlopu"):
        assert still_out in out_of_scope
    assert "przysposobieniu dziecka i w rodzinie zastępczej" in out_of_scope
    for tool in ("set_father_work", "set_father_insurance", "set_father_takeover"):
        assert f"`{tool}`" in STATIC_INSTRUCTIONS
    assert "`set_mother_situation`" in STATIC_INSTRUCTIONS


def test_the_ui_gets_the_same_next_question(client: TestClient) -> None:
    """The answer cards and chips follow the assistant's interview: one source of questions."""
    started = client.put(f"/api/session/{SESSION}/onboarding", json=ONBOARDING).json()
    assert started["question"]["key"] == "mother-work"  # the father filled in
    assert started["question"]["text"].startswith("Jak pracuje mama")
    update = timeline_after(client, "set_mother_work", {"work": "employment"})
    assert update["question"] == {
        "key": "leave-before-birth",
        "text": "Czy mama chce zacząć urlop macierzyński przed porodem (ile tygodni wcześniej?), "
        "czy pracować do dnia porodu?",
    }
    assert client.get(f"/api/session/{SESSION}").json()["question"]["key"] == "leave-before-birth"


@pytest.mark.parametrize(
    ("due", "weeks", "born", "prenatal", "maternity_end"),
    [
        # Planned 4 weeks before 12.12 (from 14.11), born 20.11: the leave started on 14.11, so
        # 20 weeks end on 14.11.2026 + 139 days = 2.04.2027.
        ("2026-12-12", 4, "2026-11-20", ("2026-11-14", "2026-11-19"), "2027-04-02"),
        # Planned 2 weeks before 12.12 (from 28.11), born 20.11, before the leave began: no
        # leave before the birth, 20 weeks from the birth end on 8.04.2027.
        ("2026-12-12", 2, "2026-11-20", None, "2027-04-08"),
        # Planned 4 weeks before 14.11 (from 17.10), born late on 20.11: the leave still started
        # on 17.10 (34 days before the birth); 17.10.2026 + 139 days = 5.03.2027.
        ("2026-11-14", 4, "2026-11-20", ("2026-10-17", "2026-11-19"), "2027-03-05"),
    ],
)
def test_a_birth_off_the_due_date_keeps_the_real_start_of_the_leave(
    client: TestClient,
    due: str,
    weeks: int,
    born: str,
    prenatal: tuple[str, str] | None,
    maternity_end: str,
) -> None:
    expecting = {**ONBOARDING, "role": "mother", "date": due, "children_count": 1}
    client.put(f"/api/session/{SESSION}/onboarding", json=expecting)
    timeline_after(client, "set_leave_before_birth", {"weeks": weeks})
    update = timeline_after(client, "set_birth_date", {"birth_date": born})
    segments = {s["id"]: (s["start"], s["end"]) for s in update["timeline"]["segments"]}
    assert segments.get("maternity-prenatal") == prenatal
    assert segments["maternity"] == (born, maternity_end)


# Applications and protection (guide A.4, I).


def test_who_pays_is_asked_last_and_recorded(client: TestClient, store: MemorySessionStore) -> None:
    """After everything else the chat asks whether the employer reports more than 20 people to
    sickness insurance (guide page 1, footnote 1); the answer says who pays. A father with his
    own business is not asked: his ZAM goes straight to ZUS."""
    remember(
        store,
        {
            "role": "mother",
            "work": "employment",
            "father_work": "business",
            "father_insured": True,
            "child_born": False,
            "due_date": "2027-03-15",
            "children_count": 1,
            "leave_before_birth_weeks": 0,
        },
    )
    assert next_question(MOTHER_PAYER_HERSELF, '`set_payer_size` (parent: "mother")') in (
        instructions_now(client)
    )
    returned: list[str] = []
    model = scripted("set_payer_size", {"parent": "mother", "size": "over-20"}, "Jasne.", returned)
    update = next(e for e in ask(client, model, "Tak, ponad 20") if e["type"] == "timeline")
    assert update["scenario"]["mother_payer_size"] == "over-20"
    assert update["focus"] == "maternity-request"
    maternity = next(s for s in update["timeline"]["segments"] if s["id"] == "maternity")
    assert maternity["details"][-1].startswith("Zasiłek mamy wypłaca jej pracodawca")
    assert "payer" in update["changed_notes"]
    assert interview(returned[0]) == "Wywiad: wszystko ustalone."
    assert update["question"] is None

    # "Nie wiem" is an answer too: not asked again.
    update = timeline_after(client, "set_payer_size", {"parent": "mother", "size": "unknown"})
    assert update["scenario"]["mother_payer_size"] == "unknown"
    assert update["question"] is None


def test_who_pays_is_not_asked_for_a_business(
    client: TestClient, store: MemorySessionStore
) -> None:
    remember(
        store,
        {
            "role": "mother",
            "work": "employment",
            "father_work": "business",
            "due_date": "2027-03-15",
        },
    )
    model = scripted("set_payer_size", {"parent": "father", "size": "over-20"}, "Dobrze.")
    out = ask(client, model, "Tata ma ponad 20 pracowników")
    assert rejected("set_payer_size") in out
    assert not any(e["type"] == "timeline" for e in out)


def test_the_ui_gets_the_payer_question(client: TestClient, store: MemorySessionStore) -> None:
    remember(
        store,
        {
            "role": "father",
            "work": "contract",
            "father_insured": True,
            "mother_work": "none",
            "child_born": False,
            "due_date": "2027-03-15",
            "children_count": 1,
        },
    )
    restored = client.get(f"/api/session/{SESSION}").json()
    assert restored["question"] == {"key": "father-payer", "text": FATHER_PAYER_CONTRACT}
