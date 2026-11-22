"""F8, planning from a goal (FUNKCJE: "użytkownik wybiera cel, silnik układa plany").

For one of four goals the engine proposes 2-3 plans of parental leave and compares them. A plan
is a set of `Scenario` changes the rules already know: the parts of parental leave
(`parental_parts`: who, how many weeks, in which order, with part-time work), the rate
(`rate_815`) and the father taking over maternity leave (`father_takes_over`). Every plan is
built by `build_timeline`, so the engine validates it (guide B.3 and E; Labour Code art. 180
§ 4-5, 182¹ᵃ, 182¹ᶜ, 182¹ᵉ, 182¹ᶠ; ustawa art. 30a): the pool for both parents, 9 weeks that
belong to each, at most 5 parts, the last day of the year the child turns 6, work only for an
employee and at most half of full time. A plan the rules refuse is never returned. The 81,5% is
offered only while its request can still be filed (21 days after the birth); afterwards the
plans keep the rate the family has.

Goals and how their plans are ranked (the figures are read from each plan's timeline):
- "most-money": the money for the leave in the plan, the most first. When no amount is known,
  the plans keep their order and the result says that the money cannot be compared;
- "longest-home": the last day the child is at home with a parent on leave, continuously from
  the birth (`home_until`), the latest first;
- "equal-split": the difference between the parents' days of leave, the smallest first;
- "quick-return": the mother's first day back at work (also part-time), the earliest first.
The plans show options and their effects; the family decides. Nothing is proposed after a
child's death or the mother's death, and not for a child taken in for upbringing (its parental
leave has no plans yet).

How the figures count (the same for the current timeline and every plan):
- leave: maternity leave (with the father's part), supplementary leave and paternity leave as
  the timeline draws them, and parental leave only where a plan decides it: a parent's share
  still drawn as an option ("do wyboru") is left out, since the plan does not take it now;
- the money: the payments for those periods (money.py); benefits in pregnancy are the same in
  every plan and are left out;
- back to work: the day after the parent's first unbroken stretch of leave, or the first day of
  a part combined with work, if earlier.
"""

import datetime as dt
import math
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel

from app.engine.amounts import dec, pln
from app.engine.compare import LEAVE_KINDS, PARENTAL_OPTIONS, right_kind, weeks_text
from app.engine.draft import DAY, WEEK, merge_sources
from app.engine.insurance import NOT_INSURED, coverage, father_coverage
from app.engine.models import (
    ParentalPart,
    Role,
    Scenario,
    ScenarioError,
    Segment,
    SourceRef,
    Timeline,
)
from app.engine.money import rates, request_deadline
from app.engine.params import Params
from app.engine.parental import parental_deadline, parental_table, parental_weeks
from app.engine.parental_plan import extension_days, fraction, part_ids, work_weeks
from app.engine.stress import sensitive, with_changes
from app.engine.timeline import build_timeline, changed_element_ids
from app.engine.wording import fmt

Goal = Literal["most-money", "longest-home", "equal-split", "quick-return"]
GOAL_LABEL: dict[Goal, str] = {
    "most-money": "najwięcej pieniędzy",
    "longest-home": "najdłużej w domu",
    "equal-split": "równy podział",
    "quick-return": "szybki powrót do pracy",
}
MAX_PLANS = 3
WHO: dict[Role, str] = {"mother": "mama", "father": "tata"}


class ParentFigures(BaseModel):
    """One parent's leave in a plan (see the module docstring for what counts)."""

    leave_days: int
    work_days: int
    """Days of parental leave combined with part-time work."""
    first_day: dt.date | None
    last_day: dt.date | None
    back_to_work: dt.date | None
    """The first day back at work, also part-time; None = no leave."""
    total: float | None
    """PLN for the leave counted; None = no amount known for this parent."""


class PlanFigures(BaseModel):
    mother: ParentFigures
    father: ParentFigures
    total: float | None
    """Both parents' money; None when no amount is known."""
    amounts_known: bool
    """Every parent with leave has a known amount."""
    home_until: dt.date | None
    """The child is at home with a parent on leave, without a break from the birth, until this
    day (also while that parent works part-time)."""
    pool_used: int
    """Weeks of the parental pool the plan takes (both parents)."""
    pool_total: int
    rate_815: bool | None


class Plan(BaseModel):
    id: str
    goal: Goal
    rank: int
    """1 = the best for the goal."""
    title: str
    summary: str
    """What the plan is, with the dates of its timeline."""
    patch: dict[str, Any]
    """The Scenario fields to set (JSON values): `parental_parts`, `rate_815`,
    `father_takes_over`, `mother_weeks_before_takeover`. Applied, they give this plan."""
    figures: PlanFigures
    given_up: list[str]
    """What the family gives up or leaves for later with this plan."""
    changed: list[str]
    """Elements that differ from the current timeline (changed_element_ids)."""
    current: bool
    """The family already has this plan: applying it changes nothing."""
    sources: list[SourceRef]
    """The rules the plan rests on, with literal quotes."""


class PlansResult(BaseModel):
    goal: Goal
    plans: list[Plan] = []
    current: PlanFigures | None = None
    """The same figures for the timeline as it is now."""
    notes: list[str] = []
    """What the comparison assumes, and what it cannot compare."""
    sensitive: bool = False
    reason: str | None = None
    """Why there are no plans."""


@dataclass(frozen=True)
class Candidate:
    id: str
    title: str
    parts: tuple[ParentalPart, ...]
    rate_815: bool | None
    takes_over: bool | None
    mother_weeks: int | None


@dataclass(frozen=True)
class Frame:
    """What the plans may use, read once from the timeline without a plan."""

    scenario: Scenario
    params: Params
    today: dt.date
    base: Timeline
    """The current answers without a plan of parental leave: every share drawn as an option."""
    total: int
    one_parent: int
    mother: bool
    """The mother has a share of parental leave."""
    father: bool
    mother_works: bool
    """The mother is an employee: she may combine parental leave with part-time work."""
    father_works: bool
    rate_open: bool
    """The request for 81,5% can still be filed."""
    takeover_weeks: int | None
    """Weeks after the birth the mother uses before the father may take over maternity leave;
    None = taking over is not an option for this family."""


def propose_plans(scenario: Scenario, params: Params, today: dt.date, goal: Goal) -> PlansResult:
    """2-3 plans for the goal, ranked. Raises ScenarioError when the scenario itself breaks a
    rule."""
    if scenario.taken_in is not None:
        return PlansResult(
            goal=goal,
            reason="Plany układamy na razie dla dziecka urodzonego w rodzinie, nie przyjętego "
            "na wychowanie.",
        )
    if scenario.anchor_date is None:
        return PlansResult(
            goal=goal, reason="Najpierw potrzebna jest data porodu: przewidywana albo faktyczna."
        )
    if scenario.children_count is None:
        return PlansResult(
            goal=goal,
            reason="Najpierw potrzebna jest liczba dzieci urodzonych przy jednym porodzie: od "
            "niej zależy długość urlopów.",
        )
    if sensitive(scenario):
        return PlansResult(
            goal=goal, sensitive=True, reason="W tej sytuacji nie proponujemy planów."
        )
    current = build_timeline(scenario, params, today)
    frame = _frame(scenario, params, today)
    if not frame.mother and not frame.father:
        return PlansResult(
            goal=goal,
            current=figures(scenario, current, params),
            reason="Na tej osi nikt nie ma już urlopu rodzicielskiego, więc nie ma czego planować.",
        )
    built: list[tuple[Candidate, Scenario, Timeline]] = []
    seen: set[str] = set()
    for candidate in CANDIDATES[goal](frame):
        if candidate is None:
            continue
        planned = _apply(scenario, candidate)
        key = str(_fields(planned))
        if key in seen:
            continue
        try:
            timeline = build_timeline(planned, params, today)
        except ScenarioError:
            continue  # the rules refuse it: never proposed
        seen.add(key)
        built.append((candidate, planned, timeline))
    scored = [(c, s, t, figures(s, t, params)) for c, s, t in built]
    ranked = sorted(enumerate(scored), key=lambda item: (_score(goal, item[1][3]), item[0]))
    plans = [
        _plan(goal, rank, frame, current, c, s, t, f)
        for rank, (_, (c, s, t, f)) in enumerate(ranked[:MAX_PLANS], 1)
    ]
    return PlansResult(
        goal=goal,
        plans=plans,
        current=figures(scenario, current, params),
        notes=_notes(goal, frame, [p.figures for p in plans]) if plans else [],
        reason=None if plans else _no_plans(goal, frame),
    )


# What the family can choose from.


def segment(timeline: Timeline, segment_id: str) -> Segment | None:
    return next((s for s in timeline.segments if s.id == segment_id), None)


def _frame(scenario: Scenario, params: Params, today: dt.date) -> Frame:
    plain = with_changes(scenario, parental_parts=[])
    base = build_timeline(plain, params, today)
    total, one_parent = parental_weeks(scenario, params)
    birth = base.birth_date
    insured = coverage(scenario) not in NOT_INSURED
    rate_open = insured and (not scenario.child_born or request_deadline(birth, params) >= today)
    return Frame(
        scenario=scenario,
        params=params,
        today=today,
        base=base,
        total=total,
        one_parent=one_parent,
        mother=segment(base, "parental") is not None,
        father=segment(base, "parental-father") is not None,
        mother_works=scenario.mothers_work == "employment",
        father_works=scenario.fathers_work == "employment",
        rate_open=rate_open,
        takeover_weeks=_takeover_weeks(scenario, params, today, base, insured),
    )


def _takeover_weeks(
    scenario: Scenario, params: Params, today: dt.date, base: Timeline, insured: bool
) -> int | None:
    """Guide B.1: after at least 14 weeks after the birth the mother may leave the rest of
    maternity leave to the father. Offered only while the family has not decided it, and never
    in the past: for a born child, from today at the earliest."""
    if (
        not insured
        or father_coverage(scenario) in NOT_INSURED
        or scenario.father_takes_over is not None
        or scenario.mother_event is not None
    ):
        return None
    maternity = segment(base, "maternity")
    if maternity is None:
        return None
    birth = base.birth_date
    weeks = params.father.takeover_after_weeks.value
    if scenario.child_born and today > birth:
        weeks = max(weeks, math.ceil((today - birth).days / 7))
    if birth + weeks * WEEK > maternity.end:
        return None
    return weeks


def _rates(frame: Frame) -> list[bool | None]:
    """The rate a plan may set: both while the request can be filed, else the family's."""
    return [False, True] if frame.rate_open else [frame.scenario.rate_815]


def _part(parent: Role, weeks: int, frame: Frame, work: bool = False) -> ParentalPart:
    fraction_ = frame.params.parental_plan.max_work_fraction.value if work else None
    return ParentalPart(parent=parent, weeks=weeks, work_fraction=fraction_)


def _whole_pool(frame: Frame, work: frozenset[Role] = frozenset()) -> tuple[ParentalPart, ...]:
    """The whole pool, one parent after the other: the mother's share right after maternity
    leave, then the father's own weeks. A parent without a share leaves it unused."""
    parts = []
    exclusive = frame.params.parental.exclusive_weeks.value
    if frame.mother:
        parts.append(_part("mother", frame.one_parent, frame, "mother" in work))
    if frame.father:
        weeks = exclusive if frame.mother else frame.one_parent
        parts.append(_part("father", weeks, frame, "father" in work))
    return tuple(parts)


def _candidate(
    id_: str,
    title: str,
    frame: Frame,
    parts: tuple[ParentalPart, ...],
    *,
    rate: bool | None | Literal["kept"] = "kept",
    takeover: tuple[bool | None, int | None] | None = None,
) -> Candidate:
    """A plan; the rate and taking over stay as the family has them unless given."""
    scenario = frame.scenario
    takes_over, weeks = takeover or (
        scenario.father_takes_over,
        scenario.mother_weeks_before_takeover,
    )
    return Candidate(
        id=id_,
        title=title,
        parts=parts,
        rate_815=scenario.rate_815 if rate == "kept" else rate,
        takes_over=takes_over,
        mother_weeks=weeks,
    )


def _with_takeover(frame: Frame) -> tuple[bool, int | None]:
    assert frame.takeover_weeks is not None
    minimum = frame.params.father.takeover_after_weeks.value
    return True, frame.takeover_weeks if frame.takeover_weeks > minimum else None


def _most_money(frame: Frame) -> list[Candidate | None]:
    """The whole pool at each rate the family may choose; and, when the father's benefit base
    is higher, the weeks the parents share taken by him."""
    found: list[Candidate | None] = []
    rf, rp, rs = rates(frame.params)
    rate_label = {False: f"{rf} i {rp}", True: rs, None: ""}
    for rate in _rates(frame):
        suffix = f", zasiłek {rate_label[rate]}" if frame.rate_open else ""
        found.append(
            _candidate(
                f"whole-pool-{_rate_id(rate)}",
                f"Cały urlop rodzicielski{suffix}",
                frame,
                _whole_pool(frame),
                rate=rate,
            )
        )
    bases = {b.parent: b.base for b in frame.base.bases}
    higher = "mother" in bases and "father" in bases and bases["father"] > bases["mother"]
    if frame.mother and frame.father and higher:
        exclusive = frame.params.parental.exclusive_weeks.value
        parts = (_part("mother", exclusive, frame), _part("father", frame.one_parent, frame))
        for rate in _rates(frame):
            suffix = f", zasiłek {rate_label[rate]}" if frame.rate_open else ""
            found.append(
                _candidate(
                    f"father-shares-{_rate_id(rate)}",
                    f"Wspólne tygodnie bierze tata{suffix}",
                    frame,
                    parts,
                    rate=rate,
                )
            )
    return found


def _rate_id(rate: bool | None) -> str:
    return {False: "100-70", True: "815", None: "rate-kept"}[rate]


def _longest_home(frame: Frame) -> list[Candidate | None]:
    """The whole pool one after the other; then with part-time work, which lengthens the leave
    (art. 182¹ᶠ): the mother's part, both parents' parts."""
    share = fraction(frame.params.parental_plan.max_work_fraction.value)
    found: list[Candidate | None] = [
        _candidate(
            "whole-pool", "Cały urlop rodzicielski, jedno po drugim", frame, _whole_pool(frame)
        )
    ]
    working: list[Role] = []
    if frame.mother and frame.mother_works:
        working.append("mother")
        found.append(
            _candidate(
                "whole-pool-mother-works",
                f"Mama łączy urlop rodzicielski z pracą na {share} etatu",
                frame,
                _whole_pool(frame, frozenset(working)),
            )
        )
    if frame.father and frame.father_works:
        working.append("father")
        both = len(working) == 2
        found.append(
            _candidate(
                "whole-pool-both-work" if both else "whole-pool-father-works",
                f"{'Oboje łączycie' if both else 'Tata łączy'} urlop rodzicielski z pracą na "
                f"{share} etatu",
                frame,
                _whole_pool(frame, frozenset(working)),
            )
        )
    return found


def _equal_split(frame: Frame) -> list[Candidate | None]:
    """Parental leave halved; the whole time at home made equal (maternity leave counted); and
    the same with the father taking over maternity leave after 14 weeks."""
    if not (frame.mother and frame.father):
        return []
    mother = frame.total // 2
    found: list[Candidate | None] = [
        _candidate(
            "parental-halves",
            "Urlop rodzicielski po równo",
            frame,
            (_part("mother", mother, frame), _part("father", frame.total - mother, frame)),
        )
    ]
    found.append(_equal_time(frame, frame.base, "equal-time", "Czas w domu po równo", None))
    if frame.takeover_weeks is not None:
        takeover = _with_takeover(frame)
        over = with_changes(
            frame.scenario,
            parental_parts=[],
            father_takes_over=True,
            mother_weeks_before_takeover=takeover[1],
        )
        try:
            base = build_timeline(over, frame.params, frame.today)
        except ScenarioError:
            return found
        found.append(
            _equal_time(
                frame,
                base,
                "takeover-equal-time",
                "Tata przejmuje urlop macierzyński, czas w domu po równo",
                takeover,
            )
        )
    return found


def _equal_time(
    frame: Frame,
    base: Timeline,
    id_: str,
    title: str,
    takeover: tuple[bool, int | None] | None,
) -> Candidate | None:
    """The father's weeks f so that the mother's leave (maternity, supplementary) plus her
    parental weeks equals his (paternity, his part of maternity leave) plus his: f = (mother's
    days + pool days − father's days) / 14, to the nearest week."""
    days = {"mother": 0, "father": 0}
    for s in base.segments:
        kind = right_kind(s.id)
        if s.lane in days and kind in LEAVE_KINDS and kind != "parental":
            days[s.lane] += s.days
    numerator = days["mother"] + frame.total * 7 - days["father"]
    father = min(max((numerator + 7) // 14, 1), frame.one_parent)
    mother = min(frame.total - father, frame.one_parent)
    if mother < 1:
        return None
    return _candidate(
        id_,
        title,
        frame,
        (_part("mother", mother, frame), _part("father", father, frame)),
        takeover=takeover,
    )


def _quick_return(frame: Frame) -> list[Candidate | None]:
    """The mother back after maternity leave, parental leave left for later (until the last
    day of the year the child turns 6); the father taking over maternity leave after 14 weeks;
    the mother back part-time right after maternity leave, on parental leave the rest of the
    time."""
    if segment(frame.base, "maternity") is None:
        return []
    share = fraction(frame.params.parental_plan.max_work_fraction.value)
    found: list[Candidate | None] = [
        _candidate("after-maternity", "Mama wraca po urlopie macierzyńskim", frame, ())
    ]
    if frame.takeover_weeks is not None:
        found.append(
            _candidate(
                "takeover",
                f"Tata przejmuje urlop macierzyński po {frame.takeover_weeks} tyg.",
                frame,
                (),
                takeover=_with_takeover(frame),
            )
        )
    if frame.mother and frame.mother_works:
        found.append(
            _candidate(
                "part-time-after-maternity",
                f"Mama wraca na {share} etatu po urlopie macierzyńskim",
                frame,
                (_part("mother", frame.one_parent, frame, work=True),),
            )
        )
    return found


CANDIDATES = {
    "most-money": _most_money,
    "longest-home": _longest_home,
    "equal-split": _equal_split,
    "quick-return": _quick_return,
}
PATCH_FIELDS = ("parental_parts", "rate_815", "father_takes_over", "mother_weeks_before_takeover")


def _fields(scenario: Scenario) -> dict[str, Any]:
    return scenario.model_dump(mode="json", include=set(PATCH_FIELDS))


def _apply(scenario: Scenario, candidate: Candidate) -> Scenario:
    return with_changes(scenario, **_patch_values(candidate))


def _patch_values(candidate: Candidate) -> dict[str, Any]:
    return {
        "parental_parts": [p.model_dump() for p in candidate.parts],
        "rate_815": candidate.rate_815,
        "father_takes_over": candidate.takes_over,
        "mother_weeks_before_takeover": candidate.mother_weeks if candidate.takes_over else None,
    }


# The figures.


def counted(timeline: Timeline) -> list[Segment]:
    """The leave that counts: see the module docstring."""
    return [
        s
        for s in timeline.segments
        if s.lane in ("mother", "father")
        and right_kind(s.id) in LEAVE_KINDS
        and s.id not in PARENTAL_OPTIONS
    ]


def figures(scenario: Scenario, timeline: Timeline, params: Params) -> PlanFigures:
    segments = counted(timeline)
    ids = {s.id for s in segments}
    by_id = dict(zip(part_ids(scenario.parental_parts), scenario.parental_parts, strict=True))
    bases = {b.parent for b in timeline.bases}
    parents = {}
    for parent in ("mother", "father"):
        mine = sorted((s for s in segments if s.lane == parent), key=lambda s: s.start)
        work_starts = [s.start for s in mine if (p := by_id.get(s.id)) and p.work_fraction]
        work_days = sum(
            work_weeks(p) * 7 for s in mine if (p := by_id.get(s.id)) and p.work_fraction
        )
        money = None
        if parent in bases:
            money = float(
                sum(
                    (
                        dec(p.total)
                        for p in timeline.payments
                        if p.lane == parent and p.segment_id in ids
                    ),
                    Decimal(0),
                )
            )
        parents[parent] = ParentFigures(
            leave_days=sum(s.days for s in mine),
            work_days=work_days,
            first_day=mine[0].start if mine else None,
            last_day=max(s.end for s in mine) if mine else None,
            back_to_work=_back_to_work(mine, work_starts),
            total=money,
        )
    known = [f.total for f in parents.values() if f.total is not None]
    used = sum(p.weeks for p in scenario.parental_parts)
    total, _ = parental_weeks(scenario, params)
    return PlanFigures(
        mother=parents["mother"],
        father=parents["father"],
        total=float(sum((dec(t) for t in known), Decimal(0))) if known else None,
        amounts_known=all(f.total is not None for f in parents.values() if f.leave_days),
        home_until=_home_until(segments, timeline.birth_date),
        pool_used=used,
        pool_total=total,
        rate_815=scenario.rate_815,
    )


def _back_to_work(mine: list[Segment], work_starts: list[dt.date]) -> dt.date | None:
    if not mine:
        return None
    end = mine[0].end
    for s in mine[1:]:
        if s.start > end + DAY:
            break
        end = max(end, s.end)
    return min([end + DAY, *work_starts])


def _home_until(segments: list[Segment], birth: dt.date) -> dt.date | None:
    cursor = birth - DAY
    for s in sorted(segments, key=lambda s: s.start):
        if s.start <= cursor + DAY:
            cursor = max(cursor, s.end)
    return cursor if cursor >= birth else None


def _score(goal: Goal, f: PlanFigures) -> tuple:
    far = dt.date.max
    match goal:
        case "most-money":
            return (-(f.total or 0),)
        case "longest-home":
            return (-(f.home_until or dt.date.min).toordinal(),)
        case "equal-split":
            return (abs(f.mother.leave_days - f.father.leave_days),)
        case "quick-return":
            main = f.mother if f.mother.leave_days else f.father
            return (main.back_to_work or far, main.last_day or far)


# The plan in words.


def _plan(
    goal: Goal,
    rank: int,
    frame: Frame,
    current: Timeline,
    candidate: Candidate,
    planned: Scenario,
    timeline: Timeline,
    f: PlanFigures,
) -> Plan:
    params = frame.params
    p, pp, m = params.parental, params.parental_plan, params.money
    sources: list[list[SourceRef]] = [
        parental_table(planned, params).sources,
        p.exclusive_weeks.sources,
        p.max_parts.sources,
        p.deadline_age.sources,
    ]
    if any(part.work_fraction for part in candidate.parts):
        sources += [pp.max_work_fraction.sources, pp.extension.sources, m.work_reduces.sources]
    if candidate.rate_815 is not None and frame.rate_open:
        sources += [m.rate_full.sources, m.rate_parental.sources, m.rate_single.sources]
        sources += [m.request_days.sources]
    if candidate.takes_over and not frame.scenario.father_takes_over:
        sources += [params.father.takeover_after_weeks.sources]
    return Plan(
        id=candidate.id,
        goal=goal,
        rank=rank,
        title=candidate.title,
        summary=_summary(frame, candidate, timeline, f),
        patch=_fields(planned),
        figures=f,
        given_up=_given_up(frame, candidate, timeline, f),
        changed=changed_element_ids(current, timeline),
        current=_fields(planned) == _fields(frame.scenario),
        sources=merge_sources(*sources),
    )


def _summary(frame: Frame, candidate: Candidate, timeline: Timeline, f: PlanFigures) -> str:
    sentences = []
    his = segment(timeline, "maternity-father")
    if candidate.takes_over and not frame.scenario.father_takes_over and his is not None:
        weeks = candidate.mother_weeks or frame.params.father.takeover_after_weeks.value
        sentences.append(
            f"Mama wykorzystuje {weeks} tyg. urlopu macierzyńskiego po porodzie, a tata "
            f"przejmuje resztę: od {fmt(his.start)} do {fmt(his.end)}."
        )
    parts = list(zip(part_ids(list(candidate.parts)), candidate.parts, strict=True))
    for part_id, part in parts:
        shown = segment(timeline, part_id)
        if shown is None:
            continue
        text = (
            f"{WHO[part.parent].capitalize()} bierze {part.weeks} tyg. urlopu rodzicielskiego: "
            f"od {fmt(shown.start)} do {fmt(shown.end)}"
        )
        if part.work_fraction:
            longer = weeks_text(extension_days(part))
            text += (
                f", przez {work_weeks(part)} tyg. pracując na {fraction(part.work_fraction)} "
                f"etatu (urlop wydłuża się o {longer})"
            )
        sentences.append(text + ".")
    if not parts:
        if f.mother.back_to_work is not None:
            sentences.append(f"Mama wraca do pracy {fmt(f.mother.back_to_work)}.")
        sentences.append("Urlopu rodzicielskiego na razie nie planujecie.")
    rf, rp, rs = rates(frame.params)
    if frame.rate_open and candidate.rate_815 is True:
        sentences.append(
            f"Zasiłek {rs} za cały urlop macierzyński i rodzicielski mamy: wniosek najpóźniej "
            f"{fmt(request_deadline(timeline.birth_date, frame.params))}."
        )
    elif frame.rate_open and candidate.rate_815 is False:
        sentences.append(f"Zasiłek {rf} za urlop macierzyński i {rp} za rodzicielski.")
    if f.total is not None:
        sentences.append(f"Zasiłki za urlopy w planie: razem {pln(dec(f.total))}.")
    return " ".join(sentences)


def _given_up(frame: Frame, candidate: Candidate, timeline: Timeline, f: PlanFigures) -> list[str]:
    params = frame.params
    exclusive = params.parental.exclusive_weeks.value
    deadline = fmt(parental_deadline(timeline.birth_date, params))
    lines = []
    left = frame.total - f.pool_used
    named = {part.parent for part in candidate.parts}
    if not frame.father and frame.mother:
        lines.append(
            f"{exclusive} tyg. urlopu rodzicielskiego należy wyłącznie do taty i nie przechodzi "
            "na mamę."
        )
        left -= exclusive
    if left > 0 and candidate.parts:
        lines.append(
            f"Z puli urlopu rodzicielskiego zostaje {left} tyg.: można je wykorzystać później, "
            f"najpóźniej do {deadline}."
        )
    elif left > 0:
        lines.append(
            f"Urlop rodzicielski ({left} tyg.) zostaje na później: można go wykorzystać "
            f"najpóźniej do {deadline}."
        )
    for parent in ("mother", "father"):
        if parent in named and getattr(frame, parent):
            weeks = sum(p.weeks for p in candidate.parts if p.parent == parent)
            if weeks < exclusive:
                lines.append(
                    f"{WHO[parent].capitalize()} bierze {weeks} tyg. ze swoich {exclusive} tyg., "
                    "których nie można przenieść na drugiego rodzica."
                )
    for part in candidate.parts:
        if part.work_fraction:
            lines.append(
                f"Przez {work_weeks(part)} tyg. {WHO[part.parent]} pracuje na "
                f"{fraction(part.work_fraction)} etatu: zasiłek za te tygodnie jest mniejszy "
                "proporcjonalnie do wymiaru pracy."
            )
    rf, rp, rs = rates(params)
    if frame.rate_open and candidate.rate_815 is True:
        lines.append(f"Za urlop macierzyński zasiłek wynosi {rs} zamiast {rf}.")
    elif frame.rate_open and candidate.rate_815 is False:
        lines.append(f"Bez wniosku o {rs}: za urlop rodzicielski zasiłek wynosi {rp}.")
    if candidate.takes_over and not frame.scenario.father_takes_over:
        lines.append(
            "Mama kończy urlop macierzyński wcześniej, a jego resztę wykorzystuje tata; zasiłek "
            "za tę resztę liczymy z podstawy taty."
        )
    return lines


def _notes(goal: Goal, frame: Frame, shown: list[PlanFigures]) -> list[str]:
    notes = [
        "Liczymy urlopy tak, jak pokazuje je oś: urlop macierzyński, uzupełniający (jeśli jest) "
        "i urlop ojcowski taty w każdym planie, a urlop rodzicielski tylko ten, który jest "
        "w planie. Kwoty to zasiłki za te urlopy, bez zasiłków w ciąży."
    ]
    if not any(f.total is not None for f in shown):
        notes.append(
            "Kwot nie porównujemy: brakuje miesięcznej kwoty, z której liczy się zasiłek. "
            "Porównujemy tygodnie i daty."
        )
        if goal == "most-money":
            notes.append(
                "Bez kwot nie da się powiedzieć, który plan daje więcej pieniędzy: podaj "
                "miesięczną kwotę wynagrodzenia."
            )
    elif not all(f.amounts_known for f in shown):
        notes.append("Kwoty liczymy tylko dla rodzica, którego miesięczna kwota jest znana.")
    scenario = frame.scenario
    if not frame.rate_open and coverage(scenario) not in NOT_INSURED:
        rf, rp, rs = rates(frame.params)
        deadline = fmt(request_deadline(frame.base.birth_date, frame.params))
        notes.append(
            f"Mama wybrała {rs}: plany zostają przy tej stawce."
            if scenario.rate_815
            else f"Termin na wniosek o {rs} minął {deadline}: plany liczą {rf} i {rp}."
        )
    if scenario.child_born is not True:
        notes.append(
            "Liczymy od przewidywanej daty porodu. Po porodzie plan przeliczy się od faktycznej "
            "daty."
        )
    return notes


def _no_plans(goal: Goal, frame: Frame) -> str:
    if goal == "equal-split" and not (frame.mother and frame.father):
        return "Równy podział wymaga, żeby oboje rodzice mieli urlop rodzicielski."
    if goal == "quick-return":
        return "Mama nie ma urlopu macierzyńskiego, więc nie ma z czego wracać wcześniej."
    return "Reguły nie pozwalają ułożyć planu dla tego celu."
