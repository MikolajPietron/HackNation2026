"""Plain-text views of the scenario and the timeline for the model.

All dates and numbers come from the engine; the model only reads them.
"""

import datetime as dt
from typing import Literal, NamedTuple

from pydantic import BaseModel

from app.assistant.guide import page_label
from app.assistant.law import ROZPORZADZENIE_NAME
from app.engine.after_insurance import after_job_loss, leave_before_cut
from app.engine.amounts import dec, pln
from app.engine.insurance import NOT_INSURED, coverage, father_coverage
from app.engine.models import (
    CaseNote,
    Document,
    Marker,
    Payment,
    RequestForm,
    Scenario,
    ScenarioError,
    Segment,
    SourceRef,
    Timeline,
    TimelineElement,
)
from app.engine.money import pay_matters
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
YES_NO = {True: "tak", False: "nie"}


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
    if source.doc == "ustawa":
        return f"Ustawa zasiłkowa, {source.article}"
    if source.doc == "zalacznik":
        return f"Załącznik ZUS, {source.section}"
    if source.doc in ROZPORZADZENIE_NAME:
        return f"{ROZPORZADZENIE_NAME[source.doc]}, {source.article}"
    return f"Przewodnik ZUS, {page_label(source.page, source.page_to)}"


# Deadlines (ZADANIA B.4): the model says "termin" only where applications.py counted one from
# the Labour Code (`Document.deadline`); any other date of a document is the day its leave,
# benefit or sick leave starts, and the materials give no deadline for it.
NO_DEADLINE = (
    "na dzień startu, bez terminu w materiałach: {day} (to nie jest termin; nie pisz przy tej "
    "dacie „najpóźniej”, „do” ani „termin”)"
)


def document_when(document: Document, today: dt.date) -> str:
    """When a document is due, in words the model may repeat."""
    if document.done:
        return "mama już je ma"
    if document.deadline is None:
        return NO_DEADLINE.format(day=fmt(document.needed_by))
    # A non-employee's ZAM for the later periods: the regulation of 27.09.2026 (applications.py).
    law = (
        "termin z rozporządzenia o dokumentach do zasiłków"
        if any(s.doc == "rozp_zasilki" for s in document.sources)
        else "termin z Kodeksu pracy"
    )
    if document.deadline < today:
        filed = (
            f"; złożony {fmt(document.needed_by)} jest w terminie dla późniejszego urlopu (zasada "
            "przy dokumencie)"
            if document.needed_by != document.deadline
            else ""
        )
        return f"{law} minął {fmt(document.deadline)}{filed}"
    return f"{law} (policzył go kalkulator): najpóźniej {fmt(document.deadline)}"


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
    if scenario.taken_in is not None:
        from app.assistant.describe_adoption import describe_taken_in

        lines.append(describe_taken_in(scenario))
    if scenario.mother_event and scenario.mother_event.kind == "death":
        lines.append(
            "Mama dziecka zmarła. Pisz krótko, z szacunkiem i współczuciem, bez wykrzykników "
            "i gratulacji, i mów tylko o tym, co przysługuje tacie."
        )
    if scenario.parental_parts:
        lines.append(describe_parental_plan(scenario))
    if scenario.earnings:
        who = "tata" if scenario.role == "father" else "mama"
        lines.append(
            f"Zarobki z onboardingu ({who}, miesięcznie brutto: {EARNINGS[scenario.earnings]}) "
            "to tylko przedział. Nic z nich nie wyliczaj: kwoty zasiłku liczy kalkulator "
            "z dokładnej kwoty, o którą pyta wywiad (`set_monthly_pay`)."
        )
    # The benefit base in detail (engine/base.py): what is recorded, so a change adds to it.
    lines += [describe_pay_history(scenario, parent) for parent in ("mother", "father")]
    return "\n".join(line for line in lines if line)


def describe_pay_history(scenario: Scenario, parent: Literal["mother", "father"]) -> str:
    """The parent's recorded pay history, as `set_pay_history` takes it; "" when none."""
    history = scenario.mother_pay_history if parent == "mother" else scenario.father_pay_history
    if history is None:
        return ""
    items = []
    for m in history.months:
        item = f"{m.month}: {_num(m.amount)} zł"
        if m.days_worked is not None:
            item += f", przepracowane {m.days_worked} z {m.days_required} dni"
        if m.fixed is not None:
            item += f", stałe z umowy {_num(m.fixed)} zł, zmienne {_num(m.variable or 0)} zł"
        if m.not_topped:
            item += f", bez uzupełniania {_num(m.not_topped)} zł"
        items.append(item)
    extra = [
        f"{label}: {value}"
        for label, value in (
            ("premie kwartalne za 4 kwartały", _num(history.quarterly_bonuses)),
            ("składniki roczne", _num(history.annual_bonus)),
            ("pełny etat", None if history.full_time is None else YES_NO[history.full_time]),
            ("ubezpieczenie od", history.insured_from and fmt(history.insured_from)),
            ("wynagrodzenie z umowy", _num(history.contract_pay)),
        )
        if value is not None
    ]
    who = "mamy" if parent == "mother" else "taty"
    months = "; ".join(items) if items else "bez miesięcy"
    return (
        f"Zapisane dane do podstawy zasiłku {who} (`set_pay_history`): {months}"
        + (f"; {'; '.join(extra)}" if extra else "")
        + ". Podstawę i kwoty liczy kalkulator."
    )


def _num(amount: float | None) -> str | None:
    """An amount as given: 8000, 2434.78 (None stays None)."""
    if amount is None:
        return None
    return f"{amount:.2f}".rstrip("0").rstrip(".")


def describe_parental_plan(scenario: Scenario) -> str:
    """The parents' plan of parental leave as recorded, so a change can restate it whole."""
    items = []
    for number, part in enumerate(scenario.parental_parts, 1):
        if part.start is not None:
            when = f"od {fmt(part.start)}"
        elif part.with_previous:
            when = "razem z poprzednią częścią"
        elif number > 1:
            when = "po poprzedniej części"
        else:
            when = "tam, gdzie oś pokazuje urlop rodzicielski"
        work = ""
        if part.work_fraction is not None:
            weeks = f"przez {part.work_weeks} tyg." if part.work_weeks else "przez całą część"
            work = f", praca na {part.work_fraction} etatu {weeks}"
        who = "mama" if part.parent == "mother" else "tata"
        items.append(f"{number}) {who}: {part.weeks} tyg., {when}{work}")
    return (
        "Zapisany plan urlopu rodzicielskiego (przy zmianie podaj w `set_parental_plan` cały plan "
        f"od nowa): {'; '.join(items)}. Daty i wydłużenie są na osi."
    )


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
    if scenario.taken_in is not None:
        # Guide section D: a child taken in for upbringing has its own questions.
        from app.assistant.describe_adoption import taken_in_questions

        return taken_in_questions(scenario)
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
    # After losing the job in pregnancy (ustawa art. 30) no leave before the birth can start.
    if insured and not leave_before_cut(scenario):
        questions += _leave_before_birth_questions(scenario)

    # Never after the loss of every child: nothing to plan there, and the questions would hurt.
    if scenario.losses and len(scenario.losses) >= (scenario.children_count or 1):
        return questions
    if insured:
        questions += _hospital_questions(scenario)
    # The father's rights do not depend on the mother's insurance.
    questions += _father_questions(scenario)
    questions += _pregnancy_questions(scenario)
    # Applications and protection (guide A.4, I): who pays decides where the request goes.
    questions += _payer_questions(scenario)
    # Section G, last: the amounts.
    return questions + _money_questions(scenario)


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


def _payer_questions(scenario: Scenario) -> list[Question]:
    """Whether the employer (or the principal of a contract of mandate) reports more than 20
    people to sickness insurance: it then pays the benefit itself, otherwise ZUS does (guide
    page 1, footnote 1). Never for a business: ZAM goes straight to ZUS. For the father only
    once his leave can be on the timeline (the number of children is known)."""
    asked = [
        (
            "mother",
            scenario.mother_payer_size,
            scenario.mothers_work,
            # After losing the job in pregnancy ZUS pays (ustawa art. 61 ust. 1).
            coverage(scenario) not in NOT_INSURED and after_job_loss(scenario) is None,
        ),
        (
            "father",
            scenario.father_payer_size,
            scenario.fathers_work,
            father_coverage(scenario) not in NOT_INSURED and scenario.children_count is not None,
        ),
    ]
    questions = []
    for parent, size, work, relevant in asked:
        if size is not None or work not in ("employment", "contract") or not relevant:
            continue
        own = scenario.role == parent
        whose = "mamy" if parent == "mother" else "taty"
        if work == "employment":
            who = "Twój pracodawca" if own else f"pracodawca {whose}"
        else:
            who = (
                "płatnik składek z Twojej umowy zlecenia (zleceniodawca)"
                if own
                else f"płatnik składek z umowy zlecenia {whose} (zleceniodawca)"
            )
        questions.append(
            Question(
                f"Czy {who} zgłasza do ubezpieczenia chorobowego więcej niż 20 osób? Od tego "
                "zależy, czy zasiłek wypłaci on, czy ZUS. Możesz też odpowiedzieć, że nie wiesz.",
                f'`set_payer_size` (parent: "{parent}")',
                f"{parent}-payer",
            )
        )
    return questions


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


PAID_WORK = ("employment", "contract", "business")


def _money_questions(scenario: Scenario) -> list[Question]:
    """Guide section G: the monthly amount the mother's benefit base comes from, her choice of
    81,5%, then the father's amount. Asked only once the periods are drawn (the number of
    children is known) and only for a parent who has paid periods (the mother's sick leave in
    pregnancy too, also when her work ended before the birth). The onboarding's range of
    earnings is never enough: the amount is asked exactly."""
    if scenario.children_count is None:
        return []
    questions = []
    mother = coverage(scenario) not in NOT_INSURED and scenario.mothers_work in PAID_WORK
    if pay_matters(scenario, "mother") and not _pay_given(scenario, "mother"):
        questions.append(_pay_question(scenario, "mother"))
    event = scenario.mother_event
    left = event is not None and event.kind in ("death", "abandonment")
    if mother and _pay_given(scenario, "mother") and scenario.rate_815 is None and not left:
        questions.append(_rate_question(scenario))
    if pay_matters(scenario, "father") and not _pay_given(scenario, "father"):
        questions.append(_pay_question(scenario, "father"))
    return questions


def _pay_given(scenario: Scenario, parent: Literal["mother", "father"]) -> bool:
    """The amount was answered (or declined), or months of pay (or the pay in the contract,
    for the first month of insurance) were given instead."""
    pay = scenario.mother_pay if parent == "mother" else scenario.father_pay
    history = scenario.mother_pay_history if parent == "mother" else scenario.father_pay_history
    detail = history is not None and (bool(history.months) or history.contract_pay is not None)
    return pay is not None or detail


def _pay_question(scenario: Scenario, parent: Literal["mother", "father"]) -> Question:
    work = scenario.mothers_work if parent == "mother" else scenario.fathers_work
    own = scenario.role == parent
    who, of = ("mama", "mamy") if parent == "mother" else ("tata", "taty")
    average = " Jeśli się zmieniała, podaj średnią z ostatnich 12 miesięcy."
    match work:
        case "employment":
            text = (
                "Ile wynosi Twoje miesięczne wynagrodzenie brutto?"
                if own
                else f"Ile wynosi miesięczne wynagrodzenie brutto {of}?"
            ) + " Jeśli w ostatnich 12 miesiącach się zmieniało, podaj średnią z tych miesięcy."
        case "contract":
            text = (
                "Jaka jest Twoja miesięczna podstawa składki na ubezpieczenie chorobowe z umowy "
                "zlecenia?"
                if own
                else f"Jaka jest miesięczna podstawa składki na ubezpieczenie chorobowe {of} "
                "z umowy zlecenia?"
            ) + average
        case _:
            text = (
                "Jaką miesięczną podstawę składki na ubezpieczenie chorobowe deklarujesz w swojej "
                "firmie?"
                if own
                else f"Jaką miesięczną podstawę składki na ubezpieczenie chorobowe deklaruje {who} "
                "w swojej firmie?"
            ) + average
    return Question(text, f'`set_monthly_pay` (parent: "{parent}")', f"{parent}-pay")


def _rate_question(scenario: Scenario) -> Question:
    born = scenario.child_born is True
    if scenario.role == "mother":
        text = (
            "Czy złożyłaś albo złożysz (najpóźniej 21 dni po porodzie)"
            if born
            else "Czy po porodzie złożysz (najpóźniej 21 dni po nim)"
        ) + (
            " wniosek o zasiłek 81,5% za cały urlop macierzyński i rodzicielski, czy wolisz "
            "100% za macierzyński i 70% za rodzicielski?"
        )
    else:
        text = (
            "Czy mama złożyła albo złoży (najpóźniej 21 dni po porodzie)"
            if born
            else "Czy mama po porodzie złoży (najpóźniej 21 dni po nim)"
        ) + (
            " wniosek o zasiłek 81,5% za cały urlop macierzyński i rodzicielski, czy woli 100% "
            "za macierzyński i 70% za rodzicielski?"
        )
    return Question(text, "`set_rate_choice`", "rate-815")


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
        f"Następne pytanie wywiadu (aplikacja dopisze je sama pod Twoją odpowiedzią; nie zadawaj "
        f"go ani innego pytania wywiadu): „{first.text}” Gdy użytkownik odpowie, najpierw zapisz "
        f"odpowiedź narzędziem {first.tool}, potem pisz.{later}{several}"
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
    if timeline.taken_in is not None:
        birth = f"Dzień przyjęcia dziecka na wychowanie: {fmt(timeline.birth_date)}."
        count = (
            f" Dzieci przyjęte jednocześnie: {timeline.children_count}."
            if timeline.children_count
            else ""
        )
    lines = [f"{birth}{count} Dziś: {fmt(timeline.today)}.", "", "Na osi (id w nawiasach):"]
    for kind in (Segment, Marker, Payment, Document):
        lines += [
            element_line(e, timeline.today) for e in timeline.elements() if isinstance(e, kind)
        ]
    if timeline.notes:
        lines += ["", "Wyjaśnienie sytuacji (z kalkulatora, z tego mów):"]
        for n in timeline.notes:
            labels = list(dict.fromkeys(source_label(s) for s in n.sources))
            backed = f" (źródła: {'; '.join(labels)})" if labels else ""
            lines.append(f"- {NOTE_KINDS[n.kind]} — {n.title}. {n.text}{backed}")
    if timeline.warnings:
        lines += ["", "Ostrzeżenia:", *(f"- {w}" for w in timeline.warnings)]
    lines += _no_return_and_left_on_table(timeline)  # F9, F10 (engine/leftover.py)
    if changed:
        lines += ["", f"Zmienione przez tę operację: {', '.join(changed)}"]
    return "\n".join(lines)


def element_line(element: TimelineElement, today: dt.date) -> str:
    """One element of the timeline as the model reads it, with its id in brackets."""
    match element:
        case Segment():
            period = f"{fmt(element.start)}–{fmt(element.end)}"
            return f"- [{element.id}] {element.title}: {period} ({element.days} dni)"
        case Marker():
            return f"- [{element.id}] {fmt(element.date)}: {element.title}"
        case Payment():
            period = f"{fmt(element.start)}–{fmt(element.end)}"
            return f"- [{element.id}] {element.title}: {period}. {element.summary}"
        case Document():
            return f"- [{element.id}] {element.title}: {document_when(element, today)}"


def describe_timeline_changes(old: Timeline | None, new: Timeline, changed: list[str]) -> str:
    """What a tool changed on the timeline (ZADANIA B.17). The whole timeline is in the current
    state of the instructions, rebuilt before every request, so a tool result does not repeat
    it: every repetition stayed in the history and was sent again on every later turn."""
    if old is None:
        return (
            "Oś czasu właśnie powstała. Całą oś i wyjaśnienie sytuacji masz w „Aktualnym stanie "
            "osi czasu” w instrukcjach."
        )
    lines = [
        "Oś przeliczona. Cała aktualna oś i wyjaśnienie sytuacji są w „Aktualnym stanie osi "
        "czasu” w instrukcjach; daty bierz stamtąd albo stąd."
    ]
    shown = [element_line(e, new.today) for e in new.elements() if e.id in changed]
    lines += ["Zmienione albo nowe na osi:", *shown] if shown else ["Na osi nic się nie zmieniło."]
    now = {e.id for e in new.elements()}
    gone = [f"[{e.id}]" for e in old.elements() if e.id not in now]
    if gone:
        lines.append(f"Zniknęły z osi: {', '.join(gone)}.")
    return "\n".join(lines)


def _no_return_and_left_on_table(timeline: Timeline) -> list[str]:
    """F10: the days after which a right is lost; F9: what the family can still use (from the
    calculator, with the amounts it computed)."""
    lines: list[str] = []
    marked = [(m, m.irreversible) for m in timeline.markers if m.irreversible is not None]
    if marked:
        lines += ["", "Punkty bez powrotu (z kalkulatora):"]
        lines += [f"- [{m.id}] {fmt(m.date)}: {point.lost}" for m, point in marked]
    if timeline.left_on_table:
        lines += ["", "Zostawiacie na stole — można jeszcze wykorzystać (z kalkulatora):"]
        for item in timeline.left_on_table:
            amount = f" Kwota: {pln(dec(item.amount))}." if item.amount else ""
            lines.append(f"- [{item.id}] do {fmt(item.last_day)}: {item.text}{amount}")
    return lines


SENSITIVE_NOTES = ("loss", "mother-event")
"""Points about the loss of the child or the mother's situation: always said, in full."""


def opening_notes(notes: list[CaseNote]) -> list[CaseNote]:
    """What the assistant says about a timeline that has just appeared: which case this is,
    the main entitlement (or what stands in its way) and the sensitive points. Everything else
    is above the timeline and in "Dlaczego tak?", so the chat does not retell it."""
    first_right = next((n for n in notes if n.kind in ("right", "risk")), None)
    return [
        n
        for n in notes
        if n.kind in ("situation", "risk") or n is first_right or n.id in SENSITIVE_NOTES
    ]


def describe_note_changes(timeline: Timeline, changed_notes: list[str] | None) -> str:
    """What to talk about after a recalculation. None = the timeline has just appeared."""
    if changed_notes is None:
        titles = [f"„{n.title}”" for n in opening_notes(timeline.notes)]
        return (
            f"Oś czasu właśnie powstała. Z wyjaśnienia sytuacji powiedz tylko: "
            f"{', '.join(titles)}, w najwyżej trzech krótkich zdaniach. Pozostałe punkty "
            "użytkownik ma nad osią i w „Dlaczego tak?”."
        )
    titles = [f"„{n.title}”" for n in timeline.notes if n.id in changed_notes]
    if not titles:
        return (
            "Wyjaśnienie sytuacji się nie zmieniło: powiedz jednym zdaniem, co zmieniło się na osi."
        )
    return (
        f"Zmienione punkty wyjaśnienia (użytkownik widzi je podświetlone nad osią): "
        f"{', '.join(titles)}. Powiedz tylko, co z tej zmiany wynika dla rodzica — najpierw nowe "
        "daty albo to, co trzeba zrobić — w najwyżej trzech krótkich zdaniach. Pozostałych "
        "punktów nie powtarzaj."
    )


def describe_form(form: RequestForm) -> list[str]:
    """What a request contains and what goes with it (engine/forms.py), for the model: the
    fields the app filled in, the ones the person types in, the attachments."""
    lines = ["", f"Wniosek jako formularz ({form.addressee_label}):"]
    if form.official_form:
        lines.append(f"- formularz ZUS: {form.official_form}, na www.zus.pl")
    for field in form.fields:
        if field.personal:
            value = "wpisuje sam rodzic (dane osobowe; nie pytaj o nie)"
        else:
            value = field.value or "do uzupełnienia przez rodzica"
        lines.append(f"- pole „{field.label}”: {value}")
    lines += [
        f"- załącznik: {a.label}" + (f" ({a.hint})" if a.hint else "") for a in form.attachments
    ]
    lines += [f"- {note.text}" for note in form.notes]
    return lines


def describe_element(element: TimelineElement, today: dt.date | None = None) -> str:
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
            if element.irreversible is not None:  # F10 (engine/leftover.py)
                lines.append(f"Punkt bez powrotu: {element.irreversible.lost}")
        case Document():
            when = document_when(element, today or element.needed_by)
            lines = [f"{element.title}: {when}.", element.rule]
            if element.form is not None:
                lines += describe_form(element.form)
        case Payment():
            period = f"{fmt(element.start)}–{fmt(element.end)}"
            lines = [
                f"{element.title}: {period}, {element.days} dni.",
                element.summary,
                *element.details,
            ]
    sources = list(element.sources)
    if isinstance(element, Document) and element.form is not None:
        quoted = {(s.doc, s.quote) for s in sources}
        sources += [s for s in element.form.legal_basis if (s.doc, s.quote) not in quoted]
    lines += ["", "Źródła (cytuj dosłownie):"]
    lines += [f"- {source_label(s)}: „{s.quote}”" for s in sources]
    return "\n".join(lines)
