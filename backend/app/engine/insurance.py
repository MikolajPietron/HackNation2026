"""Is the mother covered by sickness insurance? Guide point "Urodzenie dziecka": after the birth
the insured woman acquires the right to the maternity benefit.

The guide names two kinds of sickness insurance: obligatory (e.g. an employment contract) and
voluntary (e.g. a contract of mandate or a business). So an employed mother is covered by her
contract, a mother on a contract or with a business is covered only if she is registered for the
voluntary insurance, and a mother who does not work is not covered.
"""

from typing import Literal

from app.engine.models import Scenario, Work

Coverage = Literal[
    "obligatory", "voluntary", "not-registered", "not-working", "unknown-work", "unknown-voluntary"
]
"""obligatory = employed; voluntary = registered for the voluntary insurance; not-registered =
contract or business without it; not-working; unknown-work = nobody said how the mother works;
unknown-voluntary = contract or business, registration not established yet."""

INSURED: frozenset[Coverage] = frozenset({"obligatory", "voluntary"})
NOT_INSURED: frozenset[Coverage] = frozenset({"not-registered", "not-working"})


def work_coverage(work: Work | None, insured: bool | None) -> Coverage:
    match work:
        case None:
            return "unknown-work"
        case "employment":
            return "obligatory"
        case "none":
            return "not-working"
        case _:
            if insured is None:
                return "unknown-voluntary"
            return "voluntary" if insured else "not-registered"


def coverage(scenario: Scenario) -> Coverage:
    """The mother's sickness insurance."""
    return work_coverage(scenario.mothers_work, scenario.mother_insured)


def father_coverage(scenario: Scenario) -> Coverage:
    """The father's sickness insurance."""
    return work_coverage(scenario.fathers_work, scenario.father_insured)
