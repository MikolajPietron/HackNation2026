"""Parental leave (urlop rodzicielski): how long and until when. Guide point "Urodzenie dziecka"
and section B; Labour Code art. 182¹ᵃ and 182¹ᶜ."""

import datetime as dt

from app.engine.models import Scenario
from app.engine.params import Param, Params


def parental_table(scenario: Scenario, params: Params) -> Param[list[int]]:
    """Weeks for both parents together: [one child, more children]; longer with "Za życiem"."""
    p = params.parental
    return p.weeks_by_children_za_zyciem if scenario.za_zyciem else p.weeks_by_children


def for_children(table: Param[list[int]], count: int | None) -> int:
    return table.value[0 if count == 1 else 1]


def parental_weeks(scenario: Scenario, params: Params) -> tuple[int, int]:
    """Parental leave in weeks: for both parents together and the most the mother can use
    (the weeks that belong to the father alone cannot be passed to her)."""
    total = for_children(parental_table(scenario, params), scenario.children_count)
    return total, total - params.parental.exclusive_weeks.value


def parental_deadline(birth: dt.date, params: Params) -> dt.date:
    """The last day of the calendar year in which the child reaches the age from the rule."""
    return dt.date(birth.year + params.parental.deadline_age.value, 12, 31)
