"""Guide section D: a child taken in for upbringing (adoption, non-professional foster family),
Labour Code art. 183. Expected dates were computed by hand from the rules:
- 20 weeks from 2.11.2026 end on 21.03.2027 (140 days); 31 weeks from 2.11.2026 on 6.06.2027;
- the request 7 days after 2.11.2026: 9.11.2026; the latest start 21 days after: 23.11.2026;
- 32 weeks of parental leave from 22.03.2027 end on 31.10.2027; 9 more weeks on 2.01.2028;
- a child born 10.05.2024 turns 14 on 10.05.2038: the last day before it is 9.05.2038;
- a foster child born 15.03.2020 turns 7 on 15.03.2027: taken in 16.11.2026, the leave ends on
  14.03.2027 (119 days); turning 10 on 15.03.2030, 31 weeks from 16.11.2026 end on 20.06.2027;
- passing the leave on after 14 weeks from 2.11.2026: 29 days of November + 31 + 31 + 7 = 98,
  so the first parent's part ends on 7.02.2027 and the other's runs 8.02-21.03.2027 (42 days);
  after 16 weeks: 29 + 31 + 31 + 21 = 112, to 21.02.2027, the rest 22.02-21.03.2027 (28 days);
- taken in 20.09.2026, born 1.09.2026 between the 28th and 37th week, in hospital from the birth
  to 10.10.2026: the 8 weeks after the birth end on 26.10.2026 (1.09 + 55 days), and from the
  day of taking in 11 days of September + 10 of October = 21 days count: 3 weeks. 20 weeks from
  20.09.2026: 11 + 31 + 30 + 31 + 31 = 134 days to 31.01.2027, 6 more: 6.02.2027; then
  supplementary leave 7.02-27.02.2027 and 32 weeks of parental leave: 28.02.2027 + 223 days =
  9.10.2027;
- foster leave from 3.08.2026, adoption application on 1.10.2026: 29 + 30 = 59 days used, so
  140 - 59 = 81 days from 1.10.2026: 31 + 30 + 20, to 20.12.2026; parental leave 21.12.2026 +
  223 days = 1.08.2027, the other parent's 9 weeks 2.08-3.10.2027 (30 + 30 + 3 = 63 days);
- foster leave of 140 days used in full and 10 weeks of foster parental leave: 41 - 10 = 31
  weeks left, 22 for the person on leave from 1.10.2026: 31 + 30 + 31 + 31 + 28 = 151, 3 more:
  3.03.2027; then 9 weeks 4.03-5.05.2027 (28 + 30 + 5 = 63 days).
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
}
"""Supplementary leave is not here: a stay in hospital after taking the child in gives it
(art. 183 § 3¹)."""


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
    # Section G last: the amounts of both parents (test_money.py: the choice of 81,5%).
    money = ["mother-pay", "father-pay"]
    assert questions(taken_in="adoption", father_work="employment", **done) == [
        "adoption-ruling",
        *money,
    ]
    assert questions(taken_in="adoption", father_work="none", **done) == ["mother-pay"]
    # Foster care: no ruling; postponed schooling only when the age limit of 7 matters.
    assert questions(taken_in="foster", father_work="employment", **done) == money
    near_seven = {**done, "taken_in_on": "2026-11-16", "birth_date": "2020-03-15"}
    assert questions(taken_in="foster", father_work="employment", **near_seven) == [
        "school-postponed",
        *money,
    ]


# The edge cases of art. 183: the other parent takes the leave, passing it on, supplementary
# leave, adoption after foster care.


def test_an_uninsured_persons_partner_takes_the_leave() -> None:
    t = taken_in(work="none", father_work="employment")
    assert span(t, "adoption-leave") == ("father", TAKEN, dt.date(2027, 3, 21), 140)
    # The father's share of parental leave (41 - 9); the mother, uninsured, has none.
    assert span(t, "parental-father")[1:] == (dt.date(2027, 3, 22), dt.date(2027, 10, 31), 224)
    assert t.element("parental") is None
    insurance = next(n for n in t.notes if n.id == "insurance")
    assert (insurance.kind, insurance.title) == (
        "right",
        "Tata ma prawo do zasiłku macierzyńskiego",
    )
    assert insurance.text.startswith("Mama nie podlega ubezpieczeniu chorobowemu")
    assert any("Zakładamy, że dziecko przyjęliście razem" in a for a in t.assumptions)
    # Nobody said how the father works: nobody is assumed, the interview asks.
    assert taken_in(work="none").segments == []
    done = {"taken_in_on": TAKEN, "birth_date": BIRTH, "children_count": 1}
    assert questions(taken_in="foster", work="none", **done) == ["father-work"]


def test_the_rest_of_the_leave_passes_to_the_other_parent_after_14_weeks() -> None:
    t = taken_in(father_work="employment", taken_in_handover=True)
    assert span(t, "adoption-leave") == ("mother", TAKEN, dt.date(2027, 2, 7), 98)
    assert span(t, "adoption-leave-other") == (
        "father",
        dt.date(2027, 2, 8),
        dt.date(2027, 3, 21),
        42,
    )
    # The total does not change: parental leave starts where it did.
    assert span(t, "parental")[1] == dt.date(2027, 3, 22)
    handover = next(n for n in t.notes if n.id == "handover")
    assert handover.kind == "choice"
    assert "a tata od 8 lutego 2027 do 21 marca 2027" in handover.text
    assert {s.article for s in handover.sources if s.doc == "kp"} >= {
        "art. 183 § 2",
        "art. 180 § 4",
        "art. 180 § 14",
    }
    later = taken_in(
        father_work="employment", taken_in_handover=True, taken_in_handover_after_weeks=16
    )
    assert span(later, "adoption-leave")[1:3] == (TAKEN, dt.date(2027, 2, 21))
    assert span(later, "adoption-leave-other")[1:] == (
        dt.date(2027, 2, 22),
        dt.date(2027, 3, 21),
        28,
    )


def test_passing_the_leave_on_needs_14_weeks_and_an_insured_parent() -> None:
    with pytest.raises(ScenarioError, match="co najmniej 14 tygodni"):
        taken_in(taken_in_handover=True, taken_in_handover_after_weeks=10)
    # A 9-week leave (the child turns 14 soon) leaves nothing to pass on after 14 weeks.
    with pytest.raises(ScenarioError, match="nie zostaje nic"):
        taken_in(birth_date=dt.date(2012, 12, 1), taken_in_handover=True)
    t = taken_in(father_work="none", taken_in_handover=True)
    assert t.element("adoption-leave-other") is None
    assert span(t, "adoption-leave")[2] == dt.date(2027, 3, 21)
    handover = next(n for n in t.notes if n.id == "handover")
    assert handover.kind == "risk"


SUPPLEMENTARY = {
    "taken_in_on": "2026-09-20",
    "birth_date": "2026-09-01",
    "father_work": "employment",
    "hospital_care": True,
    "birth_week": "28-37",
    "birth_weight_up_to_1000g": False,
}


def test_a_hospital_stay_after_taking_the_child_in_gives_supplementary_leave() -> None:
    t = taken_in(**SUPPLEMENTARY, hospital_stays=[{"start": "2026-09-01", "end": "2026-10-10"}])
    assert span(t, "adoption-leave")[1:3] == (dt.date(2026, 9, 20), dt.date(2027, 2, 6))
    assert span(t, "supplementary") == ("mother", dt.date(2027, 2, 7), dt.date(2027, 2, 27), 21)
    assert span(t, "parental")[1:3] == (dt.date(2027, 2, 28), dt.date(2027, 10, 9))
    supplementary = next(n for n in t.notes if n.id == "supplementary")
    assert supplementary.kind == "relief"
    assert "Po przyjęciu dziecka liczy się 21 dni w szpitalu, więc 3 tyg." in supplementary.text
    assert any(s.article == "art. 183 § 3¹" for s in supplementary.sources)
    # A stay that ended before the child was taken in does not count.
    before = taken_in(
        **SUPPLEMENTARY, hospital_stays=[{"start": "2026-09-01", "end": "2026-09-15"}]
    )
    assert before.element("supplementary") is None
    assert next(n for n in before.notes if n.id == "supplementary").kind == "risk"


def test_the_interview_asks_about_hospital_only_for_a_newborn_taken_in() -> None:
    young = {"taken_in_on": "2026-09-20", "birth_date": "2026-09-01", "children_count": 1}
    asked = questions(taken_in="adoption", father_work="employment", **young)
    assert asked[:1] == ["taken-in-hospital"]
    told = {**young, "hospital_care": True}
    asked = questions(taken_in="adoption", father_work="employment", **told)
    assert asked[:1] == ["taken-in-hospital-details"]
    # Taken in after the 15 weeks from the birth: no hospital stay can count.
    done = {"taken_in_on": TAKEN, "birth_date": BIRTH, "children_count": 1}
    assert "taken-in-hospital" not in questions(taken_in="adoption", **done)


def test_adoption_after_foster_care_takes_off_the_leave_already_used() -> None:
    base = {"taken_in_on": "2026-10-01", "birth_date": "2020-03-15", "father_work": "employment"}
    t = taken_in(**base, foster_before={"leave_start": "2026-08-03", "leave_end": "2026-12-31"})
    assert span(t, "adoption-leave")[1:] == (dt.date(2026, 10, 1), dt.date(2026, 12, 20), 81)
    assert span(t, "parental")[1:3] == (dt.date(2026, 12, 21), dt.date(2027, 8, 1))
    assert span(t, "parental-father")[1:] == (dt.date(2027, 8, 2), dt.date(2027, 10, 3), 63)
    foster = next(n for n in t.notes if n.id == "after-foster")
    assert foster.kind == "right"
    assert "59 dni, więc zostaje 81 dni" in foster.text
    assert any(s.article == "art. 183 § 7" for s in foster.sources)
    # The whole leave used, and 10 weeks of foster parental leave: 31 weeks are left.
    used = taken_in(
        **base,
        foster_before={
            "leave_start": "2026-01-05",
            "leave_end": "2026-05-24",
            "parental_weeks": 10,
        },
    )
    assert used.element("adoption-leave") is None
    assert used.element("leave-request-deadline") is None
    assert span(used, "parental")[1:] == (dt.date(2026, 10, 1), dt.date(2027, 3, 3), 154)
    assert span(used, "parental-father")[1:] == (dt.date(2027, 3, 4), dt.date(2027, 5, 5), 63)
    foster = next(n for n in used.notes if n.id == "after-foster")
    assert foster.kind == "risk"
    assert {"art. 183 § 7", "art. 183 § 8"} <= {s.article for s in foster.sources}


@pytest.mark.parametrize(
    "answers",
    [
        {"taken_in": "foster", "foster_before": {"parental_weeks": 3}},
        {"foster_before": {"leave_start": "2026-11-02", "leave_end": "2026-11-20"}},
    ],
)
def test_impossible_foster_care_before_adoption_is_rejected(answers: dict[str, Any]) -> None:
    with pytest.raises(ScenarioError):
        taken_in(**answers)


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
    assert {"set_leave_handover", "set_foster_before"} <= set(tools)
    # A hospital stay after taking the child in gives supplementary leave (art. 183 § 3¹).
    assert "set_hospital_care" in tools
    assert not {"set_leave_before_birth", "set_birth_date", "set_rehab_benefit"} & set(tools)
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
    out = ask(api, scripted("set_leave_handover", {"handed_over": True}, "…"), "…")
    assert rejected("set_leave_handover") in out


def test_the_handed_over_leave_is_paid() -> None:
    """The father takes the rest of the leave, 8.02-21.03.2027 (42 days), at 100% of his own
    base: 6000 x 0,8629 = 5177,40; 5177,40 / 30 = 172,58 a day; 42 x 172,58 = 7248,36."""
    t = taken_in(father_work="employment", taken_in_handover=True, mother_pay=7000, father_pay=6000)
    handed = next(p for p in t.payments if p.segment_id == "adoption-leave-other")
    assert (handed.lane, handed.days, handed.rate) == ("father", 42, 100)
    assert (handed.monthly, handed.daily, handed.total) == (5177.4, 172.58, 7248.36)
