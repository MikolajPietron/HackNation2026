"""Plain-text views of the scenario and the timeline for the model.

All dates and numbers come from the engine; the model only reads them.
"""

from typing import NamedTuple

from app.assistant.guide import page_label
from app.engine.insurance import NOT_INSURED, coverage
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


# How the explanation points are named for the model; brackets are kept for element ids only.
NOTE_KINDS = {
    "situation": "Sytuacja",
    "right": "Uprawnienie",
    "risk": "Uwaga",
    "choice": "Możliwość wyboru",
    "relief": "Ułatwienie",
    "computed": "Co policzyliśmy",
}


def source_label(source: SourceRef) -> str:
    if source.doc == "kp":
        return f"Kodeks pracy, {source.article}"
    return f"Przewodnik ZUS, {page_label(source.page, source.page_to)}"


def describe_person(scenario: Scenario) -> str:
    """Who is writing and how to address them, and what the onboarding said about work."""
    match scenario.role:
        case "mother":
            lines = [
                "Rozmawiasz z mamą. Mów do niej bezpośrednio: „możesz zacząć urlop…”, "
                "„Twój urlop macierzyński…”, „masz prawo do zasiłku…”. Wyjaśnienie sytuacji "
                "pisze o mamie w trzeciej osobie; Ty przekładaj to na „Ty”."
            ]
        case "father":
            lines = [
                "Rozmawiasz z tatą. O urlopie macierzyńskim mów w trzeciej osobie: "
                "„mama może zacząć urlop…”."
            ]
        case _:
            lines = ["Nie wiesz, kto pisze. O urlopie macierzyńskim mów w trzeciej osobie."]
    if scenario.mothers_work:
        lines.append(
            f"Mama {WORK[scenario.mothers_work]}. Od tego zależy jej ubezpieczenie chorobowe "
            "i prawo do zasiłku macierzyńskiego (punkt „Uprawnienie” albo „Uwaga” w wyjaśnieniu)."
        )
    if scenario.role == "father" and scenario.work:
        lines.append(
            f"Z onboardingu wiadomo też, że tata {WORK[scenario.work]}. Ten etap aplikacji tego "
            "nie wykorzystuje: uprawnienia taty dojdą w kolejnych etapach."
        )
    if scenario.earnings:
        who = "tata" if scenario.role == "father" else "mama"
        lines.append(
            f"Zarobki z onboardingu ({who}, miesięcznie brutto: {EARNINGS[scenario.earnings]}) "
            "posłużą dopiero przy kwotach zasiłku. Nic z nich nie wyliczaj i nie dopytuj o nie."
        )
    return "\n".join(lines)


class Question(NamedTuple):
    text: str
    """Worded for whoever is writing; the assistant asks it word for word."""
    tool: str
    """The tool that saves the answer."""


def interview_questions(scenario: Scenario) -> list[Question]:
    """The questions the interview still has to ask, in order."""
    born = scenario.child_born is True
    mother = scenario.role == "mother"
    cover = coverage(scenario)
    questions = []
    if scenario.anchor_date is None:
        questions.append(
            Question(
                "Kiedy jest przewidywany poród albo kiedy urodziło się dziecko? Podaj dzień, "
                "miesiąc i rok.",
                "`set_due_date` (dziecko w drodze) albo `set_birth_date` (już urodzone)",
            )
        )
    if scenario.children_count is None:
        questions.append(
            Question(
                "Ile dzieci urodziło się przy jednym porodzie?"
                if born
                else "Ile dzieci urodzi się przy jednym porodzie?",
                "`set_children_count`",
            )
        )
    # Insurance first: without it there is nothing to plan.
    if cover == "unknown-work":
        questions.append(
            Question(
                "Jak pracuje mama: na etacie (umowa o pracę), na umowie zlecenia, prowadzi "
                "własną firmę czy nie pracuje?",
                "`set_mother_work`",
            )
        )
    elif cover == "unknown-voluntary":
        questions.append(
            Question(
                "Czy jesteś zgłoszona do dobrowolnego ubezpieczenia chorobowego (opłacasz "
                "składkę chorobową)?"
                if mother
                else "Czy mama jest zgłoszona do dobrowolnego ubezpieczenia chorobowego "
                "(opłaca składkę chorobową)?",
                "`set_voluntary_insurance`",
            )
        )
    if cover in NOT_INSURED:
        return questions

    if scenario.leave_before_birth_weeks is None:
        if born:
            text = (
                "Czy byłaś na urlopie macierzyńskim przed porodem? Jeśli tak, ile tygodni przed "
                "porodem go zaczęłaś?"
                if mother
                else "Czy mama była na urlopie macierzyńskim przed porodem? Jeśli tak, ile "
                "tygodni przed porodem go zaczęła?"
            )
        else:
            text = (
                "Chcesz zacząć urlop macierzyński przed porodem (ile tygodni wcześniej?), czy "
                "pracować do dnia porodu?"
                if mother
                else "Czy mama chce zacząć urlop macierzyński przed porodem (ile tygodni "
                "wcześniej?), czy pracować do dnia porodu?"
            )
        questions.append(Question(text, "`set_leave_before_birth` (0 = bez urlopu przed porodem)"))
    elif (
        not born
        and scenario.leave_before_birth_weeks > 0
        and scenario.has_medical_certificate is None
    ):
        questions.append(
            Question(
                "Czy masz już zaświadczenie lekarskie o przewidywanej dacie porodu?"
                if mother
                else "Czy mama ma już zaświadczenie lekarskie o przewidywanej dacie porodu?",
                "`set_medical_certificate`",
            )
        )

    # Only a born child can have been premature or in hospital: supplementary maternity leave.
    # Never after a loss of every child: nothing to plan there, and the question would hurt.
    several = (scenario.children_count or 1) > 1
    if scenario.losses and len(scenario.losses) >= (scenario.children_count or 1):
        return questions
    if born and scenario.hospital_care is None:
        questions.append(
            Question(
                "Czy dzieci urodziły się przed ukończeniem 37. tygodnia ciąży albo któreś "
                "z nich było po porodzie w szpitalu?"
                if several
                else "Czy dziecko urodziło się przed ukończeniem 37. tygodnia ciąży albo było "
                "po porodzie w szpitalu?",
                "`set_hospital_care` (applies: tak albo nie)",
            )
        )
    elif (
        born
        and scenario.hospital_care
        and (scenario.birth_week is None or scenario.birth_weight_up_to_1000g is None)
    ):
        questions.append(
            Question(
                "W którym tygodniu ciąży urodziły się dzieci, czy najlżejsze z nich ważyło nie "
                "więcej niż 1000 g i od kiedy do kiedy było w szpitalu to, które leżało najdłużej?"
                if several
                else "W którym tygodniu ciąży urodziło się dziecko, czy ważyło nie więcej niż "
                "1000 g i od kiedy do kiedy było w szpitalu?",
                "`set_hospital_care` (ze wszystkimi szczegółami naraz)",
            )
        )
    return questions


def describe_interview(scenario: Scenario) -> str:
    """The next interview question, word for word, the tool for its answer, and what follows."""
    questions = interview_questions(scenario)
    if not questions:
        return "Wywiad: wszystko ustalone."
    first, *rest = questions
    later = f" Potem: {' '.join(q.text for q in rest)}" if rest else ""
    return (
        f"Następne pytanie wywiadu (zadaj je dokładnie tak): „{first.text}” Gdy użytkownik "
        f"odpowie, najpierw zapisz odpowiedź narzędziem {first.tool}, potem pisz.{later}"
    )


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
            backed = (
                f" (źródła: {'; '.join(labels)})"
                if labels
                else " (bez źródła: to opis naszego liczenia, nie dopisuj do niego źródła)"
            )
            lines.append(f"- {NOTE_KINDS[n.kind]} — {n.title}. {n.text}{backed}")
    if timeline.warnings:
        lines += ["", "Ostrzeżenia:", *(f"- {w}" for w in timeline.warnings)]
    if changed:
        lines += ["", f"Zmienione przez tę operację: {', '.join(changed)}"]
    return "\n".join(lines)


def describe_note_changes(timeline: Timeline, changed_notes: list[str] | None) -> str:
    """What to talk about after a recalculation. None = the timeline has just appeared."""
    if changed_notes is None:
        return (
            "Oś czasu właśnie powstała: omów całe wyjaśnienie sytuacji, punkt po punkcie, "
            "w podanej kolejności."
        )
    titles = [f"„{n.title}”" for n in timeline.notes if n.id in changed_notes]
    if not titles:
        return "Wyjaśnienie sytuacji się nie zmieniło: powiedz krótko, co zmieniło się na osi."
    return (
        f"Zmienione punkty wyjaśnienia: {', '.join(titles)}. Omów teraz tylko je, w tej "
        "kolejności, po jednym–dwóch zdaniach na punkt. Pozostałych punktów nie powtarzaj: "
        "użytkownik już je zna."
    )


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
