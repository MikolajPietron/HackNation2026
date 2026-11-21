"""Guide section G "Wysokość zasiłku macierzyńskiego" (page 9) and the ustawa zasiłkowa behind
it: how much the maternity benefit is for each period on the timeline (the "Pieniądze" lane).

Applied last, on the finished periods of both parents:
- 100% of the benefit base for maternity leave (before and after the birth), supplementary
  maternity leave and paternity leave; 70% for parental leave (art. 31 ust. 1-2);
- after the mother's written request, filed not later than 21 days after the birth, 81,5% for the
  whole of maternity and parental leave (art. 30a ust. 1, art. 31 ust. 3), except the part of
  parental leave that belongs to the other parent alone: it stays at 70% (art. 31 ust. 3f);
- the base: the average monthly pay of the 12 calendar months before (an employee: art. 36
  ust. 1 with art. 47) or the average monthly income (a contract or a business: art. 48 ust. 1
  with art. 52), less 13,71% (art. 3 pkt 3-4). The amount the parent gives is taken as that
  average: the simple case of 12 full months with the same pay;
- the benefit is due for every day, days off work included (art. 31 ust. 5, art. 11 ust. 4);
  the base for one day is one thirtieth of the monthly base (art. 36 ust. 3).
Amounts appear only for a parent whose monthly amount was given in the chat; the onboarding's
range of earnings is never used.

Our readings, not settled by the materials (CLAUDE.md, open questions):
- an employee's own contributions (art. 3 pkt 3) are 13,71% of the gross pay, as the ZUS
  Załącznik says; the excerpt of the ustawa does not give their rates;
- rounding: the base, the monthly and the daily amount each to the grosz, half up; the amount
  for a period is the daily amount times its days;
- "not later than 21 days after the birth" ends on the 21st day after the day of birth;
- the father who takes over maternity leave gets 100% of his own base, also after the mother's
  request for 81,5%; supplementary leave stays at 100% (art. 31 ust. 3 does not list it);
- no minimum base (art. 45) and no top-up to the parental allowance (art. 31 ust. 3a): their
  amounts are not in the materials.
"""

import datetime as dt
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import Literal

from app.engine.draft import DAY, Draft, merge_sources
from app.engine.insurance import NOT_INSURED, Coverage
from app.engine.loss import Loss
from app.engine.models import (
    CaseNote,
    Marker,
    Payment,
    Scenario,
    Segment,
    SourceRef,
    Timeline,
    Work,
)
from app.engine.params import Param, Params
from app.engine.wording import fmt, long_date

Parent = Literal["mother", "father"]
CENT = Decimal("0.01")
MATERNITY = ("maternity-prenatal", "maternity", "maternity-resumed")
"""The mother's periods of maternity leave (art. 31 ust. 1, or ust. 3 after the request)."""
LABELS = {
    "maternity-prenatal": "urlop macierzyński przed porodem",
    "maternity": "urlop macierzyński po porodzie",
    "maternity-resumed": "dalszy urlop macierzyński",
    "maternity-father": "przejęty urlop macierzyński",
    "supplementary": "uzupełniający urlop macierzyński",
    "parental": "urlop rodzicielski",
    "parental-father": "urlop rodzicielski",
    "paternity": "urlop ojcowski",
}
"""The periods the benefit is paid for, by segment id, as a note names them."""
DEADLINE_ID = "rate-815-deadline"
CHOICE_ID = "rate-815"
NOTE_ID = "money"


def cents(amount: Decimal) -> Decimal:
    return amount.quantize(CENT, rounding=ROUND_HALF_UP)


def pln(amount: Decimal) -> str:
    """6 903,20 zł"""
    return f"{cents(amount):,.2f}".replace(",", " ").replace(".", ",") + " zł"


def percent(rate: Decimal) -> str:
    """100%, 81,5%"""
    return f"{rate.normalize():f}".replace(".", ",") + "%"


def _dec(value: float) -> Decimal:
    return Decimal(str(value))


def rates(params: Params) -> tuple[str, str, str]:
    """The three rates as the text says them: "100%", "70%", "81,5%"."""
    m = params.money
    return (
        percent(_dec(m.rate_full.value)),
        percent(_dec(m.rate_parental.value)),
        percent(_dec(m.rate_single.value)),
    )


@dataclass(frozen=True)
class Base:
    """One parent's benefit base."""

    parent: Parent
    work: Work
    pay: Decimal
    """The monthly amount the parent gave: gross pay, or the contribution base."""
    deducted: Decimal
    """Percent of `pay` deducted for the contributions."""
    base: Decimal
    """`pay` less the contributions: the monthly benefit base."""

    @property
    def employee(self) -> bool:
        return self.work == "employment"


def benefit_base(scenario: Scenario, parent: Parent, params: Params) -> Base | None:
    """The parent's benefit base, when the amount and the kind of work are known."""
    pay = scenario.mother_pay if parent == "mother" else scenario.father_pay
    work = scenario.mothers_work if parent == "mother" else scenario.fathers_work
    if not isinstance(pay, float | int) or work not in ("employment", "contract", "business"):
        return None
    amount = _dec(pay)
    deducted = _dec(params.money.contributions_percent.value)
    return Base(parent, work, amount, deducted, cents(amount * (100 - deducted) / 100))


def monthly(base: Base, rate: Decimal) -> Decimal:
    return cents(base.base * rate / 100)


def daily(base: Base, rate: Decimal, params: Params) -> Decimal:
    return cents(base.base * rate / 100 / params.money.days_in_month.value)


def request_deadline(birth: dt.date, params: Params) -> dt.date:
    """The last day for the 81,5% request: the 21st day after the birth (our reading)."""
    return birth + params.money.request_days.value * DAY


def money_active(scenario: Scenario) -> bool:
    """Section G joins the timeline once the interview has reached it: a monthly amount (or
    that it is unknown) or the mother's choice of rate."""
    return any(v is not None for v in (scenario.mother_pay, scenario.father_pay, scenario.rate_815))


def chose_815(scenario: Scenario, cover: Coverage) -> bool:
    return scenario.rate_815 is True and cover not in NOT_INSURED


def money_rules(
    draft: Draft,
    scenario: Scenario,
    params: Params,
    birth: dt.date,
    cover: Coverage,
    loss: Loss | None,
) -> None:
    """The 81,5% deadline on the child's lane and the benefit for every paid period."""
    if not money_active(scenario):
        return
    if _choice_open(draft, scenario, cover, loss):
        draft.markers.append(_deadline_marker(scenario, params, birth))
    bases = {p: benefit_base(scenario, p, params) for p in ("mother", "father")}
    for segment in draft.segments:
        base = bases[segment.lane] if segment.lane in ("mother", "father") else None
        rate = _rate(segment, scenario, params, cover)
        if base is not None and rate is not None:
            draft.payments.append(_payment(segment, base, rate, scenario, params, birth, cover))


def _choice_open(draft: Draft, scenario: Scenario, cover: Coverage, loss: Loss | None) -> bool:
    """The mother can choose 81,5%: she has maternity and parental leave, a child lives, and she
    has not said no."""
    has = {s.id for s in draft.segments if s.lane == "mother"}
    return (
        cover not in NOT_INSURED
        and {"maternity", "parental"} <= has
        and (loss is None or not loss.none_survived)
        and scenario.rate_815 is not False
    )


def _deadline_marker(scenario: Scenario, params: Params, birth: dt.date) -> Marker:
    m = params.money
    rf, rp, rs = rates(params)
    details = []
    if scenario.rate_815:
        details.append(f"Mama wybiera {rs}: wniosek trzeba złożyć najpóźniej tego dnia.")
    if not scenario.child_born:
        details.append(
            "Liczymy od przewidywanej daty porodu. Po porodzie oś przeliczy się od faktycznej daty."
        )
    return Marker(
        id=DEADLINE_ID,
        lane="child",
        label=f"Wniosek o {rs} do",
        title=f"Ostatni dzień na wniosek o zasiłek {rs}",
        date=request_deadline(birth, params),
        summary=(
            f"Najpóźniej {m.request_days.value} dni po porodzie mama może złożyć pisemny wniosek "
            f"o zasiłek w wysokości {rs} podstawy za cały urlop macierzyński i rodzicielski, "
            f"zamiast {rf} za macierzyński i {rp} za rodzicielski."
        ),
        details=details,
        sources=merge_sources(m.request_days.sources, m.rate_single.sources),
    )


def _rate(
    segment: Segment, scenario: Scenario, params: Params, cover: Coverage
) -> Param[float] | None:
    """The rate for a period, or None for a period without benefit (work, an undecided
    window)."""
    m = params.money
    single = chose_815(scenario, cover)
    if segment.lane == "mother" and segment.id in MATERNITY:
        return m.rate_single if single else m.rate_full
    if segment.lane == "mother" and segment.id == "parental":
        return m.rate_single if single else m.rate_parental
    if segment.id in ("maternity-father", "supplementary", "paternity"):
        return m.rate_full
    if segment.id == "parental-father":
        return m.rate_parental
    return None


def _base_line(base: Base, first: str = "Podstawa") -> str:
    what = (
        "wynagrodzenia brutto" if base.employee else "podstawy składki na ubezpieczenie chorobowe"
    )
    return (
        f"{first} wymiaru zasiłku: {pln(base.pay)} {what} pomniejszone o "
        f"{percent(base.deducted)}, czyli "
        f"{pln(base.base)} miesięcznie."
    )


def _base_sources(base: Base, params: Params) -> list[SourceRef]:
    m = params.money
    rule = m.base_employee if base.employee else m.base_non_employee
    contributions = [
        s
        for s in m.contributions_percent.sources
        if s.article == ("art. 3 pkt 3" if base.employee else "art. 3 pkt 4")
    ]
    return merge_sources(rule.sources, contributions)


def _payment(
    segment: Segment,
    base: Base,
    param: Param[float],
    scenario: Scenario,
    params: Params,
    birth: dt.date,
    cover: Coverage,
) -> Payment:
    m = params.money
    rf, rp, rs = rates(params)
    rate = _dec(param.value)
    per_month, per_day = monthly(base, rate), daily(base, rate, params)
    total = per_day * segment.days
    who = "mamy" if base.parent == "mother" else "taty"
    details = [
        _base_line(base),
        f"{percent(rate)} podstawy: {pln(per_month)} miesięcznie.",
        f"Za jeden dzień jedna trzydziesta: {pln(per_day)}. Zasiłek przysługuje za każdy "
        f"dzień, także wolny od pracy: {segment.days} dni × {pln(per_day)} = {pln(total)}.",
    ]
    sources = [param.sources, _base_sources(base, params), m.days_in_month.sources]
    sources.append(m.every_day.sources)
    single = chose_815(scenario, cover)
    deadline = fmt(request_deadline(birth, params))
    if param is m.rate_single:
        details.append(
            f"Mama wybiera {rs} za cały urlop macierzyński i rodzicielski: wniosek najpóźniej "
            f"{deadline}."
        )
        sources.append(m.request_days.sources)
    elif single and segment.id == "supplementary":
        details.append(
            f"{rs} dotyczy urlopu macierzyńskiego i rodzicielskiego; uzupełniający urlop "
            f"macierzyński zostaje przy {rf}."
        )
        sources.append(m.rate_single.sources)
    elif single and segment.id == "parental-father":
        weeks = params.parental.exclusive_weeks.value
        details.append(
            f"Także przy {rs} mamy część urlopu rodzicielskiego, która należy tylko do taty "
            f"({weeks} tygodni), zostaje przy {rp}."
        )
        sources.append(m.other_parent_parental.sources)
    elif single and segment.id == "maternity-father":
        details.append(
            f"Tata dostaje {rf} swojej podstawy: {rs} wiąże się z wnioskiem mamy (nasze "
            "założenie, materiały nie mówią tego wprost)."
        )
    if segment.tone == "option":
        details.append("To okres do wyboru: kwota dotyczy urlopu wziętego tak, jak pokazuje oś.")
    if not scenario.child_born:
        details.append("Liczymy od przewidywanej daty porodu.")
    return Payment(
        id=f"pay-{segment.id}",
        segment_id=segment.id,
        lane=base.parent,
        title=f"Zasiłek {who}: {LABELS[segment.id]}",
        start=segment.start,
        end=segment.end,
        days=segment.days,
        rate=float(rate),
        base=float(base.base),
        monthly=float(per_month),
        daily=float(per_day),
        total=float(total),
        summary=(
            f"{percent(rate)} podstawy: {pln(per_month)} miesięcznie. Za {segment.days} dni "
            f"razem {pln(total)}."
        ),
        details=details,
        sources=merge_sources(*sources),
    )


# The case explanation (CLAUDE.md, "Wyjaśnianie przypadku"): the choice of rate among the
# choices, what we computed after the other computed points.


def add_money_notes(
    notes: list[CaseNote], scenario: Scenario, timeline: Timeline, params: Params
) -> list[CaseNote]:
    if not money_active(scenario):
        return notes
    choice = _choice_note(scenario, timeline, params)
    if choice is not None:
        first_computed = next((i for i, n in enumerate(notes) if n.kind == "computed"), len(notes))
        notes = [*notes[:first_computed], choice, *notes[first_computed:]]
    computed = _computed_note(scenario, timeline, params)
    return [*notes, computed] if computed is not None else notes


def _choice_note(scenario: Scenario, timeline: Timeline, params: Params) -> CaseNote | None:
    """100% and 70%, or 81,5% for the whole time: what the mother decides, and by when."""
    mothers = {s.id for s in timeline.segments if s.lane == "mother"}
    if not {"maternity", "parental"} <= mothers:
        return None
    m = params.money
    rf, rp, rs = rates(params)
    marker = next((mk for mk in timeline.markers if mk.id == DEADLINE_ID), None)
    deadline = request_deadline(timeline.birth_date, params)
    weeks = params.parental.exclusive_weeks.value
    by = f" (do {long_date(deadline)})" if marker is not None else ""
    text = (
        f"Za urlop macierzyński zasiłek wynosi {rf} podstawy, a za urlop rodzicielski {rp}. "
        f"Zamiast tego mama może najpóźniej {m.request_days.value} dni po porodzie{by} złożyć "
        f"pisemny wniosek i dostawać {rs} podstawy za cały urlop macierzyński i rodzicielski. "
        f"Część urlopu rodzicielskiego, która należy tylko do taty ({weeks} tygodni), zostaje "
        f"przy {rp}."
    )
    sources = [
        m.rate_full.sources,
        m.rate_parental.sources,
        m.request_days.sources,
        m.rate_single.sources,
        m.other_parent_parental.sources,
    ]
    compare = _comparison(scenario, timeline, params)
    if compare:
        text += compare
    passed = timeline.child_born and deadline < timeline.today
    if scenario.rate_815 is True:
        text += f" Mama wybiera {rs}: wniosek trzeba złożyć do {long_date(deadline)}."
    elif scenario.rate_815 is False:
        text += f" Mama wybiera {rf} i {rp}."
    elif passed:
        text += (
            f" Termin na wniosek minął {long_date(deadline)}, więc liczymy {rf} i {rp}. Jeśli "
            "mama złożyła wniosek w terminie, napisz o tym asystentowi."
        )
    if scenario.rate_815 is not False:
        text += (
            f" Jeśli przy {rs} w pierwszym roku życia dziecka mama nie wykorzysta ani jednego "
            f"dnia zasiłku za urlop rodzicielski, za ten urlop dostanie {rp}, a zasiłek za urlop "
            f"macierzyński wyrówna się do {rf} na jej wniosek."
        )
        sources.append(m.first_year.sources)
    return CaseNote(
        id=CHOICE_ID,
        kind="choice",
        title=f"Zasiłek: {rf} i {rp} albo {rs} przez cały czas",
        text=text,
        sources=merge_sources(*sources),
    )


def _comparison(scenario: Scenario, timeline: Timeline, params: Params) -> str:
    """Both ways, for the mother's maternity and parental leave as the timeline shows them."""
    base = benefit_base(scenario, "mother", params)
    if base is None:
        return ""
    m = params.money
    rf, rp, rs = rates(params)
    periods = [
        s for s in timeline.segments if s.lane == "mother" and s.id in (*MATERNITY, "parental")
    ]
    full, parental, single = (_dec(p.value) for p in (m.rate_full, m.rate_parental, m.rate_single))
    split = sum(
        (daily(base, parental if s.id == "parental" else full, params) * s.days for s in periods),
        Decimal(0),
    )
    days = sum(s.days for s in periods)
    whole = daily(base, single, params) * days
    return (
        f" Za urlop macierzyński i rodzicielski mamy pokazany na osi ({days} dni) to razem "
        f"{pln(split)} przy {rf} i {rp} albo {pln(whole)} przy {rs}."
    )


def _computed_note(scenario: Scenario, timeline: Timeline, params: Params) -> CaseNote | None:
    """The base of each parent and the benefit for every paid period."""
    if not timeline.payments:
        return None
    m = params.money
    parts = []
    sources: list[list[SourceRef]] = []
    for parent, who in (("mother", "Mama"), ("father", "Tata")):
        paid = [p for p in timeline.payments if p.lane == parent]
        base = benefit_base(scenario, parent, params)
        if not paid or base is None:
            continue
        periods = "; ".join(
            f"{LABELS[p.segment_id]} — {percent(_dec(p.rate))}: {pln(_dec(p.monthly))} "
            f"miesięcznie, za {p.days} dni {pln(_dec(p.total))}"
            for p in paid
        )
        parts.append(f"{who} — {_base_line(base, 'podstawa')} {periods[0].upper()}{periods[1:]}.")
        sources.append(_base_sources(base, params))
        rates = {p.rate for p in paid}
        sources += [
            param.sources
            for param in (m.rate_full, m.rate_parental, m.rate_single)
            if param.value in rates
        ]
    parts.append(
        "Za jeden dzień liczymy jedną trzydziestą kwoty miesięcznej; zasiłek przysługuje za "
        "każdy dzień, także wolny od pracy."
    )
    sources += [m.days_in_month.sources, m.every_day.sources]
    return CaseNote(
        id=NOTE_ID,
        kind="computed",
        title="Ile wynosi zasiłek",
        text=" ".join(parts),
        sources=merge_sources(*sources),
    )


def money_assumptions(scenario: Scenario, timeline: Timeline, params: Params) -> list[str]:
    """What we assume about the amounts, and where the materials leave a gap."""
    if not money_active(scenario):
        return []
    rf, _, rs = rates(params)
    assumptions = []
    bases = [b for p in ("mother", "father") if (b := benefit_base(scenario, p, params))]
    if timeline.payments:
        assumptions += [
            "Podaną kwotę miesięczną traktujemy jako przeciętną z 12 pełnych miesięcy "
            "kalendarzowych przed miesiącem, w którym powstało prawo do zasiłku: tak jest, gdy "
            "przez cały ten czas była taka sama. Inne przypadki (krótsze ubezpieczenie, miesiące "
            "z nieobecnością, premie kwartalne i roczne) liczy się inaczej i tego jeszcze nie "
            "pokazujemy.",
            "Kwoty zaokrąglamy do pełnych groszy (od pół grosza w górę): podstawę, kwotę "
            "miesięczną i kwotę za dzień; kwota za okres to kwota za dzień razy liczba dni. "
            "Pokazujemy zasiłek bez potrąceń, np. zaliczki na podatek.",
            "Nie stosujemy minimalnej podstawy wymiaru (art. 45 ustawy zasiłkowej) ani "
            "podwyższenia zasiłku do kwoty świadczenia rodzicielskiego (art. 31 ust. 3a): tych "
            "kwot nie ma w naszych materiałach.",
        ]
    if any(b.employee for b in bases):
        assumptions.append(
            "Od wynagrodzenia brutto pracownika odejmujemy 13,71%: tyle wynoszą jego składki na "
            "ubezpieczenia emerytalne, rentowe i chorobowe według Załącznika ZUS. Wyciąg "
            "z ustawy wymienia te składki, ale nie podaje ich stawek."
        )
    if any(not b.employee for b in bases):
        assumptions.append(
            "Przy umowie zlecenia i własnej firmie liczymy z podanej podstawy składki "
            "chorobowej. Górnej granicy tej podstawy wyciąg z ustawy nie podaje."
        )
    if any(mk.id == DEADLINE_ID for mk in timeline.markers):
        deadline = request_deadline(timeline.birth_date, params)
        assumptions.append(
            f"{params.money.request_days.value} dni po porodzie liczymy od dnia po porodzie: "
            f"przy porodzie {fmt(timeline.birth_date)} ostatni dzień na wniosek o {rs} to "
            f"{fmt(deadline)}."
        )
    if scenario.rate_815 and any(p.segment_id == "maternity-father" for p in timeline.payments):
        assumptions.append(
            f"Gdy mama wybrała {rs}, a tata przejmuje część urlopu macierzyńskiego, liczymy mu "
            f"{rf} jego podstawy: materiały nie mówią wprost, czy {rs} obejmuje też jego część."
        )
    return assumptions
