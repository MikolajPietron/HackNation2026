"""The benefit base in detail (engine/base.py): the ustawa zasiłkowa art. 36-50 and the ZUS
Załącznik. Expected bases were computed by hand (the arithmetic is in each docstring): a month
topped up, the average, a twelfth of a bonus and the base each rounded to the grosz;
base = gross × (100% − 13,71%) = gross × 0,8629.

The usual family (as in test_money.py): a child born on 10.11.2026, today 21.11.2026, no leave
before the birth, so the right arises on 10.11.2026 and the 12 months are November 2025 to
October 2026. Maternity leave 10.11.2026–29.03.2027 (140 days).
"""

import datetime as dt
from decimal import Decimal
from typing import Any

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.api.deps import get_today
from app.assistant.describe import interview_questions
from app.engine import Scenario, Timeline, build_timeline
from app.engine.base import month_later
from app.engine.models import BenefitBase, PayHistory, Payment, PayMonth
from app.main import app
from app.services.params import load_params

PARAMS = load_params()
TODAY = dt.date(2026, 11, 21)
BORN = {"role": "mother", "work": "employment", "children_count": 1, "child_born": True}
BORN |= {"birth_date": "2026-11-10", "leave_before_birth_weeks": 0}


def months(first: str, count: int, amount: float) -> list[dict[str, Any]]:
    """`count` calendar months from `first` ("2025-11"), each with the same amount."""
    year, month = (int(part) for part in first.split("-"))
    index = year * 12 + month - 1
    return [
        {"month": f"{(index + i) // 12}-{(index + i) % 12 + 1:02d}", "amount": amount}
        for i in range(count)
    ]


def timeline(**answers: object) -> Timeline:
    return build_timeline(Scenario.model_validate(BORN | answers), PARAMS, TODAY)


def base(t: Timeline, parent: str = "mother") -> BenefitBase:
    return next(b for b in t.bases if b.parent == parent)


def pay(t: Timeline, segment_id: str) -> Payment:
    return next(p for p in t.payments if p.segment_id == segment_id)


def note(t: Timeline, note_id: str) -> str:
    return next(n.text for n in t.notes if n.id == note_id)


def articles(b: BenefitBase) -> set[str]:
    return {s.article for s in b.sources if s.article}


def test_twelve_months_of_different_pay() -> None:
    """November 2025–April 2026: 6 × 7000 = 42 000; May–October 2026: 6 × 9000 = 54 000.
    96 000 / 12 = 8000,00; 8000 × 0,8629 = 6903,20 zł. Maternity: a day 6903,20 / 30 = 230,11;
    140 × 230,11 = 32 215,40 zł."""
    t = timeline(
        mother_pay_history={"months": months("2025-11", 6, 7000) + months("2026-05", 6, 9000)}
    )
    b = base(t)
    assert (b.right_from, b.months_from, b.months_to) == (
        dt.date(2026, 11, 10),
        "2025-11",
        "2026-10",
    )
    assert (b.pay, b.base, b.detailed) == (8000, Decimal("6903.2"), True)
    assert {m.status for m in b.months} == {"full"}
    maternity = pay(t, "maternity")
    assert (maternity.base, maternity.daily, maternity.total) == (6903.2, 230.11, 32215.4)
    assert maternity.details[0] == (
        "Podstawa wymiaru zasiłku: przeciętnie 8 000,00 zł wynagrodzenia brutto miesięcznie "
        "(z 12 miesięcy) pomniejszone o 13,71%, czyli 6 903,20 zł miesięcznie."
    )
    assert b.steps[0].text.endswith("czyli od listopada 2025 do października 2026.")
    assert (
        b.steps[2].text == "Przeciętne miesięczne wynagrodzenie: 96 000,00 zł / 12 = 8 000,00 zł."
    )
    assert articles(b) >= {"art. 36 ust. 1", "art. 47", "art. 38 ust. 1", "art. 3 pkt 3"}
    assert any(s.doc == "zalacznik" for s in b.sources)
    # The steps are a point of the case explanation, right before the amounts.
    ids = [n.id for n in t.notes]
    assert ids.index("base-mother") == ids.index("money") - 1
    title = next(n.title for n in t.notes if n.id == "base-mother")
    assert title == "Podstawa wymiaru zasiłku mamy: 6 903,20 zł"


def test_months_worked_in_part_and_bonuses() -> None:
    """Nine months in full: 9 × 8000 = 72 000.
    March 2026: 8 of 21 days, less than half (2 × 8 = 16 < 21): left out.
    April 2026: 11 of 22 days, half (2 × 11 = 22): topped up 4400 / 11 × 22 = 8800,00.
    May 2026: 14 of 21 days, fixed 6000 in full + variable 1400 / 14 × 21 = 2100 + overtime 300
    as paid = 8400,00.
    (72 000 + 8800 + 8400) / 11 = 89 200 / 11 = 8109,09.
    Quarterly bonuses 6000 / 12 = 500,00; annual 9600 / 12 = 800,00; together 9409,09.
    9409,09 × 0,8629 = 8119,10 zł. Maternity: a day 8119,10 / 30 = 270,64; 140 × 270,64 =
    37 889,60 zł."""
    history = {
        "months": [
            *months("2025-11", 4, 8000),
            {"month": "2026-03", "amount": 3000, "days_required": 21, "days_worked": 8},
            {"month": "2026-04", "amount": 4400, "days_required": 22, "days_worked": 11},
            {"month": "2026-05", "amount": 7400, "days_required": 21, "days_worked": 14}
            | {"fixed": 6000, "variable": 1400, "not_topped": 300},
            *months("2026-06", 5, 8000),
        ],
        "quarterly_bonuses": 6000,
        "annual_bonus": 9600,
    }
    t = timeline(mother_pay_history=history)
    b = base(t)
    assert (float(b.pay), float(b.base)) == (9409.09, 8119.1)
    rows = {m.month: (m.status, None if m.counted is None else float(m.counted)) for m in b.months}
    assert rows["2026-03"] == ("skipped", None)
    assert rows["2026-04"] == ("topped-up", 8800.0)
    assert rows["2026-05"] == ("topped-up", 8400.0)
    assert (pay(t, "maternity").daily, pay(t, "maternity").total) == (270.64, 37889.6)
    text = note(t, "base-mother")
    assert "Miesiące przepracowane w całości (9): razem 72 000,00 zł." in text
    assert "Marzec 2026: przepracowane 8 z 21 dni, mniej niż połowa" in text
    assert "4 400,00 zł / 11 × 22 = 8 800,00 zł" in text
    assert (
        "6 000,00 zł stałego wynagrodzenia z umowy + 1 400,00 zł zmiennego / 14 × 21 + "
        "300,00 zł bez uzupełniania = 8 400,00 zł" in text
    )
    assert "89 200,00 zł / 11 = 8 109,09 zł" in text
    assert "6 000,00 zł; do podstawy wchodzi jedna dwunasta, 500,00 zł" in text
    assert "9 600,00 zł; do podstawy wchodzi jedna dwunasta, 800,00 zł" in text
    assert "Razem 9 409,09 zł pomniejszone o 13,71%" in text
    assert articles(b) >= {"art. 38 ust. 2", "art. 42 ust. 2", "art. 42 ust. 3"}
    assert "(z 11 miesięcy, z premiami)" in b.summary


def test_insured_for_a_shorter_time() -> None:
    """Insured from 15.03.2026: the first full calendar month is April 2026, so April–October
    2026, 7 months: 7 × 7000 / 7 = 7000; 7000 × 0,8629 = 6040,30 zł. March 2026 is before the
    first full month: not counted."""
    history = {
        "insured_from": "2026-03-15",
        "full_time": True,  # above the minimum: nothing changes
        "months": [{"month": "2026-03", "amount": 3500}, *months("2026-04", 7, 7000)],
    }
    b = base(timeline(mother_pay_history=history))
    assert (b.months_from, b.base) == ("2026-04", Decimal("6040.3"))
    assert b.months[0].status == "before-insurance"
    assert "Ubezpieczenie trwa od 15.03.2026, więc liczą się pełne miesiące" in b.steps[0].text
    assert "od kwietnia 2026 do października 2026 (7 miesięcy)" in b.steps[0].text
    assert articles(b) >= {"art. 36 ust. 2", "art. 36 ust. 4"}


def test_every_month_worked_less_than_half_counts_topped_up() -> None:
    """Insured from 01.08.2026: August–October 2026, each 5 of 21 days for 2000 zł. Every month
    is under half, so all count, topped up (art. 38 ust. 3): 2000 / 5 × 21 = 8400 each;
    8400 × 0,8629 = 7248,36 zł."""
    short = [
        {"month": m, "amount": 2000, "days_required": 21, "days_worked": 5}
        for m in ("2026-08", "2026-09", "2026-10")
    ]
    b = base(timeline(mother_pay_history={"months": short, "insured_from": "2026-08-01"}))
    assert b.base == Decimal("7248.36")
    assert {m.status for m in b.months} == {"topped-up"}
    assert "W każdym miesiącu przepracowano mniej niż połowę" in b.steps[1].text
    assert "art. 38 ust. 3" in articles(b)


def test_the_first_month_of_work() -> None:
    """Insured from 02.11.2026, the right on 10.11.2026: no full calendar month yet, so the pay
    in the contract (art. 37): 6000 × 0,8629 = 5177,40 zł. Without it, November's pay topped up
    by days: 1600 / 4 × 20 = 8000; 8000 × 0,8629 = 6903,20 zł."""
    b = base(timeline(mother_pay_history={"insured_from": "2026-11-02", "contract_pay": 6000}))
    assert (b.months_from, b.months_to, b.base) == (None, None, Decimal("5177.4"))
    assert "przed upływem pełnego miesiąca kalendarzowego ubezpieczenia (od 02.11.2026)" in (
        b.steps[0].text
    )
    assert "art. 37 ust. 1" in articles(b)
    first = [{"month": "2026-11", "amount": 1600, "days_required": 20, "days_worked": 4}]
    b = base(timeline(mother_pay_history={"insured_from": "2026-11-02", "months": first}))
    assert b.base == Decimal("6903.2")
    assert "1 600,00 zł / 4 × 20 = 8 000,00 zł" in b.steps[0].text
    # Insured long before: the pay in the contract alone is not the base; a warning says so.
    t = timeline(mother_pay_history={"insured_from": "2024-01-01", "contract_pay": 6000})
    assert (t.bases, t.payments) == ([], [])
    assert any("wynagrodzenie z umowy liczy się tylko wtedy" in w for w in t.warnings)
    # An insurance that begins after the right: a warning, no amounts.
    t = timeline(mother_pay=8000, mother_pay_history={"insured_from": "2026-12-01"})
    assert any("początek ubezpieczenia (01.12.2026) wypada po dniu" in w for w in t.warnings)


def test_the_minimum_base_of_full_time_work() -> None:
    """4000 × 0,8629 = 3451,60 zł; full time: not lower than 4806 × 0,8629 = 4147,10 zł
    (art. 45 ust. 1, the minimum wage from the Załącznik). Maternity: a day 4147,10 / 30 =
    138,24; 140 × 138,24 = 19 353,60 zł."""
    t = timeline(mother_pay=4000, mother_pay_history={"full_time": True})
    b = base(t)
    assert (b.base, b.detailed) == (Decimal("4147.1"), False)
    assert (pay(t, "maternity").daily, pay(t, "maternity").total) == (138.24, 19353.6)
    assert "czyli 3 451,60 zł; przy pełnym etacie podstawa nie może być niższa" in b.summary
    assert {"art. 45 ust. 1"} <= articles(b)
    # Not known whether full time: the amount stays, a step says what full time would change.
    b = base(timeline(mother_pay=4000))
    assert b.base == Decimal("3451.6")
    assert b.steps[-1].text.startswith("Jeśli to praca w pełnym wymiarze czasu pracy")
    # Part time: no minimum (art. 45 ust. 1 is about full-time work).
    b = base(timeline(mother_pay=4000, mother_pay_history={"full_time": False}))
    assert (b.base, len(b.steps)) == (Decimal("3451.6"), 2)


def test_the_cap_of_a_non_employees_contribution_base() -> None:
    """Business, 12 × 25 000: each month counts up to 23 550,00 zł (Załącznik), so 23 550 ×
    0,8629 = 20 321,295 → 20 321,30 zł, the Załącznik's limit of the base."""
    t = timeline(
        work="business",
        mother_insured=True,
        mother_pay_history={"months": months("2025-11", 12, 25000)},
    )
    b = base(t)
    assert b.base == Decimal("20321.3")
    assert {float(m.counted or 0) for m in b.months} == {23550.0}
    assert b.steps[1].text.startswith(
        "Podstawa składki na dobrowolne ubezpieczenie chorobowe nie może przekraczać 23 550,00 zł"
    )
    assert "najwyżej 23 550,00 zł" in b.summary
    # The amount alone, too.
    simple = base(timeline(work="contract", mother_insured=True, mother_pay=30000))
    assert simple.base == Decimal("20321.3")
    # The cap is the 2026 one, applied to November and December 2025 as well: an assumption.
    assert any(
        "najwyżej 23 550,00 zł miesięcznie (Załącznik ZUS). To granica na 2026 rok; stosujemy "
        "ją do każdego miesiąca, z którego liczy się podstawa, także z 2025 roku" in a
        for a in t.assumptions
    )


def test_the_assumptions_take_their_numbers_from_the_parameters() -> None:
    """13,71% and the cap come from params/2026.json: changed there (a version from the admin
    panel), the assumptions say the new numbers."""
    changed = PARAMS.model_copy(deep=True)
    changed.money.contributions_percent.value = 14.0
    changed.benefit_base.voluntary_cap.value = 24000
    for answers, text in (
        ({"mother_pay": 8000}, "Od wynagrodzenia brutto pracownika odejmujemy 14%"),
        (
            {"work": "contract", "mother_insured": True, "mother_pay": 8000},
            "najwyżej 24 000,00 zł miesięcznie",
        ),
    ):
        t = build_timeline(Scenario.model_validate(BORN | answers), changed, TODAY)
        assert any(text in a for a in t.assumptions), text


def test_a_change_of_working_time_is_an_assumption_of_the_months_given() -> None:
    """Art. 40 (through art. 47) and the ZUS Poradnik's exception to art. 43: not counted, said
    only with the months of pay (an employee)."""
    detailed = timeline(mother_pay_history={"months": months("2025-11", 12, 8000)})
    assumption = next(a for a in detailed.assumptions if "wymiar czasu pracy" in a)
    assert "art. 40 ustawy zasiłkowej, przez art. 47" in assumption
    assert "Poradnik ZUS 2026" in assumption
    simple = timeline(mother_pay=8000)
    assert not any("wymiar czasu pracy się nie zmieniał" in a for a in simple.assumptions)


def test_a_non_employees_month_of_activity_in_part() -> None:
    """Contract: November 2025, 10 of 30 days (less than half): left out; December 2025, 15 of
    30 days (half): counted as given, not topped up (art. 50 ust. 1); January–October 2026:
    10 × 5000. (2500 + 50 000) / 11 = 4772,73; 4772,73 × 0,8629 = 4118,39 zł."""
    history = {
        "months": [
            {"month": "2025-11", "amount": 2000, "days_required": 30, "days_worked": 10},
            {"month": "2025-12", "amount": 2500, "days_required": 30, "days_worked": 15},
            *months("2026-01", 10, 5000),
        ]
    }
    b = base(timeline(work="contract", mother_insured=True, mother_pay_history=history))
    assert b.base == Decimal("4118.39")
    assert [m.status for m in b.months[:2]] == ["skipped", "full"]
    assert {"art. 50 ust. 1", "art. 48 ust. 2", "art. 3 pkt 4"} <= articles(b)
    assert "art. 3 pkt 3" not in articles(b)


SICK_YEAR = months("2025-06", 5, 6000) + months("2025-11", 7, 8000)
SICK_MONTHS = [
    {"month": m, "amount": 0, "days_required": 21, "days_worked": 0}
    for m in ("2026-06", "2026-07", "2026-08", "2026-09", "2026-10")
]


def test_sick_leave_in_pregnancy_straight_into_maternity_keeps_its_base() -> None:
    """Sick leave from 01.06.2026 until the birth on 10.11.2026: no break, so the base is not set
    anew (art. 43): the 12 months before June 2026. June–October 2025: 5 × 6000 = 30 000;
    November 2025–May 2026: 7 × 8000 = 56 000. 86 000 / 12 = 7166,67; × 0,8629 = 6184,12 zł.
    A new base from the 12 months before November 2026 would leave out the five months of sick
    leave: 7 × 8000 / 7 = 8000 → 6903,20 zł."""
    sick = {"sick_leave": True, "sick_leave_start": "2026-06-01"}
    history = {"months": SICK_YEAR + SICK_MONTHS}
    b = base(timeline(**sick, mother_pay_history=history))
    assert (b.right_from, b.months_from, b.months_to) == (dt.date(2026, 6, 1), "2025-06", "2026-05")
    assert b.base == Decimal("6184.12")
    assert b.steps[0].text.startswith(
        "Zasiłek od 10.11.2026 następuje po zwolnieniu lekarskim w ciąży, które zaczęło się "
        "01.06.2026, bez przerwy albo po przerwie krótszej niż miesiąc kalendarzowy"
    )
    assert {"art. 43"} <= articles(b)
    assert any(s.doc == "kp" and s.article == "art. 92 § 2" for s in b.sources)
    # Without the sick leave: a new base, the sick months left out.
    assert base(timeline(mother_pay_history=history)).base == Decimal("6903.2")
    # Sick leave until 31.08.2026: a break from 01.09 longer than a month, a new base.
    ended = base(timeline(**sick, sick_leave_end="2026-08-31", mother_pay_history=history))
    assert (ended.right_from, ended.base) == (dt.date(2026, 11, 10), Decimal("6903.2"))
    # Until 15.10.2026: the break 16.10–09.11 is shorter than a month (16.10 + 1 month = 16.11).
    close = base(timeline(**sick, sick_leave_end="2026-10-15", mother_pay_history=history))
    assert close.right_from == dt.date(2026, 6, 1)


def test_a_month_later() -> None:
    assert month_later(dt.date(2026, 10, 16)) == dt.date(2026, 11, 16)
    assert month_later(dt.date(2026, 1, 31)) == dt.date(2026, 2, 28)
    assert month_later(dt.date(2026, 12, 15)) == dt.date(2027, 1, 15)


def test_a_business_insured_for_a_shorter_time_has_no_amounts() -> None:
    """Art. 48a needs the lowest contribution base, which is not in the materials: no amounts
    for the mother, a warning says why; the father's stay."""
    t = timeline(
        work="business",
        mother_insured=True,
        mother_pay=5000,
        mother_pay_history={"insured_from": "2026-05-01"},
        father_work="employment",
        father_pay=6000,
    )
    assert {p.lane for p in t.payments} == {"father"}
    assert [b.parent for b in t.bases] == ["father"]
    assert any(
        w.startswith("Kwot zasiłku mamy nie liczymy: ubezpieczenie chorobowe z własnej firmy")
        and "art. 48a" in w
        for w in t.warnings
    )


def test_an_expected_child_counts_the_months_given() -> None:
    """Due 15.03.2027, no leave before it: the 12 months are March 2026–February 2027. Of
    November 2025–October 2026 the last 8 count: 8 × 8000 / 8 = 8000 → 6903,20 zł; the 4 before
    March 2026 do not; November 2026–February 2027 are still to come."""
    scenario = {"role": "mother", "work": "employment", "children_count": 1, "child_born": False}
    scenario |= {
        "due_date": "2027-03-15",
        "mother_pay_history": {"months": months("2025-11", 12, 8000)},
    }
    t = build_timeline(Scenario.model_validate(scenario), PARAMS, TODAY)
    b = base(t)
    assert (b.months_from, b.months_to, b.base) == ("2026-03", "2027-02", Decimal("6903.2"))
    assert [m.status for m in b.months].count("outside") == 4
    assert (
        "Brakuje zarobków z miesięcy: listopad 2026, grudzień 2026, styczeń 2027, luty 2027."
        in b.steps[1].text
    )


def test_the_fathers_months() -> None:
    """The father's paternity leave from 21.11.2026 (the child born on 10.11.2026): his 12
    months are November 2025–October 2026; 12 × 6000 → 6000 × 0,8629 = 5177,40 zł; a day
    172,58; 14 × 172,58 = 2416,12 zł."""
    t = timeline(
        father_work="employment", father_pay_history={"months": months("2025-11", 12, 6000)}
    )
    b = base(t, "father")
    assert (b.right_from, b.base) == (dt.date(2026, 11, 21), Decimal("5177.4"))
    assert pay(t, "paternity").total == 2416.12
    assert "base-father" in [n.id for n in t.notes]
    # His parental leave comes a year later: a new base would be set; we keep this one.
    assert any("Między okresami zasiłku taty jest przerwa" in a for a in t.assumptions)


def test_the_simple_amount_keeps_its_two_steps() -> None:
    """The amount alone: the average of the months less 13,71%, no separate point."""
    t = timeline(mother_pay=8000)
    b = base(t)
    assert [s.text.split(":")[0] for s in b.steps] == [
        "Prawo do zasiłku powstaje 10.11.2026",
        "8 000,00 zł pomniejszone o 13,71% (składki na ubezpieczenia emerytalne, rentowe i "
        "chorobowe)",
    ]
    assert "base-mother" not in [n.id for n in t.notes]
    assert any("podaj zarobki z kolejnych miesięcy" in a for a in t.assumptions)


def test_months_alone_bring_the_amounts_and_end_the_question() -> None:
    """Months of pay instead of the monthly amount: the interview does not ask for it."""
    answers = BORN | {"hospital_care": False, "father_work": "none"}
    answers |= {"mother_payer_size": "over-20"}
    asked = {q.key for q in interview_questions(Scenario.model_validate(answers))}
    assert "mother-pay" in asked
    given = answers | {"mother_pay_history": {"months": months("2025-11", 12, 8000)}}
    scenario = Scenario.model_validate(given)
    assert "mother-pay" not in {q.key for q in interview_questions(scenario)}
    assert "rate-815" in {q.key for q in interview_questions(scenario)}
    assert build_timeline(scenario, PARAMS, TODAY).payments


def test_months_are_checked() -> None:
    with pytest.raises(ValidationError, match="Dni przepracowanych nie może być więcej"):
        PayMonth(month="2026-03", amount=1000, days_required=20, days_worked=21)
    with pytest.raises(ValidationError, match="podaj oba"):
        PayMonth(month="2026-03", amount=1000, days_worked=10)
    with pytest.raises(ValidationError, match="tylko raz"):
        PayHistory(
            months=[PayMonth(month="2026-03", amount=1), PayMonth(month="2026-03", amount=2)]
        )
    with pytest.raises(ValidationError):
        PayMonth(month="2026-13", amount=1000)
    # Months are kept in calendar order.
    history = PayHistory(
        months=[PayMonth(month="2026-03", amount=1), PayMonth(month="2025-12", amount=2)]
    )
    assert [m.month for m in history.months] == ["2025-12", "2026-03"]


def test_the_calculator_endpoint_takes_the_months() -> None:
    """POST /api/timeline (no AI): a form can send the payer's certificate data."""
    app.dependency_overrides[get_today] = lambda: TODAY
    try:
        answers = BORN | {"mother_pay_history": {"months": months("2025-11", 12, 8000)}}
        response = TestClient(app).post("/api/timeline", json=answers)
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 200, response.text
    body = response.json()
    (b,) = body["bases"]
    assert (b["parent"], b["base"], b["pay"], b["months_from"]) == (
        "mother",
        6903.2,
        8000.0,
        "2025-11",
    )
    assert b["months"][0] == {
        "month": "2025-11",
        "amount": 8000.0,
        "counted": 8000.0,
        "status": "full",
    }
    assert b["steps"][0]["sources"]
    assert body["payments"][0]["base"] == 6903.2
