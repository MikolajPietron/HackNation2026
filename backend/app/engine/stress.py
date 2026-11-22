"""F11, the stress test of the plan (FUNKCJE: "jeden przycisk przepuszcza plan przez zdarzenia
losowe i pokazuje, gdzie grozi utrata prawa").

The family's current scenario, with its plan of parental leave, is run through the "Coś się
zmieniło" events the engine models. For every event that can still happen to this family the
result says what it would change: entitlements gained, lost, longer or shorter; periods that
move; the money (from money.py's payments, when amounts are known); new risks (case notes of
kind "risk"); and whether the parents' plan of parental leave still fits the rules.

Pure and deterministic like the rest of the engine. Every event is a changed `Scenario` built by
`build_timeline`, and the comparison uses the engine's own diffs (`changed_element_ids`,
`changed_note_ids`, compare.py). This module states no rule: the rules and their quotes are on
the timelines (segments, notes), so the sources of every result are the sources of the changed
elements.

Events, in this order, each only when it can still happen:
- the child is on the way: a premature birth with the child in hospital (supplementary leave);
  twins; the mother's job loss in pregnancy, once for every `JobLossReason` her work allows
  (an employment contract: all of them; a contract of mandate or a business: only "other");
- maternity leave still ahead: the mother's special situations of guide B.2 (a certificate of
  inability to live independently, a stay in hospital, her death) and the father taking over
  maternity leave after 14 weeks (B.1);
- parental leave still ahead: the "Za życiem" certificate.
None after a child's death or the mother's death: in a sensitive situation the app shows no
what-ifs. None for a child taken in for upbringing: these events concern pregnancy and birth.

Synthetic dates: our choices for the what-if, not rules (each event lists its own in `assumed`):
- a premature birth `PREMATURE_DAYS_EARLY` days before the due date, between the 28th and the
  end of the 37th week, over 1000 g, the child in hospital for `CHILD_HOSPITAL_DAYS` days from
  the birth; when that day is already past, a birth on the due date with the same stay;
- the job loss `JOB_LOSS_MARGIN_DAYS` days before the earliest start of maternity leave before
  the birth (or today, if that is past), so leave before the birth can no longer start; an
  unlawful termination without a court judgment yet;
- the mother's situations on the first day the father may take over in them (8 weeks after the
  birth; today, if that is past); her stay in hospital `MOTHER_HOSPITAL_DAYS` days;
- the father taking over after the minimum of weeks (later, when the child is born and the
  minimum is past: the father cannot take over in the past).
Events after the birth, while the child is on the way, are compared with a birth on the due
date as planned. The reference is computed for today; the event's timeline as of the event's
day (`as_of`), since rules refuse a hospital stay or a death in the future.
"""

import datetime as dt
import math
from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel

from app.engine.compare import (
    MoneyChange,
    PeriodChange,
    RightChange,
    money_change,
    money_line,
    period_changes,
    period_line,
    right_changes,
    right_line,
)
from app.engine.draft import DAY, WEEK, merge_sources
from app.engine.explain import changed_note_ids
from app.engine.insurance import NOT_INSURED, coverage, father_coverage
from app.engine.models import (
    CaseNote,
    JobLossReason,
    Scenario,
    ScenarioError,
    SourceRef,
    Timeline,
)
from app.engine.params import Params
from app.engine.timeline import build_timeline, changed_element_ids
from app.engine.wording import fmt

EventId = Literal[
    "premature",
    "twins",
    "job-loss-bankruptcy",
    "job-loss-liquidation",
    "job-loss-employer-death",
    "job-loss-unlawful",
    "job-loss-other",
    "mother-incapacity",
    "mother-hospital",
    "mother-death",
    "father-takeover",
    "za-zyciem",
]
Verdict = Literal["loss", "risk", "kept"]
"""loss = an entitlement is lost or shortened, or the parents' plan stops fitting the rules;
risk = nothing is lost outright, but a new risk appears (a note of kind "risk", a warning);
kept = the entitlements stay, possibly moved, longer or with new ones."""

PREMATURE_DAYS_EARLY = 42
"""A premature birth 6 weeks before the due date (our choice: a common premature birth)."""
CHILD_HOSPITAL_DAYS = 28
"""The child stays in hospital for the first 4 weeks, from the day of birth."""
JOB_LOSS_MARGIN_DAYS = 14
"""The job ends 2 weeks before the earliest start of maternity leave before the birth."""
MOTHER_HOSPITAL_DAYS = 28
"""The mother's stay in hospital lasts 4 weeks."""

SENSITIVE_EVENTS = frozenset({"mother-incapacity", "mother-hospital", "mother-death"})
"""Events about the mother's health or death."""

JOB_LOSS_TITLE: dict[JobLossReason, str] = {
    "bankruptcy": "Utrata pracy w ciąży: upadłość pracodawcy",
    "liquidation": "Utrata pracy w ciąży: likwidacja pracodawcy",
    "employer-death": "Utrata pracy w ciąży: śmierć pracodawcy",
    "unlawful": "Utrata pracy w ciąży: rozwiązanie umowy z naruszeniem prawa",
    "other": "Koniec pracy w ciąży z innej przyczyny",
}
OTHER_END = {
    "employment": "Koniec umowy o pracę w ciąży z innej przyczyny",
    "contract": "Koniec umowy zlecenia w ciąży",
    "business": "Zamknięcie działalności w ciąży",
}


class StressEvent(BaseModel):
    """What one event would change on the family's timeline."""

    id: EventId
    title: str
    assumed: list[str]
    """The synthetic facts of the what-if (dates, weeks, weight), in Polish."""
    patch: dict[str, Any]
    """The Scenario fields the event changes, as JSON values."""
    as_of: dt.date
    """The day the event's timeline is computed for ("today" of the what-if); the reference is
    computed for the real today."""
    verdict: Verdict
    sensitive: bool = False
    """The mother's illness, stay in hospital or death: shown gently, only when asked for (the
    assistant never brings these up itself)."""
    plan_breaks: str | None = None
    """The parents' plan of parental leave no longer fits: the engine's reason. The rest of the
    result then compares both timelines without the plan."""
    rights: list[RightChange] = []
    periods: list[PeriodChange] = []
    money: MoneyChange | None = None
    """None when amounts are not known."""
    risks: list[CaseNote] = []
    """New or reworded points of the explanation of kind "risk"."""
    warnings: list[str] = []
    """New warnings of the timeline."""
    changed: list[str] = []
    """Elements of the event's timeline that are new or changed (changed_element_ids)."""
    changed_notes: list[str] = []
    lines: list[str] = []
    """The changes in plain Polish, one per line: what the UI and the assistant show."""
    sources: list[SourceRef] = []
    """The sources of the changed notes and of the new periods."""
    reference: Timeline | None = None
    timeline: Timeline | None = None
    """Both timelines, only when asked for (`timelines=True`)."""


class SkippedEvent(BaseModel):
    """An event that could happen but the engine refuses for this scenario, with its reason."""

    id: EventId
    title: str
    reason: str


class StressReport(BaseModel):
    events: list[StressEvent] = []
    skipped: list[SkippedEvent] = []
    sensitive: bool = False
    """After a child's death or the mother's death: no what-ifs."""
    reason: str | None = None
    """Why there are no events."""


@dataclass
class Trial:
    """One what-if: the reference (computed for today) and the changed scenario (as of
    `as_of`)."""

    id: EventId
    title: str
    assumed: list[str]
    reference: Scenario
    variant: Scenario
    as_of: dt.date


def stress_test(
    scenario: Scenario, params: Params, today: dt.date, *, timelines: bool = False
) -> StressReport:
    """Run the scenario through every event that can still happen. Raises ScenarioError when
    the scenario itself breaks a rule."""
    if scenario.taken_in is not None:
        return StressReport(
            reason="Test planu dotyczy ciąży i porodu, a dziecko zostało przyjęte na wychowanie."
        )
    if scenario.anchor_date is None:
        return StressReport(
            reason="Najpierw potrzebna jest data porodu: przewidywana albo faktyczna."
        )
    if sensitive(scenario):
        return StressReport(
            sensitive=True,
            reason="W tej sytuacji nie pokazujemy wariantów „co by było, gdyby”.",
        )
    current = build_timeline(scenario, params, today)
    report = StressReport()
    for trial in trials(scenario, params, today, current):
        try:
            report.events.append(_run(trial, scenario, params, today, timelines))
        except ScenarioError as exc:
            report.skipped.append(SkippedEvent(id=trial.id, title=trial.title, reason=str(exc)))
    if not report.events:
        report.reason = (
            "Najpierw potrzebna jest liczba dzieci urodzonych przy jednym porodzie."
            if scenario.children_count is None
            else "Żadne z tych zdarzeń nie może już zmienić Waszej osi."
        )
    return report


def sensitive(scenario: Scenario) -> bool:
    """A child's death or the mother's death: the app proposes nothing then."""
    event = scenario.mother_event
    return bool(scenario.losses) or (event is not None and event.kind == "death")


def with_changes(scenario: Scenario, **changes: Any) -> Scenario:
    return Scenario.model_validate({**scenario.model_dump(), **changes})


def born_on(scenario: Scenario, birth: dt.date) -> dict[str, Any]:
    """The answers once the child is born on `birth`: the same step as the assistant's
    `set_birth_date`. Leave before the birth planned in weeks before the due date counts from its
    real first day (Labour Code art. 180 § 3); a birth before that day means no leave before the
    birth (art. 183¹ § 2)."""
    changes: dict[str, Any] = {
        "child_born": True,
        "birth_date": birth,
        "has_medical_certificate": None,
    }
    weeks = scenario.leave_before_birth_weeks
    if not scenario.child_born and scenario.due_date and weeks:
        planned = scenario.due_date - weeks * WEEK
        if birth <= planned:
            changes.update(leave_before_birth_weeks=0, leave_start=None)
        else:
            changes["leave_start"] = planned
    return changes


# The events.


def trials(scenario: Scenario, params: Params, today: dt.date, current: Timeline) -> list[Trial]:
    found: list[Trial] = []
    if not scenario.child_born:
        found += _before_birth(scenario, params, today)
    found += _after_birth(scenario, params, today)
    found += _za_zyciem(scenario, current)
    return found


def _before_birth(scenario: Scenario, params: Params, today: dt.date) -> list[Trial]:
    due = scenario.due_date
    assert due is not None
    insured = coverage(scenario) not in NOT_INSURED
    found: list[Trial] = []
    if insured and scenario.children_count is not None and due > today:
        found.append(_premature(scenario, due, today))
    if scenario.children_count == 1:
        found.append(
            Trial(
                id="twins",
                title="Bliźnięta",
                assumed=["Zakładamy, że przy jednym porodzie urodzi się dwoje dzieci."],
                reference=scenario,
                variant=with_changes(scenario, children_count=2),
                as_of=today,
            )
        )
    found += _job_loss(scenario, params, today, due, insured)
    return found


def _premature(scenario: Scenario, due: dt.date, today: dt.date) -> Trial:
    early = due - PREMATURE_DAYS_EARLY * DAY
    if early >= today:
        birth, week, title = early, "28-37", "Wcześniak w szpitalu"
        when = (
            f"Zakładamy poród {fmt(birth)}, {PREMATURE_DAYS_EARLY // 7} tyg. przed przewidywaną "
            "datą porodu: po 28. i przed końcem 37. tygodnia ciąży, z masą ponad 1000 g."
        )
    else:
        birth, week, title = due, "after-37", "Dziecko w szpitalu po porodzie"
        when = f"Zakładamy poród w przewidywanym terminie ({fmt(due)}), po 37. tygodniu ciąży."
    last = birth + (CHILD_HOSPITAL_DAYS - 1) * DAY
    reference = with_changes(scenario, **born_on(scenario, due))
    variant = with_changes(
        scenario,
        **born_on(scenario, birth),
        hospital_care=True,
        birth_week=week,
        birth_weight_up_to_1000g=False,
        hospital_stays=[{"start": birth, "end": last}],
    )
    return Trial(
        id="premature",
        title=title,
        assumed=[
            when,
            f"Dziecko jest w szpitalu od dnia porodu do {fmt(last)} ({CHILD_HOSPITAL_DAYS} dni).",
            "Porównujemy z porodem w przewidywanym terminie, bez pobytu w szpitalu.",
        ],
        reference=reference,
        variant=variant,
        as_of=max(today, birth),
    )


def _job_loss(
    scenario: Scenario, params: Params, today: dt.date, due: dt.date, insured: bool
) -> list[Trial]:
    work = scenario.mothers_work
    if not insured or scenario.job_loss is not None or work not in OTHER_END:
        return []
    before = params.maternity.max_weeks_before_birth.value * 7 + JOB_LOSS_MARGIN_DAYS
    ended = max(today, due - before * DAY)
    if ended > due - 2 * DAY:
        return []  # no day of pregnancy left between the end of work and the birth
    reasons: tuple[JobLossReason, ...] = (
        ("bankruptcy", "liquidation", "employer-death", "unlawful", "other")
        if work == "employment"
        else ("other",)
    )
    found = []
    for reason in reasons:
        assumed = [f"Zakładamy, że ostatni dzień pracy mamy to {fmt(ended)}."]
        if reason == "unlawful":
            assumed.append("Sąd jeszcze nie potwierdził naruszenia prawa prawomocnym wyrokiem.")
        found.append(
            Trial(
                id=f"job-loss-{reason}",  # type: ignore[arg-type]
                title=OTHER_END[work] if reason == "other" else JOB_LOSS_TITLE[reason],
                assumed=assumed,
                reference=scenario,
                variant=with_changes(scenario, job_loss={"ended_on": ended, "reason": reason}),
                as_of=today,
            )
        )
    return found


def _after_birth(scenario: Scenario, params: Params, today: dt.date) -> list[Trial]:
    """Guide B.1-B.2, while maternity leave is still ahead."""
    if (
        coverage(scenario) in NOT_INSURED
        or scenario.children_count is None
        or scenario.mother_event is not None
    ):
        return []
    born = scenario.child_born is True
    birth = scenario.anchor_date
    assert birth is not None
    reference = scenario if born else with_changes(scenario, **born_on(scenario, birth))
    try:
        planned = build_timeline(reference, params, today)
    except ScenarioError:
        return []
    maternity = next((s for s in planned.segments if s.id == "maternity"), None)
    if maternity is None:
        return []
    found: list[Trial] = []
    compared = [] if born else ["Porównujemy z porodem w przewidywanym terminie."]
    father = father_coverage(scenario) not in NOT_INSURED
    day = max(birth + params.father.special_after_weeks.value * WEEK, today)
    if day <= maternity.end:
        when = f"Zakładamy, że to {fmt(day)}, pierwszego dnia, od którego tata może przejąć urlop."
        if father:
            found.append(
                Trial(
                    id="mother-incapacity",
                    title="Orzeczenie o niezdolności mamy do samodzielnej egzystencji",
                    assumed=[when, *compared],
                    reference=reference,
                    variant=with_changes(
                        reference, mother_event={"kind": "incapacity", "start": day}
                    ),
                    as_of=today,
                )
            )
            last = day + (MOTHER_HOSPITAL_DAYS - 1) * DAY
            found.append(
                Trial(
                    id="mother-hospital",
                    title="Pobyt mamy w szpitalu",
                    assumed=[
                        f"Zakładamy, że mama jest w szpitalu od {fmt(day)} do {fmt(last)} "
                        f"({MOTHER_HOSPITAL_DAYS} dni).",
                        *compared,
                    ],
                    reference=reference,
                    variant=with_changes(
                        reference, mother_event={"kind": "hospital", "start": day, "end": last}
                    ),
                    as_of=today,
                )
            )
        found.append(
            Trial(
                id="mother-death",
                title="Śmierć mamy",
                assumed=[f"Zakładamy datę {fmt(day)}.", *compared],
                reference=reference,
                variant=with_changes(reference, mother_event={"kind": "death", "start": day}),
                as_of=day,
            )
        )
    takeover = _takeover(scenario, params, today, planned, father)
    if takeover is not None:
        found.append(takeover)
    return found


def _takeover(
    scenario: Scenario, params: Params, today: dt.date, planned: Timeline, father: bool
) -> Trial | None:
    """Guide B.1: the father takes the rest of maternity leave after the mother's minimum."""
    if not father or scenario.father_takes_over is not None:
        return None
    birth = scenario.anchor_date
    assert birth is not None
    minimum = params.father.takeover_after_weeks.value
    weeks = minimum
    if scenario.child_born and today > birth:
        weeks = max(minimum, math.ceil((today - birth).days / 7))
    maternity = next(s for s in planned.segments if s.id == "maternity")
    start = birth + weeks * WEEK
    if start > maternity.end:
        return None
    return Trial(
        id="father-takeover",
        title="Tata przejmuje urlop macierzyński",
        assumed=[
            f"Zakładamy, że mama wykorzystuje {weeks} tyg. urlopu macierzyńskiego po porodzie, "
            f"a tata przejmuje resztę od {fmt(start)}."
        ],
        reference=scenario,
        variant=with_changes(
            scenario,
            father_takes_over=True,
            mother_weeks_before_takeover=weeks if weeks > minimum else None,
        ),
        as_of=today,
    )


def _za_zyciem(scenario: Scenario, current: Timeline) -> list[Trial]:
    if scenario.za_zyciem or scenario.children_count is None:
        return []
    if not any(s.id.startswith("parental") for s in current.segments):
        return []
    return [
        Trial(
            id="za-zyciem",
            title="Zaświadczenie „Za życiem”",
            assumed=["Zakładamy, że dziecko ma zaświadczenie „Za życiem”."],
            reference=scenario,
            variant=with_changes(scenario, za_zyciem=True),
            as_of=current.today,
        )
    ]


# The comparison.


def _run(
    trial: Trial, scenario: Scenario, params: Params, today: dt.date, timelines: bool
) -> StressEvent:
    """The reference as the family sees it today, the event's timeline as of its day."""
    reference = build_timeline(trial.reference, params, today)
    variant = trial.variant
    breaks = None
    try:
        after = build_timeline(variant, params, trial.as_of)
    except ScenarioError as exc:
        if not variant.parental_parts:
            raise
        # The plan no longer fits: say so, and compare both timelines without it, so what
        # follows is the event's own effect.
        breaks = str(exc)
        variant = variant.model_copy(update={"parental_parts": []})
        after = build_timeline(variant, params, trial.as_of)
        without = trial.reference.model_copy(update={"parental_parts": []})
        reference = build_timeline(without, params, today)
    changed = changed_element_ids(reference, after)
    changed_notes = changed_note_ids(reference, after)
    rights = right_changes(reference, after)
    periods = period_changes(reference, after)
    money = money_change(reference, after)
    risks = [n for n in after.notes if n.kind == "risk" and n.id in changed_notes]
    warnings = [w for w in after.warnings if w not in reference.warnings]
    lost = breaks is not None or any(r.days_after < r.days_before for r in rights)
    verdict: Verdict = "loss" if lost else "risk" if risks or warnings else "kept"
    added = {p.id for p in periods if p.change == "added" and p.element == "segment"}
    sources = merge_sources(
        *(n.sources for n in after.notes if n.id in changed_notes),
        *(s.sources for s in after.segments if s.id in added),
    )
    return StressEvent(
        id=trial.id,
        title=trial.title,
        assumed=trial.assumed,
        patch=_patch(scenario, variant),
        as_of=trial.as_of,
        verdict=verdict,
        sensitive=trial.id in SENSITIVE_EVENTS,
        plan_breaks=breaks,
        rights=rights,
        periods=periods,
        money=money,
        risks=risks,
        warnings=warnings,
        changed=changed,
        changed_notes=changed_notes,
        lines=_lines(breaks, rights, periods, money, risks, warnings),
        sources=sources,
        reference=reference if timelines else None,
        timeline=after if timelines else None,
    )


def _patch(scenario: Scenario, variant: Scenario) -> dict[str, Any]:
    """The fields the event changes in the family's scenario, as JSON."""
    before = scenario.model_dump(mode="json")
    after = variant.model_dump(mode="json")
    return {k: v for k, v in after.items() if before.get(k) != v}


def _lines(
    breaks: str | None,
    rights: list[RightChange],
    periods: list[PeriodChange],
    money: MoneyChange | None,
    risks: list[CaseNote],
    warnings: list[str],
) -> list[str]:
    lines = []
    if breaks is not None:
        lines.append(f"Wasz plan urlopu rodzicielskiego przestaje pasować: {breaks}")
    lines += [right_line(r) for r in rights]
    lines += [period_line(p) for p in periods if p.element == "segment"]
    lines += [period_line(p) for p in periods if p.element == "marker"]
    if money is not None and money.payments:
        lines.append(money_line(money))
    lines += [f"Uwaga: {n.title}." for n in risks]
    lines += warnings
    return lines or ["Na osi nic się nie zmienia."]
