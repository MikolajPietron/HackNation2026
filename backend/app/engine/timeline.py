"""Rules of the phases done so far (guide section A, pages 5-6, and the Labour Code).

Phase 1, preparing for the birth (A.1):
- maternity leave may start at most N weeks before the expected due date;
- that needs a medical certificate of the expected due date;
- the mother may also work until the birth; the benefit then starts after the birth.

Phase 2, the birth (A.2):
- after the birth the insured woman acquires the right to the maternity benefit; a mother who is
  not covered by sickness insurance on that day has no benefit periods (see insurance.py);
- maternity leave lasts T weeks, depending on how many children are born at once; a week of
  leave is 7 calendar days; weeks used before the birth count towards T; without leave before
  the birth the leave starts on the day of the birth; the first 14 weeks after the birth the
  mother uses personally (Labour Code art. 180 § 1-3, art. 183¹ § 1-2);
- after maternity leave, in strictly defined situations: supplementary maternity leave, a week
  for every week the child spent in hospital (guide section C; art. 180², see supplementary.py);
- then parental leave: P weeks for both parents together, of which E belong to each parent
  alone, in one piece or in at most 5 parts, until the end of the calendar year in which the
  child turns 6; longer with the "Za życiem" certificate (art. 182¹ᵃ, 182¹ᶜ).

Phase 3, stillbirth or death of the child (A.3; art. 180¹, see loss.py): maternity leave of
8 weeks after the birth (not less than 7 days from the death), or kept for 7 days from a later
death; with more children it follows the number who live. Without a living child there is no
parental leave, and leave already under way is kept for 7 days from the death.

Section B, the father (pages 7-8; see father.py), after the mother's rules: special situations
or taking over maternity leave, paternity leave, the father's part of parental leave. It runs
also when the mother has no benefit periods.

Pure and deterministic: no I/O, no database, no LLM; `today` is an argument. Every number comes
from `Params`, every element carries its sources. Later phases add rules after these.
"""

import datetime as dt
from collections.abc import Callable

from app.engine.adoption import taken_in_timeline
from app.engine.applications import add_applications
from app.engine.draft import DAY, WEEK, Draft, merge_sources
from app.engine.explain import case_notes
from app.engine.father import father_rules
from app.engine.insurance import INSURED, NOT_INSURED, Coverage, coverage, father_coverage
from app.engine.loss import Loss, child_loss, maternity_end_after_loss
from app.engine.models import (
    Document,
    Marker,
    Payment,
    Scenario,
    ScenarioError,
    Segment,
    Timeline,
    TimelineElement,
)
from app.engine.money import money_assumptions, money_rules
from app.engine.params import Params
from app.engine.parental import (
    deadline_marker,
    deadline_passed,
    for_children,
    parental_deadline,
    parental_table,
    parental_weeks,
)
from app.engine.parental_plan import parental_plan_rules
from app.engine.pregnancy import pregnancy_rules
from app.engine.supplementary import describe_case, supplementary_leave
from app.engine.wording import children_phrase, fmt, weeks_or_days

__all__ = ["DAY", "WEEK", "build_timeline", "changed_element_ids", "fmt"]


def build_timeline(scenario: Scenario, params: Params, today: dt.date) -> Timeline:
    if scenario.taken_in is not None:
        # Guide section D: a child taken in for upbringing has its own rules (adoption.py).
        timeline = taken_in_timeline(scenario, params, today)
        timeline.notes = case_notes(scenario, timeline, params)
        return timeline
    born = scenario.child_born is True
    birth = scenario.anchor_date
    if birth is None:
        raise ScenarioError("Najpierw potrzebna jest data porodu: przewidywana albo faktyczna.")
    weeks = scenario.leave_before_birth_weeks
    limit = params.maternity.max_weeks_before_birth
    if weeks is not None and weeks > limit.value and not born:
        raise ScenarioError(
            f"Urlop macierzyński można zacząć maksymalnie {limit.value} tyg. przed przewidywaną "
            "datą porodu."
        )
    table = params.maternity.weeks_by_children.value
    count = scenario.children_count
    before_days = scenario.prenatal_days(birth)
    if born and before_days and count and before_days >= table[min(count, len(table)) - 1] * 7:
        raise ScenarioError(
            "Tyle tygodni przed porodem to cały urlop macierzyński. Sprawdź liczbę tygodni."
        )

    cover = coverage(scenario)
    loss = child_loss(scenario, params, birth, today)
    draft = Draft()
    if cover in NOT_INSURED:
        # No benefit periods to draw: the day of the birth and the rule it stands for.
        draft.markers.append(_birth_marker_uninsured(scenario, params, birth))
    else:
        if born:
            _before_birth_past(draft, scenario, params, birth)
        else:
            _before_birth_plan(draft, scenario, params, birth)
        draft.markers.append(_birth_marker(scenario, params, birth))
        if scenario.children_count is not None:
            maternity_end = _maternity_after_birth(
                draft, scenario, params, birth, today, cover, loss
            )
            # A stillbirth or an early death of every child: maternity leave is all there is.
            if loss is None or not (loss.none_survived and loss.early):
                after = _supplementary(draft, scenario, params, birth, maternity_end, today)
                _parental(draft, scenario, params, birth, after, today)
            if loss is not None and loss.none_survived:
                _keep_seven_days(draft, loss, params)
    # Section B, after the mother's rules: it may shorten her maternity leave and adds the
    # father's lane, also when the mother herself has no benefit periods.
    father_rules(draft, scenario, params, birth, today, cover, loss)
    # Guide E and B.3: the parents' own plan of parental leave, when they told us one.
    plan_assumptions = parental_plan_rules(draft, scenario, params, birth, today, cover, loss)
    _for_non_employee(draft, scenario, params, cover)
    # Pregnancy (guide pages 2-4, section H): sick leave and the benefit after losing the job.
    pregnancy = pregnancy_rules(draft, scenario, params, birth)
    # Section G, last: the amount for every period both parents' rules left on the timeline.
    money_rules(draft, scenario, params, birth, cover, loss)
    draft.markers.sort(key=lambda m: m.date)

    if not born and birth < today:
        draft.warnings.append(
            f"Przewidywana data porodu ({fmt(birth)}) już minęła. Jeśli dziecko się urodziło, "
            "podaj faktyczną datę urodzenia — oś się przeliczy."
        )

    timeline = Timeline(
        params_version=params.version,
        today=today,
        birth_date=birth,
        child_born=born,
        children_count=scenario.children_count,
        segments=draft.segments,
        markers=draft.markers,
        documents=draft.documents,
        warnings=draft.warnings,
        assumptions=_assumptions(scenario, params, born, cover, loss, draft)
        + pregnancy
        + plan_assumptions,
        payments=draft.payments,
    )
    timeline.assumptions += money_assumptions(scenario, timeline, params)
    # Applications and protection (guide A.4, I): who pays, requests, protection.
    add_applications(timeline, scenario, params)
    timeline.notes = case_notes(scenario, timeline, params)
    return timeline


def _for_non_employee(draft: Draft, scenario: Scenario, params: Params, cover: Coverage) -> None:
    """A mother on a contract or with her own business gets no leave, only the benefit for the
    same periods (guide page 4); every period of leave on her lane says so. The father's lane
    has its own line (father.py)."""
    if scenario.mothers_work not in ("contract", "business") or cover in NOT_INSURED:
        return
    b = params.benefit
    note = (
        "Mama nie jest pracownicą, więc nie dostaje urlopu: ma prawo do zasiłku macierzyńskiego "
        "za okres odpowiadający urlopowi, na tych samych zasadach co do wymiaru."
    )
    draft.segments = [
        segment.model_copy(
            update={
                "details": [*segment.details, note],
                "sources": merge_sources(
                    segment.sources, b.non_employees.sources, b.same_rules_for_non_employees.sources
                ),
            }
        )
        if segment.lane == "mother" and segment.tone != "work"
        else segment
        for segment in draft.segments
    ]


def changed_element_ids(old: Timeline | None, new: Timeline) -> list[str]:
    """Elements that are new or changed since `old` — the UI highlights them."""
    if old is None:
        return []
    before = {e.id: _signature(e) for e in old.elements()}
    return [e.id for e in new.elements() if before.get(e.id) != _signature(e)]


def _signature(e: TimelineElement) -> tuple[object, ...]:
    match e:
        case Segment():
            return ("segment", e.start, e.end, e.title)
        case Marker():
            return ("marker", e.date, e.title)
        case Document():
            return ("document", e.needed_by, e.title, e.done)
        case Payment():
            return ("payment", e.start, e.end, e.rate, e.total)


def _before_birth_plan(draft: Draft, scenario: Scenario, params: Params, due: dt.date) -> None:
    """Phase 1 while the child is on the way: leave before the birth or work until the birth."""
    weeks = scenario.leave_before_birth_weeks
    limit = params.maternity.max_weeks_before_birth
    certificate = params.rules.medical_certificate
    work = params.rules.work_until_birth
    earliest = due - limit.value * WEEK
    last_day_before = due - DAY

    if weeks is None:
        draft.segments.append(
            Segment(
                id="prenatal-window",
                lane="mother",
                tone="option",
                title="Urlop macierzyński przed porodem — do wyboru",
                start=earliest,
                end=last_day_before,
                days=limit.value * 7,
                summary=(
                    f"Mama może zacząć urlop macierzyński najwcześniej {fmt(earliest)}, czyli "
                    f"maksymalnie {limit.value} tyg. przed przewidywaną datą porodu. "
                    "Może też pracować do dnia porodu."
                ),
                details=[
                    "Na urlop przed porodem potrzebne jest zaświadczenie lekarskie "
                    "o przewidywanej dacie porodu.",
                    "Jeśli pracuje do dnia porodu, zasiłek zaczyna się po urodzeniu dziecka.",
                ],
                sources=[*limit.sources, *certificate.sources, *work.sources],
            )
        )
        return

    if weeks == 0:
        draft.segments.append(
            Segment(
                id="work-until-birth",
                lane="mother",
                tone="work",
                title="Praca do dnia porodu",
                start=earliest,
                end=last_day_before,
                days=limit.value * 7,
                summary=(
                    "Mama pracuje do dnia porodu. Zasiłek macierzyński zaczyna się po urodzeniu "
                    "dziecka."
                ),
                details=[
                    f"Urlop macierzyński mogłaby zacząć najwcześniej {fmt(earliest)} "
                    f"(maksymalnie {limit.value} tyg. przed przewidywaną datą porodu)."
                ],
                sources=[*work.sources, *limit.sources],
            )
        )
        return

    start = due - weeks * WEEK
    draft.segments.append(
        Segment(
            id="maternity-prenatal",
            lane="mother",
            tone="leave",
            title="Urlop macierzyński przed porodem",
            start=start,
            end=last_day_before,
            days=weeks * 7,
            summary=(
                f"Mama zaczyna urlop macierzyński {fmt(start)}, czyli {weeks} tyg. przed "
                "przewidywaną datą porodu."
            ),
            details=[
                f"Najwcześniej można go zacząć {limit.value} tyg. przed przewidywaną datą porodu.",
                "Potrzebne jest zaświadczenie lekarskie o przewidywanej dacie porodu.",
            ],
            sources=[*limit.sources, *certificate.sources],
        )
    )
    if weeks < limit.value:
        draft.markers.append(
            Marker(
                id="earliest-start",
                lane="child",
                label="Najwcześniej",
                title="Najwcześniejszy start urlopu macierzyńskiego",
                date=earliest,
                summary=(
                    f"Urlop macierzyński można zacząć maksymalnie {limit.value} tyg. przed "
                    "przewidywaną datą porodu."
                ),
                sources=limit.sources,
            )
        )
    draft.documents.append(
        Document(
            id="medical-certificate",
            label="Zaświadczenie lekarskie",
            title="Zaświadczenie lekarskie o przewidywanej dacie porodu",
            needed_by=start,
            done=scenario.has_medical_certificate is True,
            rule=(
                "Mama potrzebuje go, żeby zacząć urlop macierzyński przed przewidywaną datą porodu."
            ),
            segment_id="maternity-prenatal",
            sources=certificate.sources,
        )
    )


def _before_birth_past(draft: Draft, scenario: Scenario, params: Params, birth: dt.date) -> None:
    """Phase 1 once the child is born: leave the mother already took before the birth."""
    days = scenario.prenatal_days(birth)
    if not days:
        return
    limit = params.maternity.max_weeks_before_birth.value
    start = birth - days * DAY
    details = ["To część urlopu macierzyńskiego, a nie dodatkowe tygodnie."]
    if scenario.leave_start is not None:
        details.append(
            f"Urlop zaczął się {fmt(start)}, jak był zaplanowany przed przewidywaną datą porodu; "
            "dziecko urodziło się innego dnia, więc przed porodem trwał "
            f"{weeks_or_days(days)}."
        )
    if days > limit * 7:
        details.append(
            f"Limit {limit} tyg. dotyczy czasu przed przewidywaną datą porodu, więc gdy dziecko "
            "urodziło się później, tygodni przed porodem może być więcej."
        )
    draft.segments.append(
        Segment(
            id="maternity-prenatal",
            lane="mother",
            tone="leave",
            title="Urlop macierzyński przed porodem",
            start=start,
            end=birth - DAY,
            days=days,
            summary=f"Mama była na urlopie macierzyńskim od {fmt(start)}, "
            f"{weeks_or_days(days)} przed porodem.",
            details=details,
            sources=[
                *params.maternity.max_weeks_before_birth.sources,
                *params.rules.rest_after_birth.sources,
            ],
        )
    )


def _birth_marker(scenario: Scenario, params: Params, birth: dt.date) -> Marker:
    if scenario.child_born:
        return Marker(
            id="birth",
            lane="child",
            label="Poród",
            title="Poród"
            if any(loss.stillborn for loss in scenario.losses)
            else "Narodziny dziecka",
            date=birth,
            summary="Od tego dnia liczymy urlop macierzyński po porodzie.",
            sources=params.rules.rest_after_birth.sources,
        )
    works_until_birth = scenario.leave_before_birth_weeks == 0
    return Marker(
        id="due-date",
        lane="child",
        label="Termin porodu",
        title="Przewidywana data porodu",
        date=birth,
        summary=(
            "Po urodzeniu dziecka zaczyna się zasiłek macierzyński."
            if works_until_birth
            else "Od tej daty liczymy urlop macierzyński: przed porodem i po porodzie."
        ),
        sources=(
            params.rules.work_until_birth.sources
            if works_until_birth
            else params.maternity.max_weeks_before_birth.sources
        ),
    )


def _birth_marker_uninsured(scenario: Scenario, params: Params, birth: dt.date) -> Marker:
    born = scenario.child_born is True
    return Marker(
        id="birth" if born else "due-date",
        lane="child",
        label="Poród" if born else "Termin porodu",
        title="Narodziny dziecka" if born else "Przewidywana data porodu",
        date=birth,
        summary=(
            "Prawo do zasiłku macierzyńskiego nabywa po porodzie mama ubezpieczona. Liczy się, "
            "czy w dniu porodu podlega ubezpieczeniu chorobowemu."
        ),
        sources=merge_sources(
            params.benefit.insured_mother.sources, params.benefit.insured_on_birth_day.sources
        ),
    )


def _maternity_after_birth(
    draft: Draft,
    scenario: Scenario,
    params: Params,
    birth: dt.date,
    today: dt.date,
    cover: Coverage,
    loss: Loss | None,
) -> dt.date:
    """Phases 2 and 3: how long maternity leave lasts, the 14 weeks after the birth and the
    benefit for that period. Returns the last day of the leave."""
    m = params.maternity
    rules = params.rules
    born = scenario.child_born is True
    count = scenario.children_count
    assert count is not None
    table = m.weeks_by_children.value
    weeks = scenario.leave_before_birth_weeks
    before_days = scenario.prenatal_days(birth) if born else (weeks or 0) * 7
    start = birth - before_days * DAY

    def weeks_for(children: int) -> int:
        return table[min(children, len(table)) - 1]

    def end_for(children: int) -> dt.date:
        return start + weeks_for(children) * WEEK - DAY

    total = weeks_for(count)
    end = end_for(count)
    if loss is not None:
        end = maternity_end_after_loss(loss, params, birth, end_for)

    details = ["Tydzień urlopu to 7 dni kalendarzowych."]
    sources = [*m.weeks_by_children.sources, *rules.week_is_7_days.sources]
    if before_days:
        details.append(
            f"{weeks_or_days(before_days)} wykorzystane przed porodem wliczają się do "
            f"{total} tyg.; reszta przysługuje po porodzie."
        )
        sources += rules.rest_after_birth.sources
    elif weeks is None and not born:
        details.append(
            f"Jeśli mama zacznie urlop przed porodem, te tygodnie wliczą się do {total} tyg., "
            "a urlop po porodzie skończy się odpowiednio wcześniej."
        )
        sources += rules.rest_after_birth.sources
    else:
        if weeks is None:
            details.append("Na razie liczymy tak, jakby mama nie była na urlopie przed porodem.")
        details.append("Bez urlopu przed porodem pierwszym dniem urlopu jest dzień porodu.")
        sources += rules.first_day_is_birth.sources
    benefit = params.benefit
    if cover == "obligatory":
        details.append(
            "Mama jest ubezpieczona, więc za ten okres ma prawo do zasiłku macierzyńskiego."
        )
        sources += benefit.insured_mother.sources
    elif cover == "voluntary":
        details.append(
            "Mama jest zgłoszona do dobrowolnego ubezpieczenia chorobowego, więc za ten okres ma "
            "prawo do zasiłku macierzyńskiego."
        )
        sources += [*benefit.insured_mother.sources, *benefit.voluntary_insurance.sources]
    else:
        details.append(
            "Zasiłek macierzyński za ten okres przysługuje mamie ubezpieczonej. Na razie "
            "zakładamy, że nią jest."
        )
        sources += benefit.insured_mother.sources
    if not born:
        details.append(
            "Liczymy od przewidywanej daty porodu. Po porodzie oś przeliczy się od faktycznej daty."
        )

    in_total = f", w tym {weeks_or_days(before_days)} przed porodem" if before_days else ""
    summary = (
        f"Urlop macierzyński przy urodzeniu {children_phrase(count)} trwa "
        f"{total} tyg.{in_total}; po porodzie do {fmt(end)}."
    )
    if loss is not None:
        summary, more = _after_loss(loss, params, birth, end, weeks_for)
        # The loss explains the length; what it replaces would only confuse.
        details = [
            d
            for d in details
            if not d.startswith("Tydzień urlopu")
            and not (loss.none_survived and "wliczają się do" in d)
        ] + more
        details.append("Tydzień urlopu to 7 dni kalendarzowych.")
        sources = [
            *sources,
            *params.loss.weeks_after_birth.sources,
            *params.loss.days_after_death.sources,
            *(params.loss.survivors.sources if loss.survivors or loss.count > 1 else []),
        ]
    draft.segments.append(
        Segment(
            id="maternity",
            lane="mother",
            tone="leave",
            title="Urlop macierzyński po porodzie",
            start=birth,
            end=end,
            days=(end - birth).days + 1,
            summary=summary,
            details=details,
            sources=merge_sources(sources),
        )
    )

    if loss is not None and loss.none_survived:
        return end
    personal = m.mother_personal_weeks
    estimate = "" if born else " Liczymy od przewidywanej daty porodu."
    draft.markers.append(
        Marker(
            id="personal-weeks",
            lane="child",
            label=f"{personal.value} tyg. po porodzie",
            title=f"Koniec {personal.value} tygodni po porodzie",
            date=birth + personal.value * WEEK - DAY,
            summary=(
                f"Pierwsze {personal.value} tygodni po porodzie mama wykorzystuje osobiście."
                f"{estimate}"
            ),
            sources=personal.sources,
        )
    )

    if born and end < today:
        draft.warnings.append(f"Urlop macierzyński skończył się {fmt(end)}.")
    return end


def _after_loss(
    loss: Loss,
    params: Params,
    birth: dt.date,
    end: dt.date,
    weeks_for: Callable[[int], int],
) -> tuple[str, list[str]]:
    """Phase 3: the summary and details of maternity leave after a stillbirth or a death."""
    days = params.loss.days_after_death.value
    weeks = params.loss.weeks_after_birth.value
    until = loss.until(params)
    if loss.survivors:
        living, born = weeks_for(loss.survivors), weeks_for(loss.count + loss.survivors)
        summary = (
            "Urlop macierzyński liczy się według liczby dzieci pozostałych przy życiu "
            f"({loss.survivors}): {living} tyg. zamiast {born}; po porodzie do {fmt(end)}."
        )
        more = []
        if end == until:
            more.append(
                f"Urlop trwa nie krócej niż {days} dni od dnia śmierci dziecka, czyli do "
                f"{fmt(end)}."
            )
        return summary, more
    if loss.early:
        lost = "urodziło się martwe" if loss.stillborn == loss.count else "zmarło"
        when = "" if loss.stillborn == loss.count else f" {fmt(loss.last)}"
        summary = (
            f"Urlop macierzyński trwa {weeks} tygodni po porodzie, nie krócej jednak niż {days} "
            f"dni od dnia śmierci dziecka: do {fmt(end)}."
        )
        more = [f"Dziecko {lost}{when}."]
        if end == until and end > birth + (weeks * 7 - 1) * DAY:
            more.append(
                f"{days} dni od dnia śmierci mija później niż {weeks} tygodni po porodzie, "
                f"dlatego urlop trwa do {fmt(end)}."
            )
        return summary, more
    if end < until:
        summary = (
            f"Urlop macierzyński trwał do {fmt(end)}: skończył się przed śmiercią dziecka."
            if end < loss.last
            else f"Mama zachowuje urlop macierzyński przez {days} dni od dnia śmierci dziecka, "
            f"ale nie dłużej, niż trwałby bez tej zmiany: do {fmt(end)}."
        )
    else:
        summary = (
            f"Mama zachowuje urlop macierzyński przez {days} dni od dnia śmierci dziecka: do "
            f"{fmt(end)}."
        )
    return summary, [f"Dziecko zmarło {fmt(loss.last)}, po upływie {weeks} tygodni życia."]


def _keep_seven_days(draft: Draft, loss: Loss, params: Params) -> None:
    """Phase 3, no child lives: supplementary or parental leave under way at the death is kept
    for 7 days from it; nothing starts later, and the parental leave deadline goes."""
    until = loss.until(params)
    days = params.loss.days_after_death.value
    kept = []
    for segment in draft.segments:
        if segment.id not in ("supplementary", "parental") or segment.end <= until:
            kept.append(segment)
        elif segment.start <= until:
            kept.append(
                segment.model_copy(
                    update={
                        "end": until,
                        "days": (until - segment.start).days + 1,
                        "summary": (
                            f"Dziecko zmarło {fmt(loss.last)}. Prawo do tego urlopu zostaje przez "
                            f"{days} dni od dnia śmierci dziecka: do {fmt(until)}."
                        ),
                        "details": ["Tydzień urlopu to 7 dni kalendarzowych."],
                        "sources": merge_sources(segment.sources, params.loss.other_leaves.sources),
                    }
                )
            )
    draft.segments = kept
    draft.markers = [m for m in draft.markers if m.id != "parental-deadline"]


def _supplementary(
    draft: Draft,
    scenario: Scenario,
    params: Params,
    birth: dt.date,
    maternity_end: dt.date,
    today: dt.date,
) -> dt.date:
    """Phase 2: supplementary maternity leave right after maternity leave, when the child was
    born prematurely or needed hospital. Returns the last day before parental leave."""
    if not scenario.child_born:
        return maternity_end
    leave = supplementary_leave(scenario, params, birth, today)
    if leave is None or leave.weeks == 0:
        return maternity_end
    s = params.supplementary
    start = maternity_end + DAY
    end = start + leave.weeks * WEEK - DAY
    details = [
        describe_case(leave, params),
        f"Policzyliśmy {leave.days} {_days(leave.days)} pobytu dziecka w szpitalu między "
        f"{fmt(leave.first_day)} a {fmt(leave.last_day)}. Okresy pobytu sumuje się"
        + (
            f", a niepełny tydzień zaokrągla w górę: stąd {leave.weeks} tyg."
            if leave.days % 7
            else f": to {leave.weeks} tyg."
        ),
    ]
    if leave.ongoing:
        grow = (
            f" Wymiar może jeszcze wzrosnąć, najwyżej do {leave.max_weeks} tyg."
            if leave.max_weeks > leave.weeks
            else ""
        )
        details.append(
            f"Dziecko jest jeszcze w szpitalu, więc liczymy do dziś ({fmt(today)}).{grow}"
        )
    count = scenario.children_count or 1
    if count > 1:
        details.append(
            "Przy więcej niż jednym dziecku liczy się masa najlżejszego dziecka i pobyt dziecka, "
            "które było w szpitalu najdłużej."
        )
    details += [
        "Urlop jest udzielany jednorazowo, bez dzielenia na części, bezpośrednio po urlopie "
        "macierzyńskim.",
        "Dzień porodu liczymy jako pierwszy dzień po porodzie, jak przy urlopie macierzyńskim. "
        "Tydzień urlopu to 7 dni kalendarzowych.",
    ]
    case_sources = {
        "early": s.limit_weeks_early.sources,
        "preterm": s.limit_weeks_preterm.sources,
        "term": s.term.sources,
    }[leave.case]
    draft.segments.append(
        Segment(
            id="supplementary",
            lane="mother",
            tone="option",
            title="Uzupełniający urlop macierzyński",
            start=start,
            end=end,
            days=leave.weeks * 7,
            summary=(
                f"Po urlopie macierzyńskim mama albo tata — tylko jedno z nich — może wziąć "
                f"{leave.weeks} tyg. uzupełniającego urlopu macierzyńskiego: tydzień za każdy "
                "tydzień pobytu dziecka w szpitalu."
            ),
            details=details,
            sources=merge_sources(
                s.situations.sources,
                case_sources,
                s.sum_and_round.sources,
                s.multiples.sources if count > 1 else [],
                s.once_after_maternity.sources,
                s.week_is_7_days.sources,
                params.rules.week_is_7_days.sources,
            ),
        )
    )
    return end


def _days(count: int) -> str:
    return "dzień" if count == 1 else "dni"


def _parental(
    draft: Draft,
    scenario: Scenario,
    params: Params,
    birth: dt.date,
    after: dt.date,
    today: dt.date,
) -> None:
    """Phase 2: parental leave after maternity (and supplementary) leave. The mother's whole
    share is drawn right after, as an option: when and in how many parts is her choice."""
    p = params.parental
    born = scenario.child_born is True
    total, mothers = parental_weeks(scenario, params)
    exclusive = p.exclusive_weeks.value
    deadline = parental_deadline(birth, params)
    age = p.deadline_age.value
    if deadline < today:
        draft.warnings.append(deadline_passed(deadline, params))
        return

    start = after + DAY
    end = start + mothers * WEEK - DAY
    count = scenario.children_count
    table = parental_table(scenario, params)
    details = [
        f"Urlop jest udzielany jednorazowo albo w nie więcej niż {p.max_parts.value} częściach.",
        f"Można go wykorzystać od razu po urlopie macierzyńskim albo później, najpóźniej do "
        f"{fmt(deadline)}: to koniec roku kalendarzowego, w którym dziecko kończy {age} lat.",
    ]
    sources = [
        p.after_maternity.sources,
        table.sources,
        p.exclusive_weeks.sources,
        p.joint.sources,
        p.max_parts.sources,
    ]
    if scenario.za_zyciem:
        details.append(
            f"Dziecko ma zaświadczenie „Za życiem”, dlatego rodzice mają razem do {total} tyg. "
            f"zamiast {for_children(p.weeks_by_children, count)}."
        )
    else:
        longer = p.weeks_by_children_za_zyciem
        details.append(
            "Jeśli dziecko ma zaświadczenie „Za życiem”, rodzice mają razem do "
            f"{for_children(longer, count)} tyg. Napisz o tym asystentowi, a oś się przeliczy."
        )
        sources.append(longer.sources)
    if not born:
        details.append(
            "Jeśli dziecko urodzi się przedwcześnie albo będzie wymagało pobytu w szpitalu, przed "
            "urlopem rodzicielskim może przysługiwać jeszcze uzupełniający urlop macierzyński: "
            "tydzień za każdy tydzień pobytu dziecka w szpitalu."
        )
        sources.append(params.supplementary.situations.sources)
    details.append("Tydzień urlopu to 7 dni kalendarzowych.")
    sources.append(p.week_is_7_days.sources)
    sources.append(params.rules.week_is_7_days.sources)
    if not born:
        details.append(
            "Liczymy od przewidywanej daty porodu. Po porodzie oś przeliczy się od faktycznej daty."
        )
    draft.segments.append(
        Segment(
            id="parental",
            lane="mother",
            tone="option",
            title="Urlop rodzicielski — do wyboru",
            start=start,
            end=end,
            days=mothers * 7,
            summary=(
                f"Po urlopie macierzyńskim mama może wziąć urlop rodzicielski. Rodzice mają razem "
                f"do {total} tyg.; każde z nich ma {exclusive} tyg. wyłącznie dla siebie, których "
                f"nie można przenieść, więc mama może wykorzystać najwięcej {mothers} tyg. Wzięte "
                f"w całości od razu, trwałyby do {fmt(end)}."
            ),
            details=details,
            sources=merge_sources(*sources),
        )
    )
    draft.markers.append(deadline_marker(birth, born, params))


def _assumptions(
    scenario: Scenario,
    params: Params,
    born: bool,
    cover: Coverage,
    loss: Loss | None,
    draft: Draft,
) -> list[str]:
    assumptions = [
        "Pokazujemy to, co wynika z Przewodnika ZUS: zasiłki w ciąży, zasiłek macierzyński mamy "
        "i jego wysokość, uprawnienia taty, łączenie urlopu rodzicielskiego z pracą, wnioski "
        "z terminami i szczególna ochrona."
    ]
    mother = cover not in NOT_INSURED
    father = father_coverage(scenario)
    fathers = [s for s in draft.segments if s.lane == "father"]
    if cover not in INSURED and mother:
        assumptions.append(
            "Na razie zakładamy, że mama podlega ubezpieczeniu chorobowemu. Potwierdzi to "
            "pytanie w rozmowie."
        )
    elif mother:
        assumptions.append(
            "Zakładamy, że ubezpieczenie chorobowe mamy trwa w dniu porodu."
            if not born
            else "Zakładamy, że mama podlegała ubezpieczeniu chorobowemu w dniu porodu."
        )
    if not born and (mother or fathers):
        assumptions.append(
            "Liczymy od przewidywanej daty porodu. Po porodzie oś przeliczy się od faktycznej daty."
        )
    if scenario.children_count is None:
        if mother or father not in NOT_INSURED:
            assumptions.append(
                "Długość urlopów pokażemy, gdy będzie wiadomo, ile dzieci urodzi się przy jednym "
                "porodzie."
            )
    elif (parental := draft.segment("parental")) is not None:
        his = draft.segment("parental-father")
        after_her = his is not None and his.start == parental.end + DAY
        weeks = params.parental.exclusive_weeks.value
        assumptions.append(
            "Urlop rodzicielski pokazujemy tak, jakby mama wzięła całą swoją część od razu po "
            "urlopie macierzyńskim"
            + (f", a tata swoje {weeks} tygodni zaraz po niej" if after_her else "")
            + ". Rodzice mogą też korzystać z niego jednocześnie albo naprzemiennie i dzielić go "
            "na części."
        )
    if mother and scenario.hospital_care:
        assumptions.append(
            "Przy uzupełniającym urlopie macierzyńskim dzień porodu liczymy jako pierwszy dzień "
            "po porodzie, jak przy urlopie macierzyńskim. Dzień przyjęcia i wypisu ze szpitala "
            "liczymy jako dni pobytu."
        )
    if mother and loss is not None:
        assumptions.append(
            "7 dni od dnia śmierci dziecka liczymy od następnego dnia. 8 tygodni życia to 56 dni, "
            "licząc dzień urodzenia jako pierwszy. Te 7 dni nie wydłużają urlopu ponad to, ile "
            "trwałby bez tej zmiany."
        )
        if loss.survivors:
            assumptions.append(
                "Długość urlopu rodzicielskiego liczymy według liczby urodzonych dzieci, jak "
                "w Kodeksie pracy (art. 182¹ᵃ § 1). Czy zmienia się po śmierci jednego z nich, "
                "materiały nie mówią."
            )
    return assumptions + _father_assumptions(scenario, params, cover, loss, draft)


def _father_assumptions(
    scenario: Scenario, params: Params, cover: Coverage, loss: Loss | None, draft: Draft
) -> list[str]:
    """Section B: what we assume about the father and where the materials leave a gap."""
    assumptions = []
    mother = cover not in NOT_INSURED
    father = father_coverage(scenario)
    child_lives = loss is None or not loss.none_survived
    shown = {s.id for s in draft.segments} | {m.id for m in draft.markers}
    if any(s.lane == "father" for s in draft.segments) and father not in INSURED:
        assumptions.append(
            "Na razie zakładamy, że tata podlega ubezpieczeniu chorobowemu. Potwierdzi to "
            "pytanie w rozmowie."
        )
    if "paternity-deadline" in shown:
        assumptions.append(
            "Urlop ojcowski można wykorzystać do ukończenia przez dziecko "
            f"{params.father.paternity_months.value} miesięcy życia: przyjmujemy, że ostatnim "
            "dniem jest dzień przed pierwszymi urodzinami."
        )
    # Parental leave on each lane: the option or the parts of the parents' plan.
    fathers = any(s.lane == "father" and s.id.startswith("parental") for s in draft.segments)
    mothers = any(s.lane == "mother" and s.id.startswith("parental") for s in draft.segments)
    if fathers and not mothers:
        assumptions.append(
            "Urlop rodzicielski taty pokazujemy bez "
            f"{params.parental.exclusive_weeks.value} tygodni, których Kodeks pracy nie pozwala "
            "przenieść na drugiego z rodziców (art. 182¹ᵃ § 4). Czy w tej sytuacji tata może "
            "wykorzystać także je, materiały nie mówią."
        )
    event = scenario.mother_event
    if event is None:
        return assumptions
    if not mother:
        assumptions.append(
            "Gdy mama nie była ubezpieczona, oś nie uwzględnia sytuacji szczególnych z części B "
            "Przewodnika: dotyczą one przejęcia urlopu macierzyńskiego mamy, a przepisów o innych "
            "przypadkach nie ma w naszych materiałach."
        )
        return assumptions
    if not child_lives:
        assumptions.append(
            "Gdy żadne dziecko nie żyje, oś nie uwzględnia sytuacji szczególnych z części B "
            "Przewodnika: dotyczą one opieki nad dzieckiem."
        )
        return assumptions
    if "maternity-father" in shown and event.kind != "death":
        assumptions.append(
            f"{params.father.special_after_weeks.value} tygodni urlopu po porodzie liczymy jako "
            f"{params.father.special_after_weeks.value * 7} dni, licząc dzień porodu jako "
            "pierwszy."
        )
    if "maternity-father" in shown and event.kind == "hospital":
        assumptions.append(
            "Pobyt mamy w szpitalu liczymy od dnia przyjęcia do dnia wypisu: tata przejmuje urlop "
            "od dnia przyjęcia, a mama wraca na urlop dzień po wypisie."
        )
    if scenario.children_count is not None and (
        event.kind == "death" or (event.kind == "abandonment" and father not in NOT_INSURED)
    ):
        what = "śmierci mamy" if event.kind == "death" else "porzuceniu dziecka przez mamę"
        assumptions.append(
            f"Po {what} oś nie pokazuje dalszych urlopów mamy."
            + (
                " Uzupełniający urlop macierzyński, jeśli przysługuje, pokazujemy u taty. Jak "
                "w tej sytuacji dzieli się urlop rodzicielski, materiały nie mówią wprost."
                if father not in NOT_INSURED
                else ""
            )
        )
    return assumptions
