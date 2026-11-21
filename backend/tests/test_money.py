"""Guide section G (page 9): the amount of the maternity benefit. Expected amounts were computed
by hand (the arithmetic is in each docstring): base = pay × (100% − 13,71%) = pay × 0,8629,
rounded to the grosz; daily amount = base × rate / 30, rounded; total = daily × days.

The usual family: a child born on 10.11.2026, today 21.11.2026, no leave before the birth.
Maternity leave 10.11.2026–29.03.2027 (140 days), the mother's parental leave right after it
30.03.2027–08.11.2027 (224 days), paternity leave 21.11.2026–04.12.2026 (14 days), the father's
parental leave 09.11.2027–10.01.2028 (63 days).
"""

import datetime as dt
from decimal import Decimal

from app.engine import Scenario, Timeline, build_timeline, changed_element_ids
from app.engine.models import Payment
from app.engine.money import cents, percent, pln
from app.services.params import load_params

PARAMS = load_params()
TODAY = dt.date(2026, 11, 21)
BORN = dt.date(2026, 11, 10)
MOTHER = {"role": "mother", "work": "employment", "children_count": 1}


def born(**answers: object) -> Timeline:
    scenario = Scenario.model_validate(
        {**MOTHER, "child_born": True, "birth_date": BORN, "leave_before_birth_weeks": 0} | answers
    )
    return build_timeline(scenario, PARAMS, TODAY)


def pay(t: Timeline, segment_id: str) -> Payment:
    return next(p for p in t.payments if p.segment_id == segment_id)


def amounts(p: Payment) -> tuple[float, float, float, float, int]:
    return p.rate, p.monthly, p.daily, p.total, p.days


def note(t: Timeline, note_id: str) -> str:
    return next(n.text for n in t.notes if n.id == note_id)


def test_wording_of_amounts() -> None:
    assert pln(Decimal("1234567.5")) == "1 234 567,50 zł"
    assert pln(Decimal("0.005")) == "0,01 zł"  # half a grosz rounds up
    assert cents(Decimal("230.10666")) == Decimal("230.11")
    assert (percent(Decimal("100.0")), percent(Decimal("81.5"))) == ("100%", "81,5%")


def test_employee_gets_100_percent_for_maternity_and_70_for_parental_leave() -> None:
    """Base: 8000 × 0,8629 = 6903,20 zł.
    Maternity, 100%: 6903,20 a month; a day 6903,20 / 30 = 230,1067 → 230,11; 140 days ×
    230,11 = 32 215,40 zł.
    Parental, 70%: 6903,20 × 0,7 = 4832,24 a month; a day 4832,24 / 30 = 161,0747 → 161,07;
    224 days × 161,07 = 36 079,68 zł."""
    t = born(mother_pay=8000)
    maternity, parental = pay(t, "maternity"), pay(t, "parental")
    assert (maternity.id, maternity.lane, maternity.base) == ("pay-maternity", "mother", 6903.2)
    assert (maternity.start, maternity.end) == (BORN, dt.date(2027, 3, 29))
    assert amounts(maternity) == (100, 6903.2, 230.11, 32215.4, 140)
    assert (parental.start, parental.end) == (dt.date(2027, 3, 30), dt.date(2027, 11, 8))
    assert amounts(parental) == (70, 4832.24, 161.07, 36079.68, 224)
    assert maternity.summary == (
        "100% podstawy: 6 903,20 zł miesięcznie. Za 140 dni razem 32 215,40 zł."
    )
    assert maternity.details[0] == (
        "Podstawa wymiaru zasiłku: 8 000,00 zł wynagrodzenia brutto pomniejszone o 13,71%, "
        "czyli 6 903,20 zł miesięcznie."
    )
    assert "140 dni × 230,11 zł = 32 215,40 zł" in maternity.details[2]
    assert {s.article for s in maternity.sources if s.doc == "ustawa"} >= {
        "art. 31 ust. 1",
        "art. 3 pkt 3",
        "art. 36 ust. 1",
        "art. 36 ust. 3",
        "art. 11 ust. 4",
    }
    assert any(s.section == "G.1" for s in maternity.sources)
    assert any(s.section == "G.2" for s in parental.sources)
    assert "To okres do wyboru" in parental.details[-1]
    # The father's amount is not known: nothing on his periods.
    assert {p.lane for p in t.payments} == {"mother"}


def test_the_onboarding_range_alone_gives_no_amounts() -> None:
    t = born(earnings="8k-12k")
    assert t.payments == []
    assert "rate-815" not in [n.id for n in t.notes]
    assert "rate-815-deadline" not in [m.id for m in t.markers]


def test_the_choice_of_81_5_percent_has_a_deadline_21_days_after_the_birth() -> None:
    """10.11.2026 + 21 days = 01.12.2026. Both ways for the mother's 364 days (140 + 224):
    100% and 70%: 32 215,40 + 36 079,68 = 68 295,08 zł.
    81,5%: 6903,20 × 0,815 = 5626,108; a day 5626,108 / 30 = 187,5369 → 187,54;
    364 × 187,54 = 68 264,56 zł."""
    t = born(mother_pay=8000)
    deadline = t.element("rate-815-deadline")
    assert deadline is not None and deadline.date == dt.date(2026, 12, 1)  # type: ignore[union-attr]
    ids = [n.id for n in t.notes]
    assert ids.index("rate-815") < ids.index("computed") < ids.index("money")
    choice = next(n for n in t.notes if n.id == "rate-815")
    assert choice.kind == "choice"
    assert "najpóźniej 21 dni po porodzie (do 1 grudnia 2026)" in choice.text
    assert "(9 tygodni), zostaje przy 70%" in choice.text
    assert "razem 68 295,08 zł przy 100% i 70% albo 68 264,56 zł przy 81,5%" in choice.text
    assert {s.article for s in choice.sources if s.doc == "ustawa"} >= {
        "art. 30a ust. 1",
        "art. 31 ust. 3",
        "art. 31 ust. 3f",
        "art. 31 ust. 3g",
    }
    assert any("ostatni dzień na wniosek o 81,5% to 01.12.2026" in a for a in t.assumptions)


def test_81_5_percent_for_the_mother_while_the_fathers_own_weeks_stay_70() -> None:
    """Mother 8000 → daily 187,54 at 81,5%: maternity 140 × 187,54 = 26 255,60 zł, parental
    224 × 187,54 = 42 008,96 zł.
    Father 6000 → base 6000 × 0,8629 = 5177,40 zł. Paternity, 100%: a day 5177,40 / 30 =
    172,58; 14 × 172,58 = 2416,12 zł. His parental leave, 70%: 3624,18 a month; a day
    3624,18 / 30 = 120,806 → 120,81; 63 × 120,81 = 7611,03 zł."""
    t = born(mother_pay=8000, father_work="employment", father_pay=6000, rate_815=True)
    assert amounts(pay(t, "maternity")) == (81.5, 5626.11, 187.54, 26255.6, 140)
    assert amounts(pay(t, "parental")) == (81.5, 5626.11, 187.54, 42008.96, 224)
    paternity, his = pay(t, "paternity"), pay(t, "parental-father")
    assert (paternity.lane, paternity.base) == ("father", 5177.4)
    assert amounts(paternity) == (100, 5177.4, 172.58, 2416.12, 14)
    assert amounts(his) == (70, 3624.18, 120.81, 7611.03, 63)
    assert any("zostaje przy 70%" in d for d in his.details)
    assert any(s.article == "art. 31 ust. 3f" for s in his.sources)
    assert "Mama wybiera 81,5%: wniosek trzeba złożyć do 1 grudnia 2026." in note(t, "rate-815")
    money = note(t, "money")
    assert money.startswith("Mama — podstawa wymiaru zasiłku: 8 000,00 zł")
    assert "Tata — podstawa wymiaru zasiłku: 6 000,00 zł" in money
    assert "Urlop ojcowski — 100%: 5 177,40 zł miesięcznie, za 14 dni 2 416,12 zł" in money


def test_100_and_70_percent_chosen_hides_the_deadline() -> None:
    t = born(mother_pay=8000, rate_815=False)
    assert "rate-815-deadline" not in [m.id for m in t.markers]
    assert "Mama wybiera 100% i 70%." in note(t, "rate-815")
    assert "pierwszym roku życia" not in note(t, "rate-815")
    assert pay(t, "maternity").rate == 100


def test_non_employee_base_is_the_contribution_base_less_13_71_percent() -> None:
    """Contract with the voluntary insurance, contribution base 5000: 5000 × 0,8629 = 4314,50 zł.
    Maternity: a day 4314,50 / 30 = 143,8167 → 143,82; 140 × 143,82 = 20 134,80 zł."""
    t = born(work="contract", mother_insured=True, mother_pay=5000)
    maternity = pay(t, "maternity")
    assert amounts(maternity) == (100, 4314.5, 143.82, 20134.8, 140)
    assert "5 000,00 zł podstawy składki na ubezpieczenie chorobowe" in maternity.details[0]
    assert any(s.article == "art. 3 pkt 4" for s in maternity.sources)
    assert any(s.article == "art. 48 ust. 1" for s in maternity.sources)
    assert not any(s.article == "art. 3 pkt 3" for s in maternity.sources)
    assert any("Górnej granicy tej podstawy" in a for a in t.assumptions)


def test_expected_child_with_leave_before_the_birth() -> None:
    """Due 15.03.2027, 2 weeks before it: 01.03–14.03.2027, 14 days × 230,11 = 3221,54 zł;
    the rest of 20 weeks after the birth: 15.03–18.07.2027, 126 days × 230,11 = 28 993,86 zł.
    The request deadline counts from the due date: 15.03.2027 + 21 days = 05.04.2027."""
    scenario = Scenario.model_validate(
        {**MOTHER, "child_born": False, "due_date": "2027-03-15", "leave_before_birth_weeks": 2}
        | {"has_medical_certificate": True, "mother_pay": 8000}
    )
    t = build_timeline(scenario, PARAMS, TODAY)
    before = pay(t, "maternity-prenatal")
    assert (before.start, before.end, before.total) == (
        dt.date(2027, 3, 1),
        dt.date(2027, 3, 14),
        3221.54,
    )
    assert amounts(pay(t, "maternity")) == (100, 6903.2, 230.11, 28993.86, 126)
    assert "Liczymy od przewidywanej daty porodu." in before.details
    assert t.element("rate-815-deadline").date == dt.date(2027, 4, 5)  # type: ignore[union-attr]


def test_after_the_deadline_the_rates_are_100_and_70() -> None:
    """Born 01.10.2026: the request was due by 22.10.2026, before today."""
    t = born(birth_date="2026-10-01", mother_pay=8000)
    assert "Termin na wniosek minął 22 października 2026, więc liczymy 100% i 70%." in note(
        t, "rate-815"
    )
    assert pay(t, "maternity").rate == 100 and pay(t, "parental").rate == 70


def test_supplementary_leave_stays_at_100_percent_with_81_5() -> None:
    """Born 01.10.2026 in week 28-37, in hospital 01.10–20.10.2026 (20 days → 3 weeks):
    supplementary leave 21 days at 100%: a day 230,11; 21 × 230,11 = 4832,31 zł."""
    t = born(
        birth_date="2026-10-01",
        mother_pay=8000,
        rate_815=True,
        hospital_care=True,
        birth_week="28-37",
        birth_weight_up_to_1000g=False,
        hospital_stays=[{"start": "2026-10-01", "end": "2026-10-20"}],
    )
    supplementary = pay(t, "supplementary")
    assert amounts(supplementary) == (100, 6903.2, 230.11, 4832.31, 21)
    assert any(
        "uzupełniający urlop macierzyński zostaje przy 100%" in d for d in supplementary.details
    )
    assert pay(t, "maternity").rate == 81.5


def test_uninsured_mother_has_no_amounts_the_father_has_his() -> None:
    """Father with his own business, contribution base 5000 → 4314,50 zł; paternity 14 days:
    a day 143,82; 14 × 143,82 = 2013,48 zł."""
    t = born(work="none", mother_pay=8000, father_work="business", father_pay=5000)
    assert {p.lane for p in t.payments} == {"father"}
    assert amounts(pay(t, "paternity")) == (100, 4314.5, 143.82, 2013.48, 14)
    assert "rate-815" not in [n.id for n in t.notes]
    assert note(t, "money").startswith("Tata — podstawa wymiaru zasiłku")


def test_unknown_amount_keeps_the_choice_without_amounts() -> None:
    t = born(mother_pay="unknown")
    assert t.payments == []
    assert "money" not in [n.id for n in t.notes]
    assert "rate-815" in [n.id for n in t.notes]
    assert "pokazany na osi" not in note(t, "rate-815")


def test_father_taking_over_gets_100_percent_of_his_base() -> None:
    """Our reading: 81,5% follows the mother's request, so the father who takes over maternity
    leave after 14 weeks gets 100% of his own base. Father 6000 → 5177,40; a day 172,58."""
    t = born(
        mother_pay=8000,
        rate_815=True,
        father_takes_over=True,
        father_work="employment",
        father_pay=6000,
    )
    his = pay(t, "maternity-father")
    assert (his.lane, his.rate, his.daily) == ("father", 100, 172.58)
    assert pay(t, "maternity").rate == 81.5
    assert any("czy 81,5% obejmuje też jego część" in a for a in t.assumptions)


def test_without_money_answers_nothing_changes() -> None:
    """Earlier phases' timelines stay as they were until the interview reaches section G."""
    t = born()
    assert t.payments == []
    assert [n.id for n in t.notes][-1] == "computed"
    assert not any("13,71%" in a for a in t.assumptions)


def test_a_new_amount_highlights_the_payments() -> None:
    before, after = born(mother_pay=8000), born(mother_pay=9000)
    changed = changed_element_ids(before, after)
    assert {"pay-maternity", "pay-parental"} <= set(changed)
    assert "maternity" not in changed
