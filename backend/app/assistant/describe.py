"""Plain-text views of the scenario and the timeline for the model.

All dates and numbers come from the engine; the model only reads them.
"""

from typing import NamedTuple

from pydantic import BaseModel

from app.assistant.guide import page_label
from app.engine.insurance import NOT_INSURED, coverage, father_coverage
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
from app.engine.pregnancy import employer_days_by_year, sick_leave
from app.engine.timeline import fmt
from app.services.params import load_params

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
    """Who is writing and how to address them, and what is known about the parents' work."""
    match scenario.role:
        case "mother":
            lines = [
                "Rozmawiasz z mamą. Mów do niej bezpośrednio: „możesz zacząć urlop…”, "
                "„Twój urlop macierzyński…”, „masz prawo do zasiłku…”. Wyjaśnienie sytuacji "
                "pisze o mamie w trzeciej osobie; Ty przekładaj to na „Ty”. O tacie mów "
                "w trzeciej osobie."
            ]
        case "father":
            lines = [
                "Rozmawiasz z tatą. O mamie i jej urlopie mów w trzeciej osobie: „mama może "
                "zacząć urlop…”. Do niego mów bezpośrednio, także o jego uprawnieniach: "
                "„możesz wziąć urlop ojcowski…”. Wyjaśnienie sytuacji pisze o tacie w trzeciej "
                "osobie; Ty przekładaj to na „Ty”."
            ]
        case _:
            lines = ["Nie wiesz, kto pisze. O mamie i o tacie mów w trzeciej osobie."]
    if scenario.mothers_work:
        lines.append(
            f"Mama {WORK[scenario.mothers_work]}. Od tego zależy jej ubezpieczenie chorobowe "
            "i prawo do zasiłku macierzyńskiego (punkt „Uprawnienie” albo „Uwaga” w wyjaśnieniu)."
        )
    if scenario.fathers_work:
        lines.append(
            f"Wiadomo też, że tata {WORK[scenario.fathers_work]}. Od tego zależą jego "
            "uprawnienia (punkty wyjaśnienia o tacie)."
        )
    if scenario.mother_event and scenario.mother_event.kind == "death":
        lines.append(
            "Mama dziecka zmarła. Pisz krótko, z szacunkiem i współczuciem, bez wykrzykników "
            "i gratulacji, i mów tylko o tym, co przysługuje tacie."
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
    key: str
    """Which question it is, for the UI's answer cards and suggestions."""


class InterviewQuestion(BaseModel):
    """The next interview question as the UI gets it: the chat and the answer cards ask the
    same thing as the assistant."""

    key: str
    text: str


def next_question(scenario: Scenario) -> InterviewQuestion | None:
    questions = interview_questions(scenario)
    return InterviewQuestion(key=questions[0].key, text=questions[0].text) if questions else None


def interview_questions(scenario: Scenario) -> list[Question]:
    """The questions the interview still has to ask, in order: the date and the children, the
    mother, then the father. Never about taking over maternity leave or the mother's special
    situations: those are recorded only when the user brings them up."""
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
                "date",
            )
        )
    if scenario.children_count is None:
        questions.append(
            Question(
                "Ile dzieci urodziło się przy jednym porodzie?"
                if born
                else "Ile dzieci urodzi się przy jednym porodzie?",
                "`set_children_count`",
                "children",
            )
        )
    # The mother's insurance first: without it she has no maternity leave to plan.
    if cover == "unknown-work":
        questions.append(
            Question(
                "Jak pracuje mama: na etacie (umowa o pracę), na umowie zlecenia, prowadzi "
                "własną firmę czy nie pracuje?",
                "`set_mother_work`",
                "mother-work",
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
                "mother-insurance",
            )
        )
    insured = cover not in NOT_INSURED
    if insured:
        questions += _leave_before_birth_questions(scenario)

    # Never after the loss of every child: nothing to plan there, and the questions would hurt.
    if scenario.losses and len(scenario.losses) >= (scenario.children_count or 1):
        return questions
    if insured:
        questions += _hospital_questions(scenario)
    # The father's rights do not depend on the mother's insurance.
    return questions + _father_questions(scenario) + _pregnancy_questions(scenario)


def _leave_before_birth_questions(scenario: Scenario) -> list[Question]:
    """Maternity leave before the birth and, when she plans it, the medical certificate."""
    born = scenario.child_born is True
    mother = scenario.role == "mother"
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
        return [
            Question(
                text,
                "`set_leave_before_birth` (0 = bez urlopu przed porodem)",
                "leave-before-birth",
            )
        ]
    if (
        not born
        and scenario.leave_before_birth_weeks > 0
        and scenario.has_medical_certificate is None
    ):
        return [
            Question(
                "Czy masz już zaświadczenie lekarskie o przewidywanej dacie porodu?"
                if mother
                else "Czy mama ma już zaświadczenie lekarskie o przewidywanej dacie porodu?",
                "`set_medical_certificate`",
                "certificate",
            )
        ]
    return []


def _hospital_questions(scenario: Scenario) -> list[Question]:
    """Only a born child can have been premature or in hospital: supplementary maternity
    leave."""
    if scenario.child_born is not True:
        return []
    several = (scenario.children_count or 1) > 1
    if scenario.hospital_care is None:
        return [
            Question(
                "Czy dzieci urodziły się przed ukończeniem 37. tygodnia ciąży albo któreś "
                "z nich było po porodzie w szpitalu?"
                if several
                else "Czy dziecko urodziło się przed ukończeniem 37. tygodnia ciąży albo było "
                "po porodzie w szpitalu?",
                "`set_hospital_care` (applies: tak albo nie)",
                "hospital",
            )
        ]
    if scenario.hospital_care and (
        scenario.birth_week is None or scenario.birth_weight_up_to_1000g is None
    ):
        return [
            Question(
                "W którym tygodniu ciąży urodziły się dzieci, czy najlżejsze z nich ważyło nie "
                "więcej niż 1000 g i od kiedy do kiedy było w szpitalu to, które leżało najdłużej?"
                if several
                else "W którym tygodniu ciąży urodziło się dziecko, czy ważyło nie więcej niż "
                "1000 g i od kiedy do kiedy było w szpitalu?",
                "`set_hospital_care` (ze wszystkimi szczegółami naraz)",
                "hospital-details",
            )
        ]
    return []


def _father_questions(scenario: Scenario) -> list[Question]:
    """How the father works and, on a contract or with a business, his voluntary insurance.
    His rights depend on it (guide section B)."""
    match father_coverage(scenario):
        case "unknown-work":
            return [
                Question(
                    "Jak pracuje tata: na etacie (umowa o pracę), na umowie zlecenia, prowadzi "
                    "własną firmę czy nie pracuje?",
                    "`set_father_work`",
                    "father-work",
                )
            ]
        case "unknown-voluntary":
            return [
                Question(
                    "Czy jesteś zgłoszony do dobrowolnego ubezpieczenia chorobowego (opłacasz "
                    "składkę chorobową)?"
                    if scenario.role == "father"
                    else "Czy tata jest zgłoszony do dobrowolnego ubezpieczenia chorobowego "
                    "(opłaca składkę chorobową)?",
                    "`set_father_insurance`",
                    "father-insurance",
                )
            ]
        case _:
            return []


def _pregnancy_questions(scenario: Scenario) -> list[Question]:
    """While the child is on the way: the mother's sick leave and, for the sickness benefit,
    since when she is insured and, past the shorter employer's limit, her age. Losing the job,
    a contract begun in pregnancy and a raised contribution base are never asked."""
    if scenario.child_born is not False or scenario.anchor_date is None:
        return []
    work = scenario.mothers_work
    if work is None or coverage(scenario) in NOT_INSURED | {"unknown-voluntary"}:
        return []
    mother = scenario.role == "mother"
    if scenario.sick_leave is None:
        return [
            Question(
                "Czy w tej ciąży jesteś albo byłaś na zwolnieniu lekarskim? Jeśli tak, od kiedy "
                "i do kiedy (albo że do porodu)?"
                if mother
                else "Czy mama w tej ciąży jest albo była na zwolnieniu lekarskim? Jeśli tak, "
                "od kiedy i do kiedy (albo że do porodu)?",
                "`set_sick_leave`",
                "sick-leave",
            )
        ]
    if not scenario.sick_leave:
        return []
    if scenario.insured_since is None:
        if work == "employment":
            text = (
                "Od kiedy bez przerwy pracujesz na umowie o pracę (podlegasz ubezpieczeniu "
                "chorobowemu)?"
                if mother
                else "Od kiedy mama bez przerwy pracuje na umowie o pracę (podlega ubezpieczeniu "
                "chorobowemu)?"
            )
        else:
            text = (
                "Od kiedy jesteś zgłoszona do dobrowolnego ubezpieczenia chorobowego?"
                if mother
                else "Od kiedy mama jest zgłoszona do dobrowolnego ubezpieczenia chorobowego?"
            )
        return [Question(text, "`set_insured_since`", "insured-since")]
    params = load_params()
    try:
        sick = sick_leave(scenario, params, scenario.anchor_date)
    except ScenarioError:
        sick = None
    shorter = params.pregnancy.employer_days_from_50.value
    paid = employer_days_by_year(sick) if sick is not None else {}
    if (
        work == "employment"
        and scenario.mother_over_50 is None
        and max(paid.values(), default=0) > shorter
    ):
        year = min(paid)
        return [
            Question(
                f"Czy skończyłaś 50 lat przed rokiem {year}? Od tego zależy, za ile dni "
                "zwolnienia płaci pracodawca."
                if mother
                else f"Czy mama skończyła 50 lat przed rokiem {year}? Od tego zależy, za ile "
                "dni zwolnienia płaci pracodawca.",
                "`set_mother_over_50`",
                "mother-over-50",
            )
        ]
    return []


def describe_interview(scenario: Scenario) -> str:
    """The next interview question, word for word, the tool for its answer, and what follows."""
    questions = interview_questions(scenario)
    if not questions:
        return "Wywiad: wszystko ustalone."
    first, *rest = questions
    later = "".join(f" Potem: „{q.text}” (narzędzie {q.tool})." for q in rest)
    several = (
        " Jeśli wiadomość odpowiada na kilka z tych pytań naraz, zapisz każdą odpowiedź jej "
        "narzędziem."
        if rest
        else ""
    )
    return (
        f"Następne pytanie wywiadu (zadaj je dokładnie tak): „{first.text}” Gdy użytkownik "
        f"odpowie, najpierw zapisz odpowiedź narzędziem {first.tool}, potem pisz.{later}{several}"
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
            backed = f" (źródła: {'; '.join(labels)})" if labels else ""
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
