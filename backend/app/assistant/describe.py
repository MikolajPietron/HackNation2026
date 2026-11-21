"""Plain-text views of the timeline for the model. All dates and numbers come from the engine."""

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


def source_label(source: SourceRef) -> str:
    return f"Przewodnik ZUS, s. {source.page}"


def describe_interview(scenario: Scenario) -> str:
    """What the interview still has to establish."""
    missing = []
    if scenario.due_date is None:
        missing.append("przewidywana data porodu")
    if scenario.leave_before_birth_weeks is None:
        missing.append("urlop przed porodem czy praca do dnia porodu")
    elif scenario.leave_before_birth_weeks > 0 and scenario.has_medical_certificate is None:
        missing.append("czy mama ma zaświadczenie lekarskie o przewidywanej dacie porodu")
    if not missing:
        return "Wywiad: wszystko ustalone."
    return "Wywiad — do ustalenia: " + "; ".join(missing) + "."


def describe_timeline(timeline: Timeline, changed: list[str] | None = None) -> str:
    lines = [
        f"Przewidywana data porodu: {fmt(timeline.due_date)}. Dziś: {fmt(timeline.today)}.",
        "",
        "Na osi (id w nawiasach):",
    ]
    for s in timeline.segments:
        lines.append(f"- [{s.id}] {s.title}: {fmt(s.start)}–{fmt(s.end)} ({s.days} dni)")
    lines += [f"- [{m.id}] {fmt(m.date)}: {m.title}" for m in timeline.markers]
    for d in timeline.documents:
        status = "mama już je ma" if d.done else "jeszcze potrzebne"
        lines.append(f"- [{d.id}] {d.title}: potrzebne na {fmt(d.needed_by)} ({status})")
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
