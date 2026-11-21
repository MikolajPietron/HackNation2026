"""Chat assistant on Pydantic AI.

The assistant runs the interview. Its tools change the `Scenario`, the deterministic engine
rebuilds the `Timeline`, and every change is emitted into the run's event stream
(`TimelineUpdated`, `ElementFocused`), so the UI redraws the timeline while the assistant
explains it. The model never computes dates.
"""

import datetime as dt
from dataclasses import dataclass, field
from typing import Annotated, Any, Literal

from pydantic import Field
from pydantic_ai import Agent, CustomEvent, ModelRetry, RunContext, UsageLimits
from pydantic_ai.capabilities import PrepareTools
from pydantic_ai.tools import ToolDefinition

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
from app.engine.models import (
    BirthWeek,
    ChildLoss,
    HospitalStay,
    JobLoss,
    MotherEvent,
    PayerSize,
    Work,
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
    answers_allowed: bool = True
    """False in a turn started by the app, not the user: nothing the parent said can be saved."""


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


# In a turn the app started (the timeline appeared), the parent has answered nothing: the model
# may only point at the timeline, never record an answer on the parent's behalf.
EXPLAIN_ONLY = {"explain_timeline_element"}


def _tools_for_turn(
    ctx: RunContext[AssistantDeps], tool_defs: list[ToolDefinition]
) -> list[ToolDefinition]:
    if ctx.deps.answers_allowed:
        return tool_defs
    return [t for t in tool_defs if t.name in EXPLAIN_ONLY]


assistant = Agent(
    deps_type=AssistantDeps,
    name="przewodnik",
    instructions=STATIC_INSTRUCTIONS,
    retries=2,
    capabilities=[PrepareTools(_tools_for_turn)],
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
    # Nobody can know before the birth whether the child will need hospital, and the mother's
    # special situations (the father takes over maternity leave early) come after the birth.
    scenario = _with(
        ctx,
        child_born=False,
        due_date=due_date,
        hospital_care=None,
        birth_week=None,
        birth_weight_up_to_1000g=None,
        hospital_stays=[],
        losses=[],
        mother_event=None,
        leave_start=None,
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
    changes: dict[str, Any] = {
        "child_born": True,
        "birth_date": birth_date,
        "has_medical_certificate": None,
    }
    before = ctx.deps.scenario
    if not before.child_born and before.due_date and before.leave_before_birth_weeks:
        # The plan counted weeks before the due date; the birth rarely falls on it. The leave
        # counts from its real first day (Labour Code art. 180 § 3); a birth before that day
        # means no leave before the birth (art. 183¹ § 2).
        planned = before.due_date - dt.timedelta(weeks=before.leave_before_birth_weeks)
        if birth_date <= planned:
            changes.update(leave_before_birth_weeks=0, leave_start=None)
        else:
            changes["leave_start"] = planned
    scenario = _with(ctx, **changes)
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

    Call it only with what the user said: a number of weeks, or that the mother works (worked)
    until the birth (0). "I want leave before the birth" without a number is not an answer:
    do not call the tool, ask how many weeks before the due date (at most 6). The tool rejects
    more weeks than the law allows.

    Args:
        weeks: Whole weeks of maternity leave before the birth, as the user said them. 0 = no
            leave before the birth (she works, or worked, until the birth).
    """
    # Weeks the user gives now count back from the birth (or the due date): no stored start.
    changes: dict[str, Any] = {"leave_before_birth_weeks": weeks, "leave_start": None}
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
async def set_father_work(ctx: RunContext[AssistantDeps], work: Work) -> str:
    """Record how the father works. It decides whether he is covered by sickness insurance
    and so what he is entitled to: paternity leave, his part of parental leave, taking over
    maternity leave.

    Args:
        work: "employment" = umowa o pracę (etat), "contract" = umowa zlecenia,
            "business" = własna działalność gospodarcza, "none" = nie pracuje.
    """
    # The father's own answer lives in `work` when he fills in, else in `father_work`.
    field = "work" if ctx.deps.scenario.role == "father" else "father_work"
    changes: dict[str, Any] = {field: work}
    if work in ("employment", "none"):
        changes["father_insured"] = None
    scenario = _with(ctx, **changes)
    return await _apply(ctx, scenario, "paternity", "maternity", "birth", "due-date")


@assistant.tool(sequential=True)
async def set_father_insurance(ctx: RunContext[AssistantDeps], registered: bool) -> str:
    """Father on a contract of mandate or with his own business: record whether he is
    registered for the voluntary sickness insurance (pays the sickness contribution).

    Args:
        registered: True if he is registered for it, False if he is not.
    """
    if ctx.deps.scenario.fathers_work not in ("contract", "business"):
        raise ModelRetry(
            "Dobrowolne ubezpieczenie chorobowe dotyczy umowy zlecenia i własnej działalności. "
            "Najpierw ustal, jak pracuje tata (set_father_work)."
        )
    scenario = _with(ctx, father_insured=registered)
    return await _apply(ctx, scenario, "paternity", "maternity", "birth", "due-date")


@assistant.tool(sequential=True)
async def set_father_takeover(
    ctx: RunContext[AssistantDeps], takes_over: bool, mother_weeks: int | None = None
) -> str:
    """Record that the father takes over the rest of maternity leave once the mother has used
    the minimum after the birth (or, False, that he does not: a correction). Before or after
    the birth: the mother may apply for only the minimum straight away. Call it only when the
    user says so; never ask about it. A mother who is ill, in hospital, died or abandoned the
    child is a special situation: `set_mother_situation`.

    Args:
        takes_over: True if the father takes over the rest of maternity leave.
        mother_weeks: Weeks of maternity leave after the birth the mother uses before he takes
            over, only if the user said how many. Leave it empty for the minimum.
    """
    minimum = ctx.deps.params.father.takeover_after_weeks.value
    if takes_over and mother_weeks is not None and mother_weeks < minimum:
        raise ModelRetry(
            f"Mama musi wykorzystać po porodzie co najmniej {minimum} tygodni urlopu "
            "macierzyńskiego, zanim tata przejmie dalszą część. Wcześniej tata przejmuje urlop "
            "tylko w sytuacjach szczególnych (set_mother_situation)."
        )
    scenario = _with(
        ctx,
        father_takes_over=takes_over,
        mother_weeks_before_takeover=mother_weeks if takes_over else None,
    )
    return await _apply(ctx, scenario, "maternity-father", "maternity")


@assistant.tool(sequential=True)
async def set_mother_situation(
    ctx: RunContext[AssistantDeps], situation: MotherEvent | None
) -> str:
    """Born child: record a special situation in which the father takes over maternity leave
    earlier. Call it only when the user says so; never ask about it. Use the dates the user
    gave; ask gently for a missing one.

    Args:
        situation: {"kind": "incapacity", "start": the day the father takes over} = the mother
            has a certificate of inability to live independently (orzeczenie o niezdolności do
            samodzielnej egzystencji); {"kind": "hospital", "start": first day, "end": last
            day} = she is in hospital and cannot look after the child (no `end` = still
            there); {"kind": "death", "start": the day she died}; {"kind": "abandonment",
            "start": the day she abandoned the child}. Null corrects an earlier answer.
    """
    if not ctx.deps.scenario.child_born:
        raise ModelRetry(
            "Najpierw zapisz datę porodu (set_birth_date): tata przejmuje urlop macierzyński "
            "w takiej sytuacji dopiero po porodzie."
        )
    scenario = _with(ctx, mother_event=None if situation is None else situation.model_dump())
    return await _apply(ctx, scenario, "maternity-father", "maternity")


@assistant.tool(sequential=True)
async def set_za_zyciem(ctx: RunContext[AssistantDeps], has_certificate: bool) -> str:
    """Record whether the child has the "Za życiem" certificate; it lengthens parental leave.
    Call it only when the user says so: never ask about it yourself.

    Args:
        has_certificate: True if the child has the certificate.
    """
    return await _apply(ctx, _with(ctx, za_zyciem=has_certificate), "parental")


@assistant.tool(sequential=True)
async def set_child_loss(ctx: RunContext[AssistantDeps], losses: list[ChildLoss]) -> str:
    """Record that a child of this birth was stillborn or died. Call it only when the user says
    so; never ask about it. With several children born at once, one entry per child who died.

    Args:
        losses: One entry per child: {"stillborn": true} for a stillborn child, or
            {"died_on": "YYYY-MM-DD"} for a child who died after being born alive.
            An empty list corrects an earlier answer.
    """
    if not ctx.deps.scenario.child_born:
        raise ModelRetry(
            "Najpierw zapisz datę porodu (set_birth_date): zasady liczą się od dnia porodu."
        )
    scenario = _with(ctx, losses=[loss.model_dump() for loss in losses])
    return await _apply(ctx, scenario, "maternity", "birth")


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


# Applications and protection (guide A.4, I).


@assistant.tool(sequential=True)
async def set_payer_size(
    ctx: RunContext[AssistantDeps], parent: Literal["mother", "father"], size: PayerSize
) -> str:
    """Record whether the employer (or the principal of a contract of mandate) of the mother or
    the father reports more than 20 people to sickness insurance. It decides who pays the
    benefit (the payer or ZUS) and where the request goes. Only for employment or a contract
    of mandate: with her (his) own business the request goes straight to ZUS.

    Args:
        parent: "mother" or "father": whose employer (principal) it is.
        size: "over-20" = more than 20 people, "up-to-20" = 20 or fewer, "unknown" = the user
            does not know.
    """
    work = ctx.deps.scenario.mothers_work if parent == "mother" else ctx.deps.scenario.fathers_work
    if work not in ("employment", "contract"):
        whose, who = ("mamy", "mama") if parent == "mother" else ("taty", "tata")
        raise ModelRetry(
            f"To pytanie dotyczy pracodawcy albo zleceniodawcy {whose}, a {who} nie pracuje na "
            "etacie ani na umowie zlecenia (przy własnej firmie wniosek ZAM idzie prosto do ZUS)."
        )
    scenario = _with(ctx, **{f"{parent}_payer_size": size})
    focus = (
        ("maternity-request", "maternity")
        if parent == "mother"
        else ("paternity-request", "father-benefit-request", "paternity")
    )
    return await _apply(ctx, scenario, *focus)


# Pregnancy (guide pages 2-4 and section H): sick leave, losing the job, risks.

SICK_LEAVE_FOCUS = ("sick-pay", "sick-benefit", "sick-benefit-right")


@assistant.tool(sequential=True)
async def set_sick_leave(
    ctx: RunContext[AssistantDeps],
    on_sick_leave: bool,
    start: dt.date | None = None,
    end: dt.date | None = None,
) -> str:
    """Record whether the mother is (or was) on sick leave (e-ZLA) in this pregnancy, and when.

    Args:
        on_sick_leave: False if she is not and was not on sick leave in this pregnancy.
        start: The first day of the sick leave, as the user gave it.
        end: The last day of the sick leave as the user gave it. Leave it empty when it lasts
            until the birth or the user does not know the end yet.
    """
    scenario = ctx.deps.scenario
    if on_sick_leave and start is None:
        raise ModelRetry("Potrzebna jest data początku zwolnienia lekarskiego: dopytaj o nią.")
    if on_sick_leave and scenario.mothers_work is None:
        raise ModelRetry(
            "Najpierw ustal, jak pracuje mama (set_mother_work): od tego zależy, kto płaci za "
            "zwolnienie lekarskie."
        )
    changes: dict[str, Any] = {
        "sick_leave": on_sick_leave,
        "sick_leave_start": start if on_sick_leave else None,
        "sick_leave_end": end if on_sick_leave else None,
    }
    if not on_sick_leave:
        changes["mother_over_50"] = None
    return await _apply(ctx, _with(ctx, **changes), *SICK_LEAVE_FOCUS)


@assistant.tool(sequential=True)
async def set_insured_since(
    ctx: RunContext[AssistantDeps],
    since: dt.date | None = None,
    started_in_pregnancy: bool | None = None,
) -> str:
    """Record since when the mother is covered by sickness insurance without a break (the day
    her employment contract, contract of mandate or business began, or she registered for the
    voluntary insurance), and whether it began in this pregnancy. Give what the user said; the
    other argument stays as it was.

    Args:
        since: The first day of her uninterrupted sickness insurance.
        started_in_pregnancy: True only if the user said the contract or business began during
            this pregnancy; never ask about it.
    """
    if since is None and started_in_pregnancy is None:
        raise ModelRetry(
            "Podaj datę początku ubezpieczenia albo to, co użytkownik o nim powiedział."
        )
    changes: dict[str, Any] = {}
    if since is not None:
        changes["insured_since"] = since
    if started_in_pregnancy is not None:
        changes["insured_in_pregnancy"] = started_in_pregnancy
    return await _apply(ctx, _with(ctx, **changes), "sick-benefit-right", *SICK_LEAVE_FOCUS)


@assistant.tool(sequential=True)
async def set_mother_over_50(ctx: RunContext[AssistantDeps], over_50: bool) -> str:
    """Record whether the mother turned 50 before the calendar year in which her sick leave
    began: the employer then pays for fewer days of sick leave.

    Args:
        over_50: True if she turned 50 before that year.
    """
    return await _apply(ctx, _with(ctx, mother_over_50=over_50), *SICK_LEAVE_FOCUS)


@assistant.tool(sequential=True)
async def set_job_loss(ctx: RunContext[AssistantDeps], job_loss: JobLoss | None) -> str:
    """Record that the mother's work ended during this pregnancy, and why. Call it only when the
    user says so; never ask about it. If she now works elsewhere, record her work instead
    (set_mother_work).

    Args:
        job_loss: {"ended_on": the last day of work, "reason": ...}. Reasons: "bankruptcy" =
            the employer went bankrupt, "liquidation" = the employer was liquidated,
            "employer-death" = the employer died, "unlawful" = the employment contract was
            terminated in breach of the law (then "court_confirmed": true if a final court
            judgment confirmed it, false if not or not yet, empty if unknown), "other" = any
            other end of work (a contract that ended, she quit, a business closed). Null
            corrects an earlier answer.
    """
    reason = job_loss.reason if job_loss is not None else None
    work = ctx.deps.scenario.mothers_work
    if reason not in (None, "other") and work not in ("employment", None):
        raise ModelRetry(
            "Ta przyczyna dotyczy rozwiązania umowy o pracę, a mama nie pracowała na umowie "
            "o pracę: zapisz koniec pracy z przyczyną „other”."
        )
    scenario = _with(ctx, job_loss=None if job_loss is None else job_loss.model_dump())
    return await _apply(ctx, scenario, "job-loss-benefit", "birth", "due-date")


@assistant.tool(sequential=True)
async def set_contribution_base_raised(ctx: RunContext[AssistantDeps], raised: bool) -> str:
    """Record that the mother raised the base of her social insurance contributions during this
    pregnancy (or, False, that she did not: a correction). Call it only when the user says so;
    never ask about it.

    Args:
        raised: True if the contribution base was raised during the pregnancy.
    """
    return await _apply(ctx, _with(ctx, contribution_base_raised=raised))
