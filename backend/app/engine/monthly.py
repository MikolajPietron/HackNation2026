"""F4 "Ile wpływa w którym miesiącu i kto płaci" (ZADANIA B.12): the payments of the timeline
(money.py) split into calendar months, who pays each parent in every month, and the totals.

Applied on the finished timeline after money.py, for a birth and for a child taken in alike:
- every calendar month from the month of the first paid day to the month of the last one is
  listed; a month without a paid day stays at 0 (a gap: work between sick leave and maternity
  leave, a break between parts of parental leave);
- a payment's amount in a month is its daily amount, already rounded to the grosz by money.py,
  times its days in that month. So the months of a payment add up to its `total` exactly, and
  all the months to the sum of the payments (`Timeline.money_total`): nothing is rounded here.
  The one-off top-up of the benefit for maternity leave to 100% (ustawa art. 31 ust. 4) is all
  in the month of its day, the child's first birthday (money.py; our reading);
- who pays, by the rules the periods already state (applications.py, pregnancy.py): the employer
  pays its own sick pay in pregnancy; the sickness benefit for the days the mother still works
  and every benefit after the birth are paid by the payer of contributions that reports more
  than 20 people to sickness insurance, otherwise by ZUS, with a business by ZUS (guide page 1,
  footnote 1); the benefits for the time after the insurance ended (the sickness benefit after
  it, the benefit equal to the maternity benefit, the maternity benefit after losing the job in
  pregnancy) by ZUS (ustawa art. 61 ust. 1 pkt 2 lit. d). A month that mixes payers has a line
  for each payer of each parent.

Our readings, not settled by the materials (CLAUDE.md, open questions):
- a month shows the money for its days, not the day it reaches the account: when the payer or
  ZUS pays it out is not counted;
- who pays the rehabilitation benefit the materials do not say (art. 61 ust. 1 names the
  zasiłki, and art. 22 does not apply it to the rehabilitation benefit): its line has no payer.
"""

import datetime as dt
from collections.abc import Iterable
from decimal import Decimal

from app.engine.amounts import dec
from app.engine.applications import payer_by_size, who_pays
from app.engine.draft import DAY
from app.engine.models import (
    MoneyTotal,
    MonthlyLine,
    MonthlyPayment,
    PaidBy,
    Payment,
    Role,
    Scenario,
    Timeline,
)
from app.engine.money import WHOSE, paid_for
from app.engine.pregnancy import SEGMENT_IDS

PARENTS: tuple[Role, ...] = ("mother", "father")
AFTER_INSURANCE = SEGMENT_IDS["after"]
NO_PAYER = "Materiały nie mówią, kto wypłaca"
ASSUMPTION = (
    "Miesiąc po miesiącu pokazujemy kwotę za dni danego miesiąca (kwota za dzień razy liczba dni "
    "w tym miesiącu), a nie dzień, w którym pieniądze wpłyną na konto: terminów wypłaty nie "
    "liczymy."
)
REHAB_ASSUMPTION = (
    "Kto wypłaca świadczenie rehabilitacyjne, materiały nie mówią, więc w zestawieniu miesięcznym "
    "nie podajemy płatnika."
)


def add_monthly(timeline: Timeline, scenario: Scenario) -> None:
    """`Timeline.monthly` and `Timeline.money_total` from the finished payments."""
    timeline.monthly = monthly(timeline.payments, scenario)
    timeline.money_total = money_total(timeline.payments)
    if timeline.monthly:
        timeline.assumptions.append(ASSUMPTION)
    if any(payer_of(p, scenario) is None for p in timeline.payments):
        timeline.assumptions.append(REHAB_ASSUMPTION)


def money_total(payments: list[Payment]) -> MoneyTotal | None:
    if not payments:
        return None
    return MoneyTotal(
        total=_sum(payments),
        mother=_sum(p for p in payments if p.lane == "mother"),
        father=_sum(p for p in payments if p.lane == "father"),
    )


def monthly(payments: list[Payment], scenario: Scenario) -> list[MonthlyPayment]:
    if not payments:
        return []
    ordered = sorted(payments, key=lambda p: (p.start, PARENTS.index(p.lane)))
    first = min(p.start for p in payments)
    last = max(p.end for p in payments)
    return [_month(start, end, ordered, scenario) for start, end in months(first, last)]


def months(first: dt.date, last: dt.date) -> list[tuple[dt.date, dt.date]]:
    """Every calendar month from the month of `first` to the month of `last`: its first and its
    last day."""
    found = []
    start = first.replace(day=1)
    while start <= last:
        following = (start.replace(day=28) + 4 * DAY).replace(day=1)
        found.append((start, following - DAY))
        start = following
    return found


def days_in(payment: Payment, start: dt.date, end: dt.date) -> int:
    """The payment's days from `start` to `end`, both inclusive."""
    return max(0, (min(payment.end, end) - max(payment.start, start)).days + 1)


def amount_in(payment: Payment, start: dt.date, end: dt.date) -> Decimal:
    """The payment's money for the days from `start` to `end`; a one-off payment (the top-up to
    100%) all of it in the month of its day."""
    if payment.one_off:
        return dec(payment.total) if start <= payment.start <= end else Decimal("0.00")
    return dec(payment.daily) * days_in(payment, start, end)


def _month(
    start: dt.date, end: dt.date, ordered: list[Payment], scenario: Scenario
) -> MonthlyPayment:
    here = [(p, days) for p in ordered if (days := days_in(p, start, end)) > 0]
    lines: dict[tuple[Role, PaidBy | None], MonthlyLine] = {}
    for payment, _ in sorted(here, key=lambda found: PARENTS.index(found[0].lane)):
        payer = payer_of(payment, scenario)
        line = lines.setdefault(
            (payment.lane, payer),
            MonthlyLine(
                parent=payment.lane,
                payer=payer,
                payer_label=payer_label(payer, payment.lane, scenario),
                amount=Decimal("0.00"),
                payment_ids=[],
            ),
        )
        line.amount += amount_in(payment, start, end)
        line.payment_ids.append(payment.id)
    found = list(lines.values())
    mother, father = (
        sum((line.amount for line in found if line.parent == parent), Decimal("0.00"))
        for parent in PARENTS
    )
    return MonthlyPayment(
        month=f"{start:%Y-%m}",
        mother=mother,
        father=father,
        total=mother + father,
        lines=found,
        payment_ids=[p.id for p, _ in here],
    )


def payer_of(payment: Payment, scenario: Scenario) -> PaidBy | None:
    """Who pays out one payment (the module docstring); None = the materials do not say."""
    paid = paid_for(payment.segment_id)
    kind = paid.kind if paid is not None else None
    if kind == "sick-pay":
        return "employer"
    if kind == "rehab":
        return None
    if kind == "job-loss" or payment.segment_id.startswith(AFTER_INSURANCE):
        return "zus"
    if kind == "sick-benefit":
        return payer_by_size(scenario, "mother")
    return who_pays(scenario, payment.lane)


def payer_label(payer: PaidBy | None, parent: Role, scenario: Scenario) -> str:
    whose = WHOSE[parent]
    work = scenario.mothers_work if parent == "mother" else scenario.fathers_work
    own = f"{'Pracodawca' if work == 'employment' else 'Zleceniodawca'} {whose}"
    match payer:
        case "employer":
            return f"Pracodawca {whose} (wynagrodzenie chorobowe)"
        case "payer":
            return own
        case "payer-or-zus":
            return f"{own} albo ZUS"
        case "zus":
            return "ZUS"
        case _:
            return NO_PAYER


def _sum(payments: Iterable[Payment]) -> Decimal:
    return sum((dec(p.total) for p in payments), Decimal("0.00"))
