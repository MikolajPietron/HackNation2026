"""Example cases: the catalogue numbering, page rendering, facts -> scenario, the insurance check
and the comparison with ZUS, and the API with a fake reader (no key, no network). Real cases are
confidential and never in the repo: files here are made up and drawn with Pillow."""

import datetime as dt
import io
from decimal import Decimal
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image, ImageDraw

from app.api.cases import get_case_cache, get_cases_folder, get_reader_factory
from app.api.deps import get_session_store, get_today
from app.cases.assess import assess, check_insurance, compare, to_scenario
from app.cases.cache import CaseCache
from app.cases.catalog import list_case_files
from app.cases.models import (
    Bonus,
    CaseFacts,
    CaseJobLoss,
    CaseMotherEvent,
    CaseResult,
    ContributionDebt,
    Decision,
    InsurancePeriod,
    LeavePeriod,
    PayDetails,
    PayMonth,
)
from app.cases.pages import render_pages
from app.main import app
from app.services.params import load_params
from app.services.sessions import MemorySessionStore

TODAY = dt.date(2026, 11, 22)


def fake_pdf(pages: int = 3, blank: tuple[int, ...] = ()) -> bytes:
    images = []
    for number in range(1, pages + 1):
        image = Image.new("RGB", (850, 1100), "white")
        if number not in blank:
            draw = ImageDraw.Draw(image)
            for row in range(40):
                draw.rectangle((60, 80 + row * 24, 790, 92 + row * 24), fill="black")
        images.append(image)
    out = io.BytesIO()
    images[0].save(out, format="PDF", save_all=True, append_images=images[1:])
    return out.getvalue()


def facts(**changes: object) -> CaseFacts:
    base = CaseFacts(
        summary="Mama wnioskuje o zasiłek macierzyński po porodzie.",
        applicant="mother",
        benefit_requested="zasiłek macierzyński",
        child_born=True,
        birth_date=dt.date(2026, 3, 10),
        due_date=None,
        children_count=1,
        documents=[],
        insurance=[
            InsurancePeriod(
                person="mother",
                title="employment",
                label="umowa o pracę",
                start=dt.date(2024, 1, 1),
                end=None,
                sickness="mandatory",
                pages=[3],
            )
        ],
        leaves=[
            LeavePeriod(person="mother", kind="maternity", start=dt.date(2026, 3, 10), pages=[1])
        ],
        pay=[
            PayMonth(month=f"2025-{m:02d}", amount=6000, kind="salary", person="mother", pages=[4])
            for m in range(1, 13)
        ],
        decision=Decision(outcome="granted", benefit="zasiłek macierzyński", reason="", pages=[9]),
    )
    return base.model_copy(update=changes)


# ---------------------------------------------------------------------------------------------
# Catalogue


def test_catalogue_numbers_cases_like_the_data_pipeline(tmp_path: Path) -> None:
    # Categories come from the names, in the order of tools/zus-data/build_catalog.py.
    for name in [
        "Kowalska macierzyński.pdf",
        "Nowak odmowa.pdf",
        "Lis urlop ojcowski.pdf",
        "Nowak odmowa (1).pdf",  # the duplicate is skipped
        "notatka.txt",
    ]:
        (tmp_path / name).write_bytes(b"%PDF-1.4")
    cases = list_case_files(tmp_path)
    assert [(c.id, c.category) for c in cases] == [
        ("S01", "Odmowa"),
        ("S02", "Urlop ojcowski"),
        ("S03", "Macierzyński"),
    ]


def test_blank_pages_are_found() -> None:
    pages = render_pages(fake_pdf(3, blank=(2,)))
    assert [p.blank for p in pages] == [False, True, False]
    assert all(len(p.tiles) == 2 for p in pages), "every page goes as two halves"
    assert all(tile.startswith(b"\xff\xd8") for p in pages for tile in p.tiles)


# ---------------------------------------------------------------------------------------------
# Facts -> answers


def test_employee_case_becomes_a_scenario_with_her_pay() -> None:
    scenario, notes = to_scenario(facts())
    assert scenario.role == "mother"
    assert scenario.work == "employment"
    assert scenario.child_born is True
    assert scenario.birth_date == dt.date(2026, 3, 10)
    assert scenario.leave_before_birth_weeks == 0
    # The months of Z-3 go to the benefit base in detail (engine/base.py), not as an average.
    assert scenario.mother_pay is None
    history = scenario.mother_pay_history
    assert history is not None
    assert [(m.month, m.amount) for m in history.months] == [
        (f"2025-{m:02d}", 6000) for m in range(1, 13)
    ]
    assert any("krok po kroku z 12 mies." in note for note in notes)
    assert not any("Uproszczenie" in note for note in notes)


def test_leave_before_the_birth_is_its_first_day() -> None:
    early = [LeavePeriod(person="mother", kind="maternity", start=dt.date(2026, 2, 20), pages=[1])]
    scenario, _ = to_scenario(facts(leaves=early))
    assert scenario.leave_start == dt.date(2026, 2, 20)


def test_sick_leave_earlier_in_pregnancy_does_not_move_the_day_of_the_right() -> None:
    leaves = [
        LeavePeriod(person="mother", kind="sick", start=dt.date(2026, 1, 5), pages=[4]),
        LeavePeriod(person="mother", kind="maternity", start=dt.date(2026, 3, 10), pages=[1]),
    ]
    assert check_insurance(facts(leaves=leaves)).on == dt.date(2026, 3, 10)


def test_parental_leave_asked_for_becomes_the_plan() -> None:
    parental = LeavePeriod(
        person="mother",
        kind="parental",
        start=dt.date(2026, 7, 28),
        end=dt.date(2027, 3, 8),
        pages=[3],
    )
    case = facts(leaves=[*facts().leaves, parental, parental.model_copy(update={"pages": [9]})])
    scenario, _ = to_scenario(case)
    assert [(p.parent, p.weeks) for p in scenario.parental_parts] == [("mother", 32)]


def test_insured_on_the_day_the_right_arises() -> None:
    check = check_insurance(facts())
    assert check.covered is True
    assert check.on == dt.date(2026, 3, 10)
    assert check.text.startswith("Mama podlega ubezpieczeniu chorobowemu")


def test_contract_ended_before_the_birth_means_no_insurance() -> None:
    ended = [
        InsurancePeriod(
            person="mother",
            title="employment",
            label="umowa o pracę na czas określony",
            start=dt.date(2025, 1, 1),
            end=dt.date(2026, 2, 28),
            sickness="mandatory",
            pages=[2],
        )
    ]
    case = facts(
        insurance=ended, decision=Decision(outcome="refused", benefit="", reason="", pages=[])
    )
    check = check_insurance(case)
    assert check.covered is False
    assert "28 lutego 2026" in check.text
    result = compare(case, check)
    assert (result.ours, result.zus, result.match) == ("refused", "refused", True)


def test_refusal_for_another_reason_is_shown_as_a_difference() -> None:
    case = facts(
        decision=Decision(
            outcome="refused",
            benefit="",
            reason="Wniosek nie zawiera wymaganych dokumentów.",
            pages=[7],
        )
    )
    result = compare(case, check_insurance(case))
    assert result.match is False
    assert result.reason == "other-refusal"
    assert "z innego powodu" in result.text


def test_a_refusal_the_calculator_checks_but_the_facts_lack_is_a_reading_error() -> None:
    # ZUS found a sham contract, but the reading kept the contract with mandatory insurance.
    case = facts(
        decision=Decision(
            outcome="refused", benefit="", reason="Umowa zawarta dla pozoru.", pages=[7]
        )
    )
    result = compare(case, check_insurance(case))
    assert (result.match, result.reason) == (False, "reading")
    assert "odczyt" in result.reason_text


def test_a_premature_child_in_hospital_gets_what_supplementary_leave_needs() -> None:
    from app.cases.models import HospitalPeriod

    case = facts(
        birth_week=29,
        birth_weight_grams=650,
        hospital_stays=[HospitalPeriod(start=dt.date(2026, 3, 10), end=dt.date(2026, 5, 20))],
    )
    scenario, _ = to_scenario(case)
    assert scenario.birth_week == "28-37"
    assert scenario.birth_weight_up_to_1000g is True
    assert scenario.hospital_care is True
    assert scenario.hospital_stays[0].end == dt.date(2026, 5, 20)
    result = assess(
        case, case_id="S99", pages=1, pages_read=1, cached=False, params=load_params(), today=TODAY
    )
    assert result.timeline is not None
    assert any(s.id == "supplementary" for s in result.timeline.segments)


def test_assess_builds_the_timeline_with_amounts() -> None:
    result = assess(
        facts(),
        case_id="S99",
        pages=10,
        pages_read=9,
        cached=False,
        params=load_params(),
        today=TODAY,
    )
    assert result.problem is None
    assert result.timeline is not None
    assert result.timeline.payments, "the pay from Z-3 gives amounts"
    assert result.comparison.match is True


def test_no_date_means_no_timeline_but_still_an_answer() -> None:
    result = assess(
        facts(birth_date=None, child_born=None, leaves=[]),
        case_id=None,
        pages=1,
        pages_read=1,
        cached=False,
        params=load_params(),
        today=TODAY,
    )
    assert result.timeline is None
    assert result.problem


def run(case: CaseFacts) -> CaseResult:
    return assess(
        case, case_id="S99", pages=1, pages_read=1, cached=False, params=load_params(), today=TODAY
    )


def period(**changes: object) -> InsurancePeriod:
    base = InsurancePeriod(
        person="mother",
        title="employment",
        label="umowa o pracę",
        start=dt.date(2024, 1, 1),
        end=None,
        sickness="mandatory",
        pages=[3],
    )
    return base.model_copy(update=changes)


def refused(reason: str = "") -> Decision:
    return Decision(outcome="refused", benefit="zasiłek macierzyński", reason=reason, pages=[9])


def z3(month: str, amount: float, required: int | None = None, worked: int | None = None):
    """A month of the mother's pay as the reader copies it from Z-3."""
    return PayMonth(
        month=month,
        amount=amount,
        kind="salary",
        person="mother",
        full_month=None if required is None else False,
        days_required=required,
        days_worked=worked,
        pages=[4],
    )


# ---------------------------------------------------------------------------------------------
# The benefit base from the payer's certificate (Z-3), computed by engine/base.py


def test_the_base_comes_from_the_payers_certificate_step_by_step() -> None:
    # S80-like, synthetic numbers: the child born 12.05.2026, maternity leave from that day, so
    # the base comes from May 2025 - April 2026. Z-3: 10 full months of 7 000 zł; August 2025
    # worked 8 of 21 days (less than half: left out); February 2026 worked 15 of 20 days (at
    # least half: 5 250 / 15 × 20 = 7 000); two quarterly bonuses of 1 200 zł; full time.
    months = [f"2025-{m:02d}" for m in range(5, 13)] + [f"2026-{m:02d}" for m in range(1, 5)]
    partial = {"2025-08": (2666.67, 21, 8), "2026-02": (5250, 20, 15)}
    pay = [z3(month, *partial[month]) if month in partial else z3(month, 7000) for month in months]
    case = facts(
        birth_date=dt.date(2026, 5, 12),
        leaves=[
            LeavePeriod(person="mother", kind="maternity", start=dt.date(2026, 5, 12), pages=[1])
        ],
        pay=pay,
        bonuses=[
            Bonus(person="mother", kind="quarterly", period="IV kwartał 2025", amount=1200),
            Bonus(person="mother", kind="quarterly", period="I kwartał 2026", amount=1200),
        ],
        pay_details=[PayDetails(person="mother", full_time=True)],
    )
    result = run(case)
    assert result.scenario.mother_pay is None
    history = result.scenario.mother_pay_history
    assert history is not None and history.quarterly_bonuses == 2400 and history.full_time
    assert result.timeline is not None
    (base,) = result.timeline.bases
    assert base.detailed is True
    assert (base.months_from, base.months_to) == ("2025-05", "2026-04")
    statuses = {m.month: (m.status, m.counted) for m in base.months}
    assert statuses["2025-08"] == ("skipped", None)
    assert statuses["2026-02"] == ("topped-up", Decimal("7000.00"))
    assert statuses["2025-05"] == ("full", Decimal("7000"))
    # (10 × 7 000 + 7 000) / 11 = 7 000; + 2 400 / 12 = 200 -> 7 200; less 13,71% -> 6 212,88.
    assert base.pay == Decimal("7200.00")
    assert base.base == Decimal("6212.88")
    steps = " ".join(step.text for step in base.steps)
    assert "5 250,00 zł / 15 × 20 = 7 000,00 zł" in steps
    assert "jedna dwunasta, 200,00 zł" in steps
    assert result.timeline.payments[0].base == 6212.88
    assert any("krok po kroku z 12 mies." in note for note in result.notes)
    assert not any("Uproszczenie" in note for note in result.notes)


def test_months_that_do_not_fit_are_checked_before_the_engine() -> None:
    pay = [
        z3("03/2025", 6000),
        z3("2025-04", 6000),
        # The same month twice with another amount: the first one counts.
        z3("2025-04", 6500),
        # More days worked than required: a misreading, the month counts as given.
        z3("2025-05", 6000, 20, 22),
        z3("maj", 6000),
    ]
    scenario, notes = to_scenario(facts(pay=pay))
    history = scenario.mother_pay_history
    assert history is not None
    assert [(m.month, m.amount, m.days_worked) for m in history.months] == [
        ("2025-03", 6000, None),
        ("2025-04", 6000, None),
        ("2025-05", 6000, None),
    ]
    assert any("dwie kwoty" in note for note in notes)
    assert any("liczba dni (22 z 20)" in note for note in notes)
    assert any("„maj”" in note for note in notes)


# ---------------------------------------------------------------------------------------------
# Facts -> scenario: the situations of the cases that differed from ZUS (ZADANIA B.2)


def test_job_loss_by_liquidation_gives_the_benefit_after_the_insurance_ended() -> None:
    # S21-like: the employer was liquidated in pregnancy; ZUS granted the benefit equal to the
    # maternity benefit until the birth and the maternity benefit after it.
    case = facts(
        birth_date=dt.date(2026, 4, 20),
        insurance=[period(end=dt.date(2026, 1, 31))],
        leaves=[LeavePeriod(person="mother", kind="other", start=dt.date(2026, 2, 1), pages=[2])],
        job_loss=CaseJobLoss(ended_on=dt.date(2026, 1, 31), reason="liquidation", pages=[5]),
        decision=Decision(outcome="granted", benefit="", reason="", pages=[9]),
    )
    result = run(case)
    assert result.scenario.job_loss is not None
    assert result.scenario.job_loss.reason == "liquidation"
    assert result.timeline is not None
    benefit = next(s for s in result.timeline.segments if s.id == "job-loss-benefit")
    assert (benefit.start, benefit.end) == (dt.date(2026, 2, 1), dt.date(2026, 4, 19))
    assert result.insurance.covered is False
    assert "likwidacji pracodawcy" in result.insurance.text
    assert (result.comparison.ours, result.comparison.match) == ("granted", True)


def test_unlawful_termination_without_a_judgment_is_not_decided() -> None:
    case = facts(
        insurance=[period(end=dt.date(2026, 1, 31))],
        job_loss=CaseJobLoss(ended_on=dt.date(2026, 1, 31), reason="unlawful"),
    )
    result = compare(case, check_insurance(case))
    assert (result.ours, result.match) == ("unknown", None)
    assert "wyrok sądu" in result.text


def test_insurance_that_ended_before_the_birth_is_a_plain_end_of_work() -> None:
    case = facts(insurance=[period(end=dt.date(2026, 2, 28))], decision=refused())
    result = run(case)
    assert result.scenario.job_loss is not None
    assert (result.scenario.job_loss.ended_on, result.scenario.job_loss.reason) == (
        dt.date(2026, 2, 28),
        "other",
    )
    assert result.timeline is not None
    assert any(n.id == "job-loss" and n.kind == "risk" for n in result.timeline.notes)
    assert not any(s.id == "maternity" for s in result.timeline.segments)
    assert (result.comparison.ours, result.comparison.match) == ("refused", True)


def test_contract_without_voluntary_sickness_insurance_is_uninsured() -> None:
    # S08-like: a contract of mandate, not registered for the voluntary sickness insurance.
    contract = period(title="contract", label="umowa zlecenia", sickness="none")
    result = run(facts(insurance=[contract], decision=refused()))
    assert result.scenario.work == "contract"
    assert result.scenario.mother_insured is False
    assert result.insurance.covered is False
    assert result.timeline is not None
    insurance = next(n for n in result.timeline.notes if n.id == "insurance")
    assert insurance.kind == "risk"
    assert (result.comparison.ours, result.comparison.match) == ("refused", True)


def test_a_finding_of_zus_wins_over_what_the_payer_declared() -> None:
    # The payer declared the voluntary insurance, ZUS found that it ended.
    contract = period(
        title="contract", label="umowa zlecenia", sickness="voluntary", zus_finding="not-subject"
    )
    result = run(facts(insurance=[contract], decision=refused()))
    assert result.scenario.mother_insured is False
    assert result.insurance.covered is False
    assert "ustalenie ZUS" in result.insurance.text
    assert result.comparison.match is True


def test_a_sham_contract_found_by_zus_gives_no_insurance_and_the_risk() -> None:
    # S09-like: ZUS ruled the employment contract a sham; the payer still declared it.
    sham = period(
        label="umowa o pracę — wg ZUS nie podlega", sickness="mandatory", zus_finding="sham"
    )
    result = run(facts(insurance=[sham], decision=refused("Umowa zawarta dla pozoru.")))
    assert result.insurance.covered is False
    assert result.scenario.work == "none"
    assert result.scenario.insured_in_pregnancy is True
    assert result.timeline is not None
    assert any(n.id == "risk-sham" for n in result.timeline.notes)
    assert not any(s.id == "maternity" for s in result.timeline.segments)
    assert (result.comparison.ours, result.comparison.match) == ("refused", True)
    assert any("dla pozoru" in note for note in result.notes)


def test_a_foster_family_is_checked_on_the_day_the_child_is_taken_in() -> None:
    # S19-like: the child (born 1.09.2025) taken in on 1.06.2026; the contract ended 30.06.2026,
    # before the leave written in the request: what counts is the day of taking in.
    case = facts(
        child_born=True,
        birth_date=dt.date(2025, 9, 1),
        taken_in="foster",
        taken_in_on=dt.date(2026, 6, 1),
        insurance=[period(start=dt.date(2026, 1, 1), end=dt.date(2026, 6, 30))],
        leaves=[LeavePeriod(person="mother", kind="other", start=dt.date(2026, 7, 1), pages=[2])],
        decision=Decision(outcome="granted", benefit="", reason="", pages=[9]),
    )
    check = check_insurance(case)
    assert check.on == dt.date(2026, 6, 1)
    assert check.covered is True
    assert "dzień przyjęcia dziecka" in check.text
    result = run(case)
    assert result.scenario.taken_in == "foster"
    assert result.scenario.work == "employment"
    assert result.scenario.job_loss is None, "no pregnancy for a child taken in"
    assert result.timeline is not None
    assert result.comparison.match is True


def test_contribution_debt_of_a_business_refuses_the_benefit() -> None:
    # S10-like: the father with his own business asks for paternity benefit; on the day the
    # right arises he owes 1 250 zł of contributions, more than 1% of the minimum wage (48,06 zł).
    case = facts(
        applicant="father",
        insurance=[
            period(person="father", title="business", label="działalność", sickness="voluntary")
        ],
        leaves=[
            LeavePeriod(
                person="father",
                kind="paternity",
                start=dt.date(2026, 4, 1),
                end=dt.date(2026, 4, 14),
                pages=[1],
            )
        ],
        pay=[],
        contribution_debt=ContributionDebt(person="father", amount=1250, pages=[6]),
        decision=refused("Zadłużenie z tytułu składek na dzień powstania prawa."),
    )
    result = run(case)
    assert result.scenario.father_contribution_debt == 1250
    assert result.insurance.covered is True
    assert result.comparison.ours == "refused"
    assert result.comparison.match is True
    assert "48,06 zł" in result.comparison.text
    assert result.timeline is not None
    debt = next(n for n in result.timeline.notes if n.id == "debt-father")
    assert debt.kind == "risk"
    # Repaid within 6 months of the day the right arose: the benefit is paid after it.
    repaid = case.model_copy(
        update={
            "contribution_debt": ContributionDebt(
                person="father", amount=1250, repaid_on=dt.date(2026, 10, 1)
            )
        }
    )
    assert compare(repaid, check_insurance(repaid)).ours == "granted"
    late = case.model_copy(
        update={
            "contribution_debt": ContributionDebt(
                person="father", amount=1250, repaid_on=dt.date(2026, 10, 2)
            )
        }
    )
    assert compare(late, check_insurance(late)).ours == "refused"
    small = case.model_copy(
        update={"contribution_debt": ContributionDebt(person="father", amount=48.06)}
    )
    assert compare(small, check_insurance(small)).ours == "granted"


def test_debt_of_an_employee_does_not_count() -> None:
    case = facts(contribution_debt=ContributionDebt(person="mother", amount=900))
    scenario, notes = to_scenario(case)
    assert scenario.mother_contribution_debt is None
    assert any(
        "osobom prowadzącym działalność i osobom z nimi współpracującym" in note for note in notes
    )


def test_more_parts_of_parental_leave_than_the_rules_allow() -> None:
    # S11-like: the sixth part is asked for; the rules allow five.
    starts = [dt.date(2026, 7, 28) + dt.timedelta(weeks=3 * k) for k in range(6)]
    parts = [
        LeavePeriod(
            person="mother",
            kind="parental",
            start=start,
            end=start + dt.timedelta(days=13),
            pages=[2],
        )
        for start in starts
    ]
    case = facts(
        leaves=[*facts().leaves, *parts],
        decision=refused("Urlop rodzicielski udzielany jest w nie więcej niż 5 częściach."),
    )
    result = run(case)
    assert len(result.scenario.parental_parts) == 5
    assert any("część 6." in note for note in result.notes)
    assert result.comparison.ours == "partial"
    assert result.comparison.match is True


def test_the_father_taking_over_maternity_leave() -> None:
    # The mother uses 16 weeks after the birth (10.03.2026 - 29.06.2026), the father the rest.
    case = facts(
        leaves=[
            *facts().leaves,
            LeavePeriod(person="father", kind="maternity", start=dt.date(2026, 6, 30), pages=[3]),
        ]
    )
    result = run(case)
    assert result.scenario.father_takes_over is True
    assert result.scenario.mother_weeks_before_takeover == 16
    assert result.timeline is not None
    father = next(s for s in result.timeline.segments if s.id == "maternity-father")
    assert father.start == dt.date(2026, 6, 30)


def test_taking_over_before_14_weeks_needs_a_special_situation() -> None:
    early = LeavePeriod(person="father", kind="maternity", start=dt.date(2026, 5, 12), pages=[3])
    scenario, notes = to_scenario(facts(leaves=[*facts().leaves, early]))
    assert scenario.father_takes_over is None
    assert any("sytuacjach szczególnych" in note for note in notes)
    event = CaseMotherEvent(kind="hospital", start=dt.date(2026, 5, 11), end=dt.date(2026, 6, 1))
    scenario, _ = to_scenario(facts(leaves=[*facts().leaves, early], mother_event=event))
    assert scenario.mother_event is not None
    assert (scenario.mother_event.kind, scenario.mother_event.end) == (
        "hospital",
        dt.date(2026, 6, 1),
    )


def test_cached_readings_without_the_new_fields_still_validate() -> None:
    old = facts().model_dump(mode="json")
    for name in ("bonuses", "pay_details", "job_loss", "mother_event", "contribution_debt"):
        old.pop(name)
    for month in old["pay"]:
        for name in ("days_required", "days_worked", "fixed", "variable", "not_topped"):
            month.pop(name)
    for item in old["insurance"]:
        item.pop("zus_finding")
    assert CaseFacts.model_validate(old).bonuses == []


# ---------------------------------------------------------------------------------------------
# Every difference from ZUS has a reason


def test_granted_by_zus_without_insurance_in_the_facts_is_a_reading_error() -> None:
    case = facts(insurance=[period(start=dt.date(2026, 4, 1))])
    result = compare(case, check_insurance(case))
    assert (result.ours, result.zus, result.match) == ("refused", "granted", False)
    assert result.reason == "reading"


def test_granted_by_zus_after_the_insurance_ended_is_a_missing_rule() -> None:
    # E.g. a fixed-term contract extended until the birth: the calculator does not apply it.
    case = facts(insurance=[period(end=dt.date(2026, 2, 28))])
    result = compare(case, check_insurance(case))
    assert (result.match, result.reason) == (False, "missing-rule")
    assert "28 lutego 2026" in result.reason_text


def test_agreeing_cases_have_no_reason() -> None:
    result = compare(facts(), check_insurance(facts()))
    assert (result.match, result.reason, result.reason_text) == (True, None, "")


# ---------------------------------------------------------------------------------------------
# API


class FakeReader:
    def __init__(self) -> None:
        self.calls = 0

    async def read(self, pages: list) -> CaseFacts:  # noqa: ANN001
        self.calls += 1
        assert pages, "blank pages are skipped, the rest is sent"
        return facts()


@pytest.fixture
def client(tmp_path: Path):
    folder = tmp_path / "sprawy"
    folder.mkdir()
    (folder / "Kowalska macierzyński.pdf").write_bytes(fake_pdf(3, blank=(3,)))
    reader = FakeReader()
    app.dependency_overrides[get_cases_folder] = lambda: folder
    app.dependency_overrides[get_case_cache] = lambda: CaseCache(tmp_path / "cache")
    app.dependency_overrides[get_reader_factory] = lambda: lambda: reader
    app.dependency_overrides[get_today] = lambda: TODAY
    sessions = MemorySessionStore()
    app.dependency_overrides[get_session_store] = lambda: sessions
    with TestClient(app) as test_client:
        test_client.reader = reader  # type: ignore[attr-defined]
        yield test_client
    app.dependency_overrides.clear()


def test_list_shows_ids_and_categories_but_no_file_names(client: TestClient) -> None:
    body = client.get("/api/cases").json()
    assert body["configured"] is True
    assert body["cases"] == [
        {"id": "S01", "category": "Macierzyński", "title": "", "pages": 3, "read": False}
    ]
    assert "Kowalska" not in str(body)


def test_a_case_is_read_once_then_comes_from_the_cache(client: TestClient) -> None:
    first = client.post("/api/cases/S01/read").json()
    assert first["id"] == "S01"
    assert (first["pages"], first["pages_read"], first["cached"]) == (3, 2, False)
    assert first["insurance"]["covered"] is True
    again = client.post("/api/cases/S01/read").json()
    assert again["cached"] is True
    assert client.reader.calls == 1  # type: ignore[attr-defined]
    assert client.get("/api/cases").json()["cases"][0]["read"] is True


def test_an_uploaded_catalogue_file_keeps_its_id(client: TestClient, tmp_path: Path) -> None:
    data = (tmp_path / "sprawy" / "Kowalska macierzyński.pdf").read_bytes()
    result = client.post(
        "/api/cases/upload", files={"file": ("sprawa.pdf", data, "application/pdf")}
    )
    assert result.status_code == 200
    assert result.json()["id"] == "S01"


def test_upload_rejects_other_files(client: TestClient) -> None:
    result = client.post("/api/cases/upload", files={"file": ("a.txt", b"hello", "text/plain")})
    assert result.status_code == 415


def test_corrected_facts_are_recalculated_without_ai(client: TestClient) -> None:
    corrected = facts(children_count=2).model_dump(mode="json")
    result = client.post("/api/cases/assess", json={"id": "S01", "facts": corrected}).json()
    assert result["scenario"]["children_count"] == 2
    assert client.reader.calls == 0  # type: ignore[attr-defined]


def test_a_case_loads_into_the_plan(client: TestClient) -> None:
    scenario = to_scenario(facts())[0].model_dump(mode="json")
    session = "8b0c7f1e-3c2a-4f6b-9d7e-2a1b3c4d5e6f"
    start = client.put(f"/api/cases/session/{session}", json={"scenario": scenario}).json()
    assert start["scenario"]["birth_date"] == "2026-03-10"
    restored = client.get(f"/api/session/{session}").json()
    assert len(restored["scenario"]["mother_pay_history"]["months"]) == 12


def test_the_agreement_report_comes_from_the_cache_only(client: TestClient) -> None:
    before = client.get("/api/cases/agreement").json()
    assert (before["configured"], before["total"], before["read"]) == (True, 1, 0)
    assert before["rows"][0] == {
        "id": "S01",
        "category": "Macierzyński",
        "read": False,
        "title": "",
        "zus": None,
        "ours": None,
        "match": None,
        "reason": None,
        "reason_text": "",
        "covered": None,
        "timeline": False,
        "payments": 0,
        "problem": None,
    }
    client.post("/api/cases/S01/read")
    after = client.get("/api/cases/agreement").json()
    assert (after["read"], after["decided"], after["agree"]) == (1, 1, 1)
    assert after["zus"] == {"granted": 1}
    assert after["reasons"] == {}
    assert (after["with_timeline"], after["with_amounts"]) == (1, 1)
    row = after["rows"][0]
    assert (row["ours"], row["zus"], row["match"], row["covered"]) == (
        "granted",
        "granted",
        True,
        True,
    )
    assert client.reader.calls == 1, "the report reads nothing"  # type: ignore[attr-defined]
