"""Stillbirth or death of the child: guide section A, point "Szczególna sytuacja" (page 6), and
Labour Code art. 180¹.

- A stillbirth, or a death before the end of 8 weeks of life: maternity leave lasts 8 weeks
  after the birth, but not less than 7 days from the day of death.
- A death after 8 weeks of life: the mother keeps the leave for 7 days from the day of death.
  The Labour Code applies this also to supplementary and parental leave (art. 180² § 7,
  art. 182¹ᵍ).
- More children at once: the leave follows the number of children who live, and (§ 2) not less
  than 7 days from the death.

Our readings, not settled by the materials (CLAUDE.md, open questions):
- 8 weeks of life are 56 days with the day of birth as the first (ZUS handbook: "8. tygodnia
  życia (56 dni)"), so a death on the date of birth + 55 days is still before their end;
- the 7 days are counted from the day after the death, so they end on the date of death + 7;
- the 7 days never make the leave longer than it would have been.
"""

import datetime as dt
from collections.abc import Callable
from dataclasses import dataclass

from app.engine.models import Scenario, ScenarioError
from app.engine.params import Params
from app.engine.wording import fmt

DAY = dt.timedelta(days=1)


@dataclass(frozen=True)
class Loss:
    count: int
    """Children of this birth who were stillborn or died."""
    survivors: int
    last: dt.date
    """The last stillbirth or death."""
    early: bool
    """The last loss came before the end of 8 weeks of life."""
    stillborn: int
    alive_before_last: int
    """Children alive just before the last loss."""

    @property
    def none_survived(self) -> bool:
        return self.survivors == 0

    def until(self, params: Params) -> dt.date:
        """The last day of the 7 days from the day of death."""
        return self.last + params.loss.days_after_death.value * DAY


def child_loss(scenario: Scenario, params: Params, birth: dt.date, today: dt.date) -> Loss | None:
    """The losses of this birth, checked against the dates, or None if there are none."""
    if not scenario.losses or not scenario.child_born:
        return None
    count = scenario.children_count
    if count is not None and len(scenario.losses) > count:
        raise ScenarioError(
            "Podano więcej dzieci, które zmarły, niż urodziło się przy jednym porodzie. "
            "Sprawdź liczbę dzieci."
        )
    dates = []
    for loss in scenario.losses:
        date = birth if loss.stillborn else loss.died_on
        assert date is not None
        if date < birth:
            raise ScenarioError(
                f"Data śmierci dziecka ({fmt(date)}) jest wcześniejsza niż data porodu "
                f"({fmt(birth)}). Sprawdź datę."
            )
        if date > today:
            raise ScenarioError(f"Data {fmt(date)} jest w przyszłości (dziś {fmt(today)}).")
        dates.append(date)
    last = max(dates)
    life = params.loss.life_weeks.value * 7
    born = count if count is not None else len(dates)
    return Loss(
        count=len(dates),
        survivors=born - len(dates),
        last=last,
        early=last <= birth + (life - 1) * DAY,
        stillborn=sum(1 for loss in scenario.losses if loss.stillborn),
        alive_before_last=born - sum(1 for date in dates if date < last),
    )


def maternity_end_after_loss(
    loss: Loss, params: Params, birth: dt.date, end_for: Callable[[int], dt.date]
) -> dt.date:
    """The last day of maternity leave after a loss; `end_for(n)` is the last day of the leave
    as it would be for n children."""
    until = loss.until(params)
    if loss.survivors:
        born = loss.count + loss.survivors
        return min(end_for(born), max(end_for(loss.survivors), until))
    if loss.early:
        weeks = params.loss.weeks_after_birth.value
        return max(birth + (weeks * 7 - 1) * DAY, until)
    return min(end_for(loss.alive_before_last), until)
