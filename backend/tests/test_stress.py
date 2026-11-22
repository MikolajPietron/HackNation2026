"""F11, the stress test of the plan (engine/stress.py) and POST /api/stress. Expected values were
computed by hand, not by the engine.

The standard family, the child on the way: due 15.03.2027, today 21.11.2026; the mother employed,
8000 zł a month, works until the birth; the father employed, 6000 zł; one child.
- Bases: mother 6903,20 zł (a day: 100% 230,11; 70% 161,07); father 5177,40 zł (100% 172,58;
  70% 120,81).
- The timeline now: maternity leave 15.03-01.08.2027 (140 days), the mother's parental leave
  02.08.2027-12.03.2028 (224 days), paternity leave 15.03-28.03.2027 (14 days), the father's
  parental leave 13.03-14.05.2028 (63 days). The money: 140 × 230,11 = 32 215,40 + 224 × 161,07
  = 36 079,68 + 14 × 172,58 = 2416,12 + 63 × 120,81 = 7611,03, together 78 322,23 zł.
"""

import datetime as dt
from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_param_store, get_session_store, get_today
from app.assistant.describe_plans import describe_stress
from app.engine import Scenario
from app.engine.compare import PeriodChange
from app.engine.stress import StressEvent, StressReport, stress_test
from app.main import app
from app.services.param_versions import MemoryParamStore
from app.services.params import load_params
from app.services.sessions import MemorySessionStore

PARAMS = load_params()
TODAY = dt.date(2026, 11, 21)
EXPECTING: dict[str, Any] = {
    "role": "mother",
    "work": "employment",
    "father_work": "employment",
    "children_count": 1,
    "child_born": False,
    "due_date": dt.date(2027, 3, 15),
    "leave_before_birth_weeks": 0,
    "mother_pay": 8000,
    "father_pay": 6000,
}


def report(**answers: Any) -> StressReport:
    return stress_test(Scenario.model_validate({**EXPECTING, **answers}), PARAMS, TODAY)


def event(r: StressReport, event_id: str) -> StressEvent:
    return next(e for e in r.events if e.id == event_id)


def period(e: StressEvent, period_id: str) -> PeriodChange:
    return next(p for p in e.periods if p.id == period_id)


def d(text: str) -> dt.date:
    return dt.date.fromisoformat(text)


def rights(e: StressEvent) -> dict[str, tuple[int, int]]:
    return {r.kind: (r.days_before, r.days_after) for r in e.rights}


def test_an_expected_child_goes_through_every_event_that_can_still_happen() -> None:
    r = report()
    assert [e.id for e in r.events] == [
        "premature",
        "twins",
        "job-loss-bankruptcy",
        "job-loss-liquidation",
        "job-loss-employer-death",
        "job-loss-unlawful",
        "job-loss-other",
        "mother-incapacity",
        "mother-hospital",
        "mother-death",
        "father-takeover",
        "za-zyciem",
    ]
    assert r.skipped == [] and not r.sensitive and r.reason is None
    assert [e.id for e in r.events if e.sensitive] == [
        "mother-incapacity",
        "mother-hospital",
        "mother-death",
    ]
    assert {e.id: e.verdict for e in r.events} == {
        "premature": "kept",
        "twins": "kept",
        "job-loss-bankruptcy": "kept",
        "job-loss-liquidation": "kept",
        "job-loss-employer-death": "kept",
        "job-loss-unlawful": "risk",
        "job-loss-other": "loss",
        "mother-incapacity": "kept",
        "mother-hospital": "kept",
        "mother-death": "loss",
        "father-takeover": "kept",
        "za-zyciem": "kept",
    }


def test_a_premature_birth_adds_supplementary_leave() -> None:
    """Born 6 weeks early, 15.03.2027 − 42 days = 01.02.2027, between the 28th and 37th week,
    in hospital 01.02-28.02.2027 (28 days): the window is 8 weeks, so 4 weeks of supplementary
    leave (art. 180² § 1 pkt 2, § 3). Maternity leave 01.02-20.06.2027 (140 days),
    supplementary 21.06-18.07.2027, the mother's parental leave 19.07.2027-27.02.2028, the
    father's 28.02-30.04.2028 (2028 is a leap year). The money: 28 × 230,11 = 6443,08 zł more."""
    e = event(report(), "premature")
    assert e.as_of == d("2027-02-01")  # the hospital stay must not be in the future
    assert rights(e) == {"supplementary": (0, 28)}
    assert (period(e, "maternity").start_after, period(e, "maternity").end_after) == (
        d("2027-02-01"),
        d("2027-06-20"),
    )
    supplementary = period(e, "supplementary")
    assert supplementary.change == "added"
    assert (supplementary.start_after, supplementary.end_after) == (
        d("2027-06-21"),
        d("2027-07-18"),
    )
    parental = period(e, "parental")
    assert (parental.start_before, parental.end_before) == (d("2027-08-02"), d("2028-03-12"))
    assert (parental.start_after, parental.end_after) == (d("2027-07-19"), d("2028-02-27"))
    assert period(e, "parental-father").end_after == d("2028-04-30")
    assert e.money is not None and e.money.diff == 6443.08
    assert e.money.total_before == 78322.23 and e.money.total_after == 84765.31
    assert "Dochodzi: uzupełniający urlop macierzyński — 4 tyg." in e.lines
    assert e.patch["birth_date"] == "2027-02-01" and e.patch["birth_week"] == "28-37"
    assert e.patch["hospital_stays"] == [{"start": "2027-02-01", "end": "2027-02-28"}]
    assert any(s.doc == "kp" and s.article and "180²" in s.article for s in e.sources)


def test_twins_lengthen_maternity_and_parental_leave() -> None:
    """31 weeks of maternity leave: 15.03-17.10.2027 (217 days); parental leave 43 weeks, the
    mother's 34: 18.10.2027-11.06.2028 (238 days), the father's 12.06-13.08.2028. The money: 77
    more days × 230,11 = 17 718,47 + 14 × 161,07 = 2254,98, so 19 973,45 zł more."""
    e = event(report(), "twins")
    # The pool grows with the options drawn on the timeline: one line says it, not two.
    assert rights(e) == {"maternity": (140, 217), "parental": (287, 301)}
    assert "Urlop rodzicielski: 43 tyg. zamiast 41 tyg. (dłużej)." in e.lines
    assert not any(line.startswith("Pula urlopu") for line in e.lines)
    assert period(e, "maternity").end_after == d("2027-10-17")
    assert (period(e, "parental").start_after, period(e, "parental").end_after) == (
        d("2027-10-18"),
        d("2028-06-11"),
    )
    assert e.money is not None and e.money.diff == 19973.45
    assert "Urlop macierzyński: 31 tyg. zamiast 20 tyg. (dłużej)." in e.lines


def test_job_loss_without_a_reason_of_the_guide_loses_the_maternity_benefit() -> None:
    """The work ends 15.03.2027 − (6 × 7 + 14) days = 18.01.2027. Not insured on the day of the
    birth: no maternity benefit and no parental leave for the mother; the father has the
    benefit for parental leave, 41 − 9 = 32 weeks (224 days). The money: paternity 2416,12 +
    224 × 120,81 = 27 061,44, together 29 477,56 zł instead of 78 322,23."""
    e = event(report(), "job-loss-other")
    assert e.verdict == "loss"
    assert e.patch == {
        "job_loss": {"ended_on": "2027-01-18", "reason": "other", "court_confirmed": None}
    }
    assert rights(e) == {"maternity": (140, 0), "parental": (287, 224)}
    assert e.money is not None
    assert (e.money.total_after, e.money.mother_after) == (29477.56, 0.0)
    # F14 adds the way on ("co zamiast") right after the note that says there is no right.
    assert {n.id for n in e.risks} == {"insurance", "job-loss", "insurance-way"}
    assert "Przepada: urlop macierzyński (20 tyg.)." in e.lines


def test_job_loss_through_bankruptcy_gives_the_benefit_until_the_birth() -> None:
    """From 19.01.2027 to 14.03.2027 (55 days) the benefit equal to the maternity benefit, 100%:
    55 × 230,11 = 12 656,05 zł. Without a judgment, an unlawful termination is a risk."""
    r = report()
    e = event(r, "job-loss-bankruptcy")
    assert rights(e) == {"job-loss": (0, 55)}
    added = period(e, "job-loss-benefit")
    assert (added.start_after, added.end_after) == (d("2027-01-19"), d("2027-03-14"))
    assert e.money is not None and e.money.diff == 12656.05
    unlawful = event(r, "job-loss-unlawful")
    assert unlawful.verdict == "risk"
    assert [n.id for n in unlawful.risks] == ["insurance"]
    assert any("Sąd jeszcze nie potwierdził" in a for a in unlawful.assumed)


def test_the_mothers_situations_after_the_birth() -> None:
    """Compared with a birth on the due date. 8 weeks after it: 15.03.2027 + 56 days =
    10.05.2027, the first day the father may take over (art. 180 § 11-§ 12).
    Incapacity: the mother until 09.05.2027, the father 10.05-01.08.2027 (84 days) at his base:
    84 × (230,11 − 172,58) = 4832,52 zł less.
    Death: her parental leave goes and the father's is 32 weeks: 287 → 224 days."""
    r = report()
    incapacity = event(r, "mother-incapacity")
    assert period(incapacity, "maternity").end_after == d("2027-05-09")
    his = period(incapacity, "maternity-father")
    assert (his.start_after, his.end_after) == (d("2027-05-10"), d("2027-08-01"))
    assert incapacity.money is not None and incapacity.money.diff == -4832.52
    death = event(r, "mother-death")
    assert death.as_of == d("2027-05-10")  # a death cannot be in the future
    assert rights(death) == {"parental": (287, 224)}
    hospital = event(r, "mother-hospital")
    assert period(hospital, "maternity-resumed").start_after == d("2027-06-07")  # 28 days later


def test_the_father_taking_over_and_za_zyciem() -> None:
    """Takeover after 14 weeks: the mother 15.03-20.06.2027, the father 21.06-01.08.2027 (42
    days), 42 × 57,53 = 2416,26 zł less. "Za życiem": 65 weeks, the mother's 56 (392 days):
    168 more days × 161,07 = 27 059,76 zł more."""
    r = report()
    takeover = event(r, "father-takeover")
    assert period(takeover, "maternity-father").start_after == d("2027-06-21")
    assert takeover.money is not None and takeover.money.diff == -2416.26
    za_zyciem = event(r, "za-zyciem")
    assert rights(za_zyciem) == {"parental": (287, 455)}
    assert za_zyciem.money is not None and za_zyciem.money.diff == 27059.76


def test_a_dated_plan_that_no_longer_fits_is_reported() -> None:
    """The plan starts the mother's parental leave on 02.08.2027. With twins maternity leave
    lasts until 17.10.2027, so the plan breaks; the rest compares both timelines without it."""
    r = report(parental_parts=[{"parent": "mother", "weeks": 20, "start": "2027-08-02"}])
    twins = event(r, "twins")
    assert twins.verdict == "loss"
    assert twins.plan_breaks == (
        "Urlop rodzicielski może się zacząć najwcześniej 18.10.2027: po urlopie macierzyńskim."
    )
    assert twins.lines[0].startswith("Wasz plan urlopu rodzicielskiego przestaje pasować")
    assert rights(twins) == {"maternity": (140, 217), "parental": (287, 301)}
    assert twins.patch["parental_parts"] == []
    assert event(r, "za-zyciem").plan_breaks is None  # the plan still fits there


def test_za_zyciem_with_a_plan_that_keeps_its_weeks_still_changes_the_pool() -> None:
    """The plan: the mother 32 weeks, the father 9 (the whole pool of 41). "Za życiem" makes the
    pool 65 weeks (KP art. 182¹ᵃ § 2) while every period of the plan stays where it is: the
    test must still say so, never "Na osi nic się nie zmienia"."""
    r = report(parental_parts=[{"parent": "mother", "weeks": 32}, {"parent": "father", "weeks": 9}])
    za_zyciem = event(r, "za-zyciem")
    assert za_zyciem.plan_breaks is None and za_zyciem.periods == []
    assert rights(za_zyciem) == {"parental-pool": (287, 455)}
    assert za_zyciem.lines[0] == "Pula urlopu rodzicielskiego: 65 tyg. zamiast 41 tyg."
    assert "Na osi nic się nie zmienia." not in za_zyciem.lines
    assert za_zyciem.verdict == "kept"  # more rights, nothing lost
    assert any(s.article == "art. 182¹ᵃ § 2" for s in za_zyciem.sources)


def test_twins_with_a_plan_of_the_whole_pool_say_the_pool_grows() -> None:
    """The plan: the mother 32 weeks, the father 9. Twins: 43 weeks for both (KP art. 182¹ᵃ
    § 1), the plan keeps its 41, so the pool line says it."""
    r = report(parental_parts=[{"parent": "mother", "weeks": 32}, {"parent": "father", "weeks": 9}])
    twins = event(r, "twins")
    assert rights(twins)["parental-pool"] == (287, 301)
    assert "Pula urlopu rodzicielskiego: 43 tyg. zamiast 41 tyg." in twins.lines


def test_a_born_child_has_only_what_can_still_happen() -> None:
    """Born 10.11.2026: nothing about pregnancy; the mother's situations from 8 weeks after the
    birth, 05.01.2027; the father taking over after 14 weeks, from 16.02.2027."""
    r = report(child_born=True, birth_date=dt.date(2026, 11, 10))
    assert [e.id for e in r.events] == [
        "mother-incapacity",
        "mother-hospital",
        "mother-death",
        "father-takeover",
        "za-zyciem",
    ]
    assert event(r, "mother-incapacity").patch == {
        "mother_event": {"kind": "incapacity", "start": "2027-01-05", "end": None}
    }
    assert period(event(r, "father-takeover"), "maternity-father").start_after == d("2027-02-16")


def test_no_what_ifs_after_a_childs_death_or_for_a_child_taken_in() -> None:
    lost = report(child_born=True, birth_date=dt.date(2026, 11, 10), losses=[{"stillborn": True}])
    assert lost.sensitive and lost.events == []
    assert lost.reason and "nie pokazuje wariantów" in describe_stress(lost)
    adopted = report(
        taken_in="adoption", taken_in_on=dt.date(2026, 11, 1), birth_date=dt.date(2026, 5, 1)
    )
    assert adopted.events == [] and adopted.reason


def test_the_assistant_reads_the_report_word_for_word() -> None:
    text = describe_stress(report())
    assert text.startswith("Test planu: co zmieniłoby każde zdarzenie")
    assert "- Koniec umowy o pracę w ciąży z innej przyczyny (grozi utrata prawa" in text
    assert "  Założenie: Zakładamy, że ostatni dzień pracy mamy to 18.01.2027." in text
    assert "  Dochodzi: uzupełniający urlop macierzyński — 4 tyg." in text
    assert "- Śmierć mamy (grozi utrata prawa albo plan przestaje pasować) (delikatnie)" in text


@pytest.fixture
def client() -> Iterator[TestClient]:
    store = MemorySessionStore()
    params = MemoryParamStore()
    app.dependency_overrides[get_today] = lambda: TODAY
    app.dependency_overrides[get_session_store] = lambda: store
    app.dependency_overrides[get_param_store] = lambda: params
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_api_stress(client: TestClient) -> None:
    scenario = Scenario.model_validate(EXPECTING).model_dump(mode="json")
    response = client.post("/api/stress", json={"scenario": scenario})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["events"][0]["id"] == "premature"
    assert body["events"][0]["timeline"] is None
    full = client.post("/api/stress", json={"scenario": scenario, "timelines": True}).json()
    premature = full["events"][0]
    assert premature["timeline"]["birth_date"] == "2027-02-01"
    assert premature["reference"]["birth_date"] == "2027-03-15"
    broken = {**scenario, "leave_before_birth_weeks": 8}
    bad = client.post("/api/stress", json={"scenario": broken})
    assert bad.status_code == 422
