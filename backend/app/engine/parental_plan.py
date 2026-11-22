"""Guide section E (page 9) and B.3 (page 7): parental leave as the parents plan it — split
between them, in parts, at the same time or one after the other, and combined with part-time
work. Calculators c and d of the challenge (page 13).

Applied after the mother's and the father's rules (timeline.py, father.py), and only when the
parents told us their plan (`Scenario.parental_parts`). Without a plan the timeline shows each
parent's share as an option (`parental`, `parental-father`). A plan replaces the share of every
parent it names with that parent's parts:
- `parental-mother-<k>`, `parental-father-<k>`: the k-th part of that parent, on the parent's
  lane, tone "leave" (decided);
- a parent the plan does not name keeps the option: the mother's shrinks to what the father's
  parts leave of the pool, the father's weeks move to right after the mother's last part.

Rules (a broken one raises ScenarioError in Polish):
- both parents together at most P weeks (41/43, with "Za życiem" 65/67), also when they use the
  leave at the same time (art. 182¹ᵃ § 1-3, § 6-7); one parent at most P - 9, because the other
  parent's 9 weeks cannot be passed on (§ 4);
- at most 5 parts (art. 182¹ᶜ; parts are counted by requests, art. 182¹ᵈ § 2), every part over
  by 31 December of the year the child turns 6;
- not before maternity (and supplementary) leave ends; one parent's parts do not overlap;
- part-time work only for an employee, at the employer that grants the leave, at most half of
  full time (guide E; art. 182¹ᵉ § 1); the part is extended by weeks of work × the part of full
  time (art. 182¹ᶠ § 2), in days with the incomplete day dropped (§ 4); the extension lengthens
  that part only (§ 3, § 5); the whole leave so extended stays within 82/86 weeks (130/134 with
  "Za życiem"; § 1, § 1¹).

Our readings, not settled by the materials (CLAUDE.md, open questions):
- the weeks of work are the first weeks of the part (the employee may choose otherwise; how the
  extension is used is set in the request, art. 182¹ᶠ § 6);
- the limit of 5 parts counts the parts of both parents together (the guide: "rodzice mogą
  podzielić na maksymalnie 5 części");
- parental leave of either parent starts after maternity (and supplementary) leave.
"""

import datetime as dt
import math
from dataclasses import dataclass
from fractions import Fraction

from app.engine.draft import DAY, WEEK, Draft, days_between, merge_sources
from app.engine.father import MATERNITY_PARTS, _insurance_lines
from app.engine.insurance import NOT_INSURED, Coverage, father_coverage
from app.engine.loss import Loss
from app.engine.models import (
    CaseNote,
    ParentalPart,
    Role,
    Scenario,
    ScenarioError,
    Segment,
    SourceRef,
    Timeline,
)
from app.engine.params import Params
from app.engine.parental import for_children, parental_deadline, parental_table, parental_weeks
from app.engine.wording import fmt, long_date

WHO = {"mother": "mama", "father": "tata"}
WHOSE = {"mother": "mamy", "father": "taty"}
WEEK_IS_7_DAYS = "Tydzień urlopu to 7 dni kalendarzowych."
ESTIMATE = "Liczymy od przewidywanej daty porodu. Po porodzie oś przeliczy się od faktycznej daty."


@dataclass(frozen=True)
class Planned:
    """One part of the plan with the dates the engine gave it."""

    number: int
    """Place in the plan, from 1: every part counts towards the limit of parts."""
    part: ParentalPart
    id: str
    start: dt.date
    end: dt.date
    extension: int
    """Days the part is extended by, for the work combined with it."""

    @property
    def work_end(self) -> dt.date | None:
        """The last day of the weeks combined with work."""
        if self.part.work_fraction is None:
            return None
        return work_end(self.part, self.start)


def work_weeks(part: ParentalPart) -> int:
    """Weeks of the part combined with work (all of it unless said otherwise)."""
    return part.work_weeks or part.weeks


def work_end(part: ParentalPart, start: dt.date) -> dt.date:
    """The last day of the weeks combined with work in a part that starts on `start`: they are
    the first weeks of the part (our reading, see the module's docstring)."""
    return start + work_weeks(part) * WEEK - DAY


def planned_parts(scenario: Scenario) -> dict[str, ParentalPart]:
    """The parts of the plan by the id of their segment (`parental-mother-1`...)."""
    parts = scenario.parental_parts
    return dict(zip(part_ids(parts), parts, strict=True))


def extension_days(part: ParentalPart) -> int:
    """Art. 182¹ᶠ § 2 and § 4: weeks combined with work × the part of full time, given in days;
    the incomplete day is dropped."""
    if part.work_fraction is None:
        return 0
    return math.floor(work_weeks(part) * 7 * part.work_fraction)


def part_ids(parts: list[ParentalPart]) -> list[str]:
    """`parental-mother-1`, `parental-father-1`, `parental-mother-2`...: numbered per parent."""
    seen: dict[str, int] = {}
    ids = []
    for part in parts:
        seen[part.parent] = seen.get(part.parent, 0) + 1
        ids.append(f"parental-{part.parent}-{seen[part.parent]}")
    return ids


def fraction(value: Fraction) -> str:
    """ "1/2", "2/5", "1"."""
    return str(value.numerator) if value.denominator == 1 else f"{value}"


def decimal(value: Fraction) -> str:
    """ "4,5"; a value without a finite decimal form is rounded: "ok. 3,33"."""
    if value.denominator == 1:
        return str(value.numerator)
    rest = value.denominator
    for prime in (2, 5):
        while rest % prime == 0:
            rest //= prime
    if rest == 1:
        return f"{float(value):.6f}".rstrip("0").replace(".", ",")
    return "ok. " + f"{float(value):.2f}".replace(".", ",")


def formula(part: ParentalPart) -> str:
    """The extension of art. 182¹ᶠ § 2 with its numbers: "20 × 1/2 = 10 tyg."."""
    assert part.work_fraction is not None
    weeks = work_weeks(part) * part.work_fraction
    product = f"{work_weeks(part)} tyg. × {fraction(part.work_fraction)} = {decimal(weeks)} tyg."
    if weeks.denominator == 1:
        return product
    days = weeks * 7
    if days.denominator == 1:
        return f"{product}, czyli {days.numerator} dni"
    return (
        f"{product}, czyli {decimal(days)} dnia; niepełny dzień się pomija, więc "
        f"{extension_days(part)} dni"
    )


def extension_label(days: int) -> str:
    return f"{days // 7} tyg." if days % 7 == 0 else f"{days} dni"


def _parts_word(count: int) -> str:
    """After a number: 1 część, 2 części, 5 części."""
    return "część" if count == 1 else "części"


# The rules.


def parental_plan_rules(
    draft: Draft,
    scenario: Scenario,
    params: Params,
    birth: dt.date,
    today: dt.date,
    cover: Coverage,
    loss: Loss | None,
) -> list[str]:
    """Replace the parents' parental leave options with their plan. Returns the assumptions
    the plan rests on (for `Timeline.assumptions`)."""
    parts = scenario.parental_parts
    if not parts or scenario.children_count is None:
        return []
    if loss is not None and loss.none_survived:
        return []  # no child to care for: no parental leave (see loss.py)
    planned = plan(draft, scenario, params, birth, today, cover)
    _replace(draft, scenario, params, birth, cover, planned)
    assumptions = [
        f"Limit {params.parental.max_parts.value} części urlopu rodzicielskiego liczymy łącznie "
        "dla obojga rodziców, jak w Przewodniku: „rodzice mogą podzielić na maksymalnie "
        f"{params.parental.max_parts.value} części”.",
        "Urlop rodzicielski obojga rodziców pokazujemy najwcześniej od dnia po urlopie "
        "macierzyńskim (i uzupełniającym, jeśli jest).",
    ]
    if any(p.part.work_fraction is not None for p in planned):
        assumptions.append(
            "Tygodnie pracy w czasie urlopu rodzicielskiego liczymy od pierwszego dnia części "
            "urlopu, a wydłużenie dodajemy na końcu tej części. Jak wykorzystać wydłużenie, "
            "pracownik określa we wniosku o podjęcie pracy."
        )
    return assumptions


def plan(
    draft: Draft,
    scenario: Scenario,
    params: Params,
    birth: dt.date,
    today: dt.date,
    cover: Coverage,
) -> list[Planned]:
    """Check the plan against the rules and give every part its dates."""
    p = params.parental
    pp = params.parental_plan
    parts = scenario.parental_parts
    total, one_parent = parental_weeks(scenario, params)
    exclusive = p.exclusive_weeks.value
    deadline = parental_deadline(birth, params)
    if deadline < today:
        raise ScenarioError(
            f"Czas na urlop rodzicielski minął {fmt(deadline)}, więc nie da się go zaplanować."
        )
    parents = {part.parent for part in parts}
    if "mother" in parents and draft.segment("parental") is None:
        raise ScenarioError(
            "Mama nie podlega ubezpieczeniu chorobowemu w dniu porodu, więc nie ma zasiłku "
            "macierzyńskiego za okres urlopu rodzicielskiego. W planie może być tylko tata."
            if cover in NOT_INSURED
            else "Na tej osi mama nie ma już urlopu rodzicielskiego. W planie może być tylko tata."
        )
    if "father" in parents and father_coverage(scenario) in NOT_INSURED:
        raise ScenarioError(
            "Tata nie podlega ubezpieczeniu chorobowemu, więc nie ma zasiłku macierzyńskiego za "
            "okres urlopu rodzicielskiego. W planie może być tylko mama."
        )
    for parent in sorted(parents):
        used = sum(part.weeks for part in parts if part.parent == parent)
        if used > one_parent:
            raise ScenarioError(
                f"{WHO[parent].capitalize()} może wykorzystać najwyżej {one_parent} tyg. urlopu "
                f"rodzicielskiego: {exclusive} tyg. z {total} należy wyłącznie do drugiego "
                f"z rodziców i nie można ich przenieść. W planie jest {used} tyg."
            )
    used = sum(part.weeks for part in parts)
    if used > total:
        raise ScenarioError(
            f"Rodzice mają razem najwyżej {total} tyg. urlopu rodzicielskiego, także gdy "
            f"korzystają z niego jednocześnie. W planie jest {used} tyg."
        )
    if len(parts) > p.max_parts.value:
        raise ScenarioError(
            f"Urlop rodzicielski można podzielić najwyżej na {p.max_parts.value} części (liczymy "
            f"części obojga rodziców razem). W planie jest {len(parts)}."
        )
    for number, part in enumerate(parts, 1):
        _check_work(scenario, params, number, part)

    earliest = (
        max(
            (s.end for s in draft.segments if s.id in (*MATERNITY_PARTS, "supplementary")),
            default=birth - DAY,
        )
        + DAY
    )
    # A part without a date starts after the previous one; the first one where the timeline
    # shows that parent's leave without a plan: the mother's right after maternity leave, the
    # father's after the mother's share (what his parts leave of it).
    mothers_option = draft.segment("parental")
    fathers_option = draft.segment("parental-father")
    base = earliest
    if "mother" not in parents and mothers_option is not None:
        fathers = sum(part.weeks for part in parts)
        base = mothers_option.start + min(one_parent, total - fathers) * WEEK
    elif "mother" not in parents and fathers_option is not None:
        base = fathers_option.start
    age = p.deadline_age.value
    planned: list[Planned] = []
    for number, (part, part_id) in enumerate(zip(parts, part_ids(parts), strict=True), 1):
        previous = planned[-1] if planned else None
        if part.start is not None:
            start = part.start
        elif previous is None:
            start = base
        elif part.with_previous:
            start = previous.start
        else:
            start = previous.end + DAY
        if start < earliest:
            raise ScenarioError(
                f"Urlop rodzicielski może się zacząć najwcześniej {fmt(earliest)}: po urlopie "
                "macierzyńskim."
            )
        extension = extension_days(part)
        end = start + part.weeks * WEEK + extension * DAY - DAY
        if end > deadline:
            raise ScenarioError(
                f"Część {number} urlopu rodzicielskiego ({WHOSE[part.parent]}) kończyłaby się "
                f"{fmt(end)}, a urlop trzeba wykorzystać do {fmt(deadline)}: do końca roku "
                f"kalendarzowego, w którym dziecko kończy {age} lat."
            )
        planned.append(Planned(number, part, part_id, start, end, extension))

    for parent in parents:
        own = sorted((x for x in planned if x.part.parent == parent), key=lambda x: x.start)
        for before, after in zip(own, own[1:], strict=False):
            if after.start <= before.end:
                raise ScenarioError(
                    f"Części urlopu {WHOSE[parent]} nachodzą na siebie: część {before.number} "
                    f"trwa do {fmt(before.end)}, a część {after.number} zaczyna się "
                    f"{fmt(after.start)}."
                )
    table = pp.max_weeks_with_work_za_zyciem if scenario.za_zyciem else pp.max_weeks_with_work
    cap = for_children(table, scenario.children_count)
    if sum(days_between(x.start, x.end) for x in planned) > cap * 7:
        raise ScenarioError(
            f"Urlop rodzicielski wydłużony przez pracę może trwać łącznie najwyżej {cap} tyg."
        )
    return planned


def _check_work(scenario: Scenario, params: Params, number: int, part: ParentalPart) -> None:
    """Guide E, art. 182¹ᵉ § 1: an employee may work at most half of full time."""
    limit = params.parental_plan.max_work_fraction.value
    if part.work_fraction is None:
        if part.work_weeks is not None:
            raise ScenarioError(
                f"Część {number}: podano tygodnie pracy, ale nie wymiar pracy (np. 1/2 etatu)."
            )
        return
    if part.work_fraction <= 0:
        raise ScenarioError(f"Część {number}: wymiar pracy musi być większy od zera.")
    if part.work_fraction > limit:
        raise ScenarioError(
            f"W czasie urlopu rodzicielskiego można pracować najwyżej na {fraction(limit)} "
            "etatu: w wymiarze nie wyższym niż połowa pełnego wymiaru czasu pracy."
        )
    if work_weeks(part) > part.weeks:
        raise ScenarioError(
            f"Część {number}: praca może trwać najwyżej tyle tygodni, ile ta część urlopu "
            f"({part.weeks} tyg.)."
        )
    work = scenario.mothers_work if part.parent == "mother" else scenario.fathers_work
    if work in ("contract", "business", "none"):
        raise ScenarioError(
            "Łączyć urlop rodzicielski z pracą może pracownik, u pracodawcy, który udziela tego "
            f"urlopu. {WHO[part.parent].capitalize()} nie pracuje na umowie o pracę, więc tej "
            "możliwości nie ma."
        )


# The timeline.


def _replace(
    draft: Draft,
    scenario: Scenario,
    params: Params,
    birth: dt.date,
    cover: Coverage,
    planned: list[Planned],
) -> None:
    """Put the planned parts where the parents' options were; move or shrink the option of a
    parent the plan does not name."""
    parents = {x.part.parent for x in planned}
    segments = {
        parent: [
            _segment(scenario, params, cover, planned, x)
            for x in planned
            if x.part.parent == parent
        ]
        for parent in parents
    }
    if "father" in segments:
        temp = Draft(segments=segments["father"])
        _insurance_lines(temp, scenario, params, father_coverage(scenario))
        segments["father"] = temp.segments
    for parent, default_id in (("mother", "parental"), ("father", "parental-father")):
        if parent not in segments:
            continue
        if draft.segment(default_id) is not None:
            draft.replace(default_id, *segments[parent])
        else:
            draft.segments += segments[parent]
    if "mother" in parents and "father" not in parents:
        _move_fathers_option(draft, scenario, params, birth, planned)
    if "father" in parents and "mother" not in parents:
        _shrink_mothers_option(draft, scenario, params, planned)
    mother = [s for s in draft.segments if s.lane != "father"]
    draft.segments = mother + sorted(
        (s for s in draft.segments if s.lane == "father"), key=lambda s: s.start
    )


def _segment(
    scenario: Scenario, params: Params, cover: Coverage, planned: list[Planned], x: Planned
) -> Segment:
    p = params.parental
    pp = params.parental_plan
    part = x.part
    parent = part.parent
    who = WHO[parent].capitalize()
    total, _ = parental_weeks(scenario, params)
    own = [y for y in planned if y.part.parent == parent]
    numbered = f" — część {own.index(x) + 1}" if len(own) > 1 else ""
    with_work = " z pracą" if part.work_fraction is not None else ""
    title = f"Urlop rodzicielski{' taty' if parent == 'father' else ''}{with_work}{numbered}"
    in_plan = (
        f" To część {x.number} z {len(planned)} w planie rodziców." if len(planned) > 1 else ""
    )
    details: list[str] = []
    sources: list[list[SourceRef]] = [
        parental_table(scenario, params).sources,
        p.exclusive_weeks.sources,
        p.max_parts.sources,
    ]
    if len(planned) > 1:
        sources.append(pp.parts_of_both_parents.sources)
    if parent == "father":
        sources.append(
            params.father.parental_uninsured_mother.sources
            if cover in NOT_INSURED
            else params.father.parental_together.sources
        )
    if part.work_fraction is None:
        summary = (
            f"{who} bierze {part.weeks} tyg. urlopu rodzicielskiego: od {fmt(x.start)} do "
            f"{fmt(x.end)}.{in_plan}"
        )
    else:
        share = fraction(part.work_fraction)
        work_end = x.work_end
        assert work_end is not None
        summary = (
            f"{who} bierze {part.weeks} tyg. urlopu rodzicielskiego i przez {work_weeks(part)} "
            f"tyg. pracuje na {share} etatu. Urlop wydłuża się o {extension_label(x.extension)}, "
            f"więc trwa od {fmt(x.start)} do {fmt(x.end)}.{in_plan}"
        )
        request = params.parental_plan.work_request_days.value
        details += [
            f"Od {fmt(x.start)} do {fmt(work_end)} {WHO[parent]} łączy urlop z pracą na {share} "
            "etatu u pracodawcy, który udziela urlopu; urlop obejmuje pozostałą część etatu.",
            "Wydłużenie to liczba tygodni pracy razy wymiar pracy: "
            f"{formula(part)}; przedłuża ono tę część urlopu.",
            "Za okres wydłużonego urlopu rodzicielskiego też przysługuje zasiłek macierzyński.",
            f"Pracę w czasie urlopu podejmuje się na wniosek złożony co najmniej {request} dni "
            f"przed jej rozpoczęciem, czyli najpóźniej {fmt(x.start - request * DAY)}.",
        ]
        sources += [
            pp.max_work_fraction.sources,
            pp.rest_of_time.sources,
            pp.extension.sources,
            pp.extension_in_days.sources if x.extension % 7 else [],
            pp.extension_of_that_part.sources,
            pp.extension_paid.sources,
            pp.work_request_days.sources,
        ]
    others = [
        y for y in planned if y.part.parent != parent and y.start <= x.end and y.end >= x.start
    ]
    if others:
        other = WHO[others[0].part.parent]
        details.append(
            f"W tym czasie z urlopu korzysta też {other}. Rodzice mogą korzystać z urlopu "
            f"rodzicielskiego jednocześnie, ale razem nie więcej niż {total} tyg."
        )
        sources.append(pp.both_at_once.sources)
    details.append(WEEK_IS_7_DAYS)
    sources += [p.week_is_7_days.sources, params.rules.week_is_7_days.sources]
    if not scenario.child_born:
        details.append(ESTIMATE)
    return Segment(
        id=x.id,
        lane=parent,
        tone="leave",
        title=title,
        start=x.start,
        end=x.end,
        days=days_between(x.start, x.end),
        summary=summary,
        details=details,
        sources=merge_sources(*sources),
    )


def _move_fathers_option(
    draft: Draft, scenario: Scenario, params: Params, birth: dt.date, planned: list[Planned]
) -> None:
    """The father's 9 weeks, shown after the mother's share, follow her planned parts."""
    option = draft.segment("parental-father")
    if option is None:
        return
    weeks = params.parental.exclusive_weeks.value
    deadline = parental_deadline(birth, params)
    start = max(x.end for x in planned) + DAY
    if start > deadline:
        draft.replace("parental-father")
        return
    full_end = start + weeks * WEEK - DAY
    end = min(full_end, deadline)
    shown = f"{weeks} tyg." if end == full_end else f"{days_between(start, end)} dni"
    details = [d for d in option.details if not d.startswith("Urlop musi się skończyć do")]
    if end < full_end:
        details.append(f"Urlop musi się skończyć do {fmt(deadline)}, dlatego pokazujemy go krócej.")
    draft.replace(
        "parental-father",
        option.model_copy(
            update={
                "start": start,
                "end": end,
                "days": days_between(start, end),
                "summary": (
                    f"Tata ma {weeks} tyg. urlopu rodzicielskiego wyłącznie dla siebie: nie można "
                    "ich przenieść na mamę. Rodzice mogą korzystać z urlopu jednocześnie albo "
                    "naprzemiennie; pokazujemy go po zaplanowanym urlopie mamy: "
                    f"{shown}, od {fmt(start)} do {fmt(end)}."
                ),
                "details": details,
            }
        ),
    )


def _shrink_mothers_option(
    draft: Draft, scenario: Scenario, params: Params, planned: list[Planned]
) -> None:
    """The mother's share, still an option, is what the father's parts leave of the pool."""
    option = draft.segment("parental")
    if option is None:
        return
    total, one_parent = parental_weeks(scenario, params)
    fathers = sum(x.part.weeks for x in planned)
    weeks = min(one_parent, total - fathers)
    if weeks == one_parent:
        return
    end = option.start + weeks * WEEK - DAY
    draft.replace(
        "parental",
        option.model_copy(
            update={
                "end": end,
                "days": weeks * 7,
                "summary": (
                    f"Po urlopie macierzyńskim mama może wziąć urlop rodzicielski. Rodzice mają "
                    f"razem do {total} tyg., a w planie taty jest {fathers} tyg., więc mamie "
                    f"zostaje najwięcej {weeks} tyg. Wzięte w całości od razu, trwałyby do "
                    f"{fmt(end)}."
                ),
            }
        ),
    )


# The case explanation (explain.py puts these notes before "Co policzyliśmy").


def parental_plan_notes(scenario: Scenario, timeline: Timeline, params: Params) -> list[CaseNote]:
    """The plan: how the parents split the leave, what working gives, and the dates. Dates are
    read from the timeline; the formula numbers come from the plan itself."""
    parts = scenario.parental_parts
    segments = {s.id: s for s in timeline.segments}
    shown = [
        (part, segments[part_id])
        for part, part_id in zip(parts, part_ids(parts), strict=True)
        if part_id in segments
    ]
    if not shown:
        return []
    return [
        note
        for note in (
            _split_note(scenario, timeline, params, shown),
            _work_note(scenario, params, shown),
            _computed_note(scenario, params, shown),
        )
        if note is not None
    ]


def _split_note(
    scenario: Scenario,
    timeline: Timeline,
    params: Params,
    shown: list[tuple[ParentalPart, Segment]],
) -> CaseNote:
    p = params.parental
    pp = params.parental_plan
    total, _ = parental_weeks(scenario, params)
    deadline = parental_deadline(timeline.birth_date, params)
    count = len(shown)
    weeks: dict[Role, int] = {"mother": 0, "father": 0}
    for part, _ in shown:
        weeks[part.parent] += part.weeks
    who = ", ".join(f"{WHO[r]} {w} tyg." for r, w in weeks.items() if w)
    used = sum(weeks.values())
    text = (
        "Rodzice mogą korzystać z urlopu rodzicielskiego jednocześnie albo naprzemiennie, "
        f"a okres urlopu mogą podzielić najwyżej na {p.max_parts.value} części, do "
        f"{long_date(deadline)}. W Waszym planie jest {count} {_parts_word(count)}: {who}; "
        f"razem {used} z {total} tyg."
    )
    if used < total:
        text += f" Z puli zostaje {total - used} tyg."
    sources = [
        pp.both_at_once.sources,
        pp.parts_of_both_parents.sources,
        p.max_parts.sources,
        parental_table(scenario, params).sources,
    ]
    together = any(
        a.lane != b.lane and a.start <= b.end and b.start <= a.end
        for _, a in shown
        for _, b in shown
    )
    if together:
        text += f" Część urlopu bierzecie jednocześnie: razem nie możecie przekroczyć {total} tyg."
    return CaseNote(
        id="parental-plan",
        kind="choice",
        title="Wasz podział urlopu rodzicielskiego",
        text=text,
        sources=merge_sources(*sources),
    )


def _work_note(
    scenario: Scenario, params: Params, shown: list[tuple[ParentalPart, Segment]]
) -> CaseNote | None:
    pp = params.parental_plan
    working = sorted({part.parent for part, _ in shown if part.work_fraction is not None})
    if not working:
        return None
    who = " i ".join(WHO[r] for r in working).capitalize()
    can = "mogą" if len(working) > 1 else "może"
    table = pp.max_weeks_with_work_za_zyciem if scenario.za_zyciem else pp.max_weeks_with_work
    cap = for_children(table, scenario.children_count)
    request = pp.work_request_days.value
    return CaseNote(
        id="parental-work",
        kind="relief",
        title="Praca w czasie urlopu rodzicielskiego wydłuża urlop",
        text=(
            f"{who} {can} łączyć urlop rodzicielski z pracą u pracodawcy, który udziela urlopu, "
            f"najwyżej na {fraction(pp.max_work_fraction.value)} etatu; urlop obejmuje wtedy "
            "pozostałą część etatu. Urlop wydłuża się proporcjonalnie do wymiaru pracy — "
            f"łącznie najwyżej do {cap} tyg. — a za wydłużony okres też przysługuje zasiłek "
            f"macierzyński. Pracę podejmuje się na wniosek złożony co najmniej {request} dni "
            "przed jej rozpoczęciem."
        ),
        sources=merge_sources(
            pp.max_work_fraction.sources,
            pp.rest_of_time.sources,
            pp.extension.sources,
            table.sources,
            pp.extension_paid.sources,
            pp.work_request_days.sources,
        ),
    )


def _computed_note(
    scenario: Scenario, params: Params, shown: list[tuple[ParentalPart, Segment]]
) -> CaseNote:
    pp = params.parental_plan
    p = params.parental
    lines = []
    in_days = False
    sources: list[list[SourceRef]] = [parental_table(scenario, params).sources]
    for number, (part, segment) in enumerate(shown, 1):
        who = WHO[part.parent]
        if part.work_fraction is None:
            lines.append(
                f"Część {number}, {who}: {part.weeks} tyg., od {long_date(segment.start)} do "
                f"{long_date(segment.end)}."
            )
            continue
        extension = segment.days - part.weeks * 7
        in_days = in_days or extension % 7 != 0
        lines.append(
            f"Część {number}, {who}: {part.weeks} tyg., z czego {work_weeks(part)} tyg. "
            f"z pracą na {fraction(part.work_fraction)} etatu. Wydłużenie: {formula(part)}, "
            f"więc ta część trwa {segment.days} dni: od {long_date(segment.start)} do "
            f"{long_date(segment.end)}."
        )
    if any(part.work_fraction is not None for part, _ in shown):
        sources += [pp.extension.sources, pp.extension_of_that_part.sources]
        if in_days:
            sources.append(pp.extension_in_days.sources)
    sources += [p.week_is_7_days.sources, params.rules.week_is_7_days.sources]
    return CaseNote(
        id="parental-plan-computed",
        kind="computed",
        title="Co policzyliśmy w planie urlopu rodzicielskiego",
        text=" ".join(lines) + f" {WEEK_IS_7_DAYS}",
        sources=merge_sources(*sources),
    )


# The assistant's tools.


def default_part(
    scenario: Scenario, params: Params, timeline: Timeline, parent: Role
) -> ParentalPart:
    """That parent's whole share, as the timeline shows it without a plan, as one part. The
    weeks are what the pool still has for that parent after the plan's other parts."""
    total, one_parent = parental_weeks(scenario, params)
    mother_has_a_share = any(
        s.lane == "mother" and s.id.startswith("parental") for s in timeline.segments
    )
    share = (
        params.parental.exclusive_weeks.value
        if parent == "father" and mother_has_a_share
        else one_parent
    )
    others = sum(part.weeks for part in scenario.parental_parts if part.parent != parent)
    weeks = min(share, total - others)
    if weeks < 1:
        raise ScenarioError(f"Z puli urlopu rodzicielskiego nie zostało nic dla: {WHO[parent]}.")
    return ParentalPart(parent=parent, weeks=weeks)
