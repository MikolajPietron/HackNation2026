"""F23 "Sprawdzanie wniosku przed złożeniem": every deterministic check on a hand-made request,
dates worked out by hand from the Labour Code days in the parameters, then the API with a
session's timeline and the optional AI rewording on a scripted model (no key, no network)."""

import asyncio
import datetime as dt
import json
from collections.abc import Iterator
from typing import Any
from uuid import UUID

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from pydantic_ai.messages import ModelMessage, ModelResponse, ToolCallPart
from pydantic_ai.models.function import AgentInfo, FunctionModel

from app.api.deps import get_param_store, get_session_store, get_today
from app.api.document_model import get_document_model_factory
from app.engine import Scenario, build_timeline
from app.engine.models import ChildLoss, HospitalStay, MotherEvent
from app.main import app
from app.request_check.adapter import field_key, read_request
from app.request_check.checks import check
from app.request_check.models import FilledRequest, RequestCheckResult, RequestField
from app.request_check.phrasing import apply_phrasing, keeps_facts
from app.services.param_versions import MemoryParamStore
from app.services.params import load_params
from app.services.sessions import MemorySessionStore, Session

TODAY = dt.date(2026, 11, 22)
PARAMS = load_params()
BIRTH = dt.date(2026, 10, 1)


def born(**changes: Any) -> Scenario:
    """Born 1 October 2026, mother employed with her pay given (so the 81,5% deadline is on the
    timeline), no leave before the birth. Maternity leave runs
    to 17 February 2027 (20 weeks), her parental leave from 18 February 2027 (option), the
    81,5% request until 22 October 2026, paternity leave until 30 September 2027, parental leave
    until 31 December 2032."""
    base = Scenario(
        role="mother",
        work="employment",
        father_work="employment",
        child_born=True,
        birth_date=BIRTH,
        children_count=1,
        leave_before_birth_weeks=0,
        mother_pay=6000,
    )
    return base.model_copy(update=changes)


def run(
    title: str,
    *fields: tuple[str, str | None],
    scenario: Scenario | None = None,
    timeline: bool = True,
    **request: Any,
) -> RequestCheckResult:
    filled = FilledRequest(
        title=title,
        fields=[RequestField(label=label, value=value) for label, value in fields],
        **request,
    )
    plan = build_timeline(scenario, PARAMS, TODAY) if scenario and timeline else None
    return check(filled, params=PARAMS, today=TODAY, scenario=scenario, timeline=plan)


def problems(result: RequestCheckResult, kind: str) -> list[Any]:
    return [p for p in result.problems if p.check == kind]


# ---------------------------------------------------------------------------------------------
# Reading the form (adapter)


def test_labels_become_keys() -> None:
    assert field_key("Data rozpoczęcia urlopu") == "start"
    assert field_key("Od kiedy") == "start"
    assert field_key("Do dnia") == "end"
    assert field_key("Okres urlopu") == "period"
    assert field_key("Liczba tygodni") == "weeks"
    assert field_key("Termin zakończenia urlopu macierzyńskiego") == "maternity_end"
    assert field_key("Termin powrotu do pracy") == "return_to_work"
    assert field_key("Data urodzenia dziecka") == "birth_date"
    assert field_key("Data złożenia wniosku") == "filed_on"
    assert field_key("Zasiłek w wysokości 81,5%") == "rate_815"
    assert field_key("Imię i nazwisko") is None


def test_the_form_is_read_in_one_place() -> None:
    filled = FilledRequest(
        title="Wniosek taty o urlop rodzicielski",
        fields=[
            RequestField(label="Okres urlopu", value="od 01.03.2027 do 2 maja 2027 r."),
            RequestField(label="Liczba tygodni", value=9),  # type: ignore[arg-type]
            RequestField(label="Data złożenia", value=dt.date(2026, 12, 1)),  # type: ignore[arg-type]
            RequestField(label="Imię i nazwisko", value=""),
            RequestField(label="Uwagi", value=None, required=False),
            RequestField(label="Załącznik: odpis aktu urodzenia", value=True),  # type: ignore[arg-type]
        ],
    )
    read = read_request(filled, PARAMS, TODAY)
    assert read.kind == "parental-father-request"
    assert read.parent == "father"
    assert (read.start, read.end, read.weeks) == (dt.date(2027, 3, 1), dt.date(2027, 5, 2), 9)
    assert read.filed_on == dt.date(2026, 12, 1)
    assert read.empty == ["Imię i nazwisko"]
    assert read.attachments == ["Załącznik: odpis aktu urodzenia"]


def test_the_timeline_document_id_names_the_request() -> None:
    by_id = FilledRequest(title="Wniosek", form_id="father-benefit-request")
    assert read_request(by_id, PARAMS, TODAY).kind == "zam"
    assert read_request(FilledRequest(title="ZAM"), PARAMS, TODAY).kind == "zam"
    zam = FilledRequest(title="Wniosek o zasiłek macierzyński")
    assert read_request(zam, PARAMS, TODAY).kind == "zam"
    assert read_request(FilledRequest(title="Coś innego"), PARAMS, TODAY).kind == "unknown"


# ---------------------------------------------------------------------------------------------
# Every check


def test_abolished_forms_after_24_october_2026() -> None:
    result = run("Wniosek ZUR", attachments=["Z-3b"])
    found = problems(result, "form-abolished")
    assert [p.message for p in found] == [
        "Formularz ZUR od 24 października 2026 r. jest zlikwidowany: połączono go z formularzem "
        "ZAM. Złóż wniosek ZAM.",
        "Formularz Z-3b od 24 października 2026 r. jest zlikwidowany.",
    ]
    assert all(p.severity == "error" and p.sources for p in found)
    assert result.ok is False
    before = run("Wniosek ZUR", filed_on=dt.date(2026, 10, 23))
    assert not problems(before, "form-abolished")


def test_empty_required_fields() -> None:
    result = run(
        "Wniosek o urlop ojcowski",
        ("Imię i nazwisko", " "),
        ("Okres urlopu", "—"),
        ("Od", "2026-12-14"),
    )
    assert [p.field for p in problems(result, "field-empty")] == [
        "Imię i nazwisko",
        "Okres urlopu",
    ]
    optional = FilledRequest(
        title="Wniosek o urlop ojcowski", fields=[RequestField(label="Uwagi", required=False)]
    )
    assert not problems(check(optional, params=PARAMS, today=TODAY), "field-empty")


def test_the_leave_cannot_end_before_it_starts() -> None:
    result = run("Wniosek o urlop rodzicielski", ("Od", "01.04.2027"), ("Do", "01.03.2027"))
    assert problems(result, "dates-order")[0].message == (
        "Koniec urlopu (01.03.2027) wypada przed jego początkiem (01.04.2027)."
    )


def test_dates_must_give_the_weeks_asked_for() -> None:
    # 18.02.2027 + 9 weeks − 1 day = 21.04.2027 (63 days).
    fine = run(
        "Wniosek o urlop rodzicielski",
        ("Od", "18.02.2027"),
        ("Do", "21.04.2027"),
        ("Liczba tygodni", "9"),
    )
    assert not problems(fine, "weeks-mismatch")
    off = run(
        "Wniosek o urlop rodzicielski",
        ("Od", "18.02.2027"),
        ("Do", "18.04.2027"),
        ("Liczba tygodni", "9"),
    )
    found = problems(off, "weeks-mismatch")[0]
    assert "to 60 dni, a we wniosku jest 9 tyg." in found.message
    assert found.sources == PARAMS.parental.week_is_7_days.sources


def test_parental_leave_deadline_21_days_before() -> None:
    # Start 01.12.2026 − 21 days = 10.11.2026: passed on 22.11.2026; filed today, in time for
    # leave from 22.11.2026 + 21 days = 13.12.2026.
    late = run("Wniosek o urlop rodzicielski", ("Od", "01.12.2026"), timeline=False)
    found = problems(late, "deadline-passed")[0]
    assert found.message == (
        "Termin minął 10.11.2026: wniosek składa się co najmniej 21 dni przed rozpoczęciem "
        "urlopu (01.12.2026). Złożony 22.11.2026 jest w terminie dla urlopu od 13.12.2026."
    )
    assert found.sources == PARAMS.applications.parental_days_before.sources
    assert found.field == "Od"
    # 13.12.2026 − 21 days = 22.11.2026: the last day, still in time.
    on_time = run("Wniosek o urlop rodzicielski", ("Od", "13.12.2026"))
    assert not problems(on_time, "deadline-passed")


def test_paternity_supplementary_and_resignation_deadlines() -> None:
    # Paternity: 7 days. 28.11.2026 − 7 = 21.11.2026, passed.
    paternity = run("Wniosek o urlop ojcowski", ("Od", "28.11.2026"))
    assert "Termin minął 21.11.2026" in problems(paternity, "deadline-passed")[0].message
    assert not problems(run("Wniosek o urlop ojcowski", ("Od", "29.11.2026")), "deadline-passed")
    # Supplementary: 21 days before maternity leave ends (10.12.2026 − 21 = 19.11.2026).
    supplementary = run(
        "Wniosek o uzupełniający urlop macierzyński",
        ("Termin zakończenia urlopu macierzyńskiego", "10.12.2026"),
    )
    found = problems(supplementary, "deadline-passed")[0]
    assert "Termin minął 19.11.2026" in found.message
    assert "Złożony" not in found.message, "a fixed day: no later start to suggest"
    # Giving up the rest of maternity leave: 7 days before the return (25.11.2026 − 7 = 18.11).
    resignation = run(
        "Wniosek o rezygnację z części urlopu macierzyńskiego",
        ("Termin powrotu do pracy", "25.11.2026"),
    )
    assert "Termin minął 18.11.2026" in problems(resignation, "deadline-passed")[0].message


def test_father_taking_over_has_no_deadline_when_the_mother_is_in_hospital() -> None:
    title = "Wniosek taty o część urlopu macierzyńskiego"
    # 01.12.2026 − 14 days = 17.11.2026, passed.
    takeover = run(title, ("Od", "01.12.2026"), scenario=born(), timeline=False)
    assert "Termin minął 17.11.2026" in problems(takeover, "deadline-passed")[0].message
    hospital = born(mother_event=MotherEvent(kind="hospital", start=dt.date(2026, 12, 1)))
    in_hospital = run(title, ("Od", "01.12.2026"), scenario=hospital, timeline=False)
    assert not problems(in_hospital, "deadline-passed")


def test_without_a_date_the_timeline_document_gives_the_deadline() -> None:
    # Supplementary leave on the timeline: its request is due 21 days before maternity leave
    # ends (17.02.2027 − 21 = 27.01.2027). Filed on 01.02.2027: too late.
    hospital = born(
        hospital_care=True,
        birth_week="28-37",
        birth_weight_up_to_1000g=False,
        hospital_stays=[HospitalStay(start=BIRTH, end=dt.date(2026, 10, 20))],
    )
    plan = build_timeline(hospital, PARAMS, TODAY)
    request = next(d for d in plan.documents if d.id == "supplementary-request")
    assert request.needed_by == dt.date(2027, 1, 27)
    filled = FilledRequest(
        title="Wniosek o uzupełniający urlop macierzyński", filed_on=dt.date(2027, 2, 1)
    )
    result = check(filled, params=PARAMS, today=TODAY, scenario=hospital, timeline=plan)
    found = problems(result, "deadline-passed")[0]
    assert "27.01.2027" in found.message
    assert found.element_id == "supplementary-request"


def test_parental_leave_of_the_mother_starts_after_maternity_leave() -> None:
    early = run("Wniosek o urlop rodzicielski", ("Od", "01.02.2027"), scenario=born())
    found = problems(early, "leave-order")[0]
    assert "urlop macierzyński trwa do 17.02.2027" in found.message
    assert found.sources == PARAMS.parental.after_maternity.sources
    assert found.element_id == "maternity"
    after = run("Wniosek o urlop rodzicielski", ("Od", "18.02.2027"), scenario=born())
    assert not problems(after, "leave-order")


def test_supplementary_leave_right_after_maternity_leave() -> None:
    wrong = run("Wniosek o uzupełniający urlop macierzyński", ("Od", "01.03.2027"), scenario=born())
    found = problems(wrong, "leave-order")[0]
    assert "według osi od 18.02.2027, a we wniosku od 01.03.2027" in found.message
    assert found.sources == PARAMS.supplementary.once_after_maternity.sources


def test_leave_after_its_last_day() -> None:
    paternity = run(
        "Wniosek o urlop ojcowski", ("Od", "05.10.2027"), ("Do", "18.10.2027"), scenario=born()
    )
    found = problems(paternity, "after-limit")[0]
    assert "najpóźniej do 30.09.2027" in found.message
    assert found.element_id == "paternity-deadline"
    assert found.sources
    parental = run(
        "Wniosek taty o urlop rodzicielski",
        ("Od", "01.12.2032"),
        ("Do", "15.01.2033"),
        scenario=born(),
    )
    assert "najpóźniej do 31.12.2032" in problems(parental, "after-limit")[0].message


def test_the_815_request_within_21_days_after_the_birth() -> None:
    late = run("Wniosek o zasiłek 81,5%", scenario=born())
    found = problems(late, "rate-815-late")[0]
    assert "do 22.10.2026: ten termin minął" in found.message
    assert found.element_id == "rate-815-deadline"
    in_zam = run("ZAM", ("Wybieram zasiłek 81,5%", "tak"), scenario=born())
    assert problems(in_zam, "rate-815-late")
    on_time = run("Wniosek o zasiłek 81,5%", scenario=born(), filed_on=dt.date(2026, 10, 22))
    assert not problems(on_time, "rate-815-late")


def test_dates_other_than_the_plan_are_pointed_out() -> None:
    other = run("Wniosek o urlop rodzicielski", ("Od", "01.03.2027"), scenario=born())
    found = problems(other, "differs-from-plan")[0]
    assert found.severity == "info"
    assert "zaczyna się 18.02.2027, a we wniosku 01.03.2027" in found.message
    assert "propozycja do wyboru" in found.message
    assert found.element_id == "parental"
    same = run("Wniosek o urlop rodzicielski", ("Od", "18.02.2027"), scenario=born())
    assert not problems(same, "differs-from-plan")


def test_attachments_of_guide_a4() -> None:
    stillborn = born(losses=[ChildLoss(stillborn=True)])
    zam = run("ZAM", scenario=stillborn, timeline=False)
    assert [p.message for p in problems(zam, "attachment-missing")] == [
        "Do wniosku dołącza się zaświadczenie o martwym urodzeniu: nie ma go na liście załączników."
    ]
    attached = run(
        "ZAM", scenario=stillborn, timeline=False, attachments=["Zaświadczenie o martwym urodzeniu"]
    )
    assert not problems(attached, "attachment-missing")

    za_zyciem = run("Wniosek o urlop rodzicielski", scenario=born(za_zyciem=True), timeline=False)
    assert "„Za życiem”" in problems(za_zyciem, "attachment-missing")[0].message
    found = problems(run("Wniosek o uzupełniający urlop macierzyński"), "attachment-missing")[0]
    assert "zaświadczenie ze szpitala" in found.message
    assert found.sources[0].article == "art. 180² § 5"


def test_leave_before_the_birth_needs_the_medical_certificate() -> None:
    expected = Scenario(
        role="mother", work="employment", child_born=False, due_date=dt.date(2027, 3, 15)
    )
    early = run("Wniosek o urlop macierzyński", ("Od", "01.02.2027"), scenario=expected)
    found = problems(early, "attachment-missing")[0]
    assert "zaświadczenie lekarskie o przewidywanej dacie porodu" in found.message
    attached = run(
        "Wniosek o urlop macierzyński",
        ("Od", "01.02.2027"),
        scenario=expected,
        attachments=["kopia zaświadczenia lekarskiego"],
    )
    assert not problems(attached, "attachment-missing")


def test_where_the_request_goes() -> None:
    to_zus = run("Wniosek o urlop rodzicielski", addressee="ZUS Oddział w Krakowie")
    found = problems(to_zus, "wrong-addressee")[0]
    assert found.message == "Wniosek o urlop składa się pracodawcy, a nie do ZUS."
    assert found.sources == PARAMS.applications.parental_days_before.sources
    business = born(work="business", mother_insured=True)
    zam = run("ZAM", scenario=business, timeline=False, addressee="Pracodawca")
    assert "bezpośrednio do ZUS" in problems(zam, "wrong-addressee")[0].message
    assert not problems(
        run("ZAM", scenario=business, timeline=False, addressee="ZUS"), "wrong-addressee"
    )
    employee = run("ZAM", scenario=born(), timeline=False)
    assert problems(employee, "wrong-addressee")[0].severity == "info"


def test_what_could_not_be_checked_is_said() -> None:
    result = run("Prośba", ("Imię i nazwisko", "Anna"))
    assert result.recognized is False
    assert {p.check for p in result.problems} == {"unknown-form", "no-timeline"}
    assert result.ok is True
    assert "leave-order" not in result.checks, "timeline checks need the timeline"


def test_a_good_request_has_no_problems() -> None:
    result = run(
        "Wniosek o urlop rodzicielski",
        ("Imię i nazwisko", "Jan Kowalski"),
        ("Od", "18.02.2027"),
        ("Do", "29.09.2027"),
        scenario=born(),
    )
    assert result.ok is True
    assert result.problems == []
    assert result.timeline_used is True
    assert result.kind_label == "Wniosek o urlop rodzicielski"


# ---------------------------------------------------------------------------------------------
# The AI may only reword


def test_a_rewording_must_keep_every_number_and_form() -> None:
    original = "Termin minął 10.11.2026: wniosek składa się co najmniej 21 dni przed urlopem."
    assert keeps_facts(original, "Spóźniłaś się: termin był 10.11.2026, 21 dni przed.", PARAMS)
    assert not keeps_facts(original, "Termin minął 10.11.2026.", PARAMS), "21 dropped"
    assert not keeps_facts(original, "Termin minął 10.11.2026, 21 dni, czyli 3 tygodnie.", PARAMS)
    assert not keeps_facts("Złóż wniosek ZAM.", "Złóż nowy wniosek.", PARAMS)


@pytest.fixture
def client() -> Iterator[TestClient]:
    store = MemorySessionStore()
    app.dependency_overrides[get_today] = lambda: TODAY
    app.dependency_overrides[get_session_store] = lambda: store
    params = MemoryParamStore()
    app.dependency_overrides[get_param_store] = lambda: params
    test_client = TestClient(app)
    test_client.store = store  # type: ignore[attr-defined]
    yield test_client
    app.dependency_overrides.clear()


def rewording(extra_number: bool = False) -> FunctionModel:
    def function(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        prompt = str(messages[0].parts[-1].content)  # type: ignore[union-attr]
        problems = []
        for line in prompt.splitlines()[1:]:
            problem_id, message = line[1:].split("] ", 1)
            text = f"Uwaga: {message}" + (" To 3 tygodnie." if extra_number else "")
            problems.append({"id": problem_id, "text": text})
        args = json.dumps({"problems": problems})
        return ModelResponse(parts=[ToolCallPart(tool_name=info.output_tools[0].name, args=args)])

    return FunctionModel(function, model_name="gemini-test")


BODY = {
    "request": {
        "title": "Wniosek o urlop rodzicielski",
        "addressee": "Pracodawca",
        "fields": [
            {"label": "Imię i nazwisko", "value": "", "source": "do uzupełnienia"},
            {"label": "Od", "value": "01.02.2027", "source": "oś czasu"},
        ],
    }
}


def test_the_api_checks_against_the_session_timeline(client: TestClient) -> None:
    session = "7a0c7f1e-3c2a-4f6b-9d7e-2a1b3c4d5e61"
    asyncio.run(client.store.save(UUID(session), Session(scenario=born())))  # type: ignore[attr-defined]
    body = client.post("/api/requests/check", json={**BODY, "session_id": session}).json()
    assert body["timeline_used"] is True
    assert {p["check"] for p in body["problems"]} == {
        "field-empty",
        "leave-order",
        "differs-from-plan",
    }
    assert body["ok"] is False
    assert body["ai"] is False
    assert all(p["phrased"] is None for p in body["problems"])


def test_the_ai_rewords_but_finds_nothing(client: TestClient) -> None:
    app.dependency_overrides[get_document_model_factory] = lambda: lambda: rewording()
    body = client.post(
        "/api/requests/check",
        json={**BODY, "scenario": born().model_dump(mode="json"), "phrase": True},
    ).json()
    assert body["ai"] is True
    assert body["ai_model"] == "gemini-test"
    checks = {p["check"] for p in body["problems"]}
    assert checks == {"field-empty", "leave-order", "differs-from-plan"}
    assert all(p["phrased"] == f"Uwaga: {p['message']}" for p in body["problems"])


def test_a_rewording_that_adds_a_number_is_dropped(client: TestClient) -> None:
    app.dependency_overrides[get_document_model_factory] = lambda: lambda: rewording(True)
    body = client.post("/api/requests/check", json={**BODY, "phrase": True}).json()
    assert body["ai"] is False
    assert all(p["phrased"] is None for p in body["problems"])


def test_without_an_allowed_model_the_check_still_works(client: TestClient) -> None:
    def refuse() -> FunctionModel:
        raise HTTPException(503, "Pisma i wnioski czyta tylko Claude albo Gemini.")

    app.dependency_overrides[get_document_model_factory] = lambda: refuse
    body = client.post("/api/requests/check", json={**BODY, "phrase": True}).json()
    assert body["ai"] is False
    assert "tylko Claude albo Gemini" in body["ai_note"]
    assert body["problems"]


def test_apply_phrasing_keeps_the_original_message() -> None:
    result = run("Wniosek o urlop ojcowski", ("Od", "28.11.2026"))
    problem = problems(result, "deadline-passed")[0]
    phrased = apply_phrasing(result.problems, {problem.id: "Za późno."}, PARAMS)
    assert next(p for p in phrased if p.id == problem.id).phrased is None
    assert next(p for p in phrased if p.id == problem.id).message == problem.message
