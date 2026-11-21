"""The case explanation: which situation the family is in, which options and reliefs the rules
give them and why, and what exactly we computed. Built from the finished timeline, so dates are
read, never recalculated. Every legal claim carries its source.

Every phase adds its notes here (CLAUDE.md, "Wyjaśnianie przypadku").
"""

from app.engine.models import CaseNote, Marker, Scenario, Segment, SourceRef, Timeline
from app.engine.params import Params
from app.engine.wording import children_phrase, long_date, multiples


def case_notes(scenario: Scenario, timeline: Timeline, params: Params) -> list[CaseNote]:
    notes = [_situation(scenario, timeline, params)]
    if not timeline.child_born:
        notes.append(_before_birth(scenario, timeline, params))
    relief = _more_children(scenario, params)
    if relief is not None:
        notes.append(relief)
    notes.append(_computed(scenario, timeline, params))
    return notes


def _segment(timeline: Timeline, segment_id: str) -> Segment | None:
    return next((s for s in timeline.segments if s.id == segment_id), None)


def _marker(timeline: Timeline, marker_id: str) -> Marker | None:
    return next((m for m in timeline.markers if m.id == marker_id), None)


def _total_weeks(count: int, params: Params) -> int:
    table = params.maternity.weeks_by_children.value
    return table[min(count, len(table)) - 1]


def _guide(sources: list[SourceRef]) -> list[SourceRef]:
    return [s for s in sources if s.doc == "przewodnik"]


def _law(sources: list[SourceRef]) -> list[SourceRef]:
    return [s for s in sources if s.doc == "kp"]


def _situation(scenario: Scenario, timeline: Timeline, params: Params) -> CaseNote:
    birth, today = timeline.birth_date, timeline.today
    rules = params.rules
    if not timeline.child_born:
        return CaseNote(
            id="situation",
            kind="situation",
            title="Dziecko jest w drodze",
            text=(
                f"Liczymy od przewidywanej daty porodu: {long_date(birth)}. Gdy dziecko się "
                "urodzi, wystarczy podać faktyczną datę, a oś przeliczy się sama."
            ),
        )

    born_today = birth == today
    title = (
        "Dziecko urodziło się dzisiaj" if born_today else f"Dziecko urodziło się {long_date(birth)}"
    )
    weeks = scenario.leave_before_birth_weeks
    prenatal = _segment(timeline, "maternity-prenatal")
    if weeks and prenatal is not None:
        verb = "trwa" if born_today else "zaczął się"
        return CaseNote(
            id="situation",
            kind="situation",
            title=title,
            text=(
                f"Liczymy od faktycznej daty urodzenia. Urlop macierzyński {verb} od "
                f"{long_date(prenatal.start)}: mama zaczęła go {weeks} tyg. przed porodem."
                if born_today
                else f"Liczymy od faktycznej daty urodzenia. Urlop macierzyński zaczął się "
                f"{long_date(prenatal.start)}, {weeks} tyg. przed porodem."
            ),
            sources=rules.rest_after_birth.sources,
        )

    start = (
        "urlop macierzyński zaczyna się dziś, w dniu porodu"
        if born_today
        else "urlop macierzyński zaczął się w dniu porodu"
    )
    if weeks is None:
        start = f"jeśli mama nie była na urlopie przed porodem, {start}"
    lead = "To upraszcza sprawę" if born_today else "Sprawa jest prostsza"
    return CaseNote(
        id="situation",
        kind="situation",
        title=title,
        text=(
            f"{lead}: nie trzeba już planować urlopu przed porodem ani zdobywać zaświadczenia "
            f"o przewidywanej dacie porodu. {start[0].upper()}{start[1:]}."
        ),
        sources=[*rules.medical_certificate.sources, *rules.first_day_is_birth.sources],
    )


def _before_birth(scenario: Scenario, timeline: Timeline, params: Params) -> CaseNote:
    """While the child is on the way: the choice between leave before the birth and work."""
    limit = params.maternity.max_weeks_before_birth
    rules = params.rules
    weeks = scenario.leave_before_birth_weeks

    if weeks is None:
        window = _segment(timeline, "prenatal-window")
        earliest = f"Najwcześniej {long_date(window.start)}. " if window else ""
        return CaseNote(
            id="before-birth",
            kind="choice",
            title=f"Urlop można zacząć nawet {limit.value} tygodni przed porodem",
            text=(
                f"{earliest}Potrzebne jest wtedy zaświadczenie lekarskie o przewidywanej dacie "
                "porodu. Można też pracować do dnia porodu — zasiłek zacznie się wtedy po "
                "urodzeniu dziecka."
            ),
            sources=[
                *limit.sources,
                *rules.medical_certificate.sources,
                *rules.work_until_birth.sources,
            ],
        )

    if weeks == 0:
        return CaseNote(
            id="before-birth",
            kind="choice",
            title="Praca do dnia porodu",
            text=(
                "Urlop macierzyński zacznie się w dniu porodu, a zasiłek po urodzeniu dziecka. "
                "Zaświadczenie o przewidywanej dacie porodu nie jest do tego potrzebne."
            ),
            sources=[*rules.work_until_birth.sources, *rules.first_day_is_birth.sources],
        )

    prenatal = _segment(timeline, "maternity-prenatal")
    assert prenatal is not None
    count = scenario.children_count
    if count is not None:
        total = _total_weeks(count, params)
        counted = (
            f"Te tygodnie wliczają się do {total} tyg. urlopu macierzyńskiego, więc po porodzie "
            f"zostaje {total - weeks} tyg."
        )
    else:
        counted = "Te tygodnie wliczają się do całego urlopu macierzyńskiego."
    certificate = (
        "Zaświadczenie lekarskie o przewidywanej dacie porodu już jest."
        if scenario.has_medical_certificate
        else f"Do {long_date(prenatal.start)} potrzebne jest zaświadczenie lekarskie "
        "o przewidywanej dacie porodu."
    )
    return CaseNote(
        id="before-birth",
        kind="choice",
        title=f"Urlop od {long_date(prenatal.start)}, {weeks} tyg. przed porodem",
        text=f"{counted} {certificate}",
        sources=[
            *limit.sources,
            *rules.medical_certificate.sources,
            *rules.rest_after_birth.sources,
        ],
    )


def _more_children(scenario: Scenario, params: Params) -> CaseNote | None:
    """More children at once: a longer maternity leave."""
    count = scenario.children_count
    if count is None or count < 2:
        return None
    weeks = params.maternity.weeks_by_children
    return CaseNote(
        id="more-children",
        kind="relief",
        title=f"{multiples(count)}: dłuższy urlop",
        text=(
            f"Przy urodzeniu {children_phrase(count)} urlop macierzyński trwa "
            f"{_total_weeks(count, params)} tyg. zamiast {weeks.value[0]}."
        ),
        sources=_law(weeks.sources),
    )


def _computed(scenario: Scenario, timeline: Timeline, params: Params) -> CaseNote:
    """What exactly the timeline shows, and the rule each number comes from."""
    m = params.maternity
    maternity = _segment(timeline, "maternity")
    personal = _marker(timeline, "personal-weeks")
    count = scenario.children_count
    if count is None or maternity is None or personal is None:
        return CaseNote(
            id="computed",
            kind="computed",
            title="Co jeszcze policzymy",
            text=(
                "Długość urlopu macierzyńskiego zależy od liczby dzieci urodzonych przy jednym "
                "porodzie. Gdy będzie wiadomo, ile ich jest, oś pokaże koniec urlopu."
            ),
            sources=_guide(m.weeks_by_children.sources),
        )

    weeks = scenario.leave_before_birth_weeks or 0
    in_total = f", w tym {weeks} tyg. przed porodem" if weeks else ""
    ended = timeline.child_born and maternity.end < timeline.today
    return CaseNote(
        id="computed",
        kind="computed",
        title="Co policzyliśmy",
        text=(
            f"Urlop macierzyński trwa {_total_weeks(count, params)} tyg.{in_total}; po porodzie "
            f"do {long_date(maternity.end)}{' (już się skończył)' if ended else ''}. Pierwsze "
            f"{m.mother_personal_weeks.value} tygodni po porodzie, do {long_date(personal.date)}, "
            "mama wykorzystuje osobiście. Tydzień urlopu to 7 dni kalendarzowych."
        ),
        sources=[
            *_guide(m.weeks_by_children.sources),
            *m.mother_personal_weeks.sources,
            *params.rules.week_is_7_days.sources,
        ],
    )
