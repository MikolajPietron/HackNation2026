"""Chat assistant on Pydantic AI.

Tools change the `Scenario`, the deterministic engine rebuilds the `Timeline`, and every change is
emitted into the run's event stream (`TimelineUpdated`, `ElementFocused`), so the UI redraws the
timeline while the assistant explains it. The model never computes dates or amounts.
"""

import datetime as dt
from dataclasses import dataclass, field
from typing import Annotated, Any

from pydantic import Field
from pydantic_ai import Agent, CustomEvent, ModelRetry, RunContext, UsageLimits

from app.assistant.describe import describe_element, describe_scenario, describe_timeline
from app.assistant.guide import guide_pages
from app.assistant.prompts import STATIC_INSTRUCTIONS, WEEKDAYS
from app.engine import (
    Params,
    Scenario,
    ScenarioError,
    Timeline,
    build_timeline,
    changed_element_ids,
)
from app.engine.timeline import DAY, add_months, fmt

USAGE_LIMITS = UsageLimits(request_limit=12)

# Plausibility checks for what the parent typed (not legal rules).
EXPECTED_DATE_GRACE = 14 * DAY
EXPECTED_DATE_MAX_MONTHS = 10


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
    head = f"Dzisiaj jest {WEEKDAYS[today.weekday()]}, {fmt(today)}."
    if ctx.deps.timeline is None:
        return f"{head}\n{describe_scenario(ctx.deps.scenario)}"
    return f"{head}\n\nAktualny stan osi czasu:\n{describe_timeline(ctx.deps.timeline)}"


def _with(ctx: RunContext[AssistantDeps], **changes: Any) -> Scenario:
    return Scenario.model_validate({**ctx.deps.scenario.model_dump(), **changes})


async def _apply(ctx: RunContext[AssistantDeps], scenario: Scenario, focus: str | None) -> str:
    """Rebuild the timeline, push it to the UI and tell the model what it looks like now."""
    deps = ctx.deps
    timeline = None
    if scenario.birth_date is not None:
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
        return "Zapisane. Oś czasu pojawi się po ustawieniu daty porodu."
    return describe_timeline(timeline, changed)


@assistant.tool(sequential=True)
async def set_birth_date(
    ctx: RunContext[AssistantDeps], birth_date: dt.date, child_born: bool
) -> str:
    """Set the child's date of birth (or the expected due date) and rebuild the whole timeline.

    Args:
        birth_date: Actual date of birth if the child is born, otherwise the expected due date.
        child_born: True if the child is already born, False if `birth_date` is the due date.
    """
    today = ctx.deps.today
    if child_born and birth_date > today:
        raise ModelRetry(
            f"Nie ustawiono: data urodzenia {fmt(birth_date)} jest w przyszłości (dziś "
            f"{fmt(today)}). Zapytaj, czy to przewidywana data porodu."
        )
    if not child_born and birth_date < today - EXPECTED_DATE_GRACE:
        raise ModelRetry(
            f"Nie ustawiono: przewidywana data porodu {fmt(birth_date)} minęła dawno. "
            "Zapytaj, czy dziecko już się urodziło i kiedy."
        )
    if not child_born and birth_date > add_months(today, EXPECTED_DATE_MAX_MONTHS):
        raise ModelRetry(
            f"Nie ustawiono: {fmt(birth_date)} to ponad {EXPECTED_DATE_MAX_MONTHS} miesięcy "
            "od dziś. Upewnij się, że to przewidywana data porodu (sprawdź rok)."
        )
    parental = ctx.deps.params.parental
    limit = dt.date(birth_date.year + parental.last_year_of_child_age.value, 12, 31)
    if limit < today:
        return (
            f"Nie ustawiono osi: urlop rodzicielski można było wykorzystać do {fmt(limit)}, "
            "więc nie ma już urlopów ani zasiłku macierzyńskiego do zaplanowania."
        )
    scenario = _with(ctx, birth_date=birth_date, child_born=child_born, paternity_start=None)
    return await _apply(ctx, scenario, focus="birth")


@assistant.tool(sequential=True)
async def set_children_count(
    ctx: RunContext[AssistantDeps], count: Annotated[int, Field(ge=1, le=10)]
) -> str:
    """Set how many children are born in one delivery (2 = twins) and rebuild the timeline.

    Args:
        count: Number of children born in one delivery.
    """
    return await _apply(ctx, _with(ctx, children_count=count), focus="maternity")


@assistant.tool(sequential=True)
async def set_maternity_leave_before_birth(
    ctx: RunContext[AssistantDeps], weeks: Annotated[int, Field(ge=0)]
) -> str:
    """Set how many weeks of maternity leave the mother takes before the (expected) birth date.

    0 means she works until the birth. The tool rejects more weeks than the law allows.

    Args:
        weeks: Whole weeks of maternity leave before the birth date.
    """
    focus = "maternity-prenatal" if weeks else "maternity"
    return await _apply(ctx, _with(ctx, maternity_weeks_before_birth=weeks), focus=focus)


@assistant.tool(sequential=True)
async def choose_benefit_variant(ctx: RunContext[AssistantDeps], flat_rate: bool) -> str:
    """Choose how the mother's maternity benefit is paid and rebuild the timeline.

    Args:
        flat_rate: True = one rate for the whole maternity and parental leave (needs a written
            application shortly after the birth, see the `flat-rate-deadline` marker).
            False = the standard rates: higher for maternity leave, lower for parental leave.
    """
    scenario = ctx.deps.scenario
    if flat_rate and scenario.birth_date is not None and scenario.child_born:
        flat = ctx.deps.params.flat_rate
        deadline = scenario.birth_date + flat.application_days_after_birth.value * DAY
        if deadline < ctx.deps.today:
            raise ModelRetry(
                f"Nie zmieniono: termin na wniosek o tę stawkę minął {fmt(deadline)}. "
                "Wyjaśnij to użytkownikowi."
            )
    focus = "flat-rate-deadline" if flat_rate else "maternity"
    return await _apply(ctx, _with(ctx, flat_rate=flat_rate), focus=focus)


@assistant.tool(sequential=True)
async def set_paternity_leave_start(ctx: RunContext[AssistantDeps], start: dt.date) -> str:
    """Set the first day of the father's paternity leave (urlop ojcowski) and rebuild the timeline.

    Args:
        start: First day of the paternity leave.
    """
    if ctx.deps.scenario.birth_date is None:
        raise ModelRetry("Najpierw ustaw datę porodu (set_birth_date).")
    return await _apply(ctx, _with(ctx, paternity_start=start), focus="paternity")


@assistant.tool
async def explain_timeline_element(ctx: RunContext[AssistantDeps], element_id: str) -> str:
    """Highlight one timeline element for the user and get its rules with quotes from the sources.

    Use it whenever you explain a leave, an important day or an application.

    Args:
        element_id: Element id from the timeline description, e.g. "maternity" or "app-paternity".
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


@assistant.tool_plain
async def read_guide(page: int) -> str:
    """Read one page of the ZUS guide for parents (Przewodnik) to answer questions beyond the
    timeline. Quote it with the page number.

    Args:
        page: Page number, see the table of contents in the instructions.
    """
    pages = guide_pages()
    if page not in pages:
        raise ModelRetry(f"Przewodnik ma strony 1–{max(pages)}.")
    return f"Przewodnik, strona {page}:\n\n{pages[page]}"
