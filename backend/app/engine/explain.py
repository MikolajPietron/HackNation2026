"""The case explanation: which situation the family is in, what the mother is entitled to, which
options and reliefs the rules give them and why, and what exactly we computed. Built from the
finished timeline, so dates are read, never recalculated. Every legal claim carries its source.

Every phase adds its notes here (CLAUDE.md, "Wyjaśnianie przypadku").
"""

from app.engine.insurance import NOT_INSURED, Coverage, coverage
from app.engine.models import CaseNote, Marker, Scenario, Segment, SourceRef, Timeline
from app.engine.params import Params
from app.engine.parental import for_children, parental_table, parental_weeks
from app.engine.supplementary import describe_case, supplementary_leave
from app.engine.wording import children_phrase, long_date, multiples

WORK_LOCATIVE = {"contract": "umowie zlecenia", "business": "własnej działalności gospodarczej"}
"""After "przy": the two ways of working the guide names for voluntary sickness insurance."""


def case_notes(scenario: Scenario, timeline: Timeline, params: Params) -> list[CaseNote]:
    cover = coverage(scenario)
    notes = [
        _situation(scenario, timeline, params, cover),
        _insurance(scenario, timeline, params, cover),
    ]
    if cover in NOT_INSURED:
        return notes
    if not timeline.child_born:
        notes.append(_before_birth(scenario, timeline, params))
    optional = [
        _parental(scenario, timeline, params),
        _more_children(scenario, timeline, params),
        _za_zyciem(scenario, timeline, params),
        _supplementary(scenario, timeline, params),
    ]
    notes += [note for note in optional if note is not None]
    notes.append(_computed(scenario, timeline, params))
    return notes


def changed_note_ids(old: Timeline | None, new: Timeline) -> list[str]:
    """Points of the explanation that are new or reworded since `old`. After a recalculation
    the assistant talks about these and the UI highlights them."""
    if old is None:
        return []
    before = {n.id: (n.kind, n.title, n.text) for n in old.notes}
    return [n.id for n in new.notes if before.get(n.id) != (n.kind, n.title, n.text)]


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


def _merge(*groups: list[SourceRef]) -> list[SourceRef]:
    """Sources of several rules in order, each quote once."""
    merged: dict[tuple[str, str], SourceRef] = {}
    for source in (source for group in groups for source in group):
        merged.setdefault((source.doc, source.quote), source)
    return list(merged.values())


def _situation(scenario: Scenario, timeline: Timeline, params: Params, cover: Coverage) -> CaseNote:
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
    if cover in NOT_INSURED:
        return CaseNote(
            id="situation",
            kind="situation",
            title=title,
            text="Liczymy od faktycznej daty urodzenia.",
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


def _insurance(scenario: Scenario, timeline: Timeline, params: Params, cover: Coverage) -> CaseNote:
    """Phase 2: the right to the maternity benefit belongs to the insured mother."""
    b = params.benefit
    born = timeline.child_born
    on_the_day = (
        "Liczy się, że mama podlegała ubezpieczeniu chorobowemu w dniu porodu."
        if born
        else "Ważne, żeby ubezpieczenie chorobowe trwało w dniu porodu."
    )
    entitled = "Mama ma prawo do zasiłku macierzyńskiego"
    # The guide: the benefit is paid "in defined situations also after the insurance has ended".
    exceptions = (
        "Tylko w określonych sytuacjach zasiłek przysługuje także po ustaniu ubezpieczenia; "
        "dodamy je w kolejnym etapie."
    )
    # Not a rule, so no quote: where the family should look next.
    father = "Uprawnienia taty opisuje dalsza część Przewodnika; też dodamy je w kolejnym etapie."
    needed = "Zasiłek macierzyński: potrzebne ubezpieczenie chorobowe"
    denied = "Bez ubezpieczenia chorobowego nie ma zasiłku macierzyńskiego"
    work = WORK_LOCATIVE.get(scenario.mothers_work or "", "")
    match cover:
        case "obligatory":
            return CaseNote(
                id="insurance",
                kind="right",
                title=entitled,
                text=(
                    "Umowa o pracę daje obowiązkowe ubezpieczenie chorobowe, a po porodzie "
                    "ubezpieczona mama nabywa prawo do zasiłku macierzyńskiego za okres urlopu "
                    f"macierzyńskiego. {on_the_day}"
                ),
                sources=_merge(
                    b.insured_mother.sources,
                    b.obligatory_insurance.sources,
                    b.insured_on_birth_day.sources,
                ),
            )
        case "voluntary":
            return CaseNote(
                id="insurance",
                kind="right",
                title=entitled,
                text=(
                    f"Przy {work} ubezpieczenie chorobowe jest dobrowolne. Mama jest do niego "
                    "zgłoszona, więc po porodzie nabywa prawo do zasiłku macierzyńskiego. Nie "
                    "jest pracownicą, dlatego nie dostaje urlopu: ma prawo do zasiłku za okres "
                    "odpowiadający urlopowi, na tych samych zasadach co do wymiaru i wysokości. "
                    f"{on_the_day}"
                ),
                sources=_merge(
                    b.insured_mother.sources,
                    b.voluntary_insurance.sources,
                    b.non_employees.sources,
                    b.same_rules_for_non_employees.sources,
                    b.insured_on_birth_day.sources,
                ),
            )
        case "unknown-voluntary":
            return CaseNote(
                id="insurance",
                kind="right",
                title=needed,
                text=(
                    "Prawo do zasiłku macierzyńskiego nabywa po porodzie mama ubezpieczona. Przy "
                    f"{work} ubezpieczenie chorobowe jest dobrowolne, więc trzeba ustalić, czy "
                    "mama jest do niego zgłoszona. Na razie oś zakłada, że tak."
                ),
                sources=_merge(b.insured_mother.sources, b.voluntary_insurance.sources),
            )
        case "unknown-work":
            return CaseNote(
                id="insurance",
                kind="right",
                title=needed,
                text=(
                    "Prawo do zasiłku macierzyńskiego nabywa po porodzie mama ubezpieczona, czyli "
                    "podlegająca ubezpieczeniu chorobowemu. Zależy to od tego, jak mama pracuje. "
                    "Na razie oś zakłada, że jest ubezpieczona."
                ),
                sources=_merge(b.insured_mother.sources, b.paid_to_the_insured.sources),
            )
        case "not-registered":
            state = (
                "a mama nie była do niego zgłoszona. Liczy się dzień porodu: bez ubezpieczenia "
                "chorobowego w tym dniu zasiłek macierzyński mamie nie przysługuje."
                if born
                else "a mama nie jest do niego zgłoszona. Liczy się dzień porodu: jeśli mama "
                "nie będzie wtedy podlegać ubezpieczeniu chorobowemu, zasiłek macierzyński nie "
                "będzie jej przysługiwał."
            )
            return CaseNote(
                id="insurance",
                kind="risk",
                title=denied,
                text=(
                    "Prawo do zasiłku macierzyńskiego nabywa po porodzie mama ubezpieczona. Przy "
                    f"{work} ubezpieczenie chorobowe jest dobrowolne, {state} {exceptions} {father}"
                ),
                sources=_merge(
                    b.insured_mother.sources,
                    b.voluntary_insurance.sources,
                    b.insured_on_birth_day.sources,
                    b.voluntary_not_registered.sources,
                    b.without_insurance.sources,
                    b.paid_to_the_insured.sources,
                ),
            )
        case "not-working":
            return CaseNote(
                id="insurance",
                kind="risk",
                title=denied,
                text=(
                    "Prawo do zasiłku macierzyńskiego nabywa po porodzie mama ubezpieczona, czyli "
                    "podlegająca ubezpieczeniu chorobowemu: obowiązkowemu (np. z umowy o pracę) "
                    "albo dobrowolnemu (np. przy umowie zlecenia lub działalności gospodarczej). "
                    "Z odpowiedzi wynika, że mama nie pracuje, więc nie ma umowy ani działalności, "
                    "z której wynikałoby to ubezpieczenie, a bez niego zasiłek macierzyński nie "
                    f"przysługuje. {exceptions} {father}"
                ),
                sources=_merge(
                    b.insured_mother.sources,
                    b.paid_to_the_insured.sources,
                    b.obligatory_insurance.sources,
                    b.voluntary_insurance.sources,
                    b.without_insurance.sources,
                ),
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


def _parental(scenario: Scenario, timeline: Timeline, params: Params) -> CaseNote | None:
    """Phase 2: after maternity leave comes parental leave; how much of it the mother can use."""
    deadline = _marker(timeline, "parental-deadline")
    if _segment(timeline, "parental") is None or deadline is None:
        return None
    p = params.parental
    total, mothers = parental_weeks(scenario, params)
    sources = [
        p.after_maternity.sources,
        parental_table(scenario, params).sources,
        p.exclusive_weeks.sources,
        p.max_parts.sources,
    ]
    longer = ""
    if not scenario.za_zyciem:
        table = p.weeks_by_children_za_zyciem
        longer = (
            " Z zaświadczeniem „Za życiem” urlop jest dłuższy: do "
            f"{for_children(table, scenario.children_count)} tyg."
        )
        sources.append(_guide(table.sources))
    return CaseNote(
        id="parental",
        kind="choice",
        title="Po urlopie macierzyńskim: urlop rodzicielski",
        text=(
            f"Rodzice mają razem do {total} tyg. urlopu rodzicielskiego. "
            f"{p.exclusive_weeks.value} tyg. z nich należy wyłącznie do taty i nie można ich "
            f"przenieść, więc mama może wykorzystać najwięcej {mothers} tyg. Urlop można wziąć "
            f"jednorazowo albo w nie więcej niż {p.max_parts.value} częściach, najpóźniej do "
            f"{long_date(deadline.date)} — końca roku, w którym dziecko kończy "
            f"{p.deadline_age.value} lat.{longer}"
        ),
        sources=_merge(*sources),
    )


def _more_children(scenario: Scenario, timeline: Timeline, params: Params) -> CaseNote | None:
    """More children at once: longer maternity leave and longer parental leave."""
    count = scenario.children_count
    if count is None or count < 2:
        return None
    weeks = params.maternity.weeks_by_children
    text = (
        f"Przy urodzeniu {children_phrase(count)} urlop macierzyński trwa "
        f"{_total_weeks(count, params)} tyg. zamiast {weeks.value[0]}"
    )
    sources = [_law(weeks.sources)]
    if _segment(timeline, "parental") is not None:
        table = parental_table(scenario, params)
        text += (
            f", a urlop rodzicielski obojga rodziców — do {table.value[1]} tyg. zamiast "
            f"{table.value[0]}"
        )
        sources.append(_law(table.sources))
    return CaseNote(
        id="more-children",
        kind="relief",
        title=f"{multiples(count)}: dłuższy urlop",
        text=f"{text}.",
        sources=_merge(*sources),
    )


def _za_zyciem(scenario: Scenario, timeline: Timeline, params: Params) -> CaseNote | None:
    """The "Za życiem" certificate: longer parental leave."""
    if not scenario.za_zyciem or _segment(timeline, "parental") is None:
        return None
    p = params.parental
    count = scenario.children_count
    total, mothers = parental_weeks(scenario, params)
    return CaseNote(
        id="za-zyciem",
        kind="relief",
        title="Zaświadczenie „Za życiem”: dłuższy urlop rodzicielski",
        text=(
            f"Dziecko ma zaświadczenie „Za życiem”, więc rodzice mają razem do {total} tyg. "
            f"urlopu rodzicielskiego zamiast {for_children(p.weeks_by_children, count)}. Mama "
            f"może z nich wykorzystać najwięcej {mothers} tyg."
        ),
        sources=_merge(p.weeks_by_children_za_zyciem.sources, p.exclusive_weeks.sources),
    )


def _supplementary(scenario: Scenario, timeline: Timeline, params: Params) -> CaseNote | None:
    """A premature child or one that needed hospital: supplementary maternity leave."""
    if not timeline.child_born or not scenario.hospital_care:
        return None
    s = params.supplementary
    leave = supplementary_leave(scenario, params, timeline.birth_date, timeline.today)
    if leave is None:
        return CaseNote(
            id="supplementary",
            kind="relief",
            title="Uzupełniający urlop macierzyński: potrzebne szczegóły",
            text=(
                "Przysługuje bezpośrednio po urlopie macierzyńskim, gdy dziecko urodziło się "
                "przedwcześnie albo o czasie, ale wymagało hospitalizacji. Żeby go policzyć, "
                "potrzebne są: tydzień ciąży, w którym urodziło się dziecko, jego masa urodzeniowa "
                "i okres pobytu w szpitalu."
            ),
            sources=_merge(s.situations.sources, s.once_after_maternity.sources),
        )
    case_sources = {
        "early": s.limit_weeks_early.sources,
        "preterm": s.limit_weeks_preterm.sources,
        "term": s.term.sources,
    }[leave.case]
    if leave.weeks == 0:
        reason = (
            "Podany pobyt w szpitalu nie spełnia tego warunku."
            if not leave.condition_met
            else "W podanych datach nie ma takiego pobytu."
        )
        return CaseNote(
            id="supplementary",
            kind="risk",
            title="Uzupełniający urlop macierzyński: warunki niespełnione",
            text=f"{describe_case(leave, params)} {reason}",
            sources=_merge(_guide(s.situations.sources), case_sources),
        )
    days = "dzień" if leave.days == 1 else "dni"
    ongoing = (
        f" Dziecko jest jeszcze w szpitalu, więc liczba tygodni może wzrosnąć, najwyżej do "
        f"{leave.limit_weeks}."
        if leave.ongoing
        else ""
    )
    return CaseNote(
        id="supplementary",
        kind="relief",
        title=f"Uzupełniający urlop macierzyński: {leave.weeks} tyg.",
        text=(
            f"{describe_case(leave, params)} Za każdy tydzień pobytu dziecka w szpitalu "
            f"przysługuje tydzień urlopu: {leave.days} {days} to {leave.weeks} tyg., bo niepełny "
            "tydzień zaokrągla się w górę. Urlop może wziąć mama albo tata, tylko jedno z nich, "
            f"bezpośrednio po urlopie macierzyńskim.{ongoing}"
        ),
        sources=_merge(
            _guide(s.situations.sources),
            case_sources,
            s.sum_and_round.sources,
            s.once_after_maternity.sources,
        ),
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
                "Długość urlopu macierzyńskiego i rodzicielskiego zależy od liczby dzieci "
                "urodzonych przy jednym porodzie. Gdy będzie wiadomo, ile ich jest, oś pokaże "
                "oba urlopy."
            ),
            sources=_merge(
                _guide(m.weeks_by_children.sources),
                _guide(params.parental.weeks_by_children.sources),
            ),
        )

    weeks = scenario.leave_before_birth_weeks or 0
    in_total = f", w tym {weeks} tyg. przed porodem" if weeks else ""
    ended = timeline.child_born and maternity.end < timeline.today
    text = (
        f"Urlop macierzyński trwa {_total_weeks(count, params)} tyg.{in_total}; po porodzie "
        f"do {long_date(maternity.end)}{' (już się skończył)' if ended else ''}. Pierwsze "
        f"{m.mother_personal_weeks.value} tygodni po porodzie, do {long_date(personal.date)}, "
        "mama wykorzystuje osobiście."
    )
    sources = [
        _guide(m.weeks_by_children.sources),
        m.mother_personal_weeks.sources,
        params.rules.week_is_7_days.sources,
    ]
    supplementary = _segment(timeline, "supplementary")
    if supplementary is not None:
        text += (
            f" Uzupełniający urlop macierzyński: {supplementary.days // 7} tyg., od "
            f"{long_date(supplementary.start)} do {long_date(supplementary.end)}."
        )
        sources.append(params.supplementary.week_is_7_days.sources)
    parental = _segment(timeline, "parental")
    if parental is not None:
        text += (
            f" Urlop rodzicielski mamy, wzięty w całości od razu potem: {parental.days // 7} "
            f"tyg., od {long_date(parental.start)} do {long_date(parental.end)}."
        )
        sources.append(params.parental.week_is_7_days.sources)
    return CaseNote(
        id="computed",
        kind="computed",
        title="Co policzyliśmy",
        text=f"{text} Tydzień urlopu to 7 dni kalendarzowych.",
        sources=_merge(*sources),
    )
