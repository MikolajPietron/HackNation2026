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

Pure and deterministic: no I/O, no database, no LLM; `today` is an argument. Every number comes
from `Params`, every element carries its sources. Later phases add rules after these.
"""

import datetime as dt
from dataclasses import dataclass, field

from app.engine.explain import case_notes
from app.engine.insurance import INSURED, NOT_INSURED, Coverage, coverage
from app.engine.models import (
    Document,
    Marker,
    Scenario,
    ScenarioError,
    Segment,
    SourceRef,
    Timeline,
    TimelineElement,
)
from app.engine.params import Params
from app.engine.parental import for_children, parental_deadline, parental_table, parental_weeks
from app.engine.supplementary import describe_case, supplementary_leave
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

    cover = coverage(scenario)
    draft = _Draft()
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
            maternity_end = _maternity_after_birth(draft, scenario, params, birth, today, cover)
            after = _supplementary(draft, scenario, params, birth, maternity_end, today)
            _parental(draft, scenario, params, birth, after, today)
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
        assumptions=_assumptions(scenario, born, cover),
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
        sources=_merge(
            params.benefit.insured_mother.sources, params.benefit.insured_on_birth_day.sources
        ),
    )


def _merge(*groups: list[SourceRef]) -> list[SourceRef]:
    """Sources of several rules in order, each quote once."""
    seen: set[tuple[str, str]] = set()
    merged = []
    for source in (source for group in groups for source in group):
        if (source.doc, source.quote) not in seen:
            seen.add((source.doc, source.quote))
            merged.append(source)
    return merged


def _maternity_after_birth(
    draft: _Draft,
    scenario: Scenario,
    params: Params,
    birth: dt.date,
    today: dt.date,
    cover: Coverage,
) -> dt.date:
    """Phase 2: how long maternity leave lasts, the 14 weeks after the birth and the benefit
    for that period. Returns the last day of the leave."""
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
    benefit = params.benefit
    if cover == "obligatory":
        details.append(
            "Mama jest ubezpieczona, więc za ten okres ma prawo do zasiłku macierzyńskiego."
        )
        sources += benefit.insured_mother.sources
    elif cover == "voluntary":
        details.append(
            "Mama nie jest pracownicą, więc nie dostaje urlopu: ma prawo do zasiłku "
            "macierzyńskiego za ten okres."
        )
        sources += [*benefit.insured_mother.sources, *benefit.non_employees.sources]
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
                f"{total} tyg.{in_total}; po porodzie do {fmt(end)}."
            ),
            details=details,
            sources=_merge(sources),
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
    return end


def _supplementary(
    draft: _Draft,
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
        f"{fmt(leave.first_day)} a {fmt(leave.last_day)}. Okresy pobytu sumuje się, a niepełny "
        f"tydzień zaokrągla w górę: stąd {leave.weeks} tyg.",
    ]
    if leave.ongoing:
        details.append(
            f"Dziecko jest jeszcze w szpitalu, więc liczymy do dziś ({fmt(today)}). Wymiar może "
            f"jeszcze wzrosnąć, najwyżej do {leave.limit_weeks} tyg."
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
        "Dni po porodzie liczymy od dnia następującego po dniu porodu. Tydzień urlopu to 7 dni "
        "kalendarzowych.",
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
            sources=_merge(
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
    draft: _Draft,
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
        draft.warnings.append(
            f"Czas na urlop rodzicielski minął {fmt(deadline)}: to koniec roku kalendarzowego, "
            f"w którym dziecko skończyło {age} lat."
        )
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
            "Jeśli dziecko urodzi się przedwcześnie albo będzie wymagało pobytu w szpitalu, "
            "przed urlopem rodzicielskim przysługuje jeszcze uzupełniający urlop macierzyński."
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
                f"do {total} tyg.; {exclusive} tyg. z nich należy wyłącznie do taty i nie można "
                f"ich przenieść, więc mama może wykorzystać najwięcej {mothers} tyg. Wzięte "
                f"w całości od razu, trwałyby do {fmt(end)}."
            ),
            details=details,
            sources=_merge(*sources),
        )
    )
    estimate = [] if born else ["Liczymy od przewidywanej daty porodu."]
    if not born and birth.month in (1, 12):
        estimate.append(
            "Gdyby dziecko urodziło się w innym roku kalendarzowym niż przewidywany, ten dzień "
            "przesunie się o rok."
        )
    draft.markers.append(
        Marker(
            id="parental-deadline",
            lane="child",
            label="Rodzicielski najpóźniej do",
            title="Koniec czasu na urlop rodzicielski",
            date=deadline,
            summary=(
                "Urlop rodzicielski można wykorzystać najpóźniej do końca roku kalendarzowego, "
                f"w którym dziecko kończy {age} lat."
            ),
            details=estimate,
            sources=p.deadline_age.sources,
        )
    )


def _assumptions(scenario: Scenario, born: bool, cover: Coverage) -> list[str]:
    assumptions = [
        "Pokazujemy to, co wynika z punktów „Przygotowanie do porodu” i „Urodzenie dziecka” "
        "Przewodnika ZUS. Kolejne części (uprawnienia taty, kwoty zasiłku, wnioski i terminy) "
        "dodajemy krok po kroku."
    ]
    if cover in NOT_INSURED:
        assumptions.append(
            "Uprawnienia taty opisuje dalsza część Przewodnika ZUS (sekcja B). Dodamy je "
            "w kolejnym etapie."
        )
        return assumptions
    if cover not in INSURED:
        assumptions.append(
            "Na razie zakładamy, że mama podlega ubezpieczeniu chorobowemu. Potwierdzi to "
            "pytanie w rozmowie."
        )
    else:
        assumptions.append(
            "Zakładamy, że ubezpieczenie chorobowe mamy trwa w dniu porodu."
            if not born
            else "Zakładamy, że mama podlegała ubezpieczeniu chorobowemu w dniu porodu."
        )
    if not born:
        assumptions.append(
            "Liczymy od przewidywanej daty porodu. Po porodzie oś przeliczy się od faktycznej daty."
        )
    if scenario.children_count is None:
        assumptions.append(
            "Długość urlopów pokażemy, gdy będzie wiadomo, ile dzieci urodzi się przy jednym "
            "porodzie."
        )
    else:
        assumptions.append(
            "Urlop rodzicielski pokazujemy tak, jakby mama wzięła całą swoją część od razu po "
            "urlopie macierzyńskim. Podział na części i udział taty dojdą w kolejnym etapie."
        )
    if scenario.hospital_care:
        assumptions.append(
            "Przy uzupełniającym urlopie macierzyńskim dni po porodzie liczymy od dnia "
            "następującego po dniu porodu."
        )
    return assumptions
