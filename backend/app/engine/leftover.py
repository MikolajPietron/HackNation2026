"""F9 "Zostawiacie na stole" and F10 "Punkty bez powrotu" (FUNKCJE 4.2; ZADANIA B.8).

Read from the finished timeline (timeline.py calls `add_leftovers` before the case notes): the
dates and the money come from its markers, periods and payments, never computed twice.

F10. A marker whose day ends a right for good, as the sources say, gets `Marker.irreversible`:
what is lost, and the quotes that say so (from the marker's own sources):
- `rate-815-deadline`: the request for 81,5% is filed "nie później niż 21 dni po porodzie"
  (after taking the child in): ustawa art. 30a ust. 1-2, guide G.3;
- `paternity-deadline`: "Jeżeli po ww. okresach ojciec nie wykorzysta urlopu ojcowskiego, to
  prawo do tego urlopu wygasa" (guide B.4);
- `parental-deadline`: parental leave is granted "nie później niż do zakończenia roku
  kalendarzowego, w którym dziecko kończy 6 rok życia" (art. 182¹ᶜ; for a child taken in, the
  limit adoption.py gives the marker).
Not marked, because the materials do not say that a right is lost: the deadlines of the requests
for leave (applications.py: a late request moves the start of the leave), the start of the leave
on the terms of maternity leave "nie później niż 21 dni" after taking the child in (art. 183
§ 6); nor the days that end something without a decision (the 14 weeks, the 270 days of the
sickness benefit, the end of the protection).

F9. What the family can still use and loses if they do nothing, by its last day, with the money
once the parent's base is known (the payments money.py computed for those days):
- every leave the timeline shows as an option: the mother's and the father's parental leave
  (the 9 weeks only one parent can use said so), paternity leave, and supplementary leave, which
  is granted right after maternity leave, so only while that day is ahead;
- the weeks of the parental leave pool the parents' plan leaves out;
- the request for 81,5% while it can be filed, with what both ways pay (money.py).
Nothing after the loss of a child or the mother's death: the sensitive mode makes no proposals
(FUNKCJE, F27).

Our readings, not settled by the materials:
- an option may have started in the past (the timeline draws parental leave right after
  maternity leave); if the family has not used it, what is left is what still fits between
  today and its last day;
- the money for those days: the payments of that period in their order, as far as the days
  reach;
- the weeks a plan leaves out: the pool (both parents, or one parent's most when only one can
  take the leave) less the weeks planned and the options still shown, at most the days between
  the first day of parental leave (or today) and its last day.
"""

from decimal import Decimal

from app.engine.adoption import taker
from app.engine.amounts import cents, dec, pln
from app.engine.draft import DAY, days_between, merge_sources
from app.engine.models import (
    Irreversible,
    Leftover,
    Marker,
    Role,
    Scenario,
    Segment,
    SourceRef,
    Timeline,
)
from app.engine.money import DEADLINE_ID, LEAVE, rates, request, request_totals
from app.engine.params import Params
from app.engine.parental import parental_table, parental_weeks
from app.engine.wording import long_date, weeks_or_days

PATERNITY_DEADLINE = "paternity-deadline"
PARENTAL_DEADLINE = "parental-deadline"
OPTIONS = ("parental", "parental-father", "paternity", "supplementary")
"""The options on the timeline that are lost if they stay unused."""

WHO = {"mother": "mama", "father": "tata"}
WHOSE = {"mother": "mamy", "father": "taty"}
TO_THE_OTHER = {"mother": "tatę", "father": "mamę"}
"""After "przenieść na": the other parent."""


def add_leftovers(timeline: Timeline, scenario: Scenario, params: Params) -> None:
    """F10 on the markers, then F9."""
    timeline.markers = [_marked(m, timeline, scenario, params) for m in timeline.markers]
    timeline.left_on_table = left_on_table(timeline, scenario, params)


def _marker(timeline: Timeline, marker_id: str) -> Marker | None:
    return next((m for m in timeline.markers if m.id == marker_id), None)


# F10: points of no return.


def _marked(marker: Marker, timeline: Timeline, scenario: Scenario, params: Params) -> Marker:
    found = no_return(marker, timeline, scenario, params)
    return marker if found is None else marker.model_copy(update={"irreversible": found})


def no_return(
    marker: Marker, timeline: Timeline, scenario: Scenario, params: Params
) -> Irreversible | None:
    """What is lost after the marker's day, or None for a day after which nothing is lost."""
    f, t = params.father, params.taken_in
    match marker.id:
        case "rate-815-deadline":
            req = request(scenario, params, timeline.birth_date)
            _, _, single = rates(params)
            after = "przyjęciu dziecka na wychowanie" if req.taken_in else "porodzie"
            lost = (
                f"Wybór zasiłku {single} za cały {LEAVE[req.leave]} i rodzicielski: pisemny "
                f"wniosek składa się nie później niż {req.days.value} dni po {after}."
            )
            sources = req.days.sources
        case "paternity-deadline":
            lost = (
                "Urlop ojcowski: jeśli tata nie wykorzysta go do tego dnia, prawo do niego wygasa."
            )
            rule = merge_sources(
                f.paternity_months.sources,
                t.paternity_months.sources,
                t.paternity_age.sources,
                f.paternity_expires.sources,
            )
            sources = [s for s in marker.sources if s in rule]
        case "parental-deadline":
            lost = "Urlop rodzicielski: niewykorzystanego do tego dnia nie można już wziąć."
            sources = marker.sources
        case _:
            return None
    return Irreversible(
        lost=lost, days_left=(marker.date - timeline.today).days, sources=list(sources)
    )


# F9: what the family would leave on the table.


def left_on_table(timeline: Timeline, scenario: Scenario, params: Params) -> list[Leftover]:
    """What the family can still use and loses if they do nothing, the soonest first. Nothing
    after the loss of a child or the mother's death: no proposals then (FUNKCJE, F27)."""
    event = scenario.mother_event
    if scenario.losses or (event is not None and event.kind == "death"):
        return []
    # After the mother abandoned the child her lane ends (father.py): her options are not hers.
    gone = event is not None and event.kind == "abandonment"
    found = [
        _unused(s, timeline, scenario, params)
        for s in timeline.segments
        if s.id in OPTIONS and s.tone == "option" and not (gone and s.lane == "mother")
    ]
    found += [_pool(timeline, scenario, params), _rate_choice(timeline, scenario, params)]
    kept = [item for item in found if item is not None and item.last_day >= timeline.today]
    return sorted(kept, key=lambda item: item.last_day)


def _money(timeline: Timeline, segment_id: str, days: int) -> float | None:
    """The benefit for `days` days of the period: its payments in order, as far as they reach.
    None while the parent's base is not known."""
    paid = sorted(
        (p for p in timeline.payments if p.segment_id == segment_id), key=lambda p: p.start
    )
    if not paid:
        return None
    total, left = Decimal(0), days
    for payment in paid:
        used = min(payment.days, left)
        total += dec(payment.daily) * used
        left -= used
    return float(cents(total))


def _work_line(scenario: Scenario, parent: Role, params: Params) -> tuple[str, list[SourceRef]]:
    """A parent who is not an employee gets the benefit for that time, not leave."""
    work = scenario.mothers_work if parent == "mother" else scenario.fathers_work
    if work not in ("contract", "business"):
        return "", []
    return (
        f" {WHO[parent].capitalize()} nie jest pracowni{'cą' if parent == 'mother' else 'kiem'}, "
        "więc zamiast urlopu ma zasiłek macierzyński za ten okres.",
        params.benefit.non_employees.sources,
    )


def _unused(
    segment: Segment, timeline: Timeline, scenario: Scenario, params: Params
) -> Leftover | None:
    if segment.id == "supplementary":
        return _supplementary(segment, timeline, params)
    deadline = _marker(
        timeline, PATERNITY_DEADLINE if segment.id == "paternity" else PARENTAL_DEADLINE
    )
    if deadline is None:
        return None
    last = deadline.date
    days = min(segment.days, days_between(max(timeline.today, segment.start), last))
    if days <= 0:
        return None
    parent: Role = "father" if segment.lane == "father" else "mother"
    work, work_sources = _work_line(scenario, parent, params)
    if segment.id == "paternity":
        title = "Urlop ojcowski"
        text = (
            f"Tata może jeszcze wykorzystać {days} dni urlopu ojcowskiego, najpóźniej do "
            f"{long_date(last)}. Jeśli go nie wykorzysta, prawo do niego wygasa.{work}"
        )
    elif _only_theirs(segment, timeline, scenario, params):
        weeks = params.parental.exclusive_weeks.value
        title = f"Urlop rodzicielski {WHOSE[parent]}"
        rest = (
            f"{WHO[parent].capitalize()} może je wykorzystać najpóźniej do {long_date(last)}."
            if days == weeks * 7
            else f"{WHO[parent].capitalize()} może jeszcze wykorzystać {weeks_or_days(days)}, "
            f"najpóźniej do {long_date(last)}."
        )
        text = (
            f"{weeks} tyg. urlopu rodzicielskiego należy wyłącznie do {WHOSE[parent]}: nie można "
            f"ich przenieść na {TO_THE_OTHER[parent]}. {rest}{work}"
        )
    else:
        title = f"Urlop rodzicielski {WHOSE[parent]}"
        text = (
            f"{WHO[parent].capitalize()} może jeszcze wykorzystać {weeks_or_days(days)} urlopu "
            f"rodzicielskiego, najpóźniej do {long_date(last)}.{work}"
        )
    return Leftover(
        id=f"left-{segment.id}",
        kind="leave",
        parent=parent,
        title=title,
        text=text,
        days=days,
        amount=_money(timeline, segment.id, days),
        last_day=last,
        start_by=last - (days - 1) * DAY,
        segment_id=segment.id,
        marker_id=deadline.id,
        sources=merge_sources(deadline.sources, segment.sources, work_sources),
    )


def _only_theirs(segment: Segment, timeline: Timeline, scenario: Scenario, params: Params) -> bool:
    """The option is the 9 weeks that belong to this parent alone: no longer than them, the
    other parent has parental leave too, and this one is not the parent whose share is drawn
    first."""
    if segment.days > params.parental.exclusive_weeks.value * 7:
        return False
    other = "mother" if segment.lane == "father" else "father"
    if not any(s.lane == other and s.id.startswith("parental") for s in timeline.segments):
        return False
    first = taker(scenario) if scenario.taken_in is not None else "mother"
    return segment.lane != first


def _supplementary(segment: Segment, timeline: Timeline, params: Params) -> Leftover | None:
    """Granted right after maternity leave, in one piece: lost unless taken from that day."""
    if timeline.taken_in is not None or segment.start < timeline.today:
        return None
    s = params.supplementary
    alone = segment.lane == "father"
    who = "tata" if alone else "mama albo tata (tylko jedno z nich)"
    return Leftover(
        id="left-supplementary",
        kind="leave",
        parent="father" if alone else None,
        title="Uzupełniający urlop macierzyński",
        text=(
            f"Po urlopie macierzyńskim {who} może wziąć {weeks_or_days(segment.days)} "
            "uzupełniającego urlopu macierzyńskiego. Przysługuje bezpośrednio po urlopie "
            f"macierzyńskim, czyli od {long_date(segment.start)}, i jest udzielany jednorazowo."
        ),
        days=segment.days,
        amount=_money(timeline, segment.id, segment.days),
        last_day=segment.end,
        start_by=segment.start,
        segment_id=segment.id,
        sources=merge_sources(s.once_after_maternity.sources, s.one_parent.sources),
    )


def _pool(timeline: Timeline, scenario: Scenario, params: Params) -> Leftover | None:
    """The weeks of the pool of parental leave the parents' plan leaves out."""
    parts = scenario.parental_parts
    deadline = _marker(timeline, PARENTAL_DEADLINE)
    if not parts or deadline is None or scenario.taken_in is not None:
        return None
    parental = [
        s
        for s in timeline.segments
        if s.lane in ("mother", "father") and s.id.startswith("parental")
    ]
    able = {s.lane for s in parental}
    if not able:
        return None
    total, one_parent = parental_weeks(scenario, params)
    pool = total if len(able) == 2 else one_parent
    options = sum(s.days for s in parental if s.id in ("parental", "parental-father"))
    left = pool * 7 - sum(part.weeks for part in parts) * 7 - options
    first = max(timeline.today, min(s.start for s in parental))
    left = min(left, days_between(first, deadline.date))
    if left <= 0:
        return None
    p = params.parental
    exclusive = p.exclusive_weeks.value
    if len(able) == 2:
        rule = f"Rodzice mają razem do {pool} tyg."
    else:
        rule = f"{WHO[next(iter(able))].capitalize()} może wykorzystać najwięcej {pool} tyg."
    text = (
        f"W planie urlopu rodzicielskiego zostało {weeks_or_days(left)}, których nikt nie "
        f"zaplanował. {rule} Urlop jest udzielany najpóźniej do {long_date(deadline.date)}."
    )
    named = {part.parent for part in parts}
    for parent in ("mother", "father"):
        planned = sum(part.weeks for part in parts if part.parent == parent)
        if len(able) == 2 and parent in named and planned < exclusive:
            text += (
                f" {weeks_or_days((exclusive - planned) * 7)} z nich może wykorzystać tylko "
                f"{WHO[parent]}: tych tygodni nie można przenieść na {TO_THE_OTHER[parent]}."
            )
    return Leftover(
        id="left-parental-pool",
        kind="leave",
        parent=None if len(able) == 2 else next(iter(able)),
        title="Niezaplanowane tygodnie urlopu rodzicielskiego",
        text=text,
        days=left,
        amount=None,
        last_day=deadline.date,
        start_by=deadline.date - (left - 1) * DAY,
        marker_id=deadline.id,
        sources=merge_sources(
            parental_table(scenario, params).sources, p.exclusive_weeks.sources, deadline.sources
        ),
    )


def _rate_choice(timeline: Timeline, scenario: Scenario, params: Params) -> Leftover | None:
    """The request for 81,5% while it can still be filed (money.py draws its last day only
    while the choice is open)."""
    marker = _marker(timeline, DEADLINE_ID)
    if marker is None or scenario.rate_815 is False:
        return None
    m = params.money
    req = request(scenario, params, timeline.birth_date)
    full, parental, single = rates(params)
    who = WHO[req.who]
    leave = LEAVE[req.leave]
    by = long_date(marker.date)
    after = "po przyjęciu dziecka na wychowanie" if req.taken_in else "po porodzie"
    otherwise = (
        f"zasiłek wynosi {full} za {leave} i {parental} za urlop rodzicielski, jak na osi"
        if not scenario.rate_815
        else f"zasiłek wyniesie {full} za {leave} i {parental} za urlop rodzicielski"
    )
    if scenario.rate_815:
        text = (
            f"{who.capitalize()} wybiera {single}: pisemny wniosek trzeba złożyć do {by}, "
            f"najpóźniej {req.days.value} dni {after}. Bez wniosku {otherwise}."
        )
    else:
        text = (
            f"Do {by}, czyli najpóźniej {req.days.value} dni {after}, {who} może złożyć pisemny "
            f"wniosek o zasiłek {single} podstawy za cały {leave} i rodzicielski. Bez wniosku "
            f"{otherwise}."
        )
    totals = request_totals(scenario, timeline, params)
    amount = None
    if totals is not None:
        text += (
            f" Za {leave} i rodzicielski {WHOSE[req.who]} pokazany na osi ({totals.days} dni): "
            f"{pln(totals.standard)} przy {full} i {parental} albo {pln(totals.single)} przy "
            f"{single}."
        )
        amount = float(cents(max(totals.single - totals.standard, Decimal(0))))
    return Leftover(
        id="left-rate-815",
        kind="choice",
        parent=req.who,
        title=f"Wniosek o zasiłek {single}",
        text=text,
        days=None,
        amount=amount,
        last_day=marker.date,
        start_by=None,
        marker_id=marker.id,
        sources=merge_sources(marker.sources, m.rate_full.sources, m.rate_parental.sources),
    )
