"""What two timelines of the same family differ in: entitlements, periods, money. Shared by the
stress test (stress.py, F11) and the plans for a goal (plans.py, F8).

Pure: it reads two finished timelines and states no rule of its own, so every claim the callers
make keeps the sources of the timelines' elements and notes.
"""

import datetime as dt
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel

from app.engine.amounts import dec, pln
from app.engine.models import Lane, Payment, Role, Segment, Timeline
from app.engine.wording import fmt

RightKind = Literal["maternity", "supplementary", "paternity", "parental", "job-loss", "sick"]
"""A kind of entitlement on the parents' lanes, whoever of them uses it."""

RIGHT_LABEL: dict[RightKind, str] = {
    "maternity": "urlop macierzyński",
    "supplementary": "uzupełniający urlop macierzyński",
    "paternity": "urlop ojcowski",
    "parental": "urlop rodzicielski",
    "job-loss": "zasiłek w wysokości zasiłku macierzyńskiego",
    "sick": "wynagrodzenie i zasiłek chorobowy w ciąży",
}
"""How a sentence names the kind, after "Dochodzi:" or "Przepada:"."""

MATERNITY_IDS = ("maternity-prenatal", "maternity", "maternity-resumed", "maternity-father")
PARENTAL_OPTIONS = ("parental", "parental-father")
"""Each parent's share of parental leave drawn as an option, while no plan decides it."""
LEAVE_KINDS: tuple[RightKind, ...] = ("maternity", "supplementary", "paternity", "parental")
"""The leave after the birth (and maternity leave before it): time at home with the child."""


def right_kind(segment_id: str) -> RightKind | None:
    """The kind of entitlement a period on the timeline stands for; None for periods that are
    not one (work until the birth, the window for leave before the birth)."""
    if segment_id in MATERNITY_IDS:
        return "maternity"
    if segment_id == "supplementary":
        return "supplementary"
    if segment_id == "paternity":
        return "paternity"
    if segment_id == "parental" or segment_id.startswith("parental-"):
        return "parental"
    if segment_id == "job-loss-benefit":
        return "job-loss"
    if segment_id.startswith(("sick-", "rehab-")):
        return "sick"
    return None


def parent_segments(timeline: Timeline) -> list[Segment]:
    return [s for s in timeline.segments if s.lane in ("mother", "father")]


def days_by_kind(timeline: Timeline) -> dict[RightKind, int]:
    """Days of every kind of entitlement on both parents' lanes, as the timeline draws them."""
    days: dict[RightKind, int] = {}
    for segment in parent_segments(timeline):
        kind = right_kind(segment.id)
        if kind is not None:
            days[kind] = days.get(kind, 0) + segment.days
    return days


class RightChange(BaseModel):
    """An entitlement the event (or the plan) adds, takes away, lengthens or shortens: days on
    both parents' lanes together."""

    kind: RightKind
    label: str
    days_before: int
    days_after: int


def right_changes(before: Timeline, after: Timeline) -> list[RightChange]:
    old, new = days_by_kind(before), days_by_kind(after)
    return [
        RightChange(
            kind=kind,
            label=RIGHT_LABEL[kind],
            days_before=old.get(kind, 0),
            days_after=new.get(kind, 0),
        )
        for kind in RIGHT_LABEL
        if old.get(kind, 0) != new.get(kind, 0)
    ]


class PeriodChange(BaseModel):
    """A period or a day on the timeline that appears, disappears or moves."""

    id: str
    element: Literal["segment", "marker"]
    lane: Lane
    title: str
    change: Literal["added", "removed", "moved"]
    start_before: dt.date | None = None
    end_before: dt.date | None = None
    """For a marker: None (its day is `start_before`)."""
    start_after: dt.date | None = None
    end_after: dt.date | None = None


def period_changes(before: Timeline, after: Timeline) -> list[PeriodChange]:
    """Periods of both parents and the days on the child's lane, in the order of the new
    timeline; what disappeared comes last."""
    changes: list[PeriodChange] = []
    old_segments = {s.id: s for s in before.segments}
    new_segments = {s.id: s for s in after.segments}
    for s in after.segments:
        o = old_segments.get(s.id)
        if o is None:
            changes.append(_segment_change(s, "added", None, s))
        elif (o.start, o.end) != (s.start, s.end):
            changes.append(_segment_change(s, "moved", o, s))
    old_markers = {m.id: m for m in before.markers}
    new_markers = {m.id: m for m in after.markers}
    for m in after.markers:
        o = old_markers.get(m.id)
        if o is None or o.date != m.date:
            changes.append(
                PeriodChange(
                    id=m.id,
                    element="marker",
                    lane=m.lane,
                    title=m.title,
                    change="added" if o is None else "moved",
                    start_before=None if o is None else o.date,
                    start_after=m.date,
                )
            )
    for s in before.segments:
        if s.id not in new_segments:
            changes.append(_segment_change(s, "removed", s, None))
    for m in before.markers:
        if m.id not in new_markers:
            changes.append(
                PeriodChange(
                    id=m.id,
                    element="marker",
                    lane=m.lane,
                    title=m.title,
                    change="removed",
                    start_before=m.date,
                )
            )
    return changes


def _segment_change(
    s: Segment,
    change: Literal["added", "removed", "moved"],
    old: Segment | None,
    new: Segment | None,
) -> PeriodChange:
    return PeriodChange(
        id=s.id,
        element="segment",
        lane=s.lane,
        title=s.title,
        change=change,
        start_before=old.start if old else None,
        end_before=old.end if old else None,
        start_after=new.start if new else None,
        end_after=new.end if new else None,
    )


class PaymentChange(BaseModel):
    """A payment that appears, disappears or changes: its monthly amount and its total."""

    id: str
    title: str
    lane: Role
    monthly_before: float | None = None
    monthly_after: float | None = None
    total_before: float | None = None
    total_after: float | None = None


class MoneyChange(BaseModel):
    """All the money on the timeline ("Pieniądze"), before and after, in PLN. A parent without
    an amount counts as 0 on both sides."""

    total_before: float
    total_after: float
    diff: float
    mother_before: float
    mother_after: float
    father_before: float
    father_after: float
    payments: list[PaymentChange] = []


def amounts_known(timeline: Timeline) -> bool:
    """The money lane has amounts: some parent's monthly amount (or months of pay) is known."""
    return bool(timeline.bases)


def total(payments: list[Payment], lane: Role | None = None) -> Decimal:
    return sum((dec(p.total) for p in payments if lane is None or p.lane == lane), Decimal(0))


def money_change(before: Timeline, after: Timeline) -> MoneyChange | None:
    """None when neither timeline has amounts."""
    if not amounts_known(before) and not amounts_known(after):
        return None
    old = {p.id: p for p in before.payments}
    new = {p.id: p for p in after.payments}
    changed = []
    for pid in [*new, *(i for i in old if i not in new)]:
        o, n = old.get(pid), new.get(pid)
        if o is not None and n is not None and _same(o, n):
            continue
        shown = n or o
        assert shown is not None
        changed.append(
            PaymentChange(
                id=pid,
                title=shown.title,
                lane=shown.lane,
                monthly_before=o.monthly if o else None,
                monthly_after=n.monthly if n else None,
                total_before=o.total if o else None,
                total_after=n.total if n else None,
            )
        )
    t_old, t_new = total(before.payments), total(after.payments)
    return MoneyChange(
        total_before=float(t_old),
        total_after=float(t_new),
        diff=float(t_new - t_old),
        mother_before=float(total(before.payments, "mother")),
        mother_after=float(total(after.payments, "mother")),
        father_before=float(total(before.payments, "father")),
        father_after=float(total(after.payments, "father")),
        payments=changed,
    )


def _same(a: Payment, b: Payment) -> bool:
    return (a.start, a.end, a.rate, a.monthly, a.total) == (
        b.start,
        b.end,
        b.rate,
        b.monthly,
        b.total,
    )


# Wording.


def weeks_text(days: int) -> str:
    """ "4 tyg." for whole weeks, else "38 dni"."""
    if days % 7 == 0:
        return f"{days // 7} tyg."
    return "1 dzień" if days == 1 else f"{days} dni"


def signed_pln(amount: Decimal) -> str:
    """ "+1 234,56 zł", "−1 234,56 zł"."""
    sign = "+" if amount >= 0 else "−"
    return sign + pln(abs(amount))


def sentence(text: str) -> str:
    """End with a full stop, once ("4 tyg." stays, "55 dni" gets one)."""
    return text if text.endswith(".") else text + "."


def right_line(change: RightChange) -> str:
    label = change.label[0].upper() + change.label[1:]
    if change.days_before == 0:
        return sentence(f"Dochodzi: {change.label} — {weeks_text(change.days_after)}")
    if change.days_after == 0:
        return f"Przepada: {change.label} ({weeks_text(change.days_before)})."
    longer = "dłużej" if change.days_after > change.days_before else "krócej"
    return (
        f"{label}: {weeks_text(change.days_after)} zamiast {weeks_text(change.days_before)} "
        f"({longer})."
    )


def _day(d: dt.date | None) -> str:
    return fmt(d) if d is not None else "—"


def period_line(change: PeriodChange) -> str:
    before = (
        _day(change.start_before)
        if change.element == "marker"
        else f"{_day(change.start_before)}–{_day(change.end_before)}"
    )
    after = (
        _day(change.start_after)
        if change.element == "marker"
        else f"{_day(change.start_after)}–{_day(change.end_after)}"
    )
    if change.change == "removed":
        return f"{change.title}: znika z osi (było {before})."
    if change.change == "added":
        return f"{change.title}: {after}."
    return f"{change.title}: {after} zamiast {before}."


def money_line(change: MoneyChange) -> str:
    diff = dec(change.diff)
    return (
        f"Pieniądze na osi razem: {pln(dec(change.total_after))} zamiast "
        f"{pln(dec(change.total_before))} ({signed_pln(diff)})."
    )
