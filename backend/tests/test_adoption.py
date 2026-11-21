"""Guide section D: a child taken in for upbringing (adoption, non-professional foster family),
Labour Code art. 183. Expected dates were computed by hand from the rules:
- 20 weeks from 2.11.2026 end on 21.03.2027 (140 days); 31 weeks from 2.11.2026 on 6.06.2027;
- the request 7 days after 2.11.2026: 9.11.2026; the latest start 21 days after: 23.11.2026;
- 32 weeks of parental leave from 22.03.2027 end on 31.10.2027; 9 more weeks on 2.01.2028;
- a child born 10.05.2024 turns 14 on 10.05.2038: the last day before it is 9.05.2038;
- a foster child born 15.03.2020 turns 7 on 15.03.2027: taken in 16.11.2026, the leave ends on
  14.03.2027 (119 days); turning 10 on 15.03.2030, 31 weeks from 16.11.2026 end on 20.06.2027.
"""

import datetime as dt
from collections.abc import AsyncIterator, Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from pydantic_ai.models.function import AgentInfo, FunctionModel

from app.api.deps import get_chat_model, get_param_store, get_session_store, get_today
from app.assistant.describe import interview_questions
from app.engine import Scenario, ScenarioError, Timeline, build_timeline
from app.engine.models import Marker, Segment
from app.main import app
from app.services.param_versions import MemoryParamStore
from app.services.params import load_params
from app.services.sessions import MemorySessionStore
from tests.test_chat_api import (
    SESSION,
    ask,
    events,
    instructions_now,
    rejected,
    scripted,
    timeline_after,
)

PARAMS = load_params()
TODAY = dt.date(2026, 11, 21)
TAKEN = dt.date(2026, 11, 2)
BIRTH = dt.date(2024, 5, 10)
BIRTH_ONLY = {
    "due-date",
    "birth",
    "maternity",
    "maternity-prenatal",
    "prenatal-window",
    "work-until-birth",
    "personal-weeks",
    "medical-certificate",
    "supplementary",
}


def taken_in(**answers: Any) -> Timeline:
    base: dict[str, Any] = {
        "role": "mother",
        "work": "employment",
        "child_born": True,
        "taken_in": "adoption",
        "taken_in_on": TAKEN,
        "birth_date": BIRTH,
        "children_count": 1,
    }
    return build_timeline(Scenario.model_validate(base | answers), PARAMS, TODAY)


def span(timeline: Timeline, segment_id: str) -> tuple[str, dt.date, dt.date, int]:
    s = timeline.element(segment_id)
    assert isinstance(s, Segment), segment_id
    return s.lane, s.start, s.end, s.days


def day(timeline: Timeline, marker_id: str) -> dt.date:
    m = timeline.element(marker_id)
    assert isinstance(m, Marker), marker_id
    return m.date


def notes(timeline: Timeline) -> list[str]:
    return [n.id for n in timeline.notes]


def questions(**answers: Any) -> list[str]:
    base: dict[str, Any] = {"role": "mother", "work": "employment", "child_born": True}
    return [q.key for q in interview_questions(Scenario.model_validate(base | answers))]


def test_adoption_leave_then_parental_leave_of_both_parents() -> None:
    t = taken_in(father_work="employment")
    assert t.taken_in == "adoption"
    assert t.birth_date == TAKEN  # the timeline counts from the day of taking in
    assert [s.id for s in t.segments] == ["adoption-leave", "parental", "parental-father"]
    assert span(t, "adoption-leave") == ("mother", TAKEN, dt.date(2027, 3, 21), 140)
    assert span(t, "parental") == ("mother", dt.date(2027, 3, 22), dt.date(2027, 10, 31), 224)
    assert span(t, "parental-father") == (
        "father",
        dt.date(2027, 11, 1),
        dt.date(2028, 1, 2),
        63,
    )
    assert day(t, "taken-in") == TAKEN
    assert day(t, "leave-request-deadline") == dt.date(2026, 11, 9)
    assert day(t, "start-limit") == dt.date(2026, 11, 23)
    assert day(t, "parental-deadline") == dt.date(2038, 5, 9)
    # Pregnancy and the birth do not apply; no paternity leave before the ruling is final.
    assert not BIRTH_ONLY & {e.id for e in t.elements()}
    assert t.element("paternity") is None
    assert t.warnings == []
    assert notes(t) == [
        "situation",
        "insurance",
        "taken-in-leave",
        "taken-in-start",
        "parental",
        "paternity",
        "computed",
    ]


def test_the_father_takes_the_leave_when_he_fills_in() -> None:
    t = taken_in(role="father", mother_work="employment")
    assert span(t, "adoption-leave") == ("father", TAKEN, dt.date(2027, 3, 21), 140)
    # His share first (41 - 9 = 32 weeks), then the mother's 9 weeks.
    assert span(t, "parental-father")[1:] == (dt.date(2027, 3, 22), dt.date(2027, 10, 31), 224)
    assert span(t, "parental")[1:] == (dt.date(2027, 11, 1), dt.date(2028, 1, 2), 63)
    assert t.element("adoption-leave").summary.startswith("Tata ma urlop")  # type: ignore[union-attr]


def test_more_children_at_once_and_za_zyciem() -> None:
    twins = taken_in(children_count=2, birth_date=dt.date(2023, 1, 1))
    assert span(twins, "adoption-leave")[1:] == (TAKEN, dt.date(2027, 6, 6), 217)
    # 43 weeks together: the mother at most 34, the father 9.
    assert span(twins, "parental")[1:] == (dt.date(2027, 6, 7), dt.date(2028, 1, 30), 238)
    assert span(twins, "parental-father")[1:] == (dt.date(2028, 1, 31), dt.date(2028, 4, 2), 63)
    assert "more-children" in notes(twins)
    longer = taken_in(children_count=2, birth_date=dt.date(2023, 1, 1), za_zyciem=True)
    # 67 weeks together: the mother at most 58.
    assert span(longer, "parental")[1:] == (dt.date(2027, 6, 7), dt.date(2028, 7, 16), 406)
    assert "za-zyciem" in notes(longer)


def test_foster_care_ends_the_leave_before_the_child_turns_seven() -> None:
    t = taken_in(
        taken_in="foster", taken_in_on=dt.date(2026, 11, 16), birth_date=dt.date(2020, 3, 15)
    )
    assert span(t, "adoption-leave")[1:] == (dt.date(2026, 11, 16), dt.date(2027, 3, 14), 119)
    assert day(t, "age-limit") == dt.date(2027, 3, 15)
    # Parental leave as for a born child: until the end of the year the child turns 6.
    assert t.element("parental") is None
    assert any("31.12.2026" in w for w in t.warnings)
    assert t.element("paternity") is None  # no paternity leave in a foster family
    assert any("Urlopu ojcowskiego nie pokazujemy" in a for a in t.assumptions)


def test_postponed_schooling_moves_the_age_limit_to_ten() -> None:
    t = taken_in(
        taken_in="foster",
        taken_in_on=dt.date(2026, 11, 16),
        birth_date=dt.date(2020, 3, 15),
        children_count=2,
        school_postponed=True,
    )
    assert span(t, "adoption-leave")[1:] == (dt.date(2026, 11, 16), dt.date(2027, 6, 20), 217)
    assert t.element("age-limit") is None
    assert "school-postponed" in notes(t)


def test_at_least_nine_weeks_when_the_age_limit_comes_sooner() -> None:
    # Turns 14 on 1.12.2026: 29 days would be left, so the leave lasts 9 weeks, to 3.01.2027.
    t = taken_in(birth_date=dt.date(2012, 12, 1))
    assert span(t, "adoption-leave")[1:] == (TAKEN, dt.date(2027, 1, 3), 63)
    assert day(t, "age-limit") == dt.date(2026, 12, 1)
    assert "taken-in-minimum" in notes(t)
    # Parental leave must end before the 14th birthday: nothing fits after the leave.
    assert t.element("parental") is None
    assert any("30.11.2026" in w for w in t.warnings)


def test_no_leave_for_a_child_older_than_the_limit() -> None:
    t = taken_in(taken_in="foster", birth_date=dt.date(2018, 1, 1))
    assert t.segments == []
    assert [m.id for m in t.markers] == ["taken-in"]  # no request or start to plan
    assert any("skończyło 7 lat 01.01.2025" in w for w in t.warnings)
    leave = next(n for n in t.notes if n.id == "taken-in-leave")
    assert leave.kind == "risk"


def test_the_benefit_needs_sickness_insurance() -> None:
    t = taken_in(work="none")
    assert t.segments == []
    assert [m.id for m in t.markers] == ["taken-in"]
    insurance = next(n for n in t.notes if n.id == "insurance")
    assert insurance.kind == "risk"
    assert "drugi rodzic" in insurance.text


def test_on_a_contract_the_benefit_without_leave_and_without_a_leave_request() -> None:
    t = taken_in(work="contract", mother_insured=True)
    assert t.element("leave-request-deadline") is None
    leave = t.element("adoption-leave")
    assert isinstance(leave, Segment)
    assert any("nie dostaje urlopu" in d for d in leave.details)


def test_paternity_leave_within_twelve_months_of_the_final_ruling() -> None:
    t = taken_in(father_work="employment", adoption_final=True, adoption_final_on="2026-11-15")
    # From today (21.11.2026), 14 days; the time runs out on 14.11.2027.
    assert span(t, "paternity") == ("father", dt.date(2026, 11, 21), dt.date(2026, 12, 4), 14)
    assert day(t, "paternity-deadline") == dt.date(2027, 11, 14)
    # Never after the child turns 14: turning 14 on 1.12.2026, it ends on 30.11.2026.
    older = taken_in(
        birth_date=dt.date(2012, 12, 1),
        father_work="employment",
        adoption_final=True,
        adoption_final_on="2026-11-15",
    )
    assert span(older, "paternity")[1:] == (dt.date(2026, 11, 21), dt.date(2026, 11, 30), 10)
    # Not final yet: no paternity leave on the timeline, the note says when it starts.
    pending = taken_in(father_work="employment", adoption_final=False)
    assert pending.element("paternity") is None
    paternity = next(n for n in pending.notes if n.id == "paternity")
    assert "uprawomocni" in paternity.text


def test_without_the_number_of_children_only_the_day_of_taking_in() -> None:
    t = taken_in(children_count=None)
    assert t.segments == []
    assert notes(t)[-1] == "computed"
    assert t.notes[-1].title == "Co jeszcze policzymy"


@pytest.mark.parametrize(
    "answers",
    [
        {"birth_date": "2026-11-10"},  # born after being taken in
        {"adoption_final": True, "adoption_final_on": "2026-10-01"},  # final before taking in
    ],
)
def test_impossible_dates_are_rejected(answers: dict[str, Any]) -> None:
    with pytest.raises(ScenarioError):
        taken_in(**answers)


def test_the_interview_asks_only_what_this_path_needs() -> None:
    assert questions(taken_in="adoption") == [
        "taken-in",
        "child-birth",
        "children",
        "father-work",
        "adoption-ruling",
    ]
    done = {"taken_in_on": TAKEN, "birth_date": BIRTH, "children_count": 1}
    assert questions(taken_in="adoption", father_work="employment", **done) == ["adoption-ruling"]
    assert questions(taken_in="adoption", father_work="none", **done) == []
    # Foster care: no ruling; postponed schooling only when the age limit of 7 matters.
    assert questions(taken_in="foster", father_work="employment", **done) == []
    near_seven = {**done, "taken_in_on": "2026-11-16", "birth_date": "2020-03-15"}
    assert questions(taken_in="foster", father_work="employment", **near_seven) == [
        "school-postponed"
    ]


# The onboarding and the chat.


@pytest.fixture
def api() -> Iterator[TestClient]:
    """The API with an in-memory session store, as in test_chat_api.py."""
    store = MemorySessionStore()
    params = MemoryParamStore()
    app.dependency_overrides[get_today] = lambda: TODAY
    app.dependency_overrides[get_session_store] = lambda: store
    app.dependency_overrides[get_param_store] = lambda: params
    yield TestClient(app)
    app.dependency_overrides.clear()


ONBOARDING = {
    "role": "mother",
    "child_born": True,
    "date": "2024-05-10",  # the child's date of birth
    "children_count": 1,
    "work": "employment",
    "earnings": "5k-8k",
    "taken_in": {"kind": "adoption", "date": "2026-11-02"},
}


def test_onboarding_starts_the_adoption_path(api: TestClient) -> None:
    started = api.put(f"/api/session/{SESSION}/onboarding", json=ONBOARDING)
    assert started.status_code == 200, started.text
    scenario = started.json()["scenario"]
    assert (scenario["taken_in"], scenario["taken_in_on"], scenario["birth_date"]) == (
        "adoption",
        "2026-11-02",
        "2024-05-10",
    )
    assert (scenario["child_born"], scenario["due_date"]) == (True, None)
    timeline = started.json()["timeline"]
    assert timeline["taken_in"] == "adoption"
    leave = next(s for s in timeline["segments"] if s["id"] == "adoption-leave")
    assert (leave["start"], leave["end"]) == ("2026-11-02", "2027-03-21")
    assert started.json()["question"]["key"] == "father-work"

    seen = instructions_now(api)
    assert "przyjęte na wychowanie (adopcja)" in seen
    assert "Dzień przyjęcia dziecka na wychowanie: 02.11.2026." in seen
    assert "Następne pytanie wywiadu (zadaj je dokładnie tak): „Jak pracuje tata:" in seen
    assert "Potem: „Czy postanowienie sądu o przysposobieniu" in seen
    assert "urlop macierzyński przed porodem" not in seen.split("# Wywiad")[-1].split("\n\n")[-1]


def test_onboarding_checks_the_adoption_dates(api: TestClient) -> None:
    later = {**ONBOARDING, "date": "2026-11-10"}  # born after being taken in
    response = api.put(f"/api/session/{SESSION}/onboarding", json=later)
    assert response.status_code == 422
    assert "Sprawdź daty" in response.json()["detail"]
    too_old = {**ONBOARDING, "date": "2000-01-01"}
    assert api.put(f"/api/session/{SESSION}/onboarding", json=too_old).status_code == 422
    # Older answers without the new field still work.
    born = {k: v for k, v in ONBOARDING.items() if k != "taken_in"} | {"date": "2026-11-10"}
    started = api.put(f"/api/session/{SESSION}/onboarding", json=born).json()
    assert started["scenario"]["taken_in"] is None
    assert started["timeline"]["segments"][0]["id"] == "maternity"


def test_the_chat_records_a_child_taken_in(api: TestClient) -> None:
    update = timeline_after(
        api,
        "set_taken_in",
        {"kind": "foster", "taken_in_on": "2026-11-16", "child_birth_date": "2020-03-15"},
    )
    assert update["scenario"]["taken_in"] == "foster"
    # The day of taking in is on the timeline; the leave waits for the number of children.
    assert update["timeline"]["segments"] == []
    assert update["timeline"]["markers"][0]["id"] == "taken-in"
    assert update["question"]["key"] == "children"
    update = timeline_after(api, "set_children_count", {"count": 1})
    leave = next(s for s in update["timeline"]["segments"] if s["id"] == "adoption-leave")
    assert (leave["start"], leave["end"]) == ("2026-11-16", "2027-03-14")
    update = timeline_after(api, "set_school_postponed", {"postponed": True})
    leave = next(s for s in update["timeline"]["segments"] if s["id"] == "adoption-leave")
    assert leave["end"] == "2027-04-04"  # 20 weeks: the limit of 10 years no longer cuts it
    # A due date: the child is on the way after all, and the adoption answers go.
    update = timeline_after(api, "set_due_date", {"due_date": "2027-03-15"})
    assert (update["scenario"]["taken_in"], update["scenario"]["taken_in_on"]) == (None, None)


def test_the_adoption_ruling_adds_paternity_leave(api: TestClient) -> None:
    api.put(f"/api/session/{SESSION}/onboarding", json=ONBOARDING)
    timeline_after(api, "set_father_work", {"work": "employment"})
    update = timeline_after(api, "set_adoption_ruling", {"final": True, "final_on": "2026-11-15"})
    paternity = next(s for s in update["timeline"]["segments"] if s["id"] == "paternity")
    assert (paternity["start"], paternity["end"]) == ("2026-11-21", "2026-12-04")
    assert update["focus"] == "paternity"


def test_tools_follow_the_path(api: TestClient) -> None:
    api.put(f"/api/session/{SESSION}/onboarding", json=ONBOARDING)
    tools: list[str] = []

    async def stream(messages: list[object], info: AgentInfo) -> AsyncIterator[str]:
        tools.extend(t.name for t in info.function_tools)
        yield "Dobrze."

    app.dependency_overrides[get_chat_model] = lambda: FunctionModel(stream_function=stream)
    events(api.post("/api/chat", json={"session_id": SESSION, "message": "Tata ma etat"}))
    assert {"set_taken_in", "set_adoption_ruling", "set_father_work"} <= set(tools)
    assert not {"set_leave_before_birth", "set_hospital_care", "set_birth_date"} & set(tools)
    # Postponed schooling matters in foster care only.
    out = ask(api, scripted("set_school_postponed", {"postponed": True}, "…"), "…")
    assert rejected("set_school_postponed") in out


def test_birth_tools_are_hidden_and_adoption_tools_too_on_the_birth_path(
    api: TestClient,
) -> None:
    born = {k: v for k, v in ONBOARDING.items() if k != "taken_in"} | {"date": "2026-11-10"}
    api.put(f"/api/session/{SESSION}/onboarding", json=born)
    out = ask(api, scripted("set_adoption_ruling", {"final": False}, "…"), "…")
    assert rejected("set_adoption_ruling") in out
