"""From the facts of a case to the calculator's answers, deterministically: the `Scenario`, the
sickness insurance on the day the right arises, the timeline (with amounts when the case has
pay data) and the comparison with the decision of ZUS. No AI here."""

import datetime as dt
from decimal import ROUND_HALF_UP, Decimal

from app.engine import Params, Scenario, ScenarioError, build_timeline
from app.engine.models import BirthWeek, ChildLoss, HospitalStay, ParentalPart, Role, Work
from app.engine.wording import long_date

from .models import CaseFacts, CaseResult, Comparison, InsuranceCheck, InsurancePeriod

WHO: dict[Role, str] = {"mother": "mama", "father": "tata"}
LEAVE_WORDS = {
    "maternity": "urlopu macierzyńskiego",
    "parental": "urlopu rodzicielskiego",
    "paternity": "urlopu ojcowskiego",
    "supplementary": "urlopu uzupełniającego",
    "sick": "zwolnienia lekarskiego",
    "other": "świadczenia",
}
SICKNESS_WORDS = {
    "mandatory": "obowiązkowe chorobowe",
    "voluntary": "dobrowolne chorobowe",
    "none": "bez chorobowego",
    "unknown": "chorobowe nieznane",
}
OUTCOME_WORDS = {
    "granted": "prawo do świadczenia",
    "refused": "brak prawa do świadczenia",
    "partial": "prawo częściowo",
    "unknown": "nie wiadomo",
}
ZUS_WORDS = {
    "granted": "ZUS przyznał świadczenie",
    "refused": "ZUS odmówił",
    "partial": "ZUS przyznał częściowo",
    "unknown": "w sprawie nie ma rozstrzygnięcia ZUS",
}
# Pay of at most this many recent months makes the monthly amount (Załącznik: 12 months).
PAY_MONTHS = 12


def _covers(period: InsurancePeriod, day: dt.date) -> bool:
    return (period.start is None or period.start <= day) and (
        period.end is None or day <= period.end
    )


def anchor_day(facts: CaseFacts) -> dt.date | None:
    """The day the timeline counts from: the child taken in, born, or expected."""
    if facts.taken_in is not None:
        return facts.taken_in_on
    if facts.birth_date is not None and facts.child_born is not False:
        return facts.birth_date
    return facts.due_date


def right_day(facts: CaseFacts, person: Role) -> tuple[dt.date | None, str]:
    """The day the right arises for the applicant: the first day of the leave or benefit they
    asked for, else the birth (or taking in). With the words that say which day it is."""
    leaves = [leave for leave in facts.leaves if leave.person == person]
    # Sick leave earlier in pregnancy is not the benefit asked for, unless it is the only one.
    asked = [leave for leave in leaves if leave.kind != "sick"] or leaves
    if asked:
        first = min(asked, key=lambda x: x.start)
        return first.start, f"pierwszy dzień {LEAVE_WORDS[first.kind]}"
    day = anchor_day(facts)
    what = "dzień przyjęcia dziecka" if facts.taken_in else "dzień porodu"
    return day, what


def work_of(facts: CaseFacts, person: Role, day: dt.date | None) -> Work | None:
    periods = [p for p in facts.insurance if p.person == person]
    if not periods:
        return None
    on_day = [p for p in periods if day is not None and _covers(p, day)]
    chosen = (on_day or periods)[0]
    return None if chosen.title == "other" else chosen.title


def insured_voluntarily(facts: CaseFacts, person: Role, day: dt.date | None) -> bool | None:
    """Voluntary sickness insurance on a contract or with a business, on the day."""
    if day is None:
        return None
    periods = [p for p in facts.insurance if p.person == person and _covers(p, day)]
    if any(p.sickness in ("voluntary", "mandatory") for p in periods):
        return True
    if periods and all(p.sickness == "none" for p in periods):
        return False
    return None


def monthly_pay(facts: CaseFacts, person: Role) -> tuple[float | None, int]:
    """The average of the most recent months of pay (at most 12), as the parent would give it."""
    months = sorted((m for m in facts.pay if m.person == person), key=lambda m: m.month)[
        -PAY_MONTHS:
    ]
    if not months:
        return None, 0
    total = sum(Decimal(str(m.amount)) for m in months)
    average = (total / len(months)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return float(average), len(months)


def to_scenario(facts: CaseFacts) -> tuple[Scenario, list[str]]:
    notes: list[str] = []
    person: Role = facts.applicant or "mother"
    other: Role = "father" if person == "mother" else "mother"
    day, _ = right_day(facts, person)
    birth = anchor_day(facts)
    taken_in = facts.taken_in is not None
    born = (
        taken_in
        or facts.child_born is True
        or (facts.child_born is None and facts.birth_date is not None)
    )

    scenario = Scenario(
        role=person,
        work=work_of(facts, person, day),
        child_born=born,
        birth_date=facts.birth_date if born else None,
        due_date=None if born else facts.due_date,
        children_count=facts.children_count or 1,
        taken_in=facts.taken_in,
        taken_in_on=facts.taken_in_on,
        za_zyciem=facts.za_zyciem,
        hospital_care=facts.hospital_after_birth if born and not taken_in else None,
    )
    if facts.children_count is None:
        notes.append("Liczba dzieci nie wynika ze sprawy: liczymy jedno dziecko.")
    other_work = work_of(facts, other, birth)
    if other_work is not None:
        if other == "mother":
            scenario.mother_work = other_work
        else:
            scenario.father_work = other_work
    mothers_work = scenario.mothers_work
    fathers_work = scenario.fathers_work
    if mothers_work in ("contract", "business"):
        scenario.mother_insured = insured_voluntarily(
            facts, "mother", day if person == "mother" else birth
        )
    if fathers_work in ("contract", "business"):
        scenario.father_insured = insured_voluntarily(
            facts, "father", day if person == "father" else birth
        )
    if facts.payer_over_20 is not None:
        size = "over-20" if facts.payer_over_20 else "up-to-20"
        if person == "mother":
            scenario.mother_payer_size = size
        else:
            scenario.father_payer_size = size
    if facts.stillborn:
        scenario.losses = [ChildLoss(stillborn=True)]
    # A premature child or a child in hospital: what the supplementary leave depends on.
    if born and not taken_in:
        if facts.birth_week is not None:
            week: BirthWeek = (
                "before-28"
                if facts.birth_week < 28
                else "28-37"
                if facts.birth_week < 37
                else "after-37"
            )
            scenario.birth_week = week
        if facts.birth_weight_grams is not None:
            scenario.birth_weight_up_to_1000g = facts.birth_weight_grams <= 1000
        if facts.hospital_stays:
            scenario.hospital_care = True
            scenario.hospital_stays = [
                HospitalStay(start=s.start, end=s.end) for s in facts.hospital_stays
            ]
    # Sick leave in pregnancy (guide: sickness benefit): the first one of the mother.
    sick = sorted(
        (x for x in facts.leaves if x.person == "mother" and x.kind == "sick"),
        key=lambda x: x.start,
    )
    if sick and not taken_in:
        scenario.sick_leave = True
        scenario.sick_leave_start = sick[0].start
        scenario.sick_leave_end = sick[-1].end

    # Maternity leave before the birth: from the leave the mother took.
    if born and not taken_in and facts.birth_date is not None:
        maternity = sorted(
            (x for x in facts.leaves if x.person == "mother" and x.kind == "maternity"),
            key=lambda x: x.start,
        )
        if maternity and maternity[0].start < facts.birth_date:
            scenario.leave_start = maternity[0].start
        elif maternity:
            scenario.leave_before_birth_weeks = 0

    scenario.parental_parts = parental_plan(facts)

    for parent in ("mother", "father"):
        amount, months = monthly_pay(facts, parent)
        if amount is None:
            continue
        kind = (
            "przychodu z Z-3"
            if any(m.kind == "salary" for m in facts.pay if m.person == parent)
            else "podstawy składek"
        )
        if parent == "mother":
            scenario.mother_pay = amount
        else:
            scenario.father_pay = amount
        notes.append(
            f"Kwotę liczymy od średniej {kind} z {months} mies. ({WHO[parent]}): {amount:.2f} zł. "
            "Uproszczenie: bez korekt za miesiące niepełne i premie (pełna podstawa wymiaru "
            "w przygotowaniu)."
        )
    if not facts.pay:
        notes.append("W sprawie nie odczytano wynagrodzeń: kalkulator nie liczy kwoty.")
    return scenario, notes


def parental_plan(facts: CaseFacts) -> list[ParentalPart]:
    """The parental leave the case asks for, as parts of whole weeks in date order (a period
    listed in two documents counts once). The engine checks the plan against the rules."""
    seen: set[tuple[str, dt.date, dt.date]] = set()
    parts: list[ParentalPart] = []
    for leave in sorted(facts.leaves, key=lambda x: x.start):
        if leave.kind != "parental" or leave.end is None:
            continue
        key = (leave.person, leave.start, leave.end)
        days = (leave.end - leave.start).days + 1
        if key in seen or days <= 0 or days % 7:
            continue
        seen.add(key)
        parts.append(ParentalPart(parent=leave.person, weeks=days // 7, start=leave.start))
    return parts


def check_insurance(facts: CaseFacts) -> InsuranceCheck:
    person: Role = facts.applicant or "mother"
    day, what = right_day(facts, person)
    who = WHO[person].capitalize()
    periods = [p for p in facts.insurance if p.person == person]
    if day is None:
        return InsuranceCheck(
            person=person,
            on=None,
            covered=None,
            period=None,
            text="W sprawie nie ma daty, od której liczy się prawo do świadczenia.",
        )
    when = f"{long_date(day)} ({what})"
    if not periods:
        return InsuranceCheck(
            person=person,
            on=day,
            covered=None,
            period=None,
            text=f"W sprawie nie odczytano okresów ubezpieczenia. Liczy się dzień {when}.",
        )
    covering = [p for p in periods if _covers(p, day)]
    sick = [p for p in covering if p.sickness in ("mandatory", "voluntary")]
    if sick:
        period = sick[0]
        span = f"od {long_date(period.start)}" if period.start else ""
        span += f" do {long_date(period.end)}" if period.end else ""
        return InsuranceCheck(
            person=person,
            on=day,
            covered=True,
            period=period,
            text=f"{who} podlega ubezpieczeniu chorobowemu w dniu {when}: {period.label}, "
            f"{SICKNESS_WORDS[period.sickness]} {span}.".replace("  ", " ").replace(" .", "."),
        )
    if covering and all(p.sickness == "unknown" for p in covering):
        period = covering[0]
        return InsuranceCheck(
            person=person,
            on=day,
            covered=None,
            period=period,
            text=f"{who} ma w dniu {when} tytuł ubezpieczenia ({period.label}), ale dokumenty "
            "nie mówią, czy obejmuje ubezpieczenie chorobowe.",
        )
    ended = sorted(
        (p for p in periods if p.end is not None and p.end < day), key=lambda p: p.end or day
    )
    if covering:
        detail = f"{covering[0].label} bez ubezpieczenia chorobowego"
        period = covering[0]
    elif ended:
        period = ended[-1]
        detail = f"ostatni okres ({period.label}) skończył się {long_date(period.end)}"
    else:
        period = None
        detail = "żaden odczytany okres nie obejmuje tego dnia"
    return InsuranceCheck(
        person=person,
        on=day,
        covered=False,
        period=period,
        text=f"W dniu {when} {WHO[person]} nie podlega ubezpieczeniu chorobowemu: {detail}.",
    )


def compare(facts: CaseFacts, insurance: InsuranceCheck) -> Comparison:
    ours = (
        "granted" if insurance.covered else "refused" if insurance.covered is False else "unknown"
    )
    zus = facts.decision.outcome if facts.decision else "unknown"
    if ours == "unknown" or zus == "unknown":
        match = None
    else:
        match = ours == zus or (zus == "partial" and ours == "granted")
    text = f"Kalkulator: {OUTCOME_WORDS[ours]}. {ZUS_WORDS[zus]}."
    if facts.decision and facts.decision.reason:
        text += f" Uzasadnienie ZUS: {facts.decision.reason}"
    if match is False and zus == "refused" and ours == "granted":
        text += (
            " Kalkulator sprawdza ubezpieczenie chorobowe w dniu powstania prawa; ZUS odmówił "
            "z innego powodu."
        )
    return Comparison(ours=ours, zus=zus, match=match, text=text)


def assess(
    facts: CaseFacts,
    *,
    case_id: str | None,
    pages: int,
    pages_read: int,
    cached: bool,
    params: Params,
    today: dt.date,
) -> CaseResult:
    scenario, notes = to_scenario(facts)
    insurance = check_insurance(facts)
    timeline = None
    problem = None
    if scenario.anchor_date is None:
        problem = (
            "To sprawa o zasiłek chorobowy w ciąży bez przewidywanej daty porodu: ubezpieczenie "
            "sprawdzamy na pierwszy dzień zwolnienia, a oś urlopów pojawi się z datą porodu."
            if scenario.sick_leave
            else "AI nie odczytało pewnie daty porodu ani przyjęcia dziecka, więc nie ma osi. "
            "Wpisz datę w „Dane ze sprawy” i przelicz."
        )
    else:
        try:
            timeline = build_timeline(scenario, params, today)
        except ScenarioError as error:
            if scenario.parental_parts:
                # The plan in the case does not fit the rules: show parental leave as a choice.
                notes.append(f"Plan urlopu rodzicielskiego ze sprawy pominięty: {error}")
                scenario.parental_parts = []
                try:
                    timeline = build_timeline(scenario, params, today)
                except ScenarioError as again:
                    problem = str(again)
            else:
                problem = str(error)
    notes.extend(f"Niepewne: {item}" for item in facts.unreadable)
    return CaseResult(
        id=case_id,
        pages=pages,
        pages_read=pages_read,
        cached=cached,
        facts=facts,
        scenario=scenario,
        timeline=timeline,
        insurance=insurance,
        comparison=compare(facts, insurance),
        notes=notes,
        problem=problem,
    )
