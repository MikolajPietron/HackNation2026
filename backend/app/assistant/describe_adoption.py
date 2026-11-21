"""The interview for a child taken in for upbringing (guide section D): what is still unknown,
in order. Nothing about pregnancy, the birth or a hospital stay is asked on this path."""

from app.assistant.describe import Question, _pay_question
from app.engine.adoption import birthday, cover_of, other, taken_in_leave, taker
from app.engine.insurance import NOT_INSURED
from app.engine.models import Role, Scenario
from app.engine.money import pay_matters
from app.engine.params import Params
from app.services.params import load_params

KIND = {"adoption": "adopcja", "foster": "rodzina zastępcza niezawodowa"}


def taken_in_questions(scenario: Scenario, params: Params | None = None) -> list[Question]:
    """`params`: the base file when not given (only the age limits and lengths are read, to
    know whether postponed schooling matters)."""
    params = params or load_params()
    adoption = scenario.taken_in == "adoption"
    several = (scenario.children_count or 1) > 1
    role = taker(scenario)
    questions = []
    if scenario.taken_in_on is None:
        questions.append(
            Question(
                "Kiedy przyjęliście dziecko na wychowanie i złożyliście w sądzie wniosek "
                "o przysposobienie? Jeśli to były różne dni, podaj późniejszy."
                if adoption
                else "Kiedy przyjęliście dziecko na wychowanie jako rodzina zastępcza? Podaj "
                "dzień, miesiąc i rok.",
                "`set_taken_in` (taken_in_on)",
                "taken-in",
            )
        )
    if scenario.birth_date is None:
        questions.append(
            Question(
                "Kiedy urodziło się najmłodsze z dzieci? Od wieku dziecka zależy długość urlopu."
                if several
                else "Kiedy urodziło się dziecko? Od jego wieku zależy długość urlopu.",
                "`set_taken_in` (child_birth_date)",
                "child-birth",
            )
        )
    if scenario.children_count is None:
        questions.append(
            Question(
                "Ile dzieci przyjęliście na wychowanie jednocześnie?",
                "`set_children_count`",
                "children",
            )
        )
    questions += _work_questions(scenario, role)
    insured = cover_of(scenario, role) not in NOT_INSURED
    if insured and _school_matters(scenario, params):
        questions.append(
            Question(
                "Czy wobec dziecka podjęto decyzję o odroczeniu obowiązku szkolnego?",
                "`set_school_postponed`",
                "school-postponed",
            )
        )
    # The other parent: their 9 weeks of parental leave and, after adoption, paternity leave.
    if insured or adoption:
        questions += _work_questions(scenario, other(role))
    father = cover_of(scenario, "father") not in NOT_INSURED
    if adoption and father and scenario.adoption_final is None:
        questions.append(
            Question(
                "Czy postanowienie sądu o przysposobieniu dziecka jest już prawomocne? Jeśli tak, "
                "podaj dzień, w którym się uprawomocniło.",
                "`set_adoption_ruling`",
                "adoption-ruling",
            )
        )
    # Section G, last: the amounts and the choice of 81,5% (ustawa art. 30a ust. 2, art. 31).
    if insured or adoption:
        questions += _money_questions(scenario, params, role, insured)
    return questions


def _money_questions(
    scenario: Scenario, params: Params, role: Role, insured: bool
) -> list[Question]:
    """The monthly amount of the person who took the child in, their choice of rate, then the
    other parent's amount; once the leave can be drawn."""
    if scenario.children_count is None or scenario.taken_in_on is None:
        return []
    questions = []
    mine = scenario.mother_pay if role == "mother" else scenario.father_pay
    if pay_matters(scenario, role) and mine is None:
        questions.append(_pay_question(scenario, role))
    leave = taken_in_leave(scenario, params)
    has_leave = insured and leave is not None and not leave.too_old
    if has_leave and mine is not None and scenario.rate_815 is None:
        days = params.money.request_days_taken_in.value
        verb, choose = {
            "mother": ("Czy złożyłaś albo złożysz", "wolisz"),
            "father": ("Czy złożyłeś albo złożysz", "wolisz"),
            None: ("Czy osoba, która przyjęła dziecko, złożyła albo złoży", "woli"),
        }[scenario.role]
        questions.append(
            Question(
                f"{verb} (najpóźniej {days} dni po przyjęciu dziecka na wychowanie) wniosek "
                "o zasiłek 81,5% za cały urlop na warunkach urlopu macierzyńskiego i urlop "
                f"rodzicielski, czy {choose} 100% za urlop na warunkach urlopu macierzyńskiego "
                "i 70% za rodzicielski?",
                "`set_rate_choice`",
                "rate-815",
            )
        )
    theirs = other(role)
    pay = scenario.mother_pay if theirs == "mother" else scenario.father_pay
    if pay_matters(scenario, theirs) and pay is None:
        questions.append(_pay_question(scenario, theirs))
    return questions


def _school_matters(scenario: Scenario, params: Params) -> bool:
    """Foster family: the age limit of 7 would end the leave early, and with postponed schooling
    it would be 10."""
    if scenario.taken_in != "foster" or scenario.school_postponed is not None:
        return False
    leave = taken_in_leave(scenario.model_copy(update={"school_postponed": False}), params)
    birth = scenario.birth_date
    if leave is None or birth is None:
        return False
    later = params.taken_in.foster.age_school_postponed
    if later is None or leave.start >= birthday(birth, later.value):
        return False
    return leave.too_old or leave.cut


def _work_questions(scenario: Scenario, role: Role) -> list[Question]:
    """How a parent works and, on a contract or with a business, their voluntary insurance."""
    mother = role == "mother"
    yourself = scenario.role == role
    match cover_of(scenario, role):
        case "unknown-work":
            return [
                Question(
                    f"Jak pracuje {'mama' if mother else 'tata'}: na etacie (umowa o pracę), na "
                    "umowie zlecenia, prowadzi własną firmę czy nie pracuje?",
                    "`set_mother_work`" if mother else "`set_father_work`",
                    "mother-work" if mother else "father-work",
                )
            ]
        case "unknown-voluntary":
            if yourself:
                text = (
                    "Czy jesteś zgłoszona do dobrowolnego ubezpieczenia chorobowego (opłacasz "
                    "składkę chorobową)?"
                    if mother
                    else "Czy jesteś zgłoszony do dobrowolnego ubezpieczenia chorobowego "
                    "(opłacasz składkę chorobową)?"
                )
            else:
                text = (
                    "Czy mama jest zgłoszona do dobrowolnego ubezpieczenia chorobowego (opłaca "
                    "składkę chorobową)?"
                    if mother
                    else "Czy tata jest zgłoszony do dobrowolnego ubezpieczenia chorobowego "
                    "(opłaca składkę chorobową)?"
                )
            return [
                Question(
                    text,
                    "`set_voluntary_insurance`" if mother else "`set_father_insurance`",
                    "mother-insurance" if mother else "father-insurance",
                )
            ]
        case _:
            return []


def describe_taken_in(scenario: Scenario) -> str:
    """For the model: this family took a child in; who takes the leave."""
    kind = KIND[scenario.taken_in or "foster"]
    who = "mamy" if taker(scenario) == "mother" else "taty"
    return (
        f"Dziecko zostało przyjęte na wychowanie ({kind}), a nie urodzone w tej rodzinie. Nie "
        "mów o ciąży, porodzie, urlopie przed porodem ani o 14 tygodniach po porodzie. Urlop na "
        f"warunkach urlopu macierzyńskiego jest na osi {who}, czyli osoby, która pisze."
    )
