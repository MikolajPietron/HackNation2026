"""Supplementary maternity leave (uzupełniający urlop macierzyński), Labour Code art. 180².

A week of leave for every week the child spends in hospital, counted in a window after the
birth that depends on when the child was born and how much it weighed:
- before the end of the 28th week of pregnancy, or no more than 1000 g: until the end of the
  15th week after the birth;
- after the 28th and before the end of the 37th week, more than 1000 g: until the end of the
  8th week;
- after the 37th week: from the 5th day until the end of the 8th week, provided the stay lasts
  at least 2 consecutive days, the first of them between the 5th and the 28th day.
Stays are added up and an incomplete week is rounded up (§ 3).

Our reading, not settled by the materials (CLAUDE.md, open questions): days and weeks "after the
birth" are counted from the day after the birth, so the n-th day is the date of birth plus n.
"""

import datetime as dt
from dataclasses import dataclass
from typing import Literal

from app.engine.models import Scenario, ScenarioError
from app.engine.params import Params
from app.engine.wording import fmt

DAY = dt.timedelta(days=1)

Case = Literal["early", "preterm", "term"]


@dataclass(frozen=True)
class Supplementary:
    case: Case
    limit_weeks: int
    first_day: dt.date
    last_day: dt.date
    """The window in which hospital days count."""
    days: int
    """Hospital days inside the window."""
    weeks: int
    ongoing: bool
    """The child is still in hospital: counted until today, the number may still grow."""
    condition_met: bool
    """For a child born after the 37th week: the stay meets the 2-consecutive-days condition."""
    before_28th_week: bool = False
    up_to_1000g: bool = False
    """Which of the two facts (or both) makes this the "early" case."""


def supplementary_leave(
    scenario: Scenario, params: Params, birth: dt.date, today: dt.date
) -> Supplementary | None:
    """What the hospital stay gives, or None while the facts are not known."""
    week, light = scenario.birth_week, scenario.birth_weight_up_to_1000g
    if not scenario.hospital_care or week is None or light is None:
        return None
    s = params.supplementary
    case: Case
    if week == "before-28" or light:
        case, limit, first_counted = "early", s.limit_weeks_early.value, 1
    elif week == "28-37":
        case, limit, first_counted = "preterm", s.limit_weeks_preterm.value, 1
    else:
        case, limit, first_counted = "term", s.term.limit_weeks, s.term.counted_from_day
    first_day = birth + first_counted * DAY
    last_day = birth + limit * 7 * DAY

    stays = _merged(scenario, birth, today)
    days = sum(
        (min(end, last_day) - max(start, first_day)).days + 1
        for start, end in stays
        if min(end, last_day) >= max(start, first_day)
    )
    condition_met = True
    if case == "term":
        condition_met = any(
            _meets_term_condition(start, end, birth, params) for start, end in stays
        )
        if not condition_met:
            days = 0
    return Supplementary(
        case=case,
        limit_weeks=limit,
        first_day=first_day,
        last_day=last_day,
        days=days,
        weeks=-(-days // 7),
        ongoing=any(stay.end is None for stay in scenario.hospital_stays),
        condition_met=condition_met,
        before_28th_week=week == "before-28",
        up_to_1000g=light,
    )


def describe_case(leave: Supplementary, params: Params) -> str:
    """Which case of art. 180² § 1 this is and which hospital days count."""
    term = params.supplementary.term
    match leave.case:
        case "early":
            if leave.before_28th_week and leave.up_to_1000g:
                fact = (
                    "Dziecko urodziło się przed ukończeniem 28. tygodnia ciąży i ważyło nie "
                    "więcej niż 1000 g"
                )
            elif leave.before_28th_week:
                fact = "Dziecko urodziło się przed ukończeniem 28. tygodnia ciąży"
            else:
                fact = "Dziecko ważyło przy urodzeniu nie więcej niż 1000 g"
            return (
                f"{fact}, więc liczy się pobyt w szpitalu do końca {leave.limit_weeks}. tygodnia "
                "po porodzie."
            )
        case "preterm":
            return (
                "Dziecko urodziło się po ukończeniu 28. i przed ukończeniem 37. tygodnia ciąży "
                "i ważyło więcej niż 1000 g, więc liczy się pobyt w szpitalu do końca "
                f"{leave.limit_weeks}. tygodnia po porodzie."
            )
        case "term":
            return (
                "Dziecko urodziło się po ukończeniu 37. tygodnia ciąży, więc liczy się pobyt "
                f"w szpitalu od {term.counted_from_day}. dnia do końca {leave.limit_weeks}. "
                f"tygodnia po porodzie — o ile trwał co najmniej {term.min_consecutive_days} "
                f"kolejne dni, z których pierwszy przypadł między {term.first_day_from}. "
                f"a {term.first_day_to}. dniem po porodzie."
            )


def _meets_term_condition(start: dt.date, end: dt.date, birth: dt.date, params: Params) -> bool:
    """At least N consecutive days in hospital, the first of them within the given days."""
    term = params.supplementary.term
    first = max(start, birth + term.first_day_from * DAY)
    return (
        first <= birth + term.first_day_to * DAY
        and first + (term.min_consecutive_days - 1) * DAY <= end
    )


def _merged(scenario: Scenario, birth: dt.date, today: dt.date) -> list[tuple[dt.date, dt.date]]:
    """Hospital stays as inclusive ranges, overlapping ones joined; an open stay runs to today."""
    ranges = []
    for stay in scenario.hospital_stays:
        if stay.start < birth:
            raise ScenarioError(
                f"Pobyt w szpitalu ({fmt(stay.start)}) zaczyna się przed dniem urodzenia "
                f"({fmt(birth)}). Liczy się pobyt dziecka w szpitalu po porodzie."
            )
        if stay.start > today:
            raise ScenarioError(
                f"Pobyt w szpitalu od {fmt(stay.start)} jest w przyszłości (dziś {fmt(today)})."
            )
        ranges.append((stay.start, stay.end or today))
    ranges.sort()
    merged: list[tuple[dt.date, dt.date]] = []
    for start, end in ranges:
        if merged and start <= merged[-1][1] + DAY:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return merged
