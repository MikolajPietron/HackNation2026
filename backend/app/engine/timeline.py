"""Base rules: from the birth date to leaves, deadlines and applications.

Pure and deterministic: no I/O, no database, no LLM; `today` is an argument. Every number comes
from `Params`, every element carries its sources. Interaction rules (premature birth, hospital,
the father taking over maternity leave...) will be applied after these, in an explicit order.
"""

import datetime as dt
from calendar import monthrange
from collections.abc import Iterable

from app.engine.models import (
    Application,
    Marker,
    Scenario,
    ScenarioError,
    Segment,
    SourceRef,
    Timeline,
    TimelineElement,
)
from app.engine.params import Params

DAY = dt.timedelta(days=1)
WEEK = dt.timedelta(days=7)


def fmt(d: dt.date) -> str:
    return d.strftime("%d.%m.%Y")


def percent(value: float) -> str:
    return f"{value:g}".replace(".", ",") + "%"


def add_months(d: dt.date, months: int) -> dt.date:
    """The same day `months` later, or the last day of that month if the day does not exist."""
    index = d.month - 1 + months
    year, month = d.year + index // 12, index % 12 + 1
    return dt.date(year, month, min(d.day, monthrange(year, month)[1]))


def span(start: dt.date, days: int) -> dt.date:
    """Inclusive last day of a period of `days` calendar days starting on `start`."""
    return start + (days - 1) * DAY


def unique(sources: Iterable[SourceRef]) -> list[SourceRef]:
    seen: set[tuple[object, ...]] = set()
    result = []
    for s in sources:
        key = (s.doc, s.page, s.article, s.quote)
        if key not in seen:
            seen.add(key)
            result.append(s)
    return result


def build_timeline(scenario: Scenario, params: Params, today: dt.date) -> Timeline:
    if scenario.birth_date is None:
        raise ScenarioError("Najpierw potrzebna jest data porodu (faktyczna albo przewidywana).")
    birth = scenario.birth_date

    maternity = _maternity(scenario, params)
    parental = _parental(scenario, params, first_day=maternity[-1].end + DAY)
    paternity = _paternity(scenario, params)
    segments = [*maternity, parental[0], paternity, parental[1]]
    by_id = {s.id: s for s in segments}

    return Timeline(
        params_version=params.version,
        today=today,
        birth_date=birth,
        child_born=scenario.child_born,
        children_count=scenario.children_count,
        segments=segments,
        markers=_markers(scenario, params),
        applications=_applications(scenario, params, by_id, today),
        warnings=_warnings(scenario, params, today),
        assumptions=_assumptions(scenario, params),
    )


def changed_element_ids(old: Timeline | None, new: Timeline) -> list[str]:
    """Elements that are new or moved/changed since `old` — the UI highlights them."""
    if old is None:
        return []
    before = {e.id: _signature(e) for e in old.elements()}
    return [e.id for e in new.elements() if before.get(e.id) != _signature(e)]


def _signature(e: TimelineElement) -> tuple[object, ...]:
    match e:
        case Segment():
            return ("segment", e.start, e.end, e.rate_percent, e.title)
        case Marker():
            return ("marker", e.date, e.title)
        case Application():
            return ("application", e.due, e.title, e.passed)


def _payer(params: Params) -> str:
    n = params.payer.employer_pays_above_insured.value
    return (
        f"Pracodawca, jeśli zgłasza do ubezpieczenia chorobowego ponad {n} osób. "
        "W pozostałych przypadkach wypłaca ZUS."
    )


def _maternity(scenario: Scenario, params: Params) -> list[Segment]:
    m = params.maternity
    birth = scenario.birth_date
    assert birth is not None
    table = m.weeks_by_children.value
    weeks = table[min(scenario.children_count, len(table)) - 1]
    before = scenario.maternity_weeks_before_birth
    max_before = m.max_weeks_before_birth.value
    if before > max_before:
        raise ScenarioError(
            f"Przed porodem można wykorzystać najwyżej {max_before} tyg. urlopu macierzyńskiego."
        )

    rate_param = params.flat_rate.rate_percent if scenario.flat_rate else m.rate_percent
    rate = rate_param.value
    benefit = f"Zasiłek macierzyński {percent(rate)}"
    payer = _payer(params)
    payer_sources = params.payer.employer_pays_above_insured.sources
    start = birth - before * WEEK
    end = span(start, weeks * 7)
    children = scenario.children_count
    segments: list[Segment] = []

    if before:
        segments.append(
            Segment(
                id="maternity-prenatal",
                lane="mother",
                title="Urlop macierzyński przed porodem",
                start=start,
                end=birth - DAY,
                days=before * 7,
                rate_percent=rate,
                benefit=benefit,
                payer=payer,
                summary=(
                    f"{before} tyg. urlopu macierzyńskiego przed porodem "
                    f"(można najwyżej {max_before} tyg.)."
                ),
                details=[
                    "Potrzebne jest zaświadczenie lekarskie o przewidywanej dacie porodu.",
                    "To część urlopu macierzyńskiego, a nie dodatkowe tygodnie.",
                    "Część niewykorzystana przed porodem przechodzi na czas po porodzie.",
                ],
                sources=unique(
                    [*m.max_weeks_before_birth.sources, *rate_param.sources, *payer_sources]
                ),
            )
        )

    details = [
        f"Pierwsze {m.mother_personal_weeks.value} tyg. po porodzie mama wykorzystuje osobiście.",
        "Tydzień urlopu to 7 dni kalendarzowych.",
    ]
    if not before:
        details.append("Bez urlopu przed porodem pierwszym dniem urlopu jest dzień porodu.")
    in_total = f" (w tym {before} tyg. przed porodem)" if before else ""
    segments.append(
        Segment(
            id="maternity",
            lane="mother",
            title="Urlop macierzyński po porodzie" if before else "Urlop macierzyński",
            start=birth,
            end=end,
            days=(end - birth).days + 1,
            rate_percent=rate,
            benefit=benefit,
            payer=payer,
            summary=(
                f"Urlop macierzyński trwa {weeks} tyg.{in_total} przy urodzeniu "
                f"{children} {'dziecka' if children == 1 else 'dzieci'}. "
                f"Zasiłek: {percent(rate)} podstawy wymiaru."
            ),
            details=details,
            sources=unique(
                [
                    *m.weeks_by_children.sources,
                    *m.mother_personal_weeks.sources,
                    *rate_param.sources,
                    *params.rules.week_is_7_days.sources,
                    *([] if before else params.rules.first_day_is_birth.sources),
                    *payer_sources,
                ]
            ),
        )
    )
    return segments


def _parental(scenario: Scenario, params: Params, first_day: dt.date) -> list[Segment]:
    p = params.parental
    birth = scenario.birth_date
    assert birth is not None
    total_param = p.weeks_single if scenario.children_count == 1 else p.weeks_multiple
    total = total_param.value
    reserved = p.reserved_weeks_per_parent.value
    mother_weeks = total - reserved
    limit_year = birth.year + p.last_year_of_child_age.value
    if scenario.flat_rate:
        mother_rate_param = params.flat_rate.rate_percent
        father_rate_param = params.flat_rate.other_parent_rate_percent
    else:
        mother_rate_param = father_rate_param = p.rate_percent
    payer = _payer(params)
    common_sources = [
        *total_param.sources,
        *p.reserved_weeks_per_parent.sources,
        *p.max_parts.sources,
        *params.rules.parents_share_parental.sources,
    ]
    share_rule = (
        f"Pula {total} tyg. jest wspólna dla obojga rodziców. Każde z nich ma {reserved} tyg. "
        "tylko dla siebie — tych tygodni nie można przekazać drugiemu rodzicowi."
    )
    parts_rule = (
        f"Urlop można podzielić na najwyżej {p.max_parts.value} części "
        f"i wykorzystać do 31.12.{limit_year}."
    )

    mother_end = span(first_day, mother_weeks * 7)
    father_start = mother_end + DAY
    mother_rate = mother_rate_param.value
    father_rate = father_rate_param.value
    father_details = [
        share_rule,
        "Rodzice mogą korzystać z urlopu rodzicielskiego jednocześnie albo na zmianę.",
        "Przykładowy plan: tata bierze swoje tygodnie po urlopie mamy.",
    ]
    if scenario.flat_rate:
        father_details.append(
            f"Przy wariancie {percent(mother_rate)} tygodnie taty są płatne {percent(father_rate)}."
        )
    return [
        Segment(
            id="parental-mother",
            lane="mother",
            title="Urlop rodzicielski — mama",
            start=first_day,
            end=mother_end,
            days=mother_weeks * 7,
            rate_percent=mother_rate,
            benefit=f"Zasiłek macierzyński {percent(mother_rate)}",
            payer=payer,
            summary=(
                f"{mother_weeks} z {total} tyg. wspólnej puli urlopu rodzicielskiego. "
                f"Zasiłek: {percent(mother_rate)} podstawy wymiaru."
            ),
            details=[
                share_rule,
                parts_rule,
                "Przykładowy plan: mama bierze swoją część zaraz po urlopie macierzyńskim.",
            ],
            is_example=True,
            sources=unique(
                [
                    *common_sources,
                    *mother_rate_param.sources,
                    *params.payer.employer_pays_above_insured.sources,
                ]
            ),
        ),
        Segment(
            id="parental-father",
            lane="father",
            title="Urlop rodzicielski — tata",
            start=father_start,
            end=span(father_start, reserved * 7),
            days=reserved * 7,
            rate_percent=father_rate,
            benefit=f"Zasiłek macierzyński {percent(father_rate)}",
            payer=payer,
            summary=(
                f"{reserved} tyg. urlopu rodzicielskiego przysługuje tylko tacie. "
                f"Zasiłek: {percent(father_rate)} podstawy wymiaru."
            ),
            details=father_details,
            is_example=True,
            sources=unique(
                [
                    *common_sources,
                    *father_rate_param.sources,
                    *params.payer.employer_pays_above_insured.sources,
                ]
            ),
        ),
    ]


def _paternity(scenario: Scenario, params: Params) -> Segment:
    pt = params.paternity
    birth = scenario.birth_date
    assert birth is not None
    days = pt.days.value
    months = pt.window_months.value
    window_end = add_months(birth, months)
    start = scenario.paternity_start or birth
    end = span(start, days)
    if start < birth:
        raise ScenarioError("Urlop ojcowski może zacząć się najwcześniej w dniu porodu.")
    if end >= window_end:
        raise ScenarioError(
            f"Urlop ojcowski trzeba wykorzystać, zanim dziecko skończy {months} miesięcy "
            f"({fmt(window_end)}). Najpóźniej można go zacząć {fmt(window_end - days * DAY)}."
        )
    rate = pt.rate_percent.value
    details = [
        "Można go wziąć jednorazowo albo w 2 częściach po co najmniej "
        f"{pt.min_part_days.value} dni.",
        "Liczba dzieci urodzonych przy jednym porodzie nie wydłuża urlopu ojcowskiego.",
    ]
    if scenario.paternity_start is None:
        details.append("Przykładowy termin: od dnia porodu.")
    return Segment(
        id="paternity",
        lane="father",
        title="Urlop ojcowski",
        start=start,
        end=end,
        days=days,
        rate_percent=rate,
        benefit=f"Zasiłek macierzyński {percent(rate)}",
        payer=_payer(params),
        summary=(
            f"{days} dni kalendarzowych. Zasiłek: {percent(rate)} podstawy wymiaru. "
            f"Trzeba go wykorzystać, zanim dziecko skończy {months} miesięcy."
        ),
        details=details,
        is_example=scenario.paternity_start is None,
        sources=unique(
            [
                *pt.days.sources,
                *pt.min_part_days.sources,
                *pt.window_months.sources,
                *pt.rate_percent.sources,
                *params.payer.employer_pays_above_insured.sources,
            ]
        ),
    )


def _markers(scenario: Scenario, params: Params) -> list[Marker]:
    birth = scenario.birth_date
    assert birth is not None
    born = scenario.child_born
    fr = params.flat_rate
    pt = params.paternity
    p = params.parental
    days_after = fr.application_days_after_birth.value
    limit = dt.date(birth.year + p.last_year_of_child_age.value, 12, 31)
    return [
        Marker(
            id="birth",
            lane="child",
            label="Poród" if born else "Termin porodu",
            title="Narodziny dziecka" if born else "Przewidywana data porodu",
            date=birth,
            summary=(
                "Od tego dnia liczymy całą oś czasu."
                if born
                else "Liczymy od przewidywanej daty porodu. Po porodzie podaj faktyczną datę "
                "— oś się przeliczy."
            ),
            details=["Bez urlopu przed porodem urlop macierzyński zaczyna się w dniu porodu."],
            sources=params.rules.first_day_is_birth.sources,
        ),
        Marker(
            id="flat-rate-deadline",
            lane="child",
            label=f"{days_after} dni: wniosek {percent(fr.rate_percent.value)}",
            title=f"{days_after} dni po porodzie: ostatni dzień na wniosek o "
            f"{percent(fr.rate_percent.value)}",
            date=birth + days_after * DAY,
            summary=(
                f"Do tego dnia mama może złożyć pisemny wniosek o zasiłek "
                f"{percent(fr.rate_percent.value)} za cały urlop macierzyński i rodzicielski — "
                f"zamiast {percent(params.maternity.rate_percent.value)} za macierzyński "
                f"i {percent(p.rate_percent.value)} za rodzicielski."
            ),
            details=[
                f"{p.reserved_weeks_per_parent.value} tyg. rodzicielskiego taty są wtedy płatne "
                f"{percent(fr.other_parent_rate_percent.value)}."
            ],
            sources=unique(
                [
                    *fr.rate_percent.sources,
                    *fr.application_days_after_birth.sources,
                    *fr.other_parent_rate_percent.sources,
                ]
            ),
        ),
        Marker(
            id="paternity-window-end",
            lane="child",
            label=f"{pt.window_months.value} miesięcy",
            title=f"Dziecko kończy {pt.window_months.value} miesięcy",
            date=add_months(birth, pt.window_months.value),
            summary=(
                f"Urlop ojcowski trzeba wykorzystać, zanim dziecko skończy "
                f"{pt.window_months.value} miesięcy. Potem prawo do niego wygasa."
            ),
            sources=pt.window_months.sources,
        ),
        Marker(
            id="parental-limit",
            lane="child",
            label="Limit rodzicielskiego",
            title="Koniec terminu na urlop rodzicielski",
            date=limit,
            summary=(
                "Cały urlop rodzicielski trzeba wykorzystać do końca roku, w którym dziecko kończy "
                f"{p.last_year_of_child_age.value} lat — najwyżej w {p.max_parts.value} częściach."
            ),
            sources=unique([*p.last_year_of_child_age.sources, *p.max_parts.sources]),
        ),
    ]


def _applications(
    scenario: Scenario, params: Params, segments: dict[str, Segment], today: dt.date
) -> list[Application]:
    birth = scenario.birth_date
    assert birth is not None
    where_mother = (
        "U pracodawcy (umowa o pracę). Bez etatu: wniosek ZAM do ZUS — przy umowie zlecenia "
        "do płatnika składek albo ZUS."
    )
    where_father = "U pracodawcy taty (umowa o pracę). Bez etatu: wniosek ZAM do ZUS."
    where_sources = [
        *params.rules.maternity_application.sources,
        *params.rules.forms_merged_into_zam.sources,
    ]
    parental_days = params.parental.application_days_before.value
    maternity_first = segments.get("maternity-prenatal") or segments["maternity"]

    apps = [
        Application(
            id="app-maternity",
            parent="mother",
            label="Wniosek: macierzyński",
            title="Wniosek o urlop macierzyński",
            due=maternity_first.start,
            is_deadline=False,
            rule=(
                "Mama składa wniosek o udzielenie urlopu macierzyńskiego. Jeśli zaraz po nim chce "
                "urlop rodzicielski, może złożyć jeden wniosek na oba urlopy. Na urlop przed "
                "porodem potrzebne jest zaświadczenie lekarskie o przewidywanej dacie porodu."
            ),
            where=where_mother,
            segment_id="maternity",
            sources=unique([*where_sources, *params.maternity.max_weeks_before_birth.sources[:1]]),
        )
    ]

    if scenario.flat_rate:
        fr = params.flat_rate
        days_after = fr.application_days_after_birth.value
        apps.append(
            Application(
                id="app-parental-mother",
                parent="mother",
                label=f"Wniosek: {percent(fr.rate_percent.value)}",
                title=f"Wniosek o zasiłek {percent(fr.rate_percent.value)} za macierzyński "
                "i rodzicielski",
                due=birth + days_after * DAY,
                is_deadline=True,
                rule=(
                    f"Najpóźniej {days_after} dni po porodzie — pisemny wniosek o zasiłek za cały "
                    "urlop macierzyński i rodzicielski w pełnym wymiarze."
                ),
                where=where_mother,
                segment_id="parental-mother",
                sources=unique([*fr.application_days_after_birth.sources, *where_sources]),
            )
        )
    else:
        apps.append(
            Application(
                id="app-parental-mother",
                parent="mother",
                label="Wniosek: rodzicielski (mama)",
                title="Wniosek o urlop rodzicielski — mama",
                due=segments["parental-mother"].start - parental_days * DAY,
                is_deadline=True,
                rule=(
                    f"Najpóźniej {parental_days} dni przed rozpoczęciem urlopu rodzicielskiego. "
                    "Można go złożyć razem z wnioskiem o urlop macierzyński."
                ),
                where=where_mother,
                segment_id="parental-mother",
                sources=unique([*params.parental.application_days_before.sources, *where_sources]),
            )
        )

    paternity_days = params.paternity.application_days_before.value
    apps += [
        Application(
            id="app-paternity",
            parent="father",
            label="Wniosek: ojcowski",
            title="Wniosek o urlop ojcowski",
            due=segments["paternity"].start - paternity_days * DAY,
            is_deadline=True,
            rule=f"Najpóźniej {paternity_days} dni przed rozpoczęciem urlopu ojcowskiego.",
            where=where_father,
            segment_id="paternity",
            sources=unique(
                [
                    *params.paternity.application_days_before.sources,
                    *params.rules.forms_merged_into_zam.sources,
                ]
            ),
        ),
        Application(
            id="app-parental-father",
            parent="father",
            label="Wniosek: rodzicielski (tata)",
            title="Wniosek o urlop rodzicielski — tata",
            due=segments["parental-father"].start - parental_days * DAY,
            is_deadline=True,
            rule=f"Najpóźniej {parental_days} dni przed rozpoczęciem urlopu rodzicielskiego.",
            where=where_father,
            segment_id="parental-father",
            sources=unique(
                [
                    *params.parental.application_days_before.sources,
                    *params.rules.forms_merged_into_zam.sources,
                ]
            ),
        ),
    ]
    for app in apps:
        app.passed = app.due < today
    return apps


def _warnings(scenario: Scenario, params: Params, today: dt.date) -> list[str]:
    birth = scenario.birth_date
    assert birth is not None
    warnings = []
    if not scenario.child_born and birth < today:
        warnings.append(
            f"Przewidywana data porodu ({fmt(birth)}) już minęła. Jeśli dziecko się urodziło, "
            "podaj faktyczną datę urodzenia — oś się przeliczy."
        )
    fr = params.flat_rate
    flat_deadline = birth + fr.application_days_after_birth.value * DAY
    if scenario.flat_rate and flat_deadline < today:
        warnings.append(
            f"Termin na wniosek o zasiłek {percent(fr.rate_percent.value)} minął "
            f"{fmt(flat_deadline)}."
        )
    limit = dt.date(birth.year + params.parental.last_year_of_child_age.value, 12, 31)
    if limit < today:
        warnings.append(f"Termin na urlop rodzicielski minął {fmt(limit)}.")
    return warnings


def _assumptions(scenario: Scenario, params: Params) -> list[str]:
    assumptions = ["Zakładamy, że mama i tata mają ubezpieczenie chorobowe (np. umowa o pracę)."]
    if not scenario.child_born:
        assumptions.append(
            "Liczymy od przewidywanej daty porodu. Po porodzie podaj faktyczną datę "
            "— oś się przeliczy."
        )
    assumptions += [
        "Urlop rodzicielski i ojcowski ułożyliśmy przykładowo. Rodzice mogą korzystać "
        "z rodzicielskiego jednocześnie albo na zmianę, w najwyżej "
        f"{params.parental.max_parts.value} częściach.",
        "Kwot jeszcze nie liczymy — potrzebna jest podstawa wymiaru zasiłku.",
    ]
    return assumptions
