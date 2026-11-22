"""The benefits after the insurance ended: the maternity benefit after losing the job in
pregnancy (ustawa art. 30 ust. 1, guide page 4) and the sickness benefit after the insurance
ended (guide page 2; ustawa art. 7, 8 ust. 2, 13 ust. 1, 61 ust. 1). Dates and amounts computed by
hand (in each docstring): base 8000 × 0,8629 = 6903,20 zł, a day at 100% = 230,11 zł.

The usual case: today 21.11.2026, due 15.03.2027, the employment ended 30.11.2026.
"""

import datetime as dt
from typing import Any

from app.assistant.describe import interview_questions
from app.engine import Scenario, Timeline, build_timeline
from app.services.params import load_params

PARAMS = load_params()
TODAY = dt.date(2026, 11, 21)
EMPLOYED = {"role": "mother", "work": "employment", "children_count": 1, "mother_pay": 8000}
ENDED = "2026-11-30"


def expecting(**answers: Any) -> Timeline:
    scenario = Scenario.model_validate(
        EMPLOYED | {"child_born": False, "due_date": "2027-03-15"} | answers
    )
    return build_timeline(scenario, PARAMS, TODAY)


def born(**answers: Any) -> Timeline:
    scenario = Scenario.model_validate(EMPLOYED | {"child_born": True} | answers)
    return build_timeline(scenario, PARAMS, TODAY)


def lost(reason: str, **extra: Any) -> dict[str, Any]:
    return {"job_loss": {"ended_on": ENDED, "reason": reason, **extra}}


def ids(t: Timeline) -> list[str]:
    return [s.id for s in t.segments if s.lane == "mother"]


def note(t: Timeline, note_id: str) -> str:
    return next(n.text for n in t.notes if n.id == note_id)


def articles(sources: list[Any]) -> set[str]:
    return {s.article for s in sources if s.doc == "ustawa"}


def test_after_the_employer_went_bankrupt_the_maternity_benefit_follows_the_birth() -> None:
    """The benefit equal to the maternity benefit 01.12.2026–14.03.2027 (31 + 31 + 28 + 14 =
    104 days): 104 × 230,11 = 23 931,44 zł; then the maternity benefit after the insurance
    ended, 15.03–01.08.2027 (140 days): 32 215,40 zł; parental leave after it."""
    t = expecting(**lost("bankruptcy"))
    # No window to start leave before the birth: she no longer works.
    assert ids(t) == ["job-loss-benefit", "maternity", "parental"]
    job, maternity = t.element("job-loss-benefit"), t.element("maternity")
    assert (job.start, job.end) == (dt.date(2026, 12, 1), dt.date(2027, 3, 14))  # type: ignore[union-attr]
    assert (maternity.start, maternity.end) == (dt.date(2027, 3, 15), dt.date(2027, 8, 1))  # type: ignore[union-attr]
    payment = next(p for p in t.payments if p.segment_id == "job-loss-benefit")
    assert (payment.rate, payment.daily, payment.days, payment.total) == (
        100,
        230.11,
        104,
        23931.44,
    )
    assert payment.title == "Zasiłek mamy w wysokości zasiłku macierzyńskiego"
    assert any("zasiłku w wysokości zasiłku macierzyńskiego" in s.quote for s in payment.sources)
    assert "Liczymy do przewidywanej daty porodu." in payment.details
    assert next(p for p in t.payments if p.segment_id == "maternity").total == 32215.4
    # After the birth: a benefit, not leave; ZUS pays.
    line = maternity.details[-2]  # type: ignore[union-attr]
    assert "Zasiłek macierzyński przysługuje jej również po ustaniu ubezpieczenia" in line
    assert "nie dostaje urlopu" in line
    assert {"art. 30 ust. 1", "art. 29a ust. 1"} <= articles(maternity.sources)  # type: ignore[union-attr]
    assert "Zasiłek mamy wypłaca ZUS" in maternity.details[-1]  # type: ignore[union-attr]
    assert "art. 30 ust. 3" in articles(job.sources)  # type: ignore[union-attr]
    # No request to an employer, no protection: ZAM to ZUS.
    # ZAM for the parental period: before that benefit starts, 02.08.2027 (rozporządzenie § 29).
    assert [d.id for d in t.documents] == ["maternity-request", "zam-parental"]
    assert t.documents[0].title == "Wniosek o zasiłek macierzyński (ZAM)"
    assert "bezpośrednio do ZUS" in t.documents[0].rule
    assert not {"protection-end", "earliest-start"} & {m.id for m in t.markers}
    notes = [n.id for n in t.notes]
    assert "before-birth" not in notes and "protection" not in notes
    insurance = next(n for n in t.notes if n.id == "insurance")
    assert (insurance.kind, insurance.title) == (
        "right",
        "Zasiłek macierzyński po ustaniu ubezpieczenia",
    )
    assert "wypłaca go ZUS" in insurance.text
    assert "Zasiłek mamy wypłaca ZUS" in note(t, "payer")
    assert "Wniosek o zasiłek macierzyński (ZAM) — do ZUS" in note(t, "applications")
    assert "Po porodzie przysługuje jej zasiłek macierzyński" in note(t, "job-loss")
    assert any("Art. 30 ust. 1 tych okresów nie ogranicza" in a for a in t.assumptions)
    assert not any("ubezpieczenie chorobowe mamy trwa w dniu porodu" in a for a in t.assumptions)


def test_leave_planned_before_the_birth_cannot_start_after_the_job_ended() -> None:
    """6 weeks before 15.03.2027 would start 01.02.2027, after the end (30.11.2026): no leave
    before the birth, no certificate, all 20 weeks after the birth (15.03–01.08.2027)."""
    t = expecting(**lost("liquidation"), leave_before_birth_weeks=6, has_medical_certificate=False)
    assert ids(t) == ["job-loss-benefit", "maternity", "parental"]
    assert "medical-certificate" not in [d.id for d in t.documents]
    assert t.element("maternity").end == dt.date(2027, 8, 1)  # type: ignore[union-attr]
    # The interview does not ask about leave before the birth, nor about the employer's size.
    keys = [
        q.key
        for q in interview_questions(
            Scenario.model_validate(
                EMPLOYED | {"child_born": False, "due_date": "2027-03-15"} | lost("liquidation")
            )
        )
    ]
    assert "leave-before-birth" not in keys and "mother-payer" not in keys


def test_leave_before_the_birth_already_under_way_goes_on() -> None:
    """Born 10.11.2026, leave from 27.10.2026 (2 weeks before), the employer liquidated
    31.10.2026: the leave goes on, no benefit equal to the maternity benefit for those days;
    maternity leave after the birth 10.11.2026–15.03.2027 (140 − 14 = 126 days)."""
    t = born(
        birth_date="2026-11-10",
        leave_before_birth_weeks=2,
        job_loss={"ended_on": "2026-10-31", "reason": "liquidation"},
    )
    assert ids(t) == ["maternity-prenatal", "maternity", "parental"]
    assert t.element("maternity").end == dt.date(2027, 3, 15)  # type: ignore[union-attr]
    assert "Urlop macierzyński przed porodem zaczął się wcześniej" in note(t, "job-loss")
    assert any("pokazujemy go dalej jako urlop macierzyński" in a for a in t.assumptions)


def test_a_breach_of_the_law_waits_for_the_court() -> None:
    """Unlawful termination without a final judgment: the benefits are options that depend on
    the judgment; with it, they are certain."""
    t = expecting(**lost("unlawful"))
    tones = {s.id: s.tone for s in t.segments if s.lane == "mother"}
    assert tones == {"job-loss-benefit": "option", "maternity": "option", "parental": "option"}
    insurance = next(n for n in t.notes if n.id == "insurance")
    assert insurance.kind == "risk" and insurance.title.endswith("— po wyroku sądu")
    payment = next(p for p in t.payments if p.segment_id == "maternity")
    assert "Kwota przysługuje, jeśli naruszenie przepisów prawa stwierdzi" in payment.details[-2]
    confirmed = expecting(**lost("unlawful", court_confirmed=True))
    assert confirmed.element("maternity").tone == "leave"  # type: ignore[union-attr]


def test_sick_leave_goes_on_after_the_work_ended_with_the_benefit_from_zus() -> None:
    """Employed, sick from 01.10.2026 until the birth; the work ended 30.11.2026 (any other
    reason): sick pay 01.10–02.11.2026 (33 days), the benefit 03.11–30.11.2026 (28 days), then
    the benefit after the insurance ended 01.12.2026–14.03.2027 (104 days, within the 270):
    104 × 230,11 = 23 931,44 zł. No maternity benefit: no insurance on the day of the birth."""
    t = expecting(**lost("other"), sick_leave=True, sick_leave_start="2026-10-01")
    assert ids(t) == ["sick-pay", "sick-benefit", "sick-after-insurance"]
    after = t.element("sick-after-insurance")
    assert (after.start, after.end, after.days) == (  # type: ignore[union-attr]
        dt.date(2026, 12, 1),
        dt.date(2027, 3, 14),
        104,
    )
    assert "Wypłaca go ZUS." in after.summary  # type: ignore[union-attr]
    assert {"art. 8 ust. 2", "art. 61 ust. 1"} <= articles(after.sources)  # type: ignore[union-attr]
    payment = next(p for p in t.payments if p.segment_id == "sick-after-insurance")
    assert (payment.rate, payment.total) == (100, 23931.44)
    assert payment.title == "Zasiłek chorobowy mamy po ustaniu ubezpieczenia"
    assert "od 1 grudnia 2026 do 14 marca 2027 wypłaca go ZUS" in note(t, "sick-leave")
    assert any("art. 46 ustawy zasiłkowej" in a for a in t.assumptions)
    assert any("art. 13 ust. 1 ustawy zasiłkowej" in a for a in t.assumptions)
    # Her amount matters for the sick leave, though she has no maternity benefit.
    keys = [
        q.key
        for q in interview_questions(
            Scenario.model_validate(
                EMPLOYED
                | {"child_born": False, "due_date": "2027-03-15", "mother_pay": None}
                | lost("other")
                | {"sick_leave": True, "sick_leave_start": "2026-10-01"}
            )
        )
    ]
    assert "mother-pay" in keys and "rate-815" not in keys


def test_no_sickness_benefit_after_the_insurance_without_the_right_during_it() -> None:
    """Insured from 10.11.2026: the right arises after 30 days, 10.12.2026, later than the end
    of the work (30.11.2026) — art. 13 ust. 1 pkt 3: nothing after the end, nothing before."""
    t = expecting(
        **lost("other"),
        sick_leave=True,
        sick_leave_start="2026-11-15",
        insured_since="2026-11-10",
    )
    assert ids(t) == []
    sick = next(n for n in t.notes if n.id == "sick-leave")
    assert "nie nabyła do niego prawa w czasie ubezpieczenia" in sick.text
    assert "art. 13 ust. 1" in articles(sick.sources)


def test_incapacity_after_the_end_of_work_needs_14_and_30_days() -> None:
    """Art. 7 pkt 1: from 05.12.2026, 5 days after the end, until the birth (27 + 31 + 28 + 14 =
    100 days ≥ 30): 100 × 230,11 = 23 011,00 zł. From 20.12.2026 (20 days after) or only
    05.12–20.12.2026 (16 days): none."""
    t = expecting(**lost("other"), sick_leave=True, sick_leave_start="2026-12-05")
    after = next(p for p in t.payments if p.segment_id == "sick-after-insurance")
    assert (after.start, after.days, after.total) == (dt.date(2026, 12, 5), 100, 23011.0)
    assert "art. 7" in articles(t.element("sick-after-insurance").sources)  # type: ignore[union-attr]
    for answers in (
        {"sick_leave_start": "2026-12-20"},
        {"sick_leave_start": "2026-12-05", "sick_leave_end": "2026-12-20"},
    ):
        late = expecting(**lost("other"), sick_leave=True, **answers)
        assert ids(late) == []
        assert "najpóźniej 14 dni po ustaniu ubezpieczenia" in note(late, "sick-leave")


def test_a_mother_who_does_not_work_hears_when_the_benefit_follows_the_insurance() -> None:
    t = born(work="none", birth_date="2026-11-10")
    insurance = next(n for n in t.notes if n.id == "insurance")
    assert "gdy ubezpieczenie ustało w ciąży wskutek śmierci, upadłości" in insurance.text
    assert "art. 30 ust. 1" in articles(insurance.sources)
