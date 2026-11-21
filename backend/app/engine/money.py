"""Guide section G "Wysokość zasiłku macierzyńskiego" (page 9) and the ustawa zasiłkowa behind
it: how much is paid for each period on the timeline (the "Pieniądze" lane). Also the money of
pregnancy (guide pages 2-4): the employer's sick pay, the sickness benefit and the benefit equal
to the maternity benefit after losing the job.

Applied last, on the finished periods of both parents. Which rule pays a period is one table,
`PAID` (segment id -> `Paid`: the kind of rule and how the period is named); a numbered id
("sick-pay-2", "parental-mother-1") falls back to its stem. A new kind of period is priced by
adding one entry there (and, for a new rule, one `Kind` and one branch in `pieces`):
- maternity: 100% of the benefit base for maternity leave and leave on its terms (art. 31
  ust. 1); after the written request of the parent it belongs to, 81,5% (art. 30a ust. 1-2,
  art. 31 ust. 3): the mother, filed not later than 21 days after the birth, or the person who
  took a child in, within 21 days after taking it in;
- full: 100% always, the request does not reach it: supplementary and paternity leave;
- taken-over: the father's part of maternity leave, 100% of his own base (our reading);
- parental: 70% (art. 31 ust. 2). After the request: 81,5% for the requesting parent, and for
  the other parent's weeks beyond their own 9, which the mother shares with the father (art. 30a
  ust. 3); the other parent's own 9 weeks stay at 70% (ust. 3f); with no day of the benefit for
  parental leave in the child's first year, 70% for all of it, and the benefit for maternity
  leave is topped up to 100% on request (ust. 3g, ust. 4). While parental leave is combined
  with part-time work, the benefit is less in proportion to the working time (ust. 4a); for the
  extension of the leave the benefit is due in full (guide E);
- sick-pay: the employer's sick pay in pregnancy, 100% of the pay, computed like the base of the
  sickness benefit, for every day (Labour Code art. 92 § 1-2);
- sick-benefit: the sickness benefit in pregnancy, 100% with code "B" (guide page 4; art. 11
  ust. 2), also after the insurance ended (pregnancy.py);
- job-loss: the benefit equal to the maternity benefit until the birth, 100% (guide page 4).
The base: the average monthly pay of the 12 calendar months before (an employee: art. 36 ust. 1,
with art. 47 for the maternity benefit and the benefit equal to it) or the average monthly income
(a contract or a business: art. 48 ust. 1 with art. 52), less 13,71% (art. 3 pkt 3-4). The amount
the parent gives is taken as that average: the simple case of 12 full months with the same pay.
Every benefit is due for every day, days off work included (art. 31 ust. 5, art. 11 ust. 4; sick
pay: art. 92 § 2); the base for one day is one thirtieth of the monthly base (art. 36 ust. 3).
Amounts appear only for a parent whose monthly amount was given in the chat; the onboarding's
range of earnings is never used.

Our readings, not settled by the materials (CLAUDE.md, open questions):
- an employee's own contributions (art. 3 pkt 3) are 13,71% of the gross pay, as the ZUS
  Załącznik says; the excerpt of the ustawa does not give their rates;
- rounding: the base, the monthly and the daily amount each to the grosz, half up; the amount
  for a period is the daily amount times its days;
- "not later than 21 days after" the birth (taking the child in) ends on the 21st day after it;
- the father who takes over maternity leave gets 100% of his own base, also after the mother's
  request for 81,5%; supplementary leave stays at 100% (art. 31 ust. 3 does not list it);
- the other parent's own 9 weeks are the first 63 days of their parental leave on the timeline;
- "the child's first year" ends the day before the first birthday; whether a day of the benefit
  for parental leave falls in it is read from the requesting mother's own parental leave; for a
  child taken in ust. 3g is not applied;
- "less in proportion to the working time" (ust. 4a): the benefit times (1 - the part of full
  time worked), for the weeks of work only;
- the benefit equal to the maternity benefit is counted like the maternity benefit: every day,
  one thirtieth of the monthly amount;
- no minimum base (art. 45), no top-up to the parental allowance (art. 31 ust. 3a) and no cap on
  the base of the sickness benefit after the insurance ended (art. 46): their amounts are not in
  the materials.
"""

import datetime as dt
import re
from dataclasses import dataclass, replace
from decimal import ROUND_HALF_UP, Decimal
from fractions import Fraction
from typing import Literal

from app.engine.adoption import cover_of, taker
from app.engine.after_insurance import PERIODS as AFTER_BIRTH
from app.engine.after_insurance import after_job_loss, confirmed
from app.engine.draft import DAY, WEEK, Draft, days_between, merge_sources, one_year_later
from app.engine.insurance import NOT_INSURED, Coverage, coverage, father_coverage, work_coverage
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
from app.engine.parental_plan import fraction, part_ids, work_weeks
from app.engine.wording import fmt, long_date

Parent = Literal["mother", "father"]
CENT = Decimal("0.01")
WHOSE = {"mother": "mamy", "father": "taty"}
WHO = {"mother": "mama", "father": "tata"}

Kind = Literal[
    "maternity",
    "full",
    "taken-over",
    "parental",
    "sick-pay",
    "sick-benefit",
    "rehab",
    "job-loss",
]
"""The rate rule that pays a period (see the module docstring)."""


@dataclass(frozen=True)
class Paid:
    """How a period on the timeline is paid."""

    kind: Kind
    label: str
    """How a note names it: "urlop macierzyński po porodzie", "wynagrodzenie chorobowe"."""
    title: str = ""
    """The payment's title, `{who}` = "mamy"/"taty"; empty = "Zasiłek {who}: <label>"."""

    def heading(self, who: str) -> str:
        return (self.title or f"Zasiłek {{who}}: {self.label}").format(who=who)


PAID: dict[str, Paid] = {
    # The maternity benefit: maternity leave and leave on its terms (art. 31 ust. 1, 3).
    "maternity-prenatal": Paid("maternity", "urlop macierzyński przed porodem"),
    "maternity": Paid("maternity", "urlop macierzyński po porodzie"),
    "maternity-resumed": Paid("maternity", "dalszy urlop macierzyński"),
    "adoption-leave": Paid("maternity", "urlop na warunkach urlopu macierzyńskiego"),
    # 100% whatever the request (art. 31 ust. 1; the father's part: our reading).
    "maternity-father": Paid("taken-over", "przejęty urlop macierzyński"),
    # The rest of the leave on the terms of maternity leave handed to the other parent
    # (KP art. 183 § 2): 100%, like the father's part of maternity leave.
    "adoption-leave-other": Paid(
        "taken-over", "przejęta część urlopu na warunkach urlopu macierzyńskiego"
    ),
    "supplementary": Paid("full", "uzupełniający urlop macierzyński"),
    "paternity": Paid("full", "urlop ojcowski"),
    # Parental leave: the options and the parts of the parents' plan (parental-<parent>-<k>).
    "parental": Paid("parental", "urlop rodzicielski"),
    "parental-father": Paid("parental", "urlop rodzicielski"),
    "parental-mother": Paid("parental", "urlop rodzicielski"),
    # Pregnancy (guide pages 2-4; pregnancy.py).
    "sick-pay": Paid(
        "sick-pay", "wynagrodzenie chorobowe w ciąży", "Wynagrodzenie chorobowe {who}"
    ),
    "sick-benefit": Paid("sick-benefit", "zasiłek chorobowy w ciąży", "Zasiłek chorobowy {who}"),
    "sick-after-insurance": Paid(
        "sick-benefit",
        "zasiłek chorobowy po ustaniu ubezpieczenia",
        "Zasiłek chorobowy {who} po ustaniu ubezpieczenia",
    ),
    # The rehabilitation benefit after the 270 days (ustawa art. 18-19, 22): its rate in
    # pregnancy, from the sickness benefit's base.
    "rehab-benefit": Paid(
        "rehab", "świadczenie rehabilitacyjne", "Świadczenie rehabilitacyjne {who}"
    ),
    "job-loss-benefit": Paid(
        "job-loss",
        "zasiłek w wysokości zasiłku macierzyńskiego",
        "Zasiłek {who} w wysokości zasiłku macierzyńskiego",
    ),
}
"""Every period that is paid, by segment id."""
LEAVE = {
    "maternity": "urlop macierzyński",
    "adoption-leave": "urlop na warunkach urlopu macierzyńskiego",
}
"""The leave a request for 81,5% covers together with parental leave."""
DEADLINE_ID = "rate-815-deadline"
CHOICE_ID = "rate-815"
NOTE_ID = "money"
JOB_LOSS_SEGMENT = "job-loss-benefit"


def paid_for(segment_id: str) -> Paid | None:
    """The rule for a period; a numbered id falls back to its stem ("sick-pay-2": "sick-pay")."""
    return PAID.get(segment_id) or PAID.get(re.sub(r"-\d+$", "", segment_id))


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


def _amounts(
    base: Base, rate: Decimal, work: Fraction | None, params: Params
) -> tuple[Decimal, Decimal]:
    """The monthly and the daily amount; while combined with part-time work, less in proportion
    to the working time (art. 31 ust. 4a)."""
    if work is None:
        return monthly(base, rate), daily(base, rate, params)
    kept = base.base * rate / 100 * (1 - Decimal(work.numerator) / Decimal(work.denominator))
    return cents(kept), cents(kept / params.money.days_in_month.value)


def request_deadline(birth: dt.date, params: Params) -> dt.date:
    """The last day for the 81,5% request: the 21st day after the birth (our reading)."""
    return birth + params.money.request_days.value * DAY


def money_active(scenario: Scenario) -> bool:
    """Section G joins the timeline once the interview has reached it: a monthly amount (or
    that it is unknown) or the mother's choice of rate."""
    return any(v is not None for v in (scenario.mother_pay, scenario.father_pay, scenario.rate_815))


def pay_matters(scenario: Scenario, parent: Parent) -> bool:
    """The parent's monthly amount gives amounts on the timeline: a paid period needs sickness
    insurance; the mother's sick leave in pregnancy needs it while she worked (her work may
    have ended before the birth)."""
    work = scenario.mothers_work if parent == "mother" else scenario.fathers_work
    if work not in ("employment", "contract", "business"):
        return False
    if parent == "father":
        return father_coverage(scenario) not in NOT_INSURED
    if coverage(scenario) not in NOT_INSURED:
        return True
    insured = work_coverage(work, scenario.mother_insured) not in NOT_INSURED
    return bool(scenario.sick_leave) and insured and scenario.taken_in is None


# Who may ask for 81,5%.


@dataclass(frozen=True)
class Request:
    """The written request for 81,5% (art. 30a): who files it, and by when."""

    who: Parent
    deadline: dt.date
    days: Param[int]
    leave: str
    """The segment id of the leave it covers with parental leave."""

    @property
    def taken_in(self) -> bool:
        return self.leave == "adoption-leave"


def request(scenario: Scenario, params: Params, anchor: dt.date) -> Request:
    """The mother, 21 days after the birth; for a child taken in, the person who took it in,
    21 days after taking it in. `anchor`: the birth (the due date) or the day of taking in."""
    m = params.money
    if scenario.taken_in is not None:
        days = m.request_days_taken_in
        return Request(taker(scenario), anchor + days.value * DAY, days, "adoption-leave")
    return Request("mother", request_deadline(anchor, params), m.request_days, "maternity")


def requester_cover(scenario: Scenario) -> Coverage:
    """The sickness insurance of the parent who may ask for 81,5%."""
    if scenario.taken_in is not None:
        return cover_of(scenario, taker(scenario))
    return coverage(scenario)


def chose_815(scenario: Scenario, cover: Coverage) -> bool:
    return scenario.rate_815 is True and cover not in NOT_INSURED


# The pieces a period is paid in.


@dataclass(frozen=True)
class Context:
    """What the rate of every period depends on, read once from the finished periods."""

    scenario: Scenario
    params: Params
    anchor: dt.date
    """The birth (or the due date), or the day the child was taken in."""
    request: Request
    requester: Parent | None
    """The parent whose request for 81,5% applies; None = 100% and 70%."""
    shares: bool
    """The other parent's weeks beyond their own are at 81,5% too (art. 30a ust. 3)."""
    first_year_lost: bool
    """No day of the requester's parental leave in the child's first year (art. 31 ust. 3g)."""
    own_end: dt.date | None
    """The last day of the other parent's own weeks of parental leave; None = all of it."""
    work: dict[str, tuple[dt.date, Fraction]]
    """Parts of the parents' plan combined with work: the last day of work, the part of full
    time."""


def context(
    segments: list[Segment], scenario: Scenario, params: Params, anchor: dt.date, cover: Coverage
) -> Context:
    """`cover`: the insurance of the parent who may ask for 81,5%."""
    req = request(scenario, params, anchor)
    requester = req.who if chose_815(scenario, cover) else None
    parental = sorted(
        (s for s in segments if _kind(s) == "parental" and s.lane in ("mother", "father")),
        key=lambda s: s.start,
    )
    mine = [s for s in parental if s.lane == requester]
    first_year_lost = (
        requester is not None
        and not req.taken_in
        and bool(mine)
        and all(s.start >= one_year_later(anchor) for s in mine)
    )
    event = scenario.mother_event
    left = event is not None and event.kind in ("death", "abandonment")
    own_end = None
    if requester is not None:
        own_end = _own_weeks_end([s for s in parental if s.lane != requester], params)
    by_id = dict(zip(part_ids(scenario.parental_parts), scenario.parental_parts, strict=True))
    work = {
        s.id: (s.start + work_weeks(part) * WEEK - DAY, part.work_fraction)
        for s in segments
        if (part := by_id.get(s.id)) is not None and part.work_fraction is not None
    }
    return Context(
        scenario=scenario,
        params=params,
        anchor=anchor,
        request=req,
        requester=requester,
        shares=requester is not None and not req.taken_in and not left,
        first_year_lost=first_year_lost,
        own_end=own_end,
        work=work,
    )


def _kind(segment: Segment) -> Kind | None:
    paid = paid_for(segment.id)
    return paid.kind if paid is not None else None


def _own_weeks_end(theirs: list[Segment], params: Params) -> dt.date | None:
    """The other parent's own 9 weeks: the first 63 days of their parental leave (our
    reading). None when all of it fits."""
    left = params.parental.exclusive_weeks.value * 7
    for segment in theirs:
        if segment.days >= left:
            return segment.start + (left - 1) * DAY
        left -= segment.days
    return None


@dataclass(frozen=True)
class Piece:
    """Days of one period paid at one rate."""

    start: dt.date
    end: dt.date
    rate: Param[float] | Param[int]
    work: Fraction | None = None
    """Part-time work combined with parental leave: the part of full time."""
    reason: Literal["", "own", "shared", "first-year"] = ""
    """Why parental leave has this rate after the request: the other parent's own weeks, the
    weeks the mother shares with the father, no day in the child's first year."""

    @property
    def days(self) -> int:
        return days_between(self.start, self.end)


def pieces(segment: Segment, paid: Paid, ctx: Context) -> list[Piece]:
    """The rate of every day of a paid period, split where it changes."""
    m, p = ctx.params.money, ctx.params.pregnancy

    def whole(rate: Param[float] | Param[int], reason: str = "") -> list[Piece]:
        return [Piece(segment.start, segment.end, rate, reason=reason)]  # type: ignore[arg-type]

    match paid.kind:
        case "maternity":
            found = whole(m.rate_single if segment.lane == ctx.requester else m.rate_full)
        case "full" | "taken-over":
            found = whole(m.rate_full)
        case "parental":
            found = _parental(segment, ctx)
        case "sick-pay":
            found = whole(m.sick_pay_rate)
        case "sick-benefit":
            found = whole(p.rate_percent)
        case "rehab":
            found = whole(p.rehab_rate_percent)
        case "job-loss":
            found = whole(p.job_loss_rate_percent)
        case _:
            found = []
    return _with_work(found, segment, ctx)


def _parental(segment: Segment, ctx: Context) -> list[Piece]:
    m = ctx.params.money
    start, end = segment.start, segment.end
    if ctx.requester is None:
        return [Piece(start, end, m.rate_parental)]
    mine = segment.lane == ctx.requester
    own = ctx.own_end
    if not mine and (own is None or end <= own):
        return [Piece(start, end, m.rate_parental, reason="own")]
    if ctx.first_year_lost:
        return [Piece(start, end, m.rate_parental, reason="first-year")]
    if mine:
        return [Piece(start, end, m.rate_single)]
    assert own is not None
    if not ctx.shares:
        return [Piece(start, end, m.rate_parental)]
    if start > own:
        return [Piece(start, end, m.rate_single, reason="shared")]
    return [
        Piece(start, own, m.rate_parental, reason="own"),
        Piece(own + DAY, end, m.rate_single, reason="shared"),
    ]


def _with_work(found: list[Piece], segment: Segment, ctx: Context) -> list[Piece]:
    """Split at the last day of part-time work: until then the benefit is less."""
    window = ctx.work.get(segment.id)
    if window is None:
        return found
    last, part = window
    split = []
    for piece in found:
        if piece.end <= last:
            split.append(replace(piece, work=part))
        elif piece.start > last:
            split.append(piece)
        else:
            split += [replace(piece, end=last, work=part), replace(piece, start=last + DAY)]
    return split


def priced(
    segments: list[Segment], scenario: Scenario, ctx: Context
) -> list[tuple[Segment, Paid, Piece, Base]]:
    """Every paid day on the timeline, for a parent whose amount is known."""
    bases: dict[str, Base | None] = {
        p: benefit_base(scenario, p, ctx.params) for p in ("mother", "father")
    }
    found = []
    for segment in segments:
        paid = paid_for(segment.id)
        base = bases.get(segment.lane)
        if paid is None or base is None:
            continue
        found += [(segment, paid, piece, base) for piece in pieces(segment, paid, ctx)]
    return found


# The rules.


def money_rules(
    draft: Draft,
    scenario: Scenario,
    params: Params,
    birth: dt.date,
    cover: Coverage,
    loss: Loss | None,
) -> None:
    """The 81,5% deadline on the child's lane and the money for every paid period."""
    if not money_active(scenario):
        return
    ctx = context(draft.segments, scenario, params, birth, cover)
    if _choice_open(draft.segments, scenario, ctx, cover, loss):
        draft.markers.append(_deadline_marker(scenario, ctx))
    draft.payments += payments(draft.segments, scenario, ctx)


def taken_in_money(timeline: Timeline, scenario: Scenario, params: Params) -> None:
    """Section G for a child taken in for upbringing (guide D; art. 30a ust. 2, art. 31): the
    leave on the terms of maternity leave and parental leave, after the timeline is built."""
    if not money_active(scenario):
        return
    cover = requester_cover(scenario)
    ctx = context(timeline.segments, scenario, params, timeline.birth_date, cover)
    if _choice_open(timeline.segments, scenario, ctx, cover, None):
        timeline.markers = sorted(
            [*timeline.markers, _deadline_marker(scenario, ctx)], key=lambda m: m.date
        )
    timeline.payments = payments(timeline.segments, scenario, ctx)
    timeline.assumptions += money_assumptions(scenario, timeline, params)


def payments(segments: list[Segment], scenario: Scenario, ctx: Context) -> list[Payment]:
    found = priced(segments, scenario, ctx)
    count: dict[str, int] = {}
    for segment, *_ in found:
        count[segment.id] = count.get(segment.id, 0) + 1
    made = []
    seen: dict[str, int] = {}
    for segment, paid, piece, base in found:
        seen[segment.id] = seen.get(segment.id, 0) + 1
        made.append(_payment(segment, paid, piece, base, ctx, seen[segment.id], count[segment.id]))
    return made


def _choice_open(
    segments: list[Segment], scenario: Scenario, ctx: Context, cover: Coverage, loss: Loss | None
) -> bool:
    """The requesting parent can choose 81,5%: they have the leave it covers and parental leave,
    a child lives, and they have not said no."""
    return (
        cover not in NOT_INSURED
        and _has_both(segments, ctx.request)
        and (loss is None or not loss.none_survived)
        and scenario.rate_815 is not False
    )


def _has_both(segments: list[Segment], req: Request) -> bool:
    mine = [s for s in segments if s.lane == req.who]
    return any(s.id == req.leave for s in mine) and any(_kind(s) == "parental" for s in mine)


def _deadline_marker(scenario: Scenario, ctx: Context) -> Marker:
    m = ctx.params.money
    req = ctx.request
    rf, rp, rs = rates(ctx.params)
    details = []
    who = WHO[req.who]
    if scenario.rate_815:
        details.append(
            f"{who.capitalize()} wybiera {rs}: wniosek trzeba złożyć najpóźniej tego dnia."
        )
    if not scenario.child_born and not req.taken_in:
        details.append(
            "Liczymy od przewidywanej daty porodu. Po porodzie oś przeliczy się od faktycznej daty."
        )
    if req.taken_in:
        summary = (
            f"Najpóźniej {req.days.value} dni po przyjęciu dziecka na wychowanie {who} może złożyć "
            f"pisemny wniosek o zasiłek w wysokości {rs} podstawy za cały urlop na warunkach "
            f"urlopu macierzyńskiego i rodzicielski, zamiast {rf} za urlop na warunkach urlopu "
            f"macierzyńskiego i {rp} za rodzicielski."
        )
    else:
        summary = (
            f"Najpóźniej {m.request_days.value} dni po porodzie mama może złożyć pisemny wniosek "
            f"o zasiłek w wysokości {rs} podstawy za cały urlop macierzyński i rodzicielski, "
            f"zamiast {rf} za macierzyński i {rp} za rodzicielski."
        )
    return Marker(
        id=DEADLINE_ID,
        lane="child",
        label=f"Wniosek o {rs} do",
        title=f"Ostatni dzień na wniosek o zasiłek {rs}",
        date=req.deadline,
        summary=summary,
        details=details,
        sources=merge_sources(req.days.sources, m.rate_single.sources),
    )


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


def _kind_sources(kind: Kind, base: Base, params: Params) -> list[SourceRef]:
    """The base and the days: the maternity benefit through art. 47 and 52; the sickness benefit
    and sick pay by their own provisions; the benefit equal to the maternity benefit by art. 47."""
    m = params.money
    base_sources = _base_sources(base, params)
    if kind in ("sick-pay", "sick-benefit", "rehab"):
        base_sources = [s for s in base_sources if s.article not in ("art. 47", "art. 52")]
    if kind == "job-loss":
        base_sources = [s for s in base_sources if s.article != "art. 47"] + m.base_job_loss.sources
    days = {
        "sick-pay": m.sick_pay_base.sources,
        "sick-benefit": [s for s in m.every_day.sources if s.article == "art. 11 ust. 4"],
        "rehab": params.pregnancy.rehab_month_days.sources,
    }.get(kind, m.every_day.sources)
    return merge_sources(base_sources, m.days_in_month.sources, days)


def _payment(
    segment: Segment,
    paid: Paid,
    piece: Piece,
    base: Base,
    ctx: Context,
    number: int,
    count: int,
) -> Payment:
    params, scenario = ctx.params, ctx.scenario
    m = params.money
    rf, rp, rs = rates(params)
    rate = _dec(piece.rate.value)
    per_month, per_day = _amounts(base, rate, piece.work, params)
    total = per_day * piece.days
    who = WHOSE[base.parent]
    what = "zasiłek"
    if paid.kind == "sick-pay":
        what = "wynagrodzenie chorobowe"
        details = [
            "Wynagrodzenie chorobowe liczy się według zasad ustalania podstawy wymiaru zasiłku "
            "chorobowego. " + _base_line(base),
            f"{percent(rate)} wynagrodzenia: {pln(monthly(base, rate))} miesięcznie.",
        ]
    else:
        if paid.kind == "rehab":
            what = "świadczenie rehabilitacyjne"
        details = [
            _base_line(base),
            f"{percent(rate)} podstawy: {pln(monthly(base, rate))} miesięcznie.",
        ]
    sources = [piece.rate.sources, _kind_sources(paid.kind, base, params)]
    if paid.kind == "sick-benefit":
        sources.append(m.sick_benefit_rate_law.sources)
    if piece.work is not None:
        share = fraction(piece.work)
        details.append(
            f"W tym czasie {WHO[base.parent]} pracuje na {share} etatu, więc zasiłek zmniejsza się "
            f"proporcjonalnie do wymiaru czasu pracy: {pln(monthly(base, rate))} × (1 − {share}) "
            f"= {pln(per_month)} miesięcznie."
        )
        sources.append(m.work_reduces.sources)
    elif segment.id in ctx.work:
        details.append(
            "Po tygodniach pracy (i za wydłużenie urlopu) zasiłek przysługuje w pełnej wysokości."
        )
        sources += [m.work_reduces.sources, params.parental_plan.extension_paid.sources]
    every = "wypłaca się" if paid.kind == "sick-pay" else "przysługuje"
    details.append(
        f"Za jeden dzień jedna trzydziesta: {pln(per_day)}. {what.capitalize()} {every} za każdy "
        f"dzień, także wolny od pracy: {piece.days} dni × {pln(per_day)} = {pln(total)}."
    )
    extra, extra_sources = _reasons(segment, paid, piece, ctx)
    details += extra
    sources += extra_sources
    if segment.tone == "option":
        details.append(_option_line(segment, scenario))
    if not scenario.child_born and paid.kind in ("sick-pay", "sick-benefit", "rehab", "job-loss"):
        if piece.end == ctx.anchor - DAY:
            details.append("Liczymy do przewidywanej daty porodu.")
    elif not scenario.child_born:
        details.append("Liczymy od przewidywanej daty porodu.")
    title = paid.heading(who)
    if count > 1:
        title += (
            f" (praca na {fraction(piece.work)} etatu)"
            if piece.work is not None
            else f" (od {fmt(piece.start)})"
        )
    reduced = f", zmniejszone za pracę na {fraction(piece.work)} etatu" if piece.work else ""
    of = "wynagrodzenia" if paid.kind == "sick-pay" else "podstawy"
    return Payment(
        id=f"pay-{segment.id}" + (f"-part-{number}" if number > 1 else ""),
        segment_id=segment.id,
        lane=base.parent,
        title=title,
        start=piece.start,
        end=piece.end,
        days=piece.days,
        rate=float(rate),
        base=float(base.base),
        monthly=float(per_month),
        daily=float(per_day),
        total=float(total),
        summary=(
            f"{percent(rate)} {of}{reduced}: {pln(per_month)} miesięcznie. Za {piece.days} dni "
            f"razem {pln(total)}."
        ),
        details=details,
        sources=merge_sources(*sources),
    )


def _reasons(
    segment: Segment, paid: Paid, piece: Piece, ctx: Context
) -> tuple[list[str], list[list[SourceRef]]]:
    """Why the rate is what it is, when the request for 81,5% is in play."""
    m = ctx.params.money
    rf, rp, rs = rates(ctx.params)
    req = ctx.request
    weeks = ctx.params.parental.exclusive_weeks.value
    deadline = fmt(req.deadline)
    lines: list[str] = []
    sources: list[list[SourceRef]] = []
    if ctx.requester is None:
        return lines, sources
    asker, other = WHO[req.who], WHOSE["father" if req.who == "mother" else "mother"]
    if piece.rate is m.rate_single and segment.lane == req.who:
        covers = (
            "urlop na warunkach urlopu macierzyńskiego i rodzicielski"
            if req.taken_in
            else "urlop macierzyński i rodzicielski"
        )
        lines.append(
            f"{asker.capitalize()} wybiera {rs} za cały {covers}: wniosek najpóźniej {deadline}."
        )
        sources.append(req.days.sources)
    if piece.reason == "shared":
        lines.append(
            f"Mama wybiera {rs} i dzieli się z tatą zasiłkiem za urlop rodzicielski: za tygodnie "
            f"ponad jego własne {weeks} tata dostaje {rs} swojej podstawy."
        )
        sources += [m.shared_with_father.sources, req.days.sources]
    if piece.reason == "own":
        lines.append(
            f"Także przy {rs} {WHOSE[req.who]} część urlopu rodzicielskiego, która należy tylko do "
            f"{other} ({weeks} tygodni), zostaje przy {rp}."
        )
        sources.append(m.other_parent_parental.sources)
    if piece.reason == "first-year":
        lines.append(
            f"W pierwszym roku życia dziecka (do {fmt(one_year_later(ctx.anchor) - DAY)}) mama "
            f"nie wykorzysta ani jednego dnia zasiłku za urlop rodzicielski, więc za ten urlop "
            f"zasiłek wynosi {rp}, choć wybrała {rs}."
        )
        sources.append(m.first_year.sources)
    if paid.kind == "maternity" and ctx.first_year_lost and segment.lane == req.who:
        lines.append(
            "Mama nie wykorzysta w pierwszym roku życia dziecka ani jednego dnia zasiłku za urlop "
            f"rodzicielski, więc na jej wniosek zasiłek za urlop macierzyński wyrówna się "
            f"jednorazowo do {rf}."
        )
        sources.append(m.first_year.sources)
    if paid.kind == "full" and segment.id == "supplementary":
        lines.append(
            f"{rs} dotyczy urlopu macierzyńskiego i rodzicielskiego; uzupełniający urlop "
            f"macierzyński zostaje przy {rf}."
        )
        sources.append(m.rate_single.sources)
    if paid.kind == "taken-over":
        lines.append(
            f"Tata dostaje {rf} swojej podstawy: {rs} wiąże się z wnioskiem mamy (nasze "
            "założenie, materiały nie mówią tego wprost)."
        )
    return lines, sources


def _option_line(segment: Segment, scenario: Scenario) -> str:
    """An option is a choice still to make, or a benefit that waits for a court judgment."""
    loss = after_job_loss(scenario)
    after_birth = segment.id in AFTER_BIRTH or segment.id.startswith("parental-mother-")
    if (
        loss is not None
        and not confirmed(loss)
        and segment.lane == "mother"
        and (segment.id == JOB_LOSS_SEGMENT or after_birth)
    ):
        return (
            "Kwota przysługuje, jeśli naruszenie przepisów prawa stwierdzi prawomocne orzeczenie "
            "sądu."
        )
    return "To okres do wyboru: kwota dotyczy urlopu wziętego tak, jak pokazuje oś."


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


def _timeline_context(scenario: Scenario, timeline: Timeline, params: Params) -> Context:
    return context(
        timeline.segments, scenario, params, timeline.birth_date, requester_cover(scenario)
    )


def _choice_note(scenario: Scenario, timeline: Timeline, params: Params) -> CaseNote | None:
    """100% and 70%, or 81,5% for the whole time: what the requesting parent decides, and by
    when."""
    req = request(scenario, params, timeline.birth_date)
    if not _has_both(timeline.segments, req):
        return None
    m = params.money
    rf, rp, rs = rates(params)
    marker = next((mk for mk in timeline.markers if mk.id == DEADLINE_ID), None)
    weeks = params.parental.exclusive_weeks.value
    by = f" (do {long_date(req.deadline)})" if marker is not None else ""
    asker = WHO[req.who]
    other = WHOSE["father" if req.who == "mother" else "mother"]
    if req.taken_in:
        text = (
            f"Za urlop na warunkach urlopu macierzyńskiego zasiłek wynosi {rf} podstawy, a za "
            f"urlop rodzicielski {rp}. Zamiast tego {asker} może najpóźniej {req.days.value} dni "
            f"po przyjęciu dziecka na wychowanie{by} złożyć pisemny wniosek i dostawać {rs} "
            "podstawy za cały urlop na warunkach urlopu macierzyńskiego i rodzicielski. Część "
            f"urlopu rodzicielskiego, która należy tylko do {other} ({weeks} tygodni), zostaje "
            f"przy {rp}."
        )
    else:
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
        req.days.sources,
        m.rate_single.sources,
        m.other_parent_parental.sources,
    ]
    text += _comparison(scenario, timeline, params, req)
    passed = timeline.child_born and req.deadline < timeline.today
    if scenario.rate_815 is True:
        until = long_date(req.deadline)
        text += f" {asker.capitalize()} wybiera {rs}: wniosek trzeba złożyć do {until}."
    elif scenario.rate_815 is False:
        text += f" {asker.capitalize()} wybiera {rf} i {rp}."
    elif passed:
        text += (
            f" Termin na wniosek minął {long_date(req.deadline)}, więc liczymy {rf} i {rp}. Jeśli "
            f"{asker} złożył{'a' if req.who == 'mother' else ''} wniosek w terminie, napisz "
            "o tym asystentowi."
        )
    if scenario.rate_815 is not False and not req.taken_in:
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


def _comparison(scenario: Scenario, timeline: Timeline, params: Params, req: Request) -> str:
    """Both ways, for the requesting parent's leave and parental leave as the timeline shows
    them (the same rules as the payments: part-time work, the first year)."""
    if benefit_base(scenario, req.who, params) is None:
        return ""
    rf, rp, rs = rates(params)
    periods = [
        s for s in timeline.segments if s.lane == req.who and _kind(s) in ("maternity", "parental")
    ]
    totals = []
    for choice in (False, True):
        asked = scenario.model_copy(update={"rate_815": choice})
        ctx = _timeline_context(asked, timeline, params)
        totals.append(
            sum(
                (
                    _amounts(base, _dec(piece.rate.value), piece.work, params)[1] * piece.days
                    for _, _, piece, base in priced(periods, asked, ctx)
                ),
                Decimal(0),
            )
        )
    days = sum(s.days for s in periods)
    whose = WHOSE[req.who]
    leave = LEAVE[req.leave]
    return (
        f" Za {leave} i rodzicielski {whose} pokazany na osi ({days} dni) to razem "
        f"{pln(totals[0])} przy {rf} i {rp} albo {pln(totals[1])} przy {rs}."
    )


def _computed_note(scenario: Scenario, timeline: Timeline, params: Params) -> CaseNote | None:
    """The base of each parent and the money for every paid period."""
    if not timeline.payments:
        return None
    m = params.money
    ctx = _timeline_context(scenario, timeline, params)
    used = priced(timeline.segments, scenario, ctx)
    parts = []
    sources: list[list[SourceRef]] = []
    for parent, who in (("mother", "Mama"), ("father", "Tata")):
        paid = [p for p in timeline.payments if p.lane == parent]
        base = benefit_base(scenario, parent, params)
        if not paid or base is None:
            continue
        periods = "; ".join(
            f"{_label(p)} — {percent(_dec(p.rate))}: {pln(_dec(p.monthly))} "
            f"miesięcznie, za {p.days} dni {pln(_dec(p.total))}"
            for p in paid
        )
        parts.append(f"{who} — {_base_line(base, 'podstawa')} {periods[0].upper()}{periods[1:]}.")
        sources.append(_base_sources(base, params))
        sources += [piece.rate.sources for _, _, piece, b in used if b.parent == parent]
    if any(piece.work is not None for _, _, piece, _ in used):
        parts.append(
            "W tygodniach pracy na część etatu zasiłek zmniejsza się proporcjonalnie do wymiaru "
            "czasu pracy."
        )
        sources.append(m.work_reduces.sources)
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


def _label(payment: Payment) -> str:
    """How the note names a payment: its period, with what tells its pieces apart."""
    paid = paid_for(payment.segment_id)
    if paid is None:
        return payment.title
    heading = paid.heading(WHOSE[payment.lane])
    return paid.label + payment.title.removeprefix(heading)


def money_assumptions(scenario: Scenario, timeline: Timeline, params: Params) -> list[str]:
    """What we assume about the amounts, and where the materials leave a gap."""
    if not money_active(scenario):
        return []
    rf, rp, rs = rates(params)
    assumptions = []
    bases = [b for p in ("mother", "father") if (b := benefit_base(scenario, p, params))]
    kinds = {paid.kind for p in timeline.payments if (paid := paid_for(p.segment_id))}
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
    if kinds & {"sick-pay", "sick-benefit", "rehab", "job-loss"}:
        assumptions.append(
            "Wynagrodzenie chorobowe, zasiłek chorobowy i zasiłek w wysokości zasiłku "
            "macierzyńskiego liczymy z tej samej podanej kwoty co zasiłek macierzyński: przy "
            "tych samych zarobkach przez 12 miesięcy podstawa wychodzi taka sama."
        )
    if "rehab" in kinds:
        assumptions.append(
            "Świadczenie rehabilitacyjne liczymy z podstawy zasiłku chorobowego bez jej "
            "waloryzacji (art. 19 ust. 2 ustawy zasiłkowej nie liczymy)."
        )
    if "job-loss" in kinds:
        assumptions.append(
            "Zasiłek w wysokości zasiłku macierzyńskiego liczymy jak zasiłek macierzyński: za "
            "każdy dzień, jedna trzydziesta kwoty miesięcznej."
        )
    if any(p.segment_id == "sick-after-insurance" for p in timeline.payments):
        assumptions.append(
            "Podstawa zasiłku chorobowego za okres po ustaniu ubezpieczenia nie może być wyższa "
            "niż przeciętne wynagrodzenie (art. 46 ustawy zasiłkowej). Tej kwoty nie ma "
            "w materiałach, więc tej granicy nie stosujemy."
        )
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
    marker = next((mk for mk in timeline.markers if mk.id == DEADLINE_ID), None)
    if marker is not None:
        days = (marker.date - timeline.birth_date).days
        after = "przyjęciu dziecka" if timeline.taken_in else "porodzie"
        assumptions.append(
            f"{days} dni po {after} liczymy od dnia po {after}: przy "
            f"{'przyjęciu' if timeline.taken_in else 'porodzie'} {fmt(timeline.birth_date)} "
            f"ostatni dzień na wniosek o {rs} to {fmt(marker.date)}."
        )
    if scenario.rate_815 and any(p.segment_id == "maternity-father" for p in timeline.payments):
        assumptions.append(
            f"Gdy mama wybrała {rs}, a tata przejmuje część urlopu macierzyńskiego, liczymy mu "
            f"{rf} jego podstawy: materiały nie mówią wprost, czy {rs} obejmuje też jego część."
        )
    ctx = _timeline_context(scenario, timeline, params)
    used = [piece for _, _, piece, _ in priced(timeline.segments, scenario, ctx)]
    if any(piece.work is not None for piece in used):
        assumptions.append(
            "„Proporcjonalnie do wymiaru czasu pracy” czytamy tak: przy pracy na 1/2 etatu "
            "zasiłek za te tygodnie jest o połowę niższy (art. 31 ust. 4a ustawy zasiłkowej). Za "
            "dni wydłużenia urlopu, bez pracy, liczymy pełny zasiłek."
        )
    if any(piece.reason == "shared" for piece in used):
        weeks = params.parental.exclusive_weeks.value
        assumptions.append(
            f"Własne {weeks} tygodni urlopu rodzicielskiego taty to pierwsze {weeks * 7} dni jego "
            f"urlopu rodzicielskiego na osi ({rp}); za dalsze, którymi mama dzieli się z nim po "
            f"wniosku o {rs}, liczymy {rs}. Materiały nie mówią, które tygodnie są które."
        )
    if ctx.first_year_lost:
        assumptions.append(
            "Pierwszy rok życia dziecka kończy się dzień przed pierwszymi urodzinami. Czy mama "
            "wykorzysta w nim dzień zasiłku za urlop rodzicielski, sprawdzamy po jej urlopie "
            "rodzicielskim na osi."
        )
    if timeline.taken_in and ctx.requester is not None:
        assumptions.append(
            f"Przy dziecku przyjętym na wychowanie nie stosujemy zasady o pierwszym roku życia "
            f"dziecka (art. 31 ust. 3g i 4): materiały nie mówią, jak ją liczyć, gdy dziecko jest "
            f"starsze. Liczymy {rs} za cały urlop rodzicielski osoby, która złożyła wniosek."
        )
    return assumptions
