"""Contribution debt of a parent who runs a business: ustawa zasiłkowa art. 2a and art. 64 ust. 3.

The challenge asks to show "danych o stanie zadłużenia z tytułu składek na ubezpieczenia
społeczne na dzień powstania prawa do świadczenia" (guide page 13). The rule behind it: the
benefits of the ustawa, the maternity benefit among them (art. 2 pkt 5), are not due to a person
running a business (or working with one) whose debt of social insurance contributions on the day
the right arises exceeds 1% of the minimum wage, until the whole debt is repaid (art. 2a ust. 1);
not repaid within 6 months of that day, the right expires (art. 2a ust. 2); once repaid, the
benefit is paid within 60 days (art. 64 ust. 3).

The interview does not ask about it: the amount comes from an example case (`app/cases`), as a
ZUS document states it (`Scenario.mother_contribution_debt`, `father_contribution_debt`). The
timeline stays as it is (it is what is due after the repayment); the case explanation gets a
point that says what the debt means.

Our readings, not settled by the materials (CLAUDE.md, open questions):
- the limit is counted from the minimum wage in the parameters (2026), also for a right that
  arose in an earlier year;
- "6 miesięcy od dnia powstania prawa": to the same day 6 months later (the last day of a
  shorter month).
"""

import calendar
import datetime as dt
from decimal import Decimal
from typing import Literal

from app.engine.amounts import cents, dec, percent, pln
from app.engine.draft import merge_sources
from app.engine.models import CaseNote, Scenario, Timeline
from app.engine.params import Params

Parent = Literal["mother", "father"]


def debt_limit(params: Params) -> Decimal:
    """The debt above which no benefit is due: 1% of the minimum wage, to the grosz."""
    wage = dec(params.benefit_base.minimum_wage.value)
    return cents(wage * dec(params.contribution_debt.limit_percent.value) / 100)


def over_limit(amount: float, params: Params) -> bool:
    """ "na kwotę przekraczającą 1 % minimalnego wynagrodzenia": strictly more."""
    return dec(amount) > debt_limit(params)


def expiry(right_day: dt.date, params: Params) -> dt.date:
    """The last day to repay the debt before the right expires (art. 2a ust. 2)."""
    months = params.contribution_debt.expiry_months.value
    index = right_day.year * 12 + right_day.month - 1 + months
    year, month = index // 12, index % 12 + 1
    return dt.date(year, month, min(right_day.day, calendar.monthrange(year, month)[1]))


def debt_of(scenario: Scenario, parent: Parent) -> float | None:
    """The parent's contribution debt, when the rule applies: only to a parent with a business."""
    work = scenario.mothers_work if parent == "mother" else scenario.fathers_work
    amount = (
        scenario.mother_contribution_debt
        if parent == "mother"
        else scenario.father_contribution_debt
    )
    return amount if work == "business" else None


# The case explanation (explain.py).


def add_debt_notes(
    notes: list[CaseNote], scenario: Scenario, timeline: Timeline, params: Params
) -> list[CaseNote]:
    """The debt point of each parent right after that parent's right: the mother's after
    "insurance", the father's after "father" (or after "insurance" when there is none)."""
    for parent, after in (("mother", ("insurance",)), ("father", ("father", "insurance"))):
        note = _debt_note(scenario, parent, params)
        if note is None:
            continue
        at = next(
            (i + 1 for anchor in after for i, n in enumerate(notes) if n.id == anchor),
            1 if notes else 0,
        )
        notes = [*notes[:at], note, *notes[at:]]
    return notes


def _debt_note(scenario: Scenario, parent: Parent, params: Params) -> CaseNote | None:
    amount = debt_of(scenario, parent)
    if amount is None or amount == 0:
        return None
    p = params.contribution_debt
    limit = debt_limit(params)
    wage = params.benefit_base.minimum_wage
    share = percent(dec(p.limit_percent.value))
    who, whose = ("Mama", "mamy") if parent == "mother" else ("Tata", "taty")
    debt = (
        f"{who} prowadzi działalność gospodarczą. Zadłużenie z tytułu składek na ubezpieczenia "
        f"społeczne w dniu powstania prawa do świadczenia: {pln(dec(amount))}"
    )
    rule = f"{share} minimalnego wynagrodzenia ({pln(dec(wage.value))}), czyli {pln(limit)}"
    if not over_limit(amount, params):
        return CaseNote(
            id=f"debt-{parent}",
            kind="right",
            title=f"Zadłużenie składkowe {whose} nie wstrzymuje zasiłku",
            text=(
                f"{debt}. Zasiłek wstrzymuje dopiero zadłużenie większe niż {rule}, więc to "
                "zadłużenie zasiłku nie wstrzymuje."
            ),
            sources=merge_sources(p.rule.sources, p.limit_percent.sources, wage.sources),
        )
    return CaseNote(
        id=f"debt-{parent}",
        kind="risk",
        title=f"Zadłużenie składkowe {whose}: zasiłek dopiero po spłacie",
        text=(
            f"{debt}, więcej niż {rule}. Osobom prowadzącym działalność zasiłki, w tym zasiłek "
            "macierzyński, nie przysługują przy takim zadłużeniu do czasu spłaty całości "
            "zadłużenia. Po spłacie zasiłek wypłaca się "
            f"najpóźniej w ciągu {p.paid_within_days.value} dni. Jeśli zadłużenie nie zostanie "
            f"spłacone w ciągu {p.expiry_months.value} miesięcy od dnia powstania prawa, prawo do "
            "zasiłku przedawnia się."
        ),
        sources=merge_sources(
            p.rule.sources,
            p.limit_percent.sources,
            wage.sources,
            p.paid_within_days.sources,
            p.expiry_months.sources,
        ),
    )
