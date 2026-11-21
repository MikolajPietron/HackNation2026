"""Plain-text views of the timeline for the model. All dates and numbers come from the engine."""

from app.engine.models import (
    Application,
    Marker,
    Scenario,
    Segment,
    SourceRef,
    Timeline,
    TimelineElement,
)
from app.engine.timeline import fmt, percent

LANES = {"mother": "Mama", "father": "Tata", "child": "Dziecko", "applications": "Wnioski"}
PARENTS = {"mother": "mama", "father": "tata"}
DOCS = {"przewodnik": "Przewodnik", "kp": "Kodeks pracy", "ustawa": "ustawa zasiłkowa"}


def source_label(source: SourceRef) -> str:
    where = f"s. {source.page}" if source.page else source.article
    return f"{DOCS[source.doc]}, {where}" if where else DOCS[source.doc]


def describe_scenario(scenario: Scenario) -> str:
    """For an empty timeline: what we already know, if anything."""
    known = []
    if scenario.children_count > 1:
        known.append(f"dzieci z jednego porodu: {scenario.children_count}")
    if scenario.maternity_weeks_before_birth:
        known.append(f"urlop przed porodem: {scenario.maternity_weeks_before_birth} tyg.")
    if scenario.flat_rate:
        known.append("wybrany wariant jednej stawki zasiłku")
    facts = f" Już wiadomo: {'; '.join(known)}." if known else ""
    return f"Data porodu nie jest jeszcze ustawiona — oś czasu jest pusta.{facts}"


def describe_timeline(timeline: Timeline, changed: list[str] | None = None) -> str:
    status = "faktyczna" if timeline.child_born else "przewidywana"
    lines = [
        f"Data porodu: {fmt(timeline.birth_date)} ({status}). "
        f"Dzieci z jednego porodu: {timeline.children_count}. Dziś: {fmt(timeline.today)}.",
        "",
        "Odcinki (id w nawiasach):",
    ]
    for s in timeline.segments:
        example = ", przykładowy termin" if s.is_example else ""
        lines.append(
            f"- [{s.id}] {LANES[s.lane]}: {s.title}, {fmt(s.start)}–{fmt(s.end)} ({s.days} dni), "
            f"zasiłek {percent(s.rate_percent)}{example}"
        )
    lines += ["", "Ważne dni:"]
    lines += [f"- [{m.id}] {fmt(m.date)}: {m.title}" for m in timeline.markers]
    lines += ["", "Wnioski:"]
    for a in timeline.applications:
        when = f"termin: {fmt(a.due)}" if a.is_deadline else f"potrzebny na: {fmt(a.due)}"
        passed = " — TERMIN MINĄŁ" if a.passed else ""
        lines.append(f"- [{a.id}] {PARENTS[a.parent]}: {a.title}, {when}{passed}")
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
                f"{element.title} ({LANES[element.lane]}): {period}, {element.days} dni.",
                f"Świadczenie: {element.benefit}. Kto wypłaca: {element.payer}",
                element.summary,
                *element.details,
            ]
        case Marker():
            lines = [f"{element.title}: {fmt(element.date)}.", element.summary, *element.details]
        case Application():
            when = ("Termin: " if element.is_deadline else "Potrzebny na: ") + fmt(element.due)
            lines = [
                f"{element.title} ({PARENTS[element.parent]}). {when}"
                f"{' (termin minął)' if element.passed else ''}.",
                f"Zasada: {element.rule}",
                f"Gdzie złożyć: {element.where}",
            ]
    lines += ["", "Źródła:"]
    for s in element.sources:
        quote = f": „{s.quote}”" if s.quote else ""
        lines.append(f"- {source_label(s)}{quote}")
    return "\n".join(lines)
