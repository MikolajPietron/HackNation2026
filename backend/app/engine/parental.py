"""Parental leave (urlop rodzicielski): how long and until when. Guide point "Urodzenie dziecka"
and section B; Labour Code art. 182¹ᵃ and 182¹ᶜ."""

import datetime as dt

from app.engine.models import Marker, Scenario
from app.engine.params import Param, Params
from app.engine.wording import fmt


def parental_table(scenario: Scenario, params: Params) -> Param[list[int]]:
    """Weeks for both parents together: [one child, more children]; longer with "Za życiem"."""
    p = params.parental
    return p.weeks_by_children_za_zyciem if scenario.za_zyciem else p.weeks_by_children


def for_children(table: Param[list[int]], count: int | None) -> int:
    return table.value[0 if count == 1 else 1]


def parental_weeks(scenario: Scenario, params: Params) -> tuple[int, int]:
    """Parental leave in weeks: for both parents together and the most one parent can use
    (the weeks that belong to the other parent alone cannot be passed on)."""
    total = for_children(parental_table(scenario, params), scenario.children_count)
    return total, total - params.parental.exclusive_weeks.value


def parental_deadline(birth: dt.date, params: Params) -> dt.date:
    """The last day of the calendar year in which the child reaches the age from the rule."""
    return dt.date(birth.year + params.parental.deadline_age.value, 12, 31)


def deadline_passed(deadline: dt.date, params: Params) -> str:
    """The warning when the time for parental leave is over."""
    return (
        f"Czas na urlop rodzicielski minął {fmt(deadline)}: to koniec roku kalendarzowego, "
        f"w którym dziecko skończyło {params.parental.deadline_age.value} lat."
    )


def deadline_marker(birth: dt.date, born: bool, params: Params) -> Marker:
    """The last day for parental leave, on the child's lane."""
    p = params.parental
    estimate = [] if born else ["Liczymy od przewidywanej daty porodu."]
    if not born and birth.month in (1, 12):
        estimate.append(
            "Gdyby dziecko urodziło się w innym roku kalendarzowym niż przewidywany, ten dzień "
            "przesunie się o rok."
        )
    return Marker(
        id="parental-deadline",
        lane="child",
        label="Rodzicielski najpóźniej do",
        title="Koniec czasu na urlop rodzicielski",
        date=parental_deadline(birth, params),
        summary=(
            "Urlop rodzicielski można wykorzystać najpóźniej do końca roku kalendarzowego, "
            f"w którym dziecko kończy {p.deadline_age.value} lat."
        ),
        details=estimate,
        sources=p.deadline_age.sources,
    )
