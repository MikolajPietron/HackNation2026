"""Chat assistant on Pydantic AI.

The assistant runs the interview. Its tools change the `Scenario`, the deterministic engine
rebuilds the `Timeline`, and every change is emitted into the run's event stream
(`TimelineUpdated`, `ElementFocused`), so the UI redraws the timeline while the assistant
explains it. The model never computes dates.
"""

import datetime as dt
from dataclasses import dataclass, field
from typing import Annotated, Any

from pydantic import Field
from pydantic_ai import Agent, CustomEvent, ModelRetry, RunContext, UsageLimits

from app.assistant.describe import (
    describe_element,
    describe_interview,
    describe_person,
    describe_timeline,
)
from app.assistant.prompts import STATIC_INSTRUCTIONS, WEEKDAYS
from app.engine import (
    Params,
    Scenario,
    ScenarioError,
    Timeline,
    build_timeline,
    changed_element_ids,
)
from app.engine.plausibility import birth_date_problem, due_date_problem
from app.engine.timeline import fmt

USAGE_LIMITS = UsageLimits(request_limit=12)


@dataclass
class AssistantDeps:
    scenario: Scenario
    params: Params
    today: dt.date
    timeline: Timeline | None = None


@dataclass(kw_only=True)
class TimelineUpdated(CustomEvent):
    """The scenario changed; carries the recalculated timeline for the UI."""

    scenario: Scenario
    timeline: Timeline | None
    changed: list[str] = field(default_factory=list)
    focus: str | None = None


@dataclass(kw_only=True)
class ElementFocused(CustomEvent):
    """The assistant is explaining this element; the UI highlights it."""

    element_id: str


assistant = Agent(
    deps_type=AssistantDeps,
    name="przewodnik",
    instructions=STATIC_INSTRUCTIONS,
    retries=2,
)


@assistant.instructions
def current_state(ctx: RunContext[AssistantDeps]) -> str:
    today = ctx.deps.today
    lines = [
        f"Dzisiaj jest {WEEKDAYS[today.weekday()]}, {fmt(today)}.",
        describe_person(ctx.deps.scenario),
        describe_interview(ctx.deps.scenario),
    ]
    if ctx.deps.timeline is None:
        lines.append("Oś czasu jest pusta.")
    else:
        lines += ["", "Aktualny stan osi czasu:", describe_timeline(ctx.deps.timeline)]
    return "\n".join(lines)


def _with(ctx: RunContext[AssistantDeps], **changes: Any) -> Scenario:
    return Scenario.model_validate({**ctx.deps.scenario.model_dump(), **changes})


async def _apply(ctx: RunContext[AssistantDeps], scenario: Scenario, focus: str | None) -> str:
    """Rebuild the timeline, push it to the UI and tell the model what it looks like now."""
    deps = ctx.deps
    timeline = None
    if scenario.anchor_date is not None:
        try:
            timeline = build_timeline(scenario, deps.params, deps.today)
        except ScenarioError as exc:
            raise ModelRetry(f"Nie zmieniono osi: {exc}") from exc
    changed = changed_element_ids(deps.timeline, timeline) if timeline else []
    deps.scenario, deps.timeline = scenario, timeline
    await ctx.emit(
        TimelineUpdated(
            scenario=scenario,
            timeline=timeline,
            changed=changed,
            focus=focus if timeline else None,
        )
    )
    if timeline is None:
        return f"Zapisane. Oś pojawi się po ustawieniu daty. {describe_interview(scenario)}"
    return f"{describe_timeline(timeline, changed)}\n\n{describe_interview(scenario)}"


@assistant.tool(sequential=True)
async def set_due_date(ctx: RunContext[AssistantDeps], due_date: dt.date) -> str:
    """The child is on the way: set the expected due date and rebuild the timeline.

    Args:
        due_date: Expected due date (przewidywana data porodu), e.g. from the pregnancy card.
    """
    problem = due_date_problem(due_date, ctx.deps.today)
    if problem:
        raise ModelRetry(
            f"Nie ustawiono: {problem} Jeśli dziecko już się urodziło, użyj set_birth_date."
        )
    scenario = _with(ctx, child_born=False, due_date=due_date)
    return await _apply(ctx, scenario, focus="due-date")


@assistant.tool(sequential=True)
async def set_birth_date(ctx: RunContext[AssistantDeps], birth_date: dt.date) -> str:
    """The child is already born: set the actual date of birth and rebuild the timeline.

    Args:
        birth_date: Date of birth, e.g. from the birth certificate.
    """
    problem = birth_date_problem(birth_date, ctx.deps.today)
    if problem:
        raise ModelRetry(f"Nie ustawiono: {problem}")
    # The certificate is needed only to start leave before an expected birth.
    scenario = _with(ctx, child_born=True, birth_date=birth_date, has_medical_certificate=None)
    return await _apply(ctx, scenario, focus="birth")


@assistant.tool(sequential=True)
async def set_children_count(
    ctx: RunContext[AssistantDeps], count: Annotated[int, Field(ge=1, le=10)]
) -> str:
    """Set how many children are (or will be) born in one delivery (2 = twins).

    Args:
        count: Number of children born in one delivery.
    """
    return await _apply(ctx, _with(ctx, children_count=count), focus="maternity")


@assistant.tool(sequential=True)
async def set_leave_before_birth(
    ctx: RunContext[AssistantDeps], weeks: Annotated[int, Field(ge=0)]
) -> str:
    """Record maternity leave before the birth: planned (child on the way) or taken (born).

    The tool rejects more weeks than the law allows.

    Args:
        weeks: Whole weeks of maternity leave before the birth. 0 = no leave before the birth
            (she works, or worked, until the birth).
    """
    changes: dict[str, Any] = {"leave_before_birth_weeks": weeks}
    if weeks == 0:
        changes["has_medical_certificate"] = None
    if weeks:
        focus = "maternity-prenatal"
    else:
        focus = "birth" if ctx.deps.scenario.child_born else "work-until-birth"
    return await _apply(ctx, _with(ctx, **changes), focus=focus)


@assistant.tool(sequential=True)
async def set_medical_certificate(ctx: RunContext[AssistantDeps], has_certificate: bool) -> str:
    """Record whether the mother already has the medical certificate of the expected due date.

    Args:
        has_certificate: True if she already has it, False if she still needs to get it.
    """
    if ctx.deps.scenario.child_born:
        raise ModelRetry("Dziecko już się urodziło: zaświadczenie nie jest już potrzebne.")
    if not ctx.deps.scenario.leave_before_birth_weeks:
        raise ModelRetry(
            "Zaświadczenie jest potrzebne tylko do urlopu przed porodem. Najpierw ustal, "
            "czy mama chce taki urlop (set_leave_before_birth)."
        )
    scenario = _with(ctx, has_medical_certificate=has_certificate)
    return await _apply(ctx, scenario, focus="medical-certificate")


@assistant.tool
async def explain_timeline_element(ctx: RunContext[AssistantDeps], element_id: str) -> str:
    """Highlight one timeline element for the user and get its rule with the literal quote.

    Use it whenever you explain something that is on the timeline.

    Args:
        element_id: Element id from the timeline description, e.g. "due-date".
    """
    timeline = ctx.deps.timeline
    if timeline is None:
        raise ModelRetry("Oś czasu jest pusta — najpierw ustaw datę porodu.")
    element = timeline.element(element_id)
    if element is None:
        ids = ", ".join(e.id for e in timeline.elements())
        raise ModelRetry(f"Nie ma elementu „{element_id}”. Dostępne: {ids}.")
    await ctx.emit(ElementFocused(element_id=element_id))
    return describe_element(element)
