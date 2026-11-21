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
    describe_note_changes,
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
    changed_note_ids,
)
from app.engine.models import BirthWeek, HospitalStay, Work
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
    changed_notes: list[str] = field(default_factory=list)
    """Points of the case explanation that are new or reworded."""
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


async def _apply(ctx: RunContext[AssistantDeps], scenario: Scenario, *focus: str) -> str:
    """Rebuild the timeline, push it to the UI and tell the model what it looks like now.
    `focus`: element ids to scroll to, the first one that is on the new timeline wins."""
    deps = ctx.deps
    timeline = None
    if scenario.anchor_date is not None:
        try:
            timeline = build_timeline(scenario, deps.params, deps.today)
        except ScenarioError as exc:
            raise ModelRetry(f"Nie zmieniono osi: {exc}") from exc
    shown = next((i for i in focus if timeline and timeline.element(i)), None)
    old = deps.timeline
    changed = changed_element_ids(old, timeline) if timeline else []
    changed_notes = changed_note_ids(old, timeline) if timeline else []
    deps.scenario, deps.timeline = scenario, timeline
    await ctx.emit(
        TimelineUpdated(
            scenario=scenario,
            timeline=timeline,
            changed=changed,
            changed_notes=changed_notes,
            focus=shown,
        )
    )
    if timeline is None:
        return f"Zapisane. Oś pojawi się po ustawieniu daty. {describe_interview(scenario)}"
    return "\n\n".join(
        [
            describe_timeline(timeline, changed),
            describe_note_changes(timeline, None if old is None else changed_notes),
            describe_interview(scenario),
        ]
    )


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
    # Nobody can know before the birth whether the child will need hospital.
    scenario = _with(
        ctx,
        child_born=False,
        due_date=due_date,
        hospital_care=None,
        birth_week=None,
        birth_weight_up_to_1000g=None,
        hospital_stays=[],
    )
    return await _apply(ctx, scenario, "due-date")


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
    return await _apply(ctx, scenario, "birth")


@assistant.tool(sequential=True)
async def set_children_count(
    ctx: RunContext[AssistantDeps], count: Annotated[int, Field(ge=1, le=10)]
) -> str:
    """Set how many children are (or will be) born in one delivery (2 = twins).

    Args:
        count: Number of children born in one delivery.
    """
    return await _apply(ctx, _with(ctx, children_count=count), "maternity")


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
    scenario = _with(ctx, **changes)
    return await _apply(ctx, scenario, "maternity-prenatal", "work-until-birth", "birth")


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
    return await _apply(ctx, scenario, "medical-certificate")


@assistant.tool(sequential=True)
async def set_mother_work(ctx: RunContext[AssistantDeps], work: Work) -> str:
    """Record how the mother works. It decides whether she is covered by sickness insurance
    and so has the right to the maternity benefit.

    Args:
        work: "employment" = umowa o pracę (etat), "contract" = umowa zlecenia,
            "business" = własna działalność gospodarcza, "none" = nie pracuje.
    """
    # The mother's own answer lives in `work` when she fills in, else in `mother_work`.
    field = "work" if ctx.deps.scenario.role == "mother" else "mother_work"
    changes: dict[str, Any] = {field: work}
    if work in ("employment", "none"):
        changes["mother_insured"] = None
    return await _apply(ctx, _with(ctx, **changes), "maternity", "birth", "due-date")


@assistant.tool(sequential=True)
async def set_voluntary_insurance(ctx: RunContext[AssistantDeps], registered: bool) -> str:
    """Mother on a contract of mandate or with her own business: record whether she is
    registered for the voluntary sickness insurance (pays the sickness contribution).

    Args:
        registered: True if she is registered for it, False if she is not.
    """
    if ctx.deps.scenario.mothers_work not in ("contract", "business"):
        raise ModelRetry(
            "Dobrowolne ubezpieczenie chorobowe dotyczy umowy zlecenia i własnej działalności. "
            "Najpierw ustal, jak pracuje mama (set_mother_work)."
        )
    scenario = _with(ctx, mother_insured=registered)
    return await _apply(ctx, scenario, "maternity", "birth", "due-date")


@assistant.tool(sequential=True)
async def set_za_zyciem(ctx: RunContext[AssistantDeps], has_certificate: bool) -> str:
    """Record whether the child has the "Za życiem" certificate; it lengthens parental leave.
    Call it only when the user says so: never ask about it yourself.

    Args:
        has_certificate: True if the child has the certificate.
    """
    return await _apply(ctx, _with(ctx, za_zyciem=has_certificate), "parental")


@assistant.tool(sequential=True)
async def set_hospital_care(
    ctx: RunContext[AssistantDeps],
    applies: bool,
    birth_week: BirthWeek | None = None,
    weight_up_to_1000g: bool | None = None,
    hospital_stays: list[HospitalStay] | None = None,
) -> str:
    """Born child: record whether it was born prematurely or stayed in hospital after the
    birth, and the facts supplementary maternity leave depends on. With several children born
    at once: the weight of the lightest and the stay of the one that stayed longest.

    Args:
        applies: False if the child was born at term and was not in hospital; then leave the
            rest empty. True otherwise.
        birth_week: When the child was born: "before-28" = before the end of the 28th week of
            pregnancy, "28-37" = after the 28th and before the end of the 37th week,
            "after-37" = after the end of the 37th week.
        weight_up_to_1000g: True if the birth weight was 1000 g or less.
        hospital_stays: Every stay in hospital after the birth: first and last day. A child that
            was in hospital from the birth starts on the date of birth. No `end` = still there.
    """
    if not ctx.deps.scenario.child_born:
        raise ModelRetry(
            "Dziecko jeszcze się nie urodziło. Uzupełniający urlop macierzyński da się policzyć "
            "dopiero po porodzie."
        )
    if not applies:
        scenario = _with(
            ctx,
            hospital_care=False,
            birth_week=None,
            birth_weight_up_to_1000g=None,
            hospital_stays=[],
        )
        return await _apply(ctx, scenario, "parental", "maternity")
    scenario = _with(
        ctx,
        hospital_care=True,
        birth_week=birth_week,
        birth_weight_up_to_1000g=weight_up_to_1000g,
        hospital_stays=[stay.model_dump() for stay in hospital_stays or []],
    )
    return await _apply(ctx, scenario, "supplementary", "maternity")


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
