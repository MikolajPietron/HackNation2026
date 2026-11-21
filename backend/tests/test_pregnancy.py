"""Pregnancy: sick leave, the benefit after losing the job, and the risks of section H (guide
pages 2-4 and 9-10, Labour Code art. 92). Expected dates were computed by hand:

- insured since 15.08.2026, 30 days: the right begins on 14.09.2026 (15.08 + 30 days);
- 33 days from 14.09.2026 end on 16.10.2026 (17 days of September + 16 of October);
- 33 days from 01.01.2027 end on 02.02.2027 (31 + 2);
- insured since 01.10.2026, 90 days: the right begins on 30.12.2026 (30 + 31 + 29 days);
- 270 days from 01.06.2026: June 30, July 31, August 31, September 30, October 31, November 30,
  December 31 (214), January 31 (245) and 25 days of February: the last is 25.02.2027.
"""

import datetime as dt

import pytest

from app.assistant.describe import interview_questions
from app.engine import Scenario, ScenarioError, Timeline, build_timeline
from app.engine.insurance import coverage
from app.engine.models import CaseNote
from app.services.params import load_params

PARAMS = load_params()
TODAY = dt.date(2026, 11, 21)
DUE = dt.date(2027, 3, 15)
EMPLOYED = {"role": "mother", "work": "employment", "children_count": 1}


def expecting(**answers: object) -> Timeline:
    scenario = Scenario.model_validate(
        {"child_born": False, "due_date": DUE, **EMPLOYED, **answers}
    )
    return build_timeline(scenario, PARAMS, TODAY)


def born(birth: dt.date, **answers: object) -> Timeline:
    scenario = Scenario.model_validate(
        {"child_born": True, "birth_date": birth, **EMPLOYED, **answers}
    )
    return build_timeline(scenario, PARAMS, TODAY)


def spans(timeline: Timeline, prefix: str) -> list[tuple[str, dt.date, dt.date, int]]:
    return [(s.id, s.start, s.end, s.days) for s in timeline.segments if s.id.startswith(prefix)]


def note(timeline: Timeline, note_id: str) -> CaseNote:
    return next(n for n in timeline.notes if n.id == note_id)


def d(text: str) -> dt.date:
    return dt.date.fromisoformat(text)


# Sick leave in pregnancy.


def test_employee_first_33_days_from_the_employer_then_the_benefit_every_year() -> None:
    t = expecting(
        leave_before_birth_weeks=0,
        sick_leave=True,
        sick_leave_start="2026-09-01",
        insured_since="2026-08-15",
    )
    assert spans(t, "sick") == [
        ("sick-pay", d("2026-09-14"), d("2026-10-16"), 33),
        ("sick-benefit", d("2026-10-17"), d("2026-12-31"), 76),
        # A new calendar year: the employer pays again for 33 days.
        ("sick-pay-2", d("2027-01-01"), d("2027-02-02"), 33),
        # Until the day before the due date; maternity leave starts on it.
        ("sick-benefit-2", d("2027-02-03"), d("2027-03-14"), 40),
    ]
    right = t.element("sick-benefit-right")
    assert right is not None and right.date == d("2026-09-14")  # type: ignore[union-attr]
    assert t.element("sick-benefit-limit") is None
    # The mother does not work while on sick leave: no "work until the birth" pill.
    assert t.element("work-until-birth") is None
    assert span_of(t, "maternity") == (DUE, d("2027-08-01"))
    sick = note(t, "sick-leave")
    assert sick.kind == "right"
    assert "od 14 września 2026 do 16 października 2026 (33 dni)" in sick.text
    assert "co do zasady po 30 dniach nieprzerwanego ubezpieczenia" in sick.text
    assert "po porodzie zaczyna się urlop macierzyński" in sick.text
    articles = {s.article for s in sick.sources if s.doc == "kp"}
    assert {"art. 92 § 1", "art. 92 § 3", "art. 92 § 4"} <= articles


def test_from_age_50_the_employer_pays_14_days() -> None:
    t = expecting(
        sick_leave=True,
        sick_leave_start="2026-11-02",
        sick_leave_end="2026-12-10",
        mother_over_50=True,
    )
    assert spans(t, "sick") == [
        ("sick-pay", d("2026-11-02"), d("2026-11-15"), 14),
        ("sick-benefit", d("2026-11-16"), d("2026-12-10"), 25),
    ]
    pay = t.element("sick-pay")
    assert pay is not None
    assert any(s.article == "art. 92 § 5" for s in pay.sources)


def test_not_an_employee_benefit_from_the_first_day_after_90_days_of_insurance() -> None:
    t = expecting(
        work="business",
        mother_insured=True,
        leave_before_birth_weeks=2,
        sick_leave=True,
        sick_leave_start="2026-11-01",
        insured_since="2026-10-01",
    )
    # 90 days from 01.10.2026: the right from 30.12.2026; maternity leave before the birth
    # starts on 01.03.2027 (2 weeks before 15.03.2027), so the sick leave ends on 28.02.2027.
    assert spans(t, "sick") == [("sick-benefit", d("2026-12-30"), d("2027-02-28"), 61)]
    assert span_of(t, "maternity-prenatal") == (d("2027-03-01"), d("2027-03-14"))
    right = t.element("sick-benefit-right")
    assert right is not None and right.date == d("2026-12-30")  # type: ignore[union-attr]
    text = note(t, "sick-leave").text
    assert "od pierwszego dnia niezdolności do pracy" in text
    assert "po 90 dniach ubezpieczenia, czyli od 30 grudnia 2026" in text
    assert "Od 1 marca 2027 mama jest na urlopie macierzyńskim" in text


def test_the_benefit_period_ends_after_270_days() -> None:
    t = expecting(
        leave_before_birth_weeks=0,
        sick_leave=True,
        sick_leave_start="2026-06-01",
        mother_over_50=False,
    )
    assert spans(t, "sick") == [
        ("sick-pay", d("2026-06-01"), d("2026-07-03"), 33),
        ("sick-benefit", d("2026-07-04"), d("2026-12-31"), 181),
        ("sick-pay-2", d("2027-01-01"), d("2027-02-02"), 33),
        ("sick-benefit-2", d("2027-02-03"), d("2027-02-25"), 23),
    ]
    limit = t.element("sick-benefit-limit")
    assert limit is not None and limit.date == d("2027-02-25")  # type: ignore[union-attr]
    assert "Okres zasiłkowy kończy się 25 lutego 2027" in note(t, "sick-leave").text


def test_sick_leave_ending_before_the_right_arises_gives_no_benefit() -> None:
    t = expecting(
        sick_leave=True,
        sick_leave_start="2026-11-01",
        sick_leave_end="2026-11-20",
        insured_since="2026-10-25",
    )
    assert spans(t, "sick") == []
    assert t.element("sick-benefit-right") is None  # 24.11.2026 is after the sick leave
    sick = note(t, "sick-leave")
    assert sick.kind == "risk"
    assert "od 24 listopada 2026" in sick.text
    assert {s.article for s in sick.sources if s.doc == "kp"} == {"art. 92 § 3"}


def test_without_sickness_insurance_there_is_no_sickness_benefit() -> None:
    t = expecting(
        work="contract", mother_insured=False, sick_leave=True, sick_leave_start="2026-11-01"
    )
    assert spans(t, "sick") == []
    sick = note(t, "sick-leave")
    assert (sick.kind, sick.title) == ("risk", "Zasiłek chorobowy wymaga ubezpieczenia chorobowego")


def test_born_child_sick_leave_ends_the_day_before_the_birth() -> None:
    t = born(
        dt.date(2026, 11, 10),
        leave_before_birth_weeks=0,
        sick_leave=True,
        sick_leave_start="2026-10-01",
        sick_leave_end="2026-12-31",
    )
    assert spans(t, "sick") == [
        ("sick-pay", d("2026-10-01"), d("2026-11-02"), 33),
        ("sick-benefit", d("2026-11-03"), d("2026-11-09"), 7),
    ]
    assert span_of(t, "maternity") == (d("2026-11-10"), d("2027-03-29"))


def test_work_until_the_birth_stops_where_the_sick_leave_starts() -> None:
    t = expecting(leave_before_birth_weeks=0, sick_leave=True, sick_leave_start="2027-02-20")
    assert span_of(t, "work-until-birth") == (d("2027-02-01"), d("2027-02-19"))
    work = t.element("work-until-birth")
    assert work is not None and work.days == 19  # type: ignore[union-attr]


@pytest.mark.parametrize(
    ("answers", "message"),
    [
        ({"sick_leave_start": "2027-03-15"}, "przed porodem"),
        ({"sick_leave_start": "2026-11-10", "sick_leave_end": "2026-11-01"}, "przed swoim"),
        # 2 weeks of leave before 15.03.2027 start on 01.03.2027.
        ({"sick_leave_start": "2027-03-05", "leave_before_birth_weeks": 2}, "w czasie urlopu"),
    ],
)
def test_impossible_sick_leave_dates_are_rejected(answers: dict[str, object], message: str) -> None:
    with pytest.raises(ScenarioError, match=message):
        expecting(sick_leave=True, **answers)


# Losing the job in pregnancy.


def test_bankruptcy_of_the_employer_benefit_until_the_birth() -> None:
    t = expecting(job_loss={"ended_on": "2026-11-30", "reason": "bankruptcy"})
    job = t.element("job-loss-benefit")
    assert job is not None
    assert (job.start, job.end, job.days, job.tone) == (  # type: ignore[union-attr]
        d("2026-12-01"),
        d("2027-03-14"),
        104,
        "leave",
    )
    assert "nie zapewniono jej innego zatrudnienia" in " ".join(job.details)  # type: ignore[union-attr]
    loss = note(t, "job-loss")
    assert loss.kind == "right"
    assert "od 1 grudnia 2026 do 14 marca 2027" in loss.text
    # From the birth the maternity leave stays on the timeline.
    assert span_of(t, "maternity") == (DUE, d("2027-08-01"))


def test_unlawful_termination_needs_a_court_judgment() -> None:
    pending = expecting(job_loss={"ended_on": "2026-11-30", "reason": "unlawful"})
    job = pending.element("job-loss-benefit")
    assert job is not None
    assert (job.tone, job.title) == (  # type: ignore[union-attr]
        "option",
        "Zasiłek w wysokości zasiłku macierzyńskiego — po wyroku sądu",
    )
    confirmed = expecting(
        job_loss={"ended_on": "2026-11-30", "reason": "unlawful", "court_confirmed": True}
    )
    assert confirmed.element("job-loss-benefit").tone == "leave"  # type: ignore[union-attr]


def test_any_other_end_of_work_leaves_no_insurance_on_the_day_of_birth() -> None:
    scenario = Scenario.model_validate(
        {
            "child_born": True,
            "birth_date": "2026-11-10",
            **EMPLOYED,
            "job_loss": {"ended_on": "2026-08-31", "reason": "other"},
        }
    )
    assert coverage(scenario) == "not-working"
    t = build_timeline(scenario, PARAMS, TODAY)
    assert [s for s in t.segments if s.lane == "mother"] == []
    loss = note(t, "job-loss")
    assert (loss.kind, loss.title) == ("risk", "Koniec pracy przed porodem")
    assert any(s.section == "H.3" for s in loss.sources)


def test_sick_leave_ends_with_the_job_and_the_benefit_follows() -> None:
    t = expecting(
        sick_leave=True,
        sick_leave_start="2026-10-01",
        job_loss={"ended_on": "2026-11-30", "reason": "liquidation"},
    )
    assert spans(t, "sick") == [
        ("sick-pay", d("2026-10-01"), d("2026-11-02"), 33),
        ("sick-benefit", d("2026-11-03"), d("2026-11-30"), 28),
    ]
    assert span_of(t, "job-loss-benefit") == (d("2026-12-01"), d("2027-03-14"))


def test_impossible_job_loss_is_rejected() -> None:
    with pytest.raises(ScenarioError, match="przed porodem"):
        expecting(job_loss={"ended_on": "2027-03-15", "reason": "bankruptcy"})
    with pytest.raises(ScenarioError, match="umowy o pracę"):
        expecting(
            work="contract",
            mother_insured=True,
            job_loss={"ended_on": "2026-11-30", "reason": "bankruptcy"},
        )


# Section H, risks 1 and 2.


def test_risks_are_explained_only_when_the_parent_said_so() -> None:
    plain = expecting(work="business", mother_insured=True)
    assert not {"risk-sham", "risk-base"} & {n.id for n in plain.notes}
    t = expecting(
        work="business",
        mother_insured=True,
        insured_in_pregnancy=True,
        contribution_base_raised=True,
    )
    sham, base = note(t, "risk-sham"), note(t, "risk-base")
    assert (sham.kind, base.kind) == ("risk", "risk")
    assert {s.section for s in sham.sources} == {"H.1"}
    assert {s.section for s in base.sources} == {"H.2"}


# The interview.


def keys(**answers: object) -> list[str]:
    scenario = Scenario.model_validate(
        {
            "child_born": False,
            "due_date": DUE,
            **EMPLOYED,
            "leave_before_birth_weeks": 0,
            "father_work": "employment",
            # Who pays is asked after the pregnancy questions (test_applications covers it).
            "mother_payer_size": "over-20",
            "father_payer_size": "over-20",
            **answers,
        }
    )
    return [q.key for q in interview_questions(scenario)]


def test_the_interview_asks_about_sick_leave_then_insurance_then_age() -> None:
    assert keys() == ["sick-leave"]
    assert keys(sick_leave=False) == []
    assert keys(sick_leave=True, sick_leave_start="2026-11-02") == ["insured-since"]
    # 33 days paid by the employer in 2026: more than 14, so the age matters.
    assert keys(sick_leave=True, sick_leave_start="2026-11-02", insured_since="2020-01-01") == [
        "mother-over-50"
    ]
    # 10 days: the age does not change anything.
    short = {"sick_leave_start": "2026-11-02", "sick_leave_end": "2026-11-11"}
    assert keys(sick_leave=True, insured_since="2020-01-01", **short) == []
    # A born child: the sick leave is behind; a mother without insurance: nothing to pay.
    born_child = {"child_born": True, "birth_date": "2026-11-10", "hospital_care": False}
    assert "sick-leave" not in keys(**born_child)
    assert keys(work="none") == []


def span_of(timeline: Timeline, segment_id: str) -> tuple[dt.date, dt.date]:
    segment = next(s for s in timeline.segments if s.id == segment_id)
    return segment.start, segment.end
