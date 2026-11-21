"""Plain-text views of the scenario and the timeline for the model.

All dates and numbers come from the engine; the model only reads them.
"""

from app.engine.models import (
    Document,
    Marker,
    Scenario,
    Segment,
    SourceRef,
    Timeline,
    TimelineElement,
)
from app.engine.timeline import fmt

WORK = {
    "employment": "pracuje na etacie (umowa o pracę)",
    "contract": "pracuje na umowie zlecenia",
    "business": "prowadzi własną firmę (JDG)",
    "none": "nie pracuje",
}
EARNINGS = {
    "under-5k": "do 5 000 zł",
    "5k-8k": "5 000 – 8 000 zł",
    "8k-12k": "8 000 – 12 000 zł",
    "over-12k": "powyżej 12 000 zł",
    "unknown": "nie wiem",
}


def source_label(source: SourceRef) -> str:
    if source.doc == "kp":
        return f"Kodeks pracy, {source.article}"
    return f"Przewodnik ZUS, s. {source.page}"


def describe_person(scenario: Scenario) -> str:
    """Who is writing and how to address them, plus the onboarding answers no phase uses yet."""
    match scenario.role:
        case "mother":
            lines = [
                "Rozmawiasz z mamą. Mów do niej bezpośrednio: „możesz zacząć urlop…”, "
                "„Twój urlop macierzyński…”."
            ]
        case "father":
            lines = [
                "Rozmawiasz z tatą. O urlopie macierzyńskim mów w trzeciej osobie: "
                "„mama może zacząć urlop…”."
            ]
        case _:
            lines = ["Nie wiesz, kto pisze. O urlopie macierzyńskim mów w trzeciej osobie."]
    facts = []
    if scenario.work:
        facts.append(WORK[scenario.work])
    if scenario.earnings:
        facts.append(f"zarabia miesięcznie brutto: {EARNINGS[scenario.earnings]}")
    if facts:
        who = "tata" if scenario.role == "father" else "ta osoba"
        lines.append(
            f"Z onboardingu wiadomo też, że {who} {', '.join(facts)}. To odpowiedzi osoby, która "
            "pisze. Ten etap aplikacji jeszcze ich nie wykorzystuje: posłużą w kolejnych etapach "
            "(kto wypłaca zasiłek, wnioski, kwoty). Nic z nich nie wyliczaj i nie dopytuj o nie."
        )
    return "\n".join(lines)


def describe_interview(scenario: Scenario) -> str:
    """What the interview still has to establish, in order."""
    born = scenario.child_born is True
    missing = []
    if scenario.anchor_date is None:
        missing.append("data porodu: przewidywana albo, jeśli dziecko już jest, data urodzenia")
    if scenario.children_count is None:
        missing.append("ile dzieci przy jednym porodzie")
    if scenario.leave_before_birth_weeks is None:
        missing.append(
            "czy mama była na urlopie macierzyńskim przed porodem (ile tygodni)"
            if born
            else "urlop przed porodem (ile tygodni) czy praca do dnia porodu"
        )
    elif (
        not born
        and scenario.leave_before_birth_weeks > 0
        and scenario.has_medical_certificate is None
    ):
        missing.append("czy mama ma zaświadczenie lekarskie o przewidywanej dacie porodu")
    if not missing:
        return "Wywiad: wszystko ustalone."
    return "Wywiad — do ustalenia: " + "; ".join(missing) + "."


def describe_timeline(timeline: Timeline, changed: list[str] | None = None) -> str:
    birth = (
        f"Data urodzenia: {fmt(timeline.birth_date)}."
        if timeline.child_born
        else f"Przewidywana data porodu: {fmt(timeline.birth_date)}."
    )
    count = (
        f" Dzieci przy jednym porodzie: {timeline.children_count}."
        if timeline.children_count
        else ""
    )
    lines = [f"{birth}{count} Dziś: {fmt(timeline.today)}.", "", "Na osi (id w nawiasach):"]
    for s in timeline.segments:
        lines.append(f"- [{s.id}] {s.title}: {fmt(s.start)}–{fmt(s.end)} ({s.days} dni)")
    lines += [f"- [{m.id}] {fmt(m.date)}: {m.title}" for m in timeline.markers]
    for d in timeline.documents:
        status = "mama już je ma" if d.done else "jeszcze potrzebne"
        lines.append(f"- [{d.id}] {d.title}: potrzebne na {fmt(d.needed_by)} ({status})")
    if timeline.notes:
        lines += ["", "Wyjaśnienie sytuacji (z kalkulatora, z tego mów):"]
        for n in timeline.notes:
            labels = list(dict.fromkeys(source_label(s) for s in n.sources))
            backed = f" (źródła: {'; '.join(labels)})" if labels else ""
            lines.append(f"- [{n.kind}] {n.title}: {n.text}{backed}")
    if timeline.warnings:
        lines += ["", "Ostrzeżenia:", *(f"- {w}" for w in timeline.warnings)]
    if changed:
        lines += ["", f"Zmienione przez tę operację: {', '.join(changed)}"]
    return "\n".join(lines)


def describe_element(element: TimelineElement) -> str:
    match element:
        case Segment():
            period = f"{fmt(element.start)}–{fmt(element.end)}"
            lines = [
                f"{element.title}: {period}, {element.days} dni.",
                element.summary,
                *element.details,
            ]
        case Marker():
            lines = [f"{element.title}: {fmt(element.date)}.", element.summary, *element.details]
        case Document():
            status = "mama już je ma" if element.done else "jeszcze potrzebne"
            lines = [
                f"{element.title}: potrzebne na {fmt(element.needed_by)} ({status}).",
                element.rule,
            ]
    lines += ["", "Źródła (cytuj dosłownie):"]
    lines += [f"- {source_label(s)}: „{s.quote}”" for s in element.sources]
    return "\n".join(lines)
