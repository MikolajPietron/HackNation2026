"""Phase 1 rules: preparing for the birth (guide section A, page 5).

- The mother may start maternity leave at most N weeks before the expected due date.
- For that she needs a medical certificate of the expected due date.
- She may also work until the day of the birth; the benefit then starts after the birth.

Pure and deterministic: no I/O, no database, no LLM; `today` is an argument. Every number comes
from `Params`, every element carries its sources. Later phases add rules after these.
"""

import datetime as dt

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

DAY = dt.timedelta(days=1)
WEEK = dt.timedelta(days=7)


def fmt(d: dt.date) -> str:
    return d.strftime("%d.%m.%Y")


def build_timeline(scenario: Scenario, params: Params, today: dt.date) -> Timeline:
    if scenario.due_date is None:
        raise ScenarioError("Najpierw potrzebna jest przewidywana data porodu.")
    due = scenario.due_date
    weeks = scenario.leave_before_birth_weeks
    limit = params.maternity.max_weeks_before_birth
    if weeks is not None and weeks > limit.value:
        raise ScenarioError(
            f"Urlop macierzyński można zacząć maksymalnie {limit.value} tyg. przed przewidywaną "
            "datą porodu."
        )

    certificate = params.rules.medical_certificate
    work = params.rules.work_until_birth
    earliest = due - limit.value * WEEK
    last_day_before = due - DAY
    segments: list[Segment] = []
    markers: list[Marker] = []
    documents: list[Document] = []

    if weeks is None:
        segments.append(
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
    elif weeks == 0:
        segments.append(
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
    else:
        start = due - weeks * WEEK
        segments.append(
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
                    f"Najwcześniej można go zacząć {limit.value} tyg. przed przewidywaną datą "
                    "porodu.",
                    "Potrzebne jest zaświadczenie lekarskie o przewidywanej dacie porodu.",
                ],
                sources=[*limit.sources, *certificate.sources],
            )
        )
        if weeks < limit.value:
            markers.append(
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
        has_certificate = scenario.has_medical_certificate is True
        documents.append(
            Document(
                id="medical-certificate",
                label="Zaświadczenie lekarskie",
                title="Zaświadczenie lekarskie o przewidywanej dacie porodu",
                needed_by=start,
                done=has_certificate,
                rule=(
                    "Mama potrzebuje go, żeby zacząć urlop macierzyński przed przewidywaną "
                    "datą porodu."
                ),
                segment_id="maternity-prenatal",
                sources=certificate.sources,
            )
        )

    markers.append(
        Marker(
            id="due-date",
            lane="child",
            label="Termin porodu",
            title="Przewidywana data porodu",
            date=due,
            summary=(
                "Po urodzeniu dziecka zaczyna się zasiłek macierzyński."
                if weeks == 0
                else "Od tej daty liczymy, kiedy najwcześniej może zacząć się urlop macierzyński."
            ),
            sources=work.sources if weeks == 0 else limit.sources,
        )
    )
    markers.sort(key=lambda m: m.date)

    warnings = []
    if due < today:
        warnings.append(
            f"Przewidywana data porodu ({fmt(due)}) już minęła. Sprawdź, czy data jest dobra."
        )

    return Timeline(
        params_version=params.version,
        today=today,
        due_date=due,
        segments=segments,
        markers=markers,
        documents=documents,
        warnings=warnings,
        assumptions=[
            "Na tym etapie pokazujemy przygotowanie do porodu (Przewodnik ZUS, s. 5). "
            "Kolejne części Przewodnika dodajemy krok po kroku.",
            "Wszystko liczymy od przewidywanej daty porodu.",
        ],
    )


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
