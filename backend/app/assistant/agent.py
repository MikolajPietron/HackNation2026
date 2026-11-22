"""Chat assistant on Pydantic AI.

The assistant runs the interview. Its tools change the `Scenario`, the deterministic engine
rebuilds the `Timeline`, and every change is emitted into the run's event stream
(`TimelineUpdated`, `ElementFocused`), so the UI redraws the timeline while the assistant
explains it. The model never computes dates.
"""

import datetime as dt
from dataclasses import dataclass, field
from typing import Annotated, Any, Literal

from pydantic import Field, ValidationError
from pydantic_ai import Agent, CustomEvent, ModelRetry, RunContext, UsageLimits
from pydantic_ai.capabilities import AbstractCapability, PrepareTools, RetryOnModelErrors
from pydantic_ai.settings import ModelSettings
from pydantic_ai.tools import ToolDefinition

from app.assistant.describe import (
    describe_element,
    describe_interview,
    describe_note_changes,
    describe_person,
    describe_timeline,
    describe_timeline_changes,
)
from app.assistant.describe_plans import describe_plans, describe_stress
from app.assistant.prompts import (
    BASE_INSTRUCTIONS,
    WEEKDAYS,
    late_instructions,
    stage_instructions,
)
from app.assistant.stage import Topic, hidden_tools, stage_topics
from app.engine import (
    Params,
    Scenario,
    ScenarioError,
    Timeline,
    build_timeline,
    changed_element_ids,
    changed_note_ids,
)
from app.engine.insurance import NOT_INSURED, coverage, father_coverage
from app.engine.models import (
    BirthWeek,
    ChildLoss,
    HospitalStay,
    JobLoss,
    MotherEvent,
    ParentalPart,
    PayerSize,
    PayHistory,
    PayMonth,
    RehabStatus,
    Role,
    TakenIn,
    Work,
)
from app.engine.money import pay_matters, requester_cover
from app.engine.parental_plan import default_part, part_ids
from app.engine.plans import Goal
from app.engine.plans import propose_plans as plans_for_goal
from app.engine.plausibility import (
    birth_date_problem,
    child_birth_problem,
    due_date_problem,
    taken_in_problem,
)
from app.engine.stress import stress_test as run_stress_test
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
    """Before every request: only the tools that can apply now (stage.hidden_tools). A child taken
    in has nothing about pregnancy or the birth, a child on the way nothing that needs the date
    of birth; a tool comes back as soon as a fact recorded in this turn makes it apply."""
    if not ctx.deps.answers_allowed:
        return [t for t in tool_defs if t.name in EXPLAIN_ONLY]
    hidden = hidden_tools(ctx.deps.scenario, ctx.deps.timeline)
    return [t for t in tool_defs if t.name not in hidden]


MAX_TOKENS = 4096
"""Output cap of one answer, thinking included: a few short sentences ("Styl odpowiedzi") need a
few hundred tokens, a plan list or a calm answer after a loss a few more; the cap only stops a
runaway answer."""
EVENT_MAX_TOKENS = 2048
"""The welcome after the onboarding: at most three short sentences and one highlight."""


def _turn_settings(ctx: RunContext[AssistantDeps]) -> ModelSettings:
    """No long thinking (ZADANIA B.17): the engine computes, the model only records and explains.
    `LLM_THINKING` still sets it for answers; the welcome turn thinks "low" — not "minimal",
    which Gemini Flash refuses with 400 (found by the real-model eval, 22.11.2026)."""
    if not ctx.deps.answers_allowed:
        return ModelSettings(thinking="low", max_tokens=EVENT_MAX_TOKENS)
    thinking = (ctx.model_settings or {}).get("thinking") or "low"
    return ModelSettings(thinking=thinking, max_tokens=MAX_TOKENS)


@dataclass
class StageInstructions(AbstractCapability[AssistantDeps]):
    """The instructions and literal sources for the family's stage, and the turn's settings.

    The stage is read when the turn starts and its text is static, so it follows
    `BASE_INSTRUCTIONS` in the cached prefix: turns of one stage send the same prefix. When a
    tool moves the family to another stage during the turn (the birth, a loss, an amount),
    `late_instructions` adds what the new stage needs for the rest of the turn, after the prefix.
    """

    topics: frozenset[Topic] = frozenset()

    async def for_run(self, ctx: RunContext[AssistantDeps]) -> "StageInstructions":
        return StageInstructions(topics=stage_topics(ctx.deps.scenario))

    def get_instructions(self) -> Any:
        if not self.topics:  # the agent's own instance, before any run
            return None
        return [stage_instructions(self.topics), self.late]

    def late(self, ctx: RunContext[AssistantDeps]) -> str:
        return late_instructions(self.topics, stage_topics(ctx.deps.scenario))

    def get_model_settings(self) -> Any:
        return _turn_settings


assistant = Agent(
    deps_type=AssistantDeps,
    name="przewodnik",
    instructions=BASE_INSTRUCTIONS,
    retries=2,
    capabilities=[
        PrepareTools(_tools_for_turn),
        StageInstructions(),
        # A rate limit or a network error: one more attempt after a short wait, then the chat
        # shows a short Polish message (api/chat.py). The SDKs' own retries are off (deps.py).
        RetryOnModelErrors(max_attempts=2, initial_delay=1.0, max_delay=10.0),
    ],
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
    # Only what changed: the whole timeline is in the current state, rebuilt before the next
    # request (`current_state`), and a tool result stays in the history for every later turn.
    return "\n\n".join(
        [
            describe_timeline_changes(old, timeline, changed),
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
        taken_in=None,
        taken_in_on=None,
        school_postponed=None,
        adoption_final=None,
        adoption_final_on=None,
        taken_in_handover=None,
        taken_in_handover_after_weeks=None,
        foster_before=None,
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
    at once: the weight of the lightest and the stay of the one that stayed longest. A child
    taken in for upbringing: whether it was in hospital after being taken in; give its stays as
    the user told them (the calculator counts only the days from the day of taking in).

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
        return await _apply(ctx, scenario, "parental", "maternity", "adoption-leave")
    scenario = _with(
        ctx,
        hospital_care=True,
        birth_week=birth_week,
        birth_weight_up_to_1000g=weight_up_to_1000g,
        hospital_stays=[stay.model_dump() for stay in hospital_stays or []],
    )
    return await _apply(ctx, scenario, "supplementary", "maternity", "adoption-leave")


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
    return describe_element(element, timeline.today)


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
        changes.update(mother_over_50=None, rehab_benefit=None, rehab_benefit_end=None)
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


@assistant.tool(sequential=True)
async def set_rehab_benefit(
    ctx: RunContext[AssistantDeps], status: RehabStatus | None, end: dt.date | None = None
) -> str:
    """Record what the user said about the rehabilitation benefit (świadczenie rehabilitacyjne)
    after the sickness benefit in pregnancy ran out (270 days). Call it only when the user says
    so; never ask about it.

    Args:
        status: "applied" = she applied for it and there is no decision yet; "granted" = it was
            granted; "refused" = it was refused. Null corrects an earlier answer.
        end: The last day of the period it was granted (or applied) for, only if the user gave
            it.
    """
    timeline = ctx.deps.timeline
    if status is not None and (timeline is None or timeline.element("sick-benefit-limit") is None):
        raise ModelRetry(
            "Świadczenie rehabilitacyjne przysługuje po wyczerpaniu zasiłku chorobowego (w ciąży "
            "270 dni), a zwolnienie lekarskie na osi go nie wyczerpuje. Najpierw ustal zwolnienie "
            "lekarskie w ciąży (set_sick_leave): od kiedy i do kiedy trwa."
        )
    scenario = _with(ctx, rehab_benefit=status, rehab_benefit_end=end if status else None)
    return await _apply(ctx, scenario, "rehab-benefit", "sick-benefit-limit")


# Parental leave with work (guide sections E and B.3).


@assistant.tool(sequential=True)
async def set_parental_plan(ctx: RunContext[AssistantDeps], parts: list[ParentalPart]) -> str:
    """Record how the parents split parental leave: who takes how many weeks, in which order,
    at the same time or one after the other, and where one of them works part-time. Call it
    only when the user says so; never ask about it. Give the whole plan every time: it replaces
    the previous one. An empty list removes the plan.

    Args:
        parts: The parts in the order the parents take them (at most 5 for both together).
            Each: {"parent": "mother" or "father"; "weeks": weeks of leave taken from the pool,
            without the extension from work; "start": "YYYY-MM-DD" only if the user gave that
            date (empty = right after the previous part; the first part: where the timeline
            shows that parent's parental leave); "with_previous": true = starts on the same day
            as the previous part (both parents at once); "work_fraction": part of full time
            worked during this part, e.g. "1/2" (empty = no work); "work_weeks": weeks of work
            from the first day of the part, only if the user said (empty = the whole part)}.
    """
    if ctx.deps.scenario.children_count is None:
        raise ModelRetry(
            "Najpierw ustal liczbę dzieci (set_children_count): od niej zależy wymiar urlopu "
            "rodzicielskiego."
        )
    scenario = _with(ctx, parental_parts=[part.model_dump() for part in parts])
    return await _apply(ctx, scenario, *part_ids(parts), "parental", "parental-father")


@assistant.tool(sequential=True)
async def set_parental_work(
    ctx: RunContext[AssistantDeps],
    parent: Role,
    work_fraction: str | None,
    weeks: int | None = None,
    part: int | None = None,
) -> str:
    """Record that the mother or the father works part-time during parental leave (or, with an
    empty work_fraction, that they do not: a correction). Call it only when the user says so;
    never ask about it. The calculator extends the leave and computes every date. Without a
    plan, that parent's whole share of parental leave becomes the part they work in.

    Args:
        parent: "mother" or "father".
        work_fraction: Part of full time, as the user said it: "1/2", "1/4", "0.4", "40%".
            Empty = no work during parental leave.
        weeks: Weeks of work, from the first day of that part of the leave, only if the user
            said how many (empty = all of it).
        part: Which of that parent's parts of the plan (1 = the first), only when the plan has
            more than one part for that parent.
    """
    deps = ctx.deps
    if deps.scenario.children_count is None or deps.timeline is None:
        raise ModelRetry(
            "Najpierw ustal datę porodu i liczbę dzieci: od nich zależy urlop rodzicielski."
        )
    who = "Mama" if parent == "mother" else "Tata"
    parts = list(deps.scenario.parental_parts)
    own = [i for i, p in enumerate(parts) if p.parent == parent]
    if not own:
        if work_fraction is None:
            raise ModelRetry(
                f"{who} nie ma w planie urlopu rodzicielskiego: nie ma czego zmieniać."
            )
        try:
            parts.append(default_part(deps.scenario, deps.params, deps.timeline, parent))
        except ScenarioError as exc:
            raise ModelRetry(f"Nie zmieniono osi: {exc}") from exc
        own = [len(parts) - 1]
    if part is None and len(own) > 1:
        raise ModelRetry(
            f"{who} ma w planie {len(own)} części urlopu rodzicielskiego: podaj, w której "
            "pracuje (part)."
        )
    number = part or 1
    if not 1 <= number <= len(own):
        raise ModelRetry(f"{who} ma w planie {len(own)} części urlopu rodzicielskiego.")
    index = own[number - 1]
    try:
        parts[index] = ParentalPart.model_validate(
            {
                **parts[index].model_dump(),
                "work_fraction": work_fraction,
                "work_weeks": weeks if work_fraction is not None else None,
            }
        )
    except ValidationError as exc:
        raise ModelRetry(
            "Nie rozumiem wymiaru pracy albo liczby tygodni. Podaj wymiar jako ułamek etatu, "
            "np. „1/2”, a tygodnie jako liczbę całkowitą."
        ) from exc
    scenario = _with(ctx, parental_parts=[p.model_dump() for p in parts])
    return await _apply(ctx, scenario, part_ids(parts)[index])


# Guide section D: a child taken in for upbringing (adoption, non-professional foster family).


@assistant.tool(sequential=True)
async def set_taken_in(
    ctx: RunContext[AssistantDeps],
    kind: TakenIn | None,
    taken_in_on: dt.date | None = None,
    child_birth_date: dt.date | None = None,
) -> str:
    """The child was taken in for upbringing, not born to this family: record how, the day of
    taking in and the child's date of birth (any of them may come later; give what the user
    said). Pregnancy and the birth no longer apply. Null `kind` corrects an earlier answer: the
    child was born to the family after all.

    Args:
        kind: "adoption" = took the child in and asked the guardianship court to start adoption
            proceedings; "foster" = a non-professional foster family (rodzina zastępcza
            niezawodowa). Null = not taken in.
        taken_in_on: The day the child was taken in; for adoption the day the child was taken in
            and the court application filed, the later of the two.
        child_birth_date: The child's date of birth (with several children: the youngest's).
    """
    today = ctx.deps.today
    if kind is None:
        scenario = _with(
            ctx,
            taken_in=None,
            taken_in_on=None,
            school_postponed=None,
            adoption_final=None,
            adoption_final_on=None,
            taken_in_handover=None,
            taken_in_handover_after_weeks=None,
            foster_before=None,
        )
        return await _apply(ctx, scenario, "birth", "due-date")
    problem = (taken_in_on and taken_in_problem(taken_in_on, today)) or (
        child_birth_date and child_birth_problem(child_birth_date, today)
    )
    if problem:
        raise ModelRetry(f"Nie ustawiono: {problem}")
    before = ctx.deps.scenario
    changes: dict[str, Any] = {"taken_in": kind, "child_born": True, "due_date": None}
    if before.taken_in is None:
        # Nothing about pregnancy or the birth applies to a child taken in. A hospital stay
        # told on this path (supplementary leave, art. 183 § 3¹) stays when the path goes on.
        changes.update(
            leave_before_birth_weeks=None,
            has_medical_certificate=None,
            leave_start=None,
            hospital_care=None,
            birth_week=None,
            birth_weight_up_to_1000g=None,
            hospital_stays=[],
            losses=[],
            father_takes_over=None,
            mother_weeks_before_takeover=None,
            mother_event=None,
            rehab_benefit=None,
            rehab_benefit_end=None,
        )
    if kind != before.taken_in:
        changes.update(school_postponed=None, adoption_final=None, adoption_final_on=None)
        if kind != "adoption":
            changes.update(foster_before=None)
    if taken_in_on is not None:
        changes["taken_in_on"] = taken_in_on
    if child_birth_date is not None:
        changes["birth_date"] = child_birth_date
    return await _apply(ctx, _with(ctx, **changes), "adoption-leave", "taken-in")


@assistant.tool(sequential=True)
async def set_school_postponed(ctx: RunContext[AssistantDeps], postponed: bool) -> str:
    """Foster family: record whether compulsory schooling of the child was postponed; the leave
    then lasts until the child turns 10, not 7.

    Args:
        postponed: True if a decision postponing compulsory schooling was made.
    """
    if ctx.deps.scenario.taken_in != "foster":
        raise ModelRetry("Odroczenie obowiązku szkolnego ma znaczenie tylko w rodzinie zastępczej.")
    scenario = _with(ctx, school_postponed=postponed)
    return await _apply(ctx, scenario, "adoption-leave", "age-limit")


@assistant.tool(sequential=True)
async def set_adoption_ruling(
    ctx: RunContext[AssistantDeps], final: bool, final_on: dt.date | None = None
) -> str:
    """Adoption: record whether the court's adoption ruling is final, and since when. Paternity
    leave of the adoptive father runs from that day.

    Args:
        final: True if the adoption ruling is already final (prawomocne).
        final_on: The day it became final; required when `final` is true.
    """
    if ctx.deps.scenario.taken_in != "adoption":
        raise ModelRetry("Postanowienie o przysposobieniu dotyczy tylko adopcji (set_taken_in).")
    if final and final_on is None:
        raise ModelRetry("Zapytaj, którego dnia postanowienie o przysposobieniu się uprawomocniło.")
    scenario = _with(ctx, adoption_final=final, adoption_final_on=final_on if final else None)
    return await _apply(ctx, scenario, "paternity", "paternity-deadline")


@assistant.tool(sequential=True)
async def set_leave_handover(
    ctx: RunContext[AssistantDeps], handed_over: bool, weeks: int | None = None
) -> str:
    """Record that the person on leave on the terms of maternity leave leaves the rest of it to
    the other parent after at least 14 weeks (or, False, that they do not: a correction). Call
    it only when the user says so; never ask about it.

    Args:
        handed_over: True if the other parent takes the rest of the leave.
        weeks: Weeks of the leave used before the other parent takes over, only if the user
            said how many (empty = 14, the earliest).
    """
    scenario = _with(
        ctx,
        taken_in_handover=handed_over,
        taken_in_handover_after_weeks=weeks if handed_over else None,
    )
    return await _apply(ctx, scenario, "adoption-leave-other", "adoption-leave")


@assistant.tool(sequential=True)
async def set_foster_before(
    ctx: RunContext[AssistantDeps],
    used_leave: bool,
    leave_start: dt.date | None = None,
    leave_end: dt.date | None = None,
    parental_weeks: int | None = None,
) -> str:
    """Adoption after foster care: the child was first in the family as a non-professional foster
    family, and the adoption application came later. Record the leave used as a foster family;
    the leave connected with adoption is shorter by it. Call it only when the user says so;
    never ask about it.

    Args:
        used_leave: True if the child was in foster care with this family before the adoption
            application; False corrects an earlier answer.
        leave_start: First day of the leave on the terms of maternity leave used as a foster
            family, as the user gave it (empty if they took none).
        leave_end: Its last day (for leave still under way: the day before the adoption
            application).
        parental_weeks: Weeks of parental leave used as a foster family, only if the user said.
    """
    if ctx.deps.scenario.taken_in != "adoption":
        raise ModelRetry(
            "Urlop z rodziny zastępczej odejmuje się od urlopu związanego z przysposobieniem: "
            "najpierw zapisz adopcję (set_taken_in)."
        )
    if used_leave and (leave_start is None) != (leave_end is None):
        raise ModelRetry(
            "Potrzebny jest pierwszy i ostatni dzień urlopu: dopytaj o brakującą datę."
        )
    before = (
        {"leave_start": leave_start, "leave_end": leave_end, "parental_weeks": parental_weeks}
        if used_leave
        else None
    )
    try:
        scenario = _with(ctx, foster_before=before)
    except ValidationError as exc:
        raise ModelRetry(
            "Urlop nie może skończyć się przed swoim początkiem: sprawdź daty."
        ) from exc
    return await _apply(ctx, scenario, "adoption-leave", "parental", "parental-father")


# Section G: the amounts.

MIN_MONTHLY_PAY = 100
"""Below this a monthly amount in PLN is almost surely a slip ("8" for 8000)."""


@assistant.tool(sequential=True)
async def set_monthly_pay(
    ctx: RunContext[AssistantDeps],
    parent: Literal["mother", "father"],
    amount: Annotated[float, Field(gt=0)] | None,
) -> str:
    """Record the monthly amount a parent's benefit base comes from; the calculator turns it
    into the benefit for every period. Only an exact amount the user gave: never the range from
    the onboarding, never your own estimate.

    Args:
        parent: Whose amount it is.
        amount: In PLN per month, as the user gave it ("8 tys." = 8000). An employee: gross
            monthly salary (the average of the last 12 months, if it changed). A contract of
            mandate or a business: the monthly base of the sickness contribution. Null = the
            user does not know it or does not want to give it.
    """
    scenario = ctx.deps.scenario
    who = "mama" if parent == "mother" else "tata"
    if not pay_matters(scenario, parent):
        raise ModelRetry(
            f"Kwotę zasiłku liczymy tylko, gdy {who} pracuje i podlega ubezpieczeniu "
            "chorobowemu. Najpierw ustal, jak pracuje."
        )
    if amount is not None and amount < MIN_MONTHLY_PAY:
        raise ModelRetry(
            "To bardzo mała kwota miesięczna. Zapisz ją w złotych (np. 8000, a nie 8) albo "
            "dopytaj użytkownika."
        )
    field = "mother_pay" if parent == "mother" else "father_pay"
    updated = _with(ctx, **{field: "unknown" if amount is None else amount})
    first = "pay-maternity" if parent == "mother" else "pay-paternity"
    return await _apply(
        ctx,
        updated,
        first,
        "pay-adoption-leave",
        "pay-parental",
        "pay-parental-father",
        "pay-job-loss-benefit",
        "pay-sick-pay",
        "pay-sick-benefit",
    )


# The benefit base in detail (engine/base.py): the data of the payer's certificate.


@assistant.tool(sequential=True)
async def set_pay_history(
    ctx: RunContext[AssistantDeps],
    parent: Literal["mother", "father"],
    months: list[PayMonth] | None = None,
    quarterly_bonuses: Annotated[float, Field(ge=0)] | None = None,
    annual_bonus: Annotated[float, Field(ge=0)] | None = None,
    full_time: bool | None = None,
    insured_from: dt.date | None = None,
    contract_pay: Annotated[float, Field(gt=0)] | None = None,
    replace: bool = False,
) -> str:
    """Record what a parent's benefit base is computed from, in detail, as the user gave it:
    pay month by month (e.g. copied from the payer's certificate Z-3 or Z-3a, from payslips or
    from the declared contribution base), quarterly and annual bonuses, full-time work, the start
    of insurance with this payer, the monthly pay in the contract. The calculator computes the
    base and the benefit: never sum, average, top up or compute anything yourself, and never
    guess a number the user did not give. Fields left out keep what was recorded; a month given
    again replaces that month.

    Args:
        parent: Whose pay it is.
        months: Calendar months before the right to the benefit, each with: month ("RRRR-MM");
            amount in PLN (an employee: gross pay for that month without quarterly and annual
            bonuses; a contract or business: the base of the sickness contribution); and only if
            the user gave them, for a month not worked in full (e.g. sick leave): days_required
            (days to work that month) and days_worked; fixed (the fixed monthly pay from the
            contract) and variable (variable pay for the days worked); not_topped (overtime,
            night work, commission in that month).
        quarterly_bonuses: Quarterly bonuses and awards paid for the four quarters before,
            together.
        annual_bonus: Annual pay (the thirteenth salary, an annual award) for the year before.
        full_time: True = works full time; False = part time.
        insured_from: The first day of insurance with this payer (this contract, this business).
        contract_pay: The monthly pay (or contract income) set in the contract.
        replace: True = forget what was recorded for this parent before and keep only this;
            with nothing else given it removes the record.
    """
    scenario = ctx.deps.scenario
    work = scenario.mothers_work if parent == "mother" else scenario.fathers_work
    cover = coverage(scenario) if parent == "mother" else father_coverage(scenario)
    who = "mama" if parent == "mother" else "tata"
    if work not in ("employment", "contract", "business") or cover in NOT_INSURED:
        raise ModelRetry(
            f"Podstawę zasiłku liczymy tylko, gdy {who} pracuje i podlega ubezpieczeniu "
            "chorobowemu. Najpierw ustal, jak pracuje."
        )
    if any(0 < m.amount < MIN_MONTHLY_PAY for m in months or []):
        raise ModelRetry(
            "To bardzo mała kwota miesięczna. Zapisz ją w złotych (np. 8000, a nie 8) albo "
            "dopytaj użytkownika."
        )
    field = "mother_pay_history" if parent == "mother" else "father_pay_history"
    recorded = getattr(scenario, field)
    old = PayHistory() if replace or recorded is None else recorded
    given = {m.month: m for m in months or []}
    changes = {
        name: value
        for name, value in (
            ("quarterly_bonuses", quarterly_bonuses),
            ("annual_bonus", annual_bonus),
            ("full_time", full_time),
            ("insured_from", insured_from),
            ("contract_pay", contract_pay),
        )
        if value is not None
    }
    kept = [m for m in old.months if m.month not in given]
    try:
        history = PayHistory.model_validate(
            old.model_dump() | changes | {"months": [*kept, *given.values()]}
        )
    except ValidationError as exc:
        raise ModelRetry(f"Nie zapisano: {exc.errors()[0]['msg']}") from exc
    empty = history == PayHistory()
    updated = _with(ctx, **{field: None if empty else history.model_dump()})
    first = "pay-maternity" if parent == "mother" else "pay-paternity"
    return await _apply(ctx, updated, first, "pay-parental", "pay-parental-father")


@assistant.tool(sequential=True)
async def set_rate_choice(ctx: RunContext[AssistantDeps], rate_815: bool | None) -> str:
    """Record the mother's choice of the benefit rate: the written request, filed not later than
    21 days after the birth, for 81,5% for the whole of maternity and parental leave (True), or
    100% for maternity and 70% for parental leave (False). For a child taken in for upbringing:
    the same choice of the person who took the child in, within 21 days after taking it in, for
    the leave on the terms of maternity leave and parental leave. Only what the user said.

    Args:
        rate_815: True = the request for 81,5% is (or was) filed; False = 100% and 70%;
            null = not decided (a correction).
    """
    if requester_cover(ctx.deps.scenario) in NOT_INSURED:
        who = "Ta osoba" if ctx.deps.scenario.taken_in is not None else "Mama"
        raise ModelRetry(
            f"{who} nie podlega ubezpieczeniu chorobowemu, więc nie ma czego wybierać."
        )
    scenario = _with(ctx, rate_815=rate_815)
    return await _apply(
        ctx, scenario, "rate-815-deadline", "pay-maternity", "pay-adoption-leave", "pay-parental"
    )


# F8 plans for a goal and F11 the stress test (engine/plans.py, engine/stress.py). Read-only:
# the engine computes, the model shows the options and their effects, the parents decide.


@assistant.tool
async def propose_plans(ctx: RunContext[AssistantDeps], goal: Goal) -> str:
    """Propose 2-3 plans of parental leave for the parents' goal, computed and compared by the
    calculator: money, weeks at home for each parent, the return to work, what is given up. It
    changes nothing: record a plan only when the user chooses one, with the tools the result
    names. Call it when the user asks how to plan or split the leave for a goal.

    Args:
        goal: "most-money" = najwięcej pieniędzy; "longest-home" = najdłużej w domu;
            "equal-split" = równy podział między rodziców; "quick-return" = szybki powrót do
            pracy.
    """
    try:
        result = plans_for_goal(ctx.deps.scenario, ctx.deps.params, ctx.deps.today, goal)
    except ScenarioError as exc:
        raise ModelRetry(f"Nie da się ułożyć planów: {exc}") from exc
    return describe_plans(result)


@assistant.tool
async def stress_test(ctx: RunContext[AssistantDeps]) -> str:
    """Check what would change on the current timeline and plan if something happened: a
    premature birth, twins, a job loss in pregnancy, the mother's illness, stay in hospital or
    death, the father taking over maternity leave, the "Za życiem" certificate. Computed by the
    calculator with example dates; it changes nothing. Call it when the user asks what could go
    wrong or what happens if something changes."""
    try:
        report = run_stress_test(ctx.deps.scenario, ctx.deps.params, ctx.deps.today)
    except ScenarioError as exc:
        raise ModelRetry(f"Nie da się sprawdzić planu: {exc}") from exc
    return describe_stress(report)
