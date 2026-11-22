"""F4 (ZADANIA B.12): the payments month by month and who pays them (engine/monthly.py). A
payment's amount in a month is its daily amount times its days in that month. Expected amounts
were computed by hand from the daily amounts of test_money.py:

- the mother, 8000 zł: base 6903,20; 100%: 230,11 a day; 70%: 4832,24 / 30 = 161,0747 → 161,07;
- the father, 6000 zł: base 6000 × 0,8629 = 5177,40; 100%: 5177,40 / 30 = 172,58; 70%:
  3624,18 / 30 = 120,806 → 120,81.

The usual family (test_money.py): born 10.11.2026; maternity leave 10.11.2026–29.03.2027, the
mother's parental leave 30.03–08.11.2027, paternity leave 21.11–04.12.2026, the father's parental
leave 09.11.2027–10.01.2028.
"""

import datetime as dt
from decimal import Decimal
from typing import Any

import pytest

from app.engine import Scenario, Timeline, build_timeline
from app.engine.models import MonthlyPayment
from app.services.params import load_params

PARAMS = load_params()
TODAY = dt.date(2026, 11, 21)
MOTHER = {"role": "mother", "work": "employment", "children_count": 1}
USUAL = MOTHER | {
    "child_born": True,
    "birth_date": "2026-11-10",
    "leave_before_birth_weeks": 0,
    "mother_pay": 8000,
}
FATHER = {"father_work": "employment", "father_pay": 6000}
FAMILY = USUAL | FATHER | {"mother_payer_size": "over-20"}
"""The usual family with both amounts; the mother's employer reports more than 20 people."""
EXPECTING = MOTHER | {"child_born": False, "due_date": "2027-03-15", "mother_pay": 8000}
SICK = EXPECTING | {
    "leave_before_birth_weeks": 0,
    "sick_leave": True,
    "sick_leave_start": "2026-10-15",
    "insured_since": "2020-01-01",
    "mother_payer_size": "up-to-20",
}
"""Sick from 15.10.2026 until the birth on 15.03.2027. 33 days of sick pay from 15.10.2026: 17
days of October + 16 of November, to 16.11.2026; the sickness benefit 17.11–31.12.2026; in 2027
sick pay again 01.01–02.02.2027 (31 + 2 = 33 days), the benefit 03.02–14.03.2027; maternity leave
from 15.03.2027."""
ADOPTION = {
    "role": "mother",
    "work": "employment",
    "child_born": True,
    "taken_in": "adoption",
    "taken_in_on": "2026-11-02",
    "birth_date": "2024-05-10",
    "children_count": 1,
}


def build(answers: dict[str, Any]) -> Timeline:
    return build_timeline(Scenario.model_validate(answers), PARAMS, TODAY)


def month(t: Timeline, name: str) -> MonthlyPayment:
    return next(m for m in t.monthly if m.month == name)


def lines(m: MonthlyPayment) -> list[tuple[str, str | None, str, Decimal, list[str]]]:
    return [(x.parent, x.payer, x.payer_label, x.amount, x.payment_ids) for x in m.lines]


def d(text: str) -> Decimal:
    return Decimal(text)


def test_a_period_starting_in_the_middle_of_a_month_is_paid_for_its_days_in_it() -> None:
    """November 2026: the mother 10–30.11 = 21 days × 230,11 = 4 832,31 zł; the father 21–30.11
    = 10 days × 172,58 = 1 725,80 zł; together 6 558,11 zł. December: the mother 31 × 230,11 =
    7 133,41 zł, the father 1–4.12 = 4 × 172,58 = 690,32 zł. The months run from November 2026
    to January 2028, the last day of the father's parental leave: 15 months."""
    t = build(FAMILY)
    november = month(t, "2026-11")
    assert (november.mother, november.father, november.total) == (
        d("4832.31"),
        d("1725.80"),
        d("6558.11"),
    )
    assert lines(november) == [
        ("mother", "payer", "Pracodawca mamy", d("4832.31"), ["pay-maternity"]),
        ("father", "payer-or-zus", "Pracodawca taty albo ZUS", d("1725.80"), ["pay-paternity"]),
    ]
    assert november.payment_ids == ["pay-maternity", "pay-paternity"]
    december = month(t, "2026-12")
    assert (december.mother, december.father) == (d("7133.41"), d("690.32"))
    assert [m.month for m in t.monthly][0::7] == ["2026-11", "2027-06", "2028-01"]
    assert len(t.monthly) == 15
    # Mother 32 215,40 + 36 079,68 = 68 295,08; father 14 × 172,58 = 2 416,12 and
    # 63 × 120,81 = 7 611,03, together 10 027,15; both 78 322,23 zł.
    assert t.money_total is not None
    assert (t.money_total.mother, t.money_total.father, t.money_total.total) == (
        d("68295.08"),
        d("10027.15"),
        d("78322.23"),
    )


def test_maternity_leave_ends_and_parental_leave_starts_in_one_month_at_100_then_70() -> None:
    """March 2027: maternity leave 1–29.03 at 100% = 29 × 230,11 = 6 673,19 zł; parental leave
    30–31.03 at 70% = 2 × 161,07 = 322,14 zł; together 6 995,33 zł, from the same payer: one
    line. November 2027: the mother's last 8 days, 8 × 161,07 = 1 288,56 zł, and the father's
    first 22, 9–30.11: 22 × 120,81 = 2 657,82 zł; together 3 946,38 zł."""
    t = build(FAMILY)
    march = month(t, "2027-03")
    assert (march.mother, march.father, march.total) == (d("6995.33"), d("0.00"), d("6995.33"))
    assert lines(march) == [
        ("mother", "payer", "Pracodawca mamy", d("6995.33"), ["pay-maternity", "pay-parental"])
    ]
    assert [(p.rate, p.daily) for p in t.payments if p.id in march.payment_ids] == [
        (100, 230.11),
        (70, 161.07),
    ]
    november = month(t, "2027-11")
    assert (november.mother, november.father, november.total) == (
        d("1288.56"),
        d("2657.82"),
        d("3946.38"),
    )
    assert november.payment_ids == ["pay-parental", "pay-parental-father"]


def test_sick_pay_from_the_employer_then_the_sickness_benefit_from_zus_in_one_month() -> None:
    """The employer reports up to 20 people, so ZUS pays the benefits. November 2026: sick pay
    1–16.11 = 16 × 230,11 = 3 681,76 zł from the employer; the sickness benefit 17–30.11 = 14 ×
    230,11 = 3 221,54 zł from ZUS; together 6 903,30 zł. February 2027: sick pay 1–2.02 = 2 ×
    230,11 = 460,22 zł, the benefit 3–28.02 = 26 × 230,11 = 5 982,86 zł. March 2027: the
    sickness benefit 1–14.03 and maternity leave 15–31.03, both from ZUS: 31 × 230,11 =
    7 133,41 zł."""
    t = build(SICK)
    november = month(t, "2026-11")
    employer = "Pracodawca mamy (wynagrodzenie chorobowe)"
    assert lines(november) == [
        ("mother", "employer", employer, d("3681.76"), ["pay-sick-pay"]),
        ("mother", "zus", "ZUS", d("3221.54"), ["pay-sick-benefit"]),
    ]
    assert (november.mother, november.total) == (d("6903.30"), d("6903.30"))
    february = month(t, "2027-02")
    assert lines(february) == [
        ("mother", "employer", employer, d("460.22"), ["pay-sick-pay-2"]),
        ("mother", "zus", "ZUS", d("5982.86"), ["pay-sick-benefit-2"]),
    ]
    march = month(t, "2027-03")
    assert lines(march) == [
        ("mother", "zus", "ZUS", d("7133.41"), ["pay-sick-benefit-2", "pay-maternity"])
    ]
    # With more than 20 insured the employer pays the benefit too, in a line of its own.
    big = build(SICK | {"mother_payer_size": "over-20"})
    assert [(x.payer, x.payer_label) for x in month(big, "2026-11").lines] == [
        ("employer", employer),
        ("payer", "Pracodawca mamy"),
    ]


def test_months_without_a_paid_day_stay_at_zero() -> None:
    """The sick leave ends on 30.11.2026 and the mother works until the birth on 15.03.2027:
    December, January and February are gaps. March: maternity leave 15–31.03 = 17 × 230,11 =
    3 911,87 zł."""
    t = build(SICK | {"sick_leave_end": "2026-11-30"})
    assert [m.month for m in t.monthly][:6] == [
        "2026-10",
        "2026-11",
        "2026-12",
        "2027-01",
        "2027-02",
        "2027-03",
    ]
    for name in ("2026-12", "2027-01", "2027-02"):
        gap = month(t, name)
        assert (gap.mother, gap.father, gap.total) == (0, 0, 0)
        assert (gap.lines, gap.payment_ids) == ([], [])
    assert month(t, "2027-03").total == d("3911.87")
    # Amounts are numbers in the API.
    dumped = t.model_dump(mode="json")
    assert dumped["monthly"][2]["total"] == 0.0
    assert dumped["monthly"][5]["mother"] == 3911.87
    assert dumped["money_total"]["total"] == float(t.money_total.total)  # type: ignore[union-attr]


def test_the_benefits_for_the_time_after_the_insurance_ended_are_paid_by_zus() -> None:
    """Sick from 01.10.2026, the work ended on 30.11.2026 for another reason (test_after_
    insurance.py): sick pay 01.10–02.11 (33 days), the sickness benefit 03.11–30.11 (28 days),
    the benefit after the insurance ended 01.12.2026–14.03.2027. The employer reports more than
    20 people. November: sick pay 2 × 230,11 = 460,22 zł and the benefit 28 × 230,11 =
    6 443,08 zł, both from the employer; December: 31 × 230,11 = 7 133,41 zł from ZUS."""
    loss = {"job_loss": {"ended_on": "2026-11-30", "reason": "other"}}
    sick = {"sick_leave": True, "sick_leave_start": "2026-10-01", "mother_payer_size": "over-20"}
    t = build(EXPECTING | loss | sick)
    assert [(x.payer, x.amount) for x in month(t, "2026-11").lines] == [
        ("employer", d("460.22")),
        ("payer", d("6443.08")),
    ]
    assert lines(month(t, "2026-12")) == [
        ("mother", "zus", "ZUS", d("7133.41"), ["pay-sick-after-insurance"])
    ]
    # The period itself says the same: the sickness benefit before the end of work is the
    # employer's to pay, not ZUS's.
    benefit = t.element("sick-benefit")
    assert benefit is not None
    assert "Zasiłek chorobowy mamy wypłaca jej pracodawca" in benefit.details[-1]  # type: ignore[union-attr]
    # After a bankruptcy: the benefit equal to the maternity benefit and the maternity benefit
    # after it come from ZUS.
    bankrupt = build(
        EXPECTING | {"job_loss": {"ended_on": "2026-11-30", "reason": "bankruptcy"}} | sick
    )
    march = month(bankrupt, "2027-03")
    assert [(x.payer, x.payment_ids) for x in march.lines] == [
        ("zus", ["pay-job-loss-benefit", "pay-maternity"])
    ]


@pytest.mark.parametrize(
    ("answers", "payer", "label"),
    [
        ({"mother_payer_size": "over-20"}, "payer", "Pracodawca mamy"),
        ({"mother_payer_size": "up-to-20"}, "zus", "ZUS"),
        ({}, "payer-or-zus", "Pracodawca mamy albo ZUS"),
        (
            {"work": "contract", "mother_insured": True, "mother_payer_size": "over-20"},
            "payer",
            "Zleceniodawca mamy",
        ),
        (
            {"work": "contract", "mother_insured": True, "mother_payer_size": "unknown"},
            "payer-or-zus",
            "Zleceniodawca mamy albo ZUS",
        ),
        ({"work": "business", "mother_insured": True}, "zus", "ZUS"),
    ],
)
def test_who_pays_the_benefit(answers: dict[str, Any], payer: str, label: str) -> None:
    line = month(build(USUAL | answers), "2026-11").lines[0]
    assert (line.parent, line.payer, line.payer_label) == ("mother", payer, label)


def test_who_pays_the_rehabilitation_benefit_the_materials_do_not_say() -> None:
    t = build(
        EXPECTING
        | {"leave_before_birth_weeks": 0, "sick_leave": True, "sick_leave_start": "2026-06-01"}
        | {"mother_over_50": False, "rehab_benefit": "granted", "mother_payer_size": "up-to-20"}
    )
    rehab = month(t, "2027-03").lines[0]
    assert (rehab.payer, rehab.payer_label, rehab.payment_ids) == (
        None,
        "Materiały nie mówią, kto wypłaca",
        ["pay-rehab-benefit"],
    )
    assert any("świadczenie rehabilitacyjne, materiały nie mówią" in a for a in t.assumptions)


def test_a_child_taken_in_gets_the_months_too() -> None:
    """test_adoption.py: the mother (7000 zł: base 6040,30, a day 201,34) is on leave on the
    terms of maternity leave 02.11.2026–07.02.2027 and hands the rest to the father, 08.02–
    21.03.2027 (172,58 a day). February 2027: the mother 1–7.02 = 7 × 201,34 = 1 409,38 zł, the
    father 8–28.02 = 21 × 172,58 = 3 624,18 zł; together 5 033,56 zł. March: the father 1–21.03 =
    21 × 172,58 = 3 624,18 zł; the mother's parental leave from 22.03 at 70%: 6040,30 × 0,7 =
    4228,21, a day 140,94; 22–31.03 = 10 × 140,94 = 1 409,40 zł."""
    t = build(
        ADOPTION
        | {"father_work": "employment", "taken_in_handover": True}
        | {"mother_pay": 7000, "father_pay": 6000}
    )
    february = month(t, "2027-02")
    assert (february.mother, february.father, february.total) == (
        d("1409.38"),
        d("3624.18"),
        d("5033.56"),
    )
    assert february.payment_ids == ["pay-adoption-leave", "pay-adoption-leave-other"]
    march = month(t, "2027-03")
    assert (march.mother, march.father) == (d("1409.40"), d("3624.18"))
    assert t.monthly[0].month == "2026-11"
    assert t.money_total is not None
    assert t.money_total.total == sum((Decimal(str(p.total)) for p in t.payments), Decimal(0))


def test_no_amounts_no_months() -> None:
    for answers in (
        MOTHER | {"child_born": True, "birth_date": "2026-11-10"},
        USUAL | {"mother_pay": "unknown"},
    ):
        t = build(answers)
        assert (t.payments, t.monthly, t.money_total) == ([], [], None)
        assert not any("Miesiąc po miesiącu" in a for a in t.assumptions)


# The months add up to the payments, grosz for grosz, whatever the case.

SWEEP: list[dict[str, Any]] = [
    USUAL,
    USUAL | FATHER,
    USUAL | FATHER | {"rate_815": True},
    USUAL | FATHER | {"children_count": 2, "za_zyciem": True},
    USUAL
    | {"mother_pay": 12345.67, "father_work": "contract", "father_insured": True}
    | {"father_pay": 4321.09},
    USUAL | FATHER | {"father_takes_over": True},
    USUAL
    | FATHER
    | {
        "hospital_care": True,
        "birth_week": "before-28",
        "birth_weight_up_to_1000g": True,
        "hospital_stays": [{"start": "2026-11-10", "end": "2026-12-20"}],
    },
    EXPECTING | FATHER | {"leave_before_birth_weeks": 6, "has_medical_certificate": True},
    EXPECTING | FATHER | {"leave_before_birth_weeks": 2, "rate_815": True},
    EXPECTING | FATHER | {"rate_815": True, "parental_parts": [{"parent": "father", "weeks": 12}]},
    EXPECTING
    | FATHER
    | {
        "parental_parts": [
            {"parent": "mother", "weeks": 20, "work_fraction": "1/2", "work_weeks": 6},
            {"parent": "father", "weeks": 9, "with_previous": True},
            {"parent": "mother", "weeks": 12, "start": "2028-03-01"},
        ]
    },
    SICK,
    SICK | {"sick_leave_end": "2026-11-30"},
    SICK | {"mother_payer_size": "over-20", "rate_815": True} | FATHER,
    EXPECTING
    | {"job_loss": {"ended_on": "2026-11-30", "reason": "bankruptcy"}}
    | {"sick_leave": True, "sick_leave_start": "2026-10-01"},
    EXPECTING
    | {"job_loss": {"ended_on": "2026-11-30", "reason": "other"}}
    | {"sick_leave": True, "sick_leave_start": "2026-10-01"},
    EXPECTING
    | {"leave_before_birth_weeks": 0, "sick_leave": True, "sick_leave_start": "2026-06-01"}
    | {"mother_over_50": False, "rehab_benefit": "granted"},
    USUAL | {"work": "business", "mother_insured": True, "mother_pay": 5432.1} | FATHER,
    USUAL | FATHER | {"losses": [{"stillborn": True}]},
    ADOPTION | {"mother_pay": 7000},
    ADOPTION
    | {"father_work": "employment", "taken_in_handover": True}
    | {"mother_pay": 7000}
    | {"father_pay": 6000, "rate_815": True},
    ADOPTION | {"taken_in": "foster", "mother_pay": 9100.55} | FATHER,
]


@pytest.mark.parametrize("answers", SWEEP)
def test_the_months_add_up_to_the_payments(answers: dict[str, Any]) -> None:
    t = build(answers)
    assert t.payments, "every case of the sweep has amounts"
    totals = {p.id: Decimal(str(p.total)) for p in t.payments}
    first = min(p.start for p in t.payments)
    last = max(p.end for p in t.payments)
    # Every calendar month from the first paid day to the last, once, in order.
    expected, year, number = [], first.year, first.month
    while (year, number) <= (last.year, last.month):
        expected.append(f"{year}-{number:02d}")
        year, number = (year + 1, 1) if number == 12 else (year, number + 1)
    assert [m.month for m in t.monthly] == expected
    by_payment: dict[str, Decimal] = dict.fromkeys(totals, Decimal(0))
    for m in t.monthly:
        assert m.total == m.mother + m.father
        for parent, amount in (("mother", m.mother), ("father", m.father)):
            assert amount == sum((x.amount for x in m.lines if x.parent == parent), Decimal(0))
        assert sorted(m.payment_ids) == sorted(i for x in m.lines for i in x.payment_ids)
        for x in m.lines:
            for pid in x.payment_ids:
                p = next(p for p in t.payments if p.id == pid)
                assert p.lane == x.parent
                by_payment[pid] += Decimal(str(p.daily)) * sum(
                    1
                    for day in range((p.end - p.start).days + 1)
                    if f"{p.start + dt.timedelta(days=day):%Y-%m}" == m.month
                )
    # Each payment's months add up to its total; all the months to all the payments.
    assert by_payment == totals
    assert t.money_total is not None
    assert sum((m.total for m in t.monthly), Decimal(0)) == t.money_total.total
    assert t.money_total.total == sum(totals.values(), Decimal(0))
    assert t.money_total.mother == sum(
        (totals[p.id] for p in t.payments if p.lane == "mother"), Decimal(0)
    )
    assert t.money_total.father == sum(
        (totals[p.id] for p in t.payments if p.lane == "father"), Decimal(0)
    )
    assert t.money_total.total == t.money_total.mother + t.money_total.father
