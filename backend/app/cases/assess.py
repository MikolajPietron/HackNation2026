"""From the facts of a case to the calculator's answers, deterministically: the `Scenario`, the
sickness insurance on the day the right arises, the timeline (with amounts when the case has
pay data) and the comparison with the decision of ZUS. No AI here.

What the facts become in the scenario:
- the pay of the payer's certificate (Z-3, Z-3a) month by month, with the days of a month not
  worked in full, the bonuses, full-time work, the start of insurance and the pay in the
  contract: `PayHistory`, from which engine/base.py computes the benefit base step by step;
- the mother's employment that ended in pregnancy: `JobLoss` (after_insurance.py); when the
  case says nothing of it but every insurance period of the mother ended before the birth, a
  plain end of work before the birth (reason "other");
- a finding of ZUS that a period gives no insurance: no sickness insurance in that period, and
  for a sham contract or business of the mother the risk of section H.1 (`insured_in_pregnancy`);
- a child taken in: the right arises on the day of taking in, the insurance is checked then;
- contribution debt of a business on the day the right arises (debt.py);
- the parts of parental leave (at most as many as the rules allow) and the father taking over
  maternity leave or a special situation of the mother (father.py).
"""

import datetime as dt
import re
from dataclasses import dataclass
from decimal import Decimal
from typing import Literal

from pydantic import ValidationError

from app.engine import Params, Scenario, ScenarioError, build_timeline
from app.engine.after_insurance import REASON as JOB_LOSS_REASON
from app.engine.amounts import dec, pln
from app.engine.debt import debt_limit, expiry, over_limit
from app.engine.draft import WEEK
from app.engine.models import (
    BirthWeek,
    ChildLoss,
    HospitalStay,
    JobLoss,
    MotherEvent,
    ParentalPart,
    PayHistory,
    Role,
    Work,
)
from app.engine.models import PayMonth as EnginePayMonth
from app.engine.wording import long_date
from app.services.params import load_params

from .models import (
    CaseFacts,
    CaseResult,
    Comparison,
    DifferenceReason,
    InsuranceCheck,
    InsurancePeriod,
    Outcome,
    SicknessInsurance,
)

WHO: dict[Role, str] = {"mother": "mama", "father": "tata"}
WHOSE: dict[Role, str] = {"mother": "mamy", "father": "taty"}
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
PAID_WORK: tuple[Work, ...] = ("employment", "contract", "business")
# A month as the reader may write it: "2025-03", "2025.3", "03/2025".
YEAR_FIRST = re.compile(r"^\s*(\d{4})\D+(\d{1,2})\s*$")
MONTH_FIRST = re.compile(r"^\s*(\d{1,2})\D+(\d{4})\s*$")
# Words of a refusal for a reason the calculator checks: sickness insurance (a sham contract,
# not subject to insurance, insurance ended, not registered for the voluntary one), debt, or the
# number of parts of parental leave.
CHECKED_REASONS = re.compile(
    r"pozor|niepodleg|nie podleg|ustał|ustani|dobrowoln|niezgłos|nie zgłos|zadłuż|zaległ"
    r"|częściach|szóst",
    re.IGNORECASE,
)


def sickness(period: InsurancePeriod) -> SicknessInsurance:
    """What the period gives, the finding of ZUS first: a period ZUS ruled out gives no
    sickness insurance, whatever the payer declared."""
    return "none" if period.zus_finding is not None else period.sickness


def _insured(period: InsurancePeriod) -> bool:
    return sickness(period) in ("mandatory", "voluntary")


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
    """The day the right arises for the applicant: for a child taken in, the day of taking in
    (paternity leave: its first day); otherwise the first day of the leave or benefit they asked
    for, else the birth. With the words that say which day it is."""
    leaves = [leave for leave in facts.leaves if leave.person == person]
    # Sick leave earlier in pregnancy is not the benefit asked for, unless it is the only one.
    asked = [leave for leave in leaves if leave.kind != "sick"] or leaves
    first = min(asked, key=lambda x: x.start) if asked else None
    paternity = first is not None and first.kind == "paternity"
    if facts.taken_in is not None and facts.taken_in_on is not None and not paternity:
        return facts.taken_in_on, "dzień przyjęcia dziecka"
    if first is not None:
        return first.start, f"pierwszy dzień {LEAVE_WORDS[first.kind]}"
    day = anchor_day(facts)
    what = "dzień przyjęcia dziecka" if facts.taken_in else "dzień porodu"
    return day, what


def work_of(facts: CaseFacts, person: Role, day: dt.date | None) -> Work | None:
    """How the person works on the day: the period that covers it (one with sickness insurance
    first). Employment that ZUS ruled gives no insurance (e.g. a sham contract) counts as no
    work: the engine knows no employment without insurance."""
    periods = [p for p in facts.insurance if p.person == person]
    if not periods:
        return None
    on_day = [p for p in periods if day is not None and _covers(p, day)]
    if on_day:
        chosen = next((p for p in on_day if _insured(p)), on_day[0])
        if chosen.title == "employment" and sickness(chosen) == "none":
            return "none"
    else:
        chosen = periods[0]
    return None if chosen.title == "other" else chosen.title


def ended_before(facts: CaseFacts, person: Role, day: dt.date | None) -> InsurancePeriod | None:
    """The person's last insurance period, when every period read ended before `day`."""
    if day is None:
        return None
    periods = [p for p in facts.insurance if p.person == person]
    if not periods or any(p.end is None or p.end >= day for p in periods):
        return None
    return max(periods, key=lambda p: p.end or day)


def insured_voluntarily(facts: CaseFacts, person: Role, day: dt.date | None) -> bool | None:
    """Voluntary sickness insurance on a contract or with a business, on the day."""
    if day is None:
        return None
    periods = [p for p in facts.insurance if p.person == person and _covers(p, day)]
    if any(_insured(p) for p in periods):
        return True
    if periods and all(sickness(p) == "none" for p in periods):
        return False
    return None


# ---------------------------------------------------------------------------------------------
# The pay: the payer's certificate as engine/base.py takes it.


def _month_key(text: str) -> str | None:
    if match := YEAR_FIRST.match(text):
        year, month = int(match[1]), int(match[2])
    elif match := MONTH_FIRST.match(text):
        month, year = int(match[1]), int(match[2])
    else:
        return None
    return f"{year:04d}-{month:02d}" if 1 <= month <= 12 else None


def _amount(value: float | None) -> float | None:
    return value if value is not None and value >= 0 else None


def pay_history(
    facts: CaseFacts, person: Role, work: Work | None
) -> tuple[PayHistory | None, list[str]]:
    """The person's months of pay (an employee: the pay from Z-3; a contract or business: the
    contribution base), bonuses and the rest of what the base depends on, checked so the engine
    takes them; with notes on what was left out and why. None when there is nothing to compute
    the base from."""
    notes: list[str] = []
    who = WHO[person]
    mine = [m for m in facts.pay if m.person == person]
    wanted = "salary" if work == "employment" else "contribution_base"
    if work in PAID_WORK and any(m.kind == wanted for m in mine):
        other = [m for m in mine if m.kind != wanted]
        if other:
            notes.append(
                f"Pomijamy {len(other)} mies. ({who}) z innego tytułu niż ten, z którego liczy "
                "się zasiłek."
            )
        mine = [m for m in mine if m.kind == wanted]
    months: dict[str, EnginePayMonth] = {}
    for m in mine:
        key = _month_key(m.month)
        if key is None or m.amount < 0:
            notes.append(f"Miesiąc „{m.month}” ({who}) jest nieczytelny: pomijamy go.")
            continue
        required, worked = m.days_required, m.days_worked
        days_fit = (
            required is not None
            and worked is not None
            and required >= 1
            and 0 <= worked <= required
        )
        if not days_fit:
            if required is not None or worked is not None:
                notes.append(
                    f"{key} ({who}): liczba dni ({worked} z {required}) się nie zgadza, więc "
                    "liczymy miesiąc tak, jak go podano."
                )
            required = worked = None
        if required is None and m.full_month is False:
            notes.append(
                f"{key} ({who}): miesiąc niepełny, ale bez liczby dni, więc liczymy go tak, jak go "
                "podano."
            )
        not_topped = _amount(m.not_topped)
        if not_topped is not None and not_topped > m.amount:
            not_topped = None
        try:
            month = EnginePayMonth(
                month=key,
                amount=m.amount,
                days_required=required,
                days_worked=worked,
                fixed=_amount(m.fixed) if required is not None else None,
                variable=_amount(m.variable) if required is not None else None,
                not_topped=not_topped,
            )
        except ValidationError:
            notes.append(f"{key} ({who}): dane miesiąca się nie zgadzają, pomijamy go.")
            continue
        previous = months.get(key)
        if previous is None:
            months[key] = month
        elif previous.amount != month.amount:
            notes.append(
                f"{key} ({who}) ma w sprawie dwie kwoty, {pln(dec(previous.amount))} "
                f"i {pln(dec(month.amount))}: liczymy pierwszą."
            )
        elif previous.days_required is None and month.days_required is not None:
            months[key] = month  # the same month again, with the days: keep the detail
    bonuses = [b for b in facts.bonuses if b.person == person and b.amount > 0]
    quarterly = sum((dec(b.amount) for b in bonuses if b.kind == "quarterly"), Decimal(0))
    annual = sum((dec(b.amount) for b in bonuses if b.kind == "annual"), Decimal(0))
    if bonuses:
        listed = ", ".join(f"{b.period}: {pln(dec(b.amount))}" for b in bonuses)
        notes.append(f"Premie z zaświadczenia płatnika ({who}): {listed}.")
    details = next((d for d in facts.pay_details if d.person == person), None)
    contract = details.contract_pay if details and (details.contract_pay or 0) > 0 else None
    if not months and contract is None:
        return None, notes
    history = PayHistory(
        months=list(months.values()),
        quarterly_bonuses=float(quarterly) if quarterly else None,
        annual_bonus=float(annual) if annual else None,
        full_time=details.full_time if details else None,
        insured_from=details.insured_from if details else None,
        contract_pay=contract,
    )
    return history, notes


# ---------------------------------------------------------------------------------------------
# Facts -> scenario


def to_scenario(facts: CaseFacts, params: Params | None = None) -> tuple[Scenario, list[str]]:
    params = params or load_params()
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
    ended = ended_before(facts, "father", day) if person == "father" else None
    if ended is not None and ended.end is not None:
        scenario.work = "none"
        notes.append(
            f"Ostatni odczytany okres ubezpieczenia taty ({ended.label}) skończył się "
            f"{long_date(ended.end)}, przed dniem powstania prawa: liczymy tatę jako "
            "nieubezpieczonego."
        )
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

    _job_loss(facts, scenario, birth, notes)
    _zus_findings(facts, scenario, notes)
    _father_takes_over(facts, scenario, params, notes)
    parts = parental_plan(facts)
    limit = params.parental.max_parts.value
    if len(parts) > limit:
        extra = parts[limit].start
        since = f" (od {long_date(extra)})" if extra else ""
        notes.append(
            f"W sprawie jest {len(parts)} części urlopu rodzicielskiego. Urlop można podzielić "
            f"najwyżej na {limit} części, więc na osi jest pierwszych {limit}; część "
            f"{limit + 1}.{since} nie przysługuje."
        )
        parts = parts[:limit]
    scenario.parental_parts = parts
    _contribution_debt(facts, scenario, notes)

    for parent in ("mother", "father"):
        work = scenario.mothers_work if parent == "mother" else scenario.fathers_work
        history, found = pay_history(facts, parent, work)
        notes.extend(found)
        if history is None:
            continue
        if parent == "mother":
            scenario.mother_pay_history = history
        else:
            scenario.father_pay_history = history
        kind = (
            "przychodu z zaświadczenia płatnika"
            if work == "employment"
            else "podstawy składek na ubezpieczenie chorobowe"
        )
        n = len(history.months)
        source = f"z {n} mies. {kind}" if n else "z kwoty określonej w umowie"
        notes.append(
            f"Podstawę wymiaru zasiłku ({WHOSE[parent]}) liczymy krok po kroku {source} "
            "odczytanych ze sprawy: miesiące niepełne, premie, 13,71% — kroki są przy kwotach."
        )
    if not facts.pay:
        notes.append("W sprawie nie odczytano wynagrodzeń: kalkulator nie liczy kwoty.")
    return scenario, notes


def _job_loss(
    facts: CaseFacts, scenario: Scenario, birth: dt.date | None, notes: list[str]
) -> None:
    """The mother's work ended in pregnancy: as the case says, or because every insurance period
    of hers ended before the birth (a plain end of work, guide section H, risk 3)."""
    if facts.taken_in is not None or birth is None:
        return
    loss = facts.job_loss
    if loss is not None:
        if loss.ended_on >= birth:
            notes.append(
                f"Koniec pracy mamy ({long_date(loss.ended_on)}) nie wypada przed porodem: "
                "pomijamy go."
            )
            return
        reason = loss.reason
        if reason != "other" and scenario.mothers_work not in ("employment", None):
            notes.append(
                "Zasiłek po utracie pracy z powodu pracodawcy dotyczy umowy o pracę, a mama nie "
                "pracowała na niej: liczymy to jako zwykły koniec pracy przed porodem."
            )
            reason = "other"
        scenario.job_loss = JobLoss(
            ended_on=loss.ended_on,
            reason=reason,
            court_confirmed=loss.court_confirmed if reason == "unlawful" else None,
        )
        return
    ended = ended_before(facts, "mother", birth)
    if ended is not None and ended.end is not None:
        scenario.job_loss = JobLoss(ended_on=ended.end, reason="other")
        notes.append(
            f"Ostatni odczytany okres ubezpieczenia mamy ({ended.label}) skończył się "
            f"{long_date(ended.end)}, przed porodem: liczymy to jako koniec pracy przed porodem."
        )


def _zus_findings(facts: CaseFacts, scenario: Scenario, notes: list[str]) -> None:
    """A period ZUS ruled out gives no sickness insurance (`sickness`); a sham contract or
    business of the mother is the risk of section H.1."""
    for period in facts.insurance:
        if period.zus_finding is None:
            continue
        what = "uznał umowę za zawartą dla pozoru i " if period.zus_finding == "sham" else ""
        notes.append(
            f"ZUS {what}ustalił, że {WHO[period.person]} nie podlega ubezpieczeniu chorobowemu "
            f"z tytułu „{period.label}”: liczymy ten okres bez ubezpieczenia chorobowego."
        )
    sham = any(p.person == "mother" and p.zus_finding == "sham" for p in facts.insurance)
    if sham and facts.taken_in is None:
        scenario.insured_in_pregnancy = True


def _father_takes_over(
    facts: CaseFacts, scenario: Scenario, params: Params, notes: list[str]
) -> None:
    """A special situation of the mother, or the father's maternity leave after at least the
    weeks the mother must use (guide section B)."""
    birth = facts.birth_date
    if facts.taken_in is not None or birth is None or not scenario.child_born:
        return
    event = facts.mother_event
    if event is not None:
        end = event.end if event.kind == "hospital" else None
        if end is not None and end < event.start:
            notes.append("Koniec pobytu mamy w szpitalu wypada przed jego początkiem: pomijamy go.")
            end = None
        scenario.mother_event = MotherEvent(kind=event.kind, start=event.start, end=end)
        return
    fathers = sorted(
        (x for x in facts.leaves if x.person == "father" and x.kind == "maternity"),
        key=lambda x: x.start,
    )
    if not fathers:
        return
    start = fathers[0].start
    days = (start - birth).days
    weeks = days // 7
    minimum = params.father.takeover_after_weeks.value
    if weeks < minimum:
        notes.append(
            f"Tata zaczyna urlop macierzyński {long_date(start)}, {weeks} tyg. po porodzie. "
            f"Przed upływem {minimum} tygodni tata przejmuje urlop tylko w sytuacjach "
            "szczególnych, a tych nie odczytano ze sprawy: pomijamy przejęcie."
        )
        return
    scenario.father_takes_over = True
    scenario.mother_weeks_before_takeover = weeks
    if days % 7:
        notes.append(
            f"Tata przejmuje urlop macierzyński od {long_date(start)}. Kalkulator liczy pełne "
            f"tygodnie mamy po porodzie ({weeks}), więc na osi przejęcie zaczyna się "
            f"{long_date(birth + weeks * WEEK)}."
        )


def _contribution_debt(facts: CaseFacts, scenario: Scenario, notes: list[str]) -> None:
    """Contribution debt counts for a person with a business and for one cooperating with them
    (ustawa art. 2a ust. 1); the cases give us only the parent's own business."""
    debt = facts.contribution_debt
    if debt is None or debt.amount < 0:
        return
    work = scenario.mothers_work if debt.person == "mother" else scenario.fathers_work
    if work != "business":
        notes.append(
            f"Zadłużenie składkowe ({WHO[debt.person]}) odbiera prawo do zasiłku osobom "
            "prowadzącym działalność i osobom z nimi współpracującym (art. 2a ust. 1); tu go nie "
            "uwzględniamy."
        )
        return
    if debt.person == "mother":
        scenario.mother_contribution_debt = debt.amount
    else:
        scenario.father_contribution_debt = debt.amount


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


# ---------------------------------------------------------------------------------------------
# The insurance on the day the right arises


def after_insurance(facts: CaseFacts, person: Role) -> tuple[Outcome, str] | None:
    """The maternity benefit after the insurance ended (ustawa art. 30 ust. 1 and 3): the
    mother's employment ended in pregnancy for a reason of the employer, or unlawfully."""
    loss, birth = facts.job_loss, anchor_day(facts)
    if person != "mother" or facts.taken_in is not None or loss is None or birth is None:
        return None
    if loss.reason == "other" or loss.ended_on >= birth:
        return None
    if work_of(facts, "mother", loss.ended_on) not in ("employment", None):
        return None
    why = (
        f"zatrudnienie mamy ustało {long_date(loss.ended_on)}, w ciąży, z powodu "
        f"{JOB_LOSS_REASON[loss.reason]}"
    )
    if loss.reason == "unlawful" and loss.court_confirmed is not True:
        return "unknown", (
            f"{why}: zasiłek po ustaniu ubezpieczenia przysługuje, gdy naruszenie prawa stwierdzi "
            "prawomocny wyrok sądu, a sprawa tego nie mówi"
        )
    return "granted", (
        f"{why}: do porodu przysługuje zasiłek w wysokości zasiłku macierzyńskiego, a po porodzie "
        "zasiłek macierzyński po ustaniu ubezpieczenia"
    )


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
    sick = [p for p in covering if _insured(p)]
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
    if covering and all(sickness(p) == "unknown" for p in covering):
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
        period = next((p for p in covering if p.zus_finding is not None), covering[0])
        finding = " (ustalenie ZUS)" if period.zus_finding is not None else ""
        detail = f"{period.label} bez ubezpieczenia chorobowego{finding}"
    elif ended:
        period = ended[-1]
        detail = f"ostatni okres ({period.label}) skończył się {long_date(period.end)}"
    else:
        period = None
        detail = "żaden odczytany okres nie obejmuje tego dnia"
    text = f"W dniu {when} {WHO[person]} nie podlega ubezpieczeniu chorobowemu: {detail}."
    after = after_insurance(facts, person)
    if after is not None:
        text += f" Ale {after[1]}."
    return InsuranceCheck(person=person, on=day, covered=False, period=period, text=text)


# ---------------------------------------------------------------------------------------------
# The comparison with the decision of ZUS


Basis = Literal["insurance", "after-insurance", "debt", "parts"]


@dataclass(frozen=True)
class Verdict:
    """The calculator's answer for the benefit asked, and what it rests on."""

    outcome: Outcome
    basis: Basis
    why: str = ""
    """After "Kalkulator: <outcome> (" — empty when the insurance check says it all."""


def verdict(facts: CaseFacts, insurance: InsuranceCheck, params: Params) -> Verdict:
    """The rules the calculator applies to the case, in order: the benefit after the insurance
    ended (art. 30), the sickness insurance on the day the right arises, contribution debt of a
    business (art. 2a) and the number of parts of parental leave (KP art. 182¹ᶜ)."""
    after = after_insurance(facts, insurance.person) if insurance.covered is not True else None
    if after is not None:
        return Verdict(after[0], "after-insurance", after[1])
    if insurance.covered is None:
        return Verdict("unknown", "insurance")
    if insurance.covered is False:
        return Verdict("refused", "insurance")
    debt = facts.contribution_debt
    business = insurance.period is not None and insurance.period.title == "business"
    if debt and debt.person == insurance.person and business and over_limit(debt.amount, params):
        amount, limit = pln(dec(debt.amount)), pln(debt_limit(params))
        p = params.contribution_debt
        on = insurance.on
        if debt.repaid_on is not None and on is not None and debt.repaid_on <= expiry(on, params):
            return Verdict(
                "granted",
                "debt",
                f"zadłużenie składkowe {amount}, więcej niż {limit}, spłacono "
                f"{long_date(debt.repaid_on)}, w ciągu {p.expiry_months.value} miesięcy od dnia "
                "powstania prawa: zasiłek przysługuje po spłacie",
            )
        return Verdict(
            "refused",
            "debt",
            f"zadłużenie składkowe w dniu powstania prawa {amount}, więcej niż {limit}: zasiłek "
            "nie przysługuje do czasu spłaty całości zadłużenia, a bez spłaty w ciągu "
            f"{p.expiry_months.value} miesięcy prawo się przedawnia",
        )
    parts = parental_plan(facts)
    limit_parts = params.parental.max_parts.value
    if len(parts) > limit_parts:
        return Verdict(
            "partial",
            "parts",
            f"w sprawie jest {len(parts)} części urlopu rodzicielskiego, a można go podzielić "
            f"najwyżej na {limit_parts}: część {limit_parts + 1}. nie przysługuje",
        )
    return Verdict("granted", "insurance")


def compare(
    facts: CaseFacts, insurance: InsuranceCheck, params: Params | None = None
) -> Comparison:
    params = params or load_params()
    found = verdict(facts, insurance, params)
    ours = found.outcome
    zus = facts.decision.outcome if facts.decision else "unknown"
    if ours == "unknown" or zus == "unknown":
        match = None
    else:
        match = (
            ours == zus
            or (zus == "partial" and ours == "granted")
            # The part beyond the limit refused, the rest granted: ZUS refused that part.
            or (ours == "partial" and zus == "refused")
        )
    why = f" ({found.why})" if found.why else ""
    text = f"Kalkulator: {OUTCOME_WORDS[ours]}{why}. {ZUS_WORDS[zus]}."
    if facts.decision and facts.decision.reason:
        text += f" Uzasadnienie ZUS: {facts.decision.reason}"
    reason, reason_text = (None, "") if match is not False else _difference(facts, insurance, found)
    if reason == "other-refusal":
        text += (
            " Kalkulator sprawdza ubezpieczenie chorobowe w dniu powstania prawa; ZUS odmówił "
            "z innego powodu."
        )
    return Comparison(
        ours=ours, zus=zus, match=match, text=text, reason=reason, reason_text=reason_text
    )


def _difference(
    facts: CaseFacts, insurance: InsuranceCheck, found: Verdict
) -> tuple[DifferenceReason, str]:
    """Why the calculator and ZUS differ, as far as the facts tell."""
    said = facts.decision.reason if facts.decision else ""
    if found.outcome == "granted":  # ZUS refused
        if CHECKED_REASONS.search(said):
            return "reading", (
                "ZUS odmówił z powodu, który kalkulator sprawdza (ubezpieczenie chorobowe w dniu "
                "powstania prawa, zadłużenie składkowe albo liczbę części urlopu "
                "rodzicielskiego), ale odczytane dane tego nie pokazują: trzeba sprawdzić odczyt "
                "okresów ubezpieczenia, ustaleń ZUS, zadłużenia i urlopów."
            )
        return "other-refusal", (
            "ZUS odmówił z powodu, którego kalkulator nie sprawdza. Kalkulator sprawdza "
            "ubezpieczenie chorobowe w dniu powstania prawa, utratę pracy w ciąży, zadłużenie "
            "składkowe przy działalności i liczbę części urlopu rodzicielskiego."
        )
    # ZUS granted (or partly), the calculator did not.
    if found.basis == "debt":
        return "reading", (
            "ZUS przyznał świadczenie mimo odczytanego zadłużenia składkowego: trzeba sprawdzić "
            "kwotę, dzień stanu zadłużenia i datę spłaty."
        )
    if found.basis == "parts":
        return "reading", (
            "W odczycie jest więcej części urlopu rodzicielskiego, niż pozwalają przepisy, "
            "a ZUS przyznał świadczenie: trzeba sprawdzić okresy urlopu w odczycie."
        )
    ended = ended_before(facts, insurance.person, insurance.on)
    if ended is not None and ended.end is not None:
        return "missing-rule", (
            f"ZUS przyznał świadczenie, choć odczytane ubezpieczenie skończyło się "
            f"{long_date(ended.end)}, przed dniem powstania prawa. Zasiłek po ustaniu "
            "ubezpieczenia kalkulator liczy tylko po utracie pracy w ciąży z powodu pracodawcy "
            "albo z naruszeniem prawa; inną podstawę (np. umowę przedłużoną do dnia porodu) "
            "trzeba sprawdzić w aktach."
        )
    return "reading", (
        "ZUS przyznał świadczenie, a w odczytanych danych nie ma ubezpieczenia chorobowego w dniu "
        "powstania prawa: trzeba sprawdzić odczytane okresy ubezpieczenia i datę powstania prawa."
    )


# ---------------------------------------------------------------------------------------------
# The whole case


OPTIONAL: list[tuple[str, str]] = [
    ("parental_parts", "Plan urlopu rodzicielskiego ze sprawy pominięty"),
    ("father_takes_over", "Przejęcie urlopu macierzyńskiego przez tatę pominięte"),
    ("mother_event", "Sytuacja szczególna mamy pominięta"),
    ("job_loss", "Koniec pracy mamy w ciąży pominięty"),
]
"""What the case adds to the scenario and may be dropped when it does not fit the rules (a
reading error, or a plan the rules do not allow), in this order."""
RESET: dict[str, dict[str, object]] = {
    "parental_parts": {"parental_parts": []},
    "father_takes_over": {"father_takes_over": None, "mother_weeks_before_takeover": None},
    "mother_event": {"mother_event": None},
    "job_loss": {"job_loss": None},
}


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
    scenario, notes = to_scenario(facts, params)
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
        while True:
            try:
                timeline = build_timeline(scenario, params, today)
                break
            except ScenarioError as error:
                # Drop what the case added, one thing at a time, until the rules accept it.
                field = next((f for f, _ in OPTIONAL if getattr(scenario, f)), None)
                if field is None:
                    problem = str(error)
                    break
                label = dict(OPTIONAL)[field]
                notes.append(f"{label}: {error}")
                scenario = scenario.model_copy(update=RESET[field])
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
        comparison=compare(facts, insurance, params),
        notes=notes,
        problem=problem,
    )
