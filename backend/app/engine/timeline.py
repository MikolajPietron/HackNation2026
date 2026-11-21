"""Rules of the phases done so far (guide section A, page 5, and the Labour Code).

Phase 1, preparing for the birth (A.1):
- maternity leave may start at most N weeks before the expected due date;
- that needs a medical certificate of the expected due date;
- the mother may also work until the birth; the benefit then starts after the birth.

Phase 2a, after the birth (A.2; Labour Code art. 180 § 1-3, art. 183¹ § 1-2):
- maternity leave lasts T weeks, depending on how many children are born at once;
- a week of leave is 7 calendar days;
- weeks used before the birth count towards T; the rest follows the birth;
- without leave before the birth, the leave starts on the day of the birth;
- the first 14 weeks after the birth the mother uses personally.

Pure and deterministic: no I/O, no database, no LLM; `today` is an argument. Every number comes
from `Params`, every element carries its sources. Later phases add rules after these.
"""

import datetime as dt
from dataclasses import dataclass, field

from app.engine.explain import case_notes
from app.engine.models import (
    Document,
    Marker,
    Scenario,
    ScenarioError,
    Segment,
    Timeline,
    TimelineElement,
)
from app.engine.params import Params
from app.engine.wording import children_phrase, fmt

__all__ = ["DAY", "WEEK", "build_timeline", "changed_element_ids", "fmt"]

DAY = dt.timedelta(days=1)
WEEK = dt.timedelta(days=7)


@dataclass
class _Draft:
    segments: list[Segment] = field(default_factory=list)
    markers: list[Marker] = field(default_factory=list)
    documents: list[Document] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def build_timeline(scenario: Scenario, params: Params, today: dt.date) -> Timeline:
    born = scenario.child_born is True
    birth = scenario.anchor_date
    if birth is None:
        raise ScenarioError("Najpierw potrzebna jest data porodu: przewidywana albo faktyczna.")
    weeks = scenario.leave_before_birth_weeks
    limit = params.maternity.max_weeks_before_birth
    if weeks is not None and weeks > limit.value:
        raise ScenarioError(
            f"Urlop macierzyński można zacząć maksymalnie {limit.value} tyg. przed przewidywaną "
            "datą porodu."
        )

    draft = _Draft()
    if born:
        _before_birth_past(draft, scenario, params, birth)
    else:
        _before_birth_plan(draft, scenario, params, birth)
    draft.markers.append(_birth_marker(scenario, params, birth))
    if scenario.children_count is not None:
        _maternity_after_birth(draft, scenario, params, birth, today)
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
        assumptions=_assumptions(scenario, born),
    )
    timeline.notes = case_notes(scenario, timeline, params)
    return timeline


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


def _before_birth_plan(draft: _Draft, scenario: Scenario, params: Params, due: dt.date) -> None:
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


def _before_birth_past(draft: _Draft, scenario: Scenario, params: Params, birth: dt.date) -> None:
    """Phase 1 once the child is born: leave the mother already took before the birth."""
    weeks = scenario.leave_before_birth_weeks
    if not weeks:
        return
    start = birth - weeks * WEEK
    draft.segments.append(
        Segment(
            id="maternity-prenatal",
            lane="mother",
            tone="leave",
            title="Urlop macierzyński przed porodem",
            start=start,
            end=birth - DAY,
            days=weeks * 7,
            summary=f"Mama była na urlopie macierzyńskim {weeks} tyg. przed porodem.",
            details=["To część urlopu macierzyńskiego, a nie dodatkowe tygodnie."],
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
            title="Narodziny dziecka",
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


def _maternity_after_birth(
    draft: _Draft, scenario: Scenario, params: Params, birth: dt.date, today: dt.date
) -> None:
    """Phase 2a: how long maternity leave lasts and the 14 weeks after the birth."""
    m = params.maternity
    rules = params.rules
    born = scenario.child_born is True
    count = scenario.children_count
    assert count is not None
    table = m.weeks_by_children.value
    total = table[min(count, len(table)) - 1]
    weeks = scenario.leave_before_birth_weeks
    before = weeks or 0
    end = birth - before * WEEK + total * WEEK - DAY

    details = ["Tydzień urlopu to 7 dni kalendarzowych."]
    sources = [*m.weeks_by_children.sources, *rules.week_is_7_days.sources]
    if before:
        details.append(
            f"{before} tyg. wykorzystane przed porodem wliczają się do {total} tyg.; "
            "reszta przysługuje po porodzie."
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
    if not born:
        details.append(
            "Liczymy od przewidywanej daty porodu. Po porodzie oś przeliczy się od faktycznej daty."
        )

    in_total = f", w tym {before} tyg. przed porodem" if before else ""
    draft.segments.append(
        Segment(
            id="maternity",
            lane="mother",
            tone="leave",
            title="Urlop macierzyński po porodzie",
            start=birth,
            end=end,
            days=(end - birth).days + 1,
            summary=(
                f"Urlop macierzyński przy urodzeniu {children_phrase(count)} trwa "
                f"{total} tyg.{in_total}. Po porodzie trwa do {fmt(end)}."
            ),
            details=details,
            sources=sources,
        )
    )

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


def _assumptions(scenario: Scenario, born: bool) -> list[str]:
    assumptions = [
        "Pokazujemy przygotowanie do porodu i długość urlopu macierzyńskiego. Kolejne części "
        "Przewodnika ZUS dodajemy krok po kroku."
    ]
    if not born:
        assumptions.append(
            "Liczymy od przewidywanej daty porodu. Po porodzie oś przeliczy się od faktycznej daty."
        )
    if scenario.children_count is None:
        assumptions.append(
            "Długość urlopu macierzyńskiego pokażemy, gdy będzie wiadomo, ile dzieci urodzi się "
            "przy jednym porodzie."
        )
    assumptions.append(
        "Zakładamy, że mama ma prawo do zasiłku macierzyńskiego. Ubezpieczenie sprawdzimy "
        "w kolejnym etapie."
    )
    return assumptions
