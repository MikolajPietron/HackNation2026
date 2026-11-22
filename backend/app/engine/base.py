"""The benefit base (podstawa wymiaru zasiłku) in detail: the challenge's calculator "with an
individual benefit base" (guide page 13, point f).

The ustawa zasiłkowa, chapter 8 (employees, art. 36-45) and chapter 9 (non-employees, art. 48-50),
which apply to the maternity benefit "odpowiednio" (art. 47, 52), and the chapter of the ZUS
Załącznik on the benefit base. One entry point, `benefit_base`, which money.py calls for each
parent's first paid period; the result (`BenefitBase`) carries every step with its sources.

Input: the monthly amount the parent gave (`mother_pay`, `father_pay`), taken as the average of
the months, or in detail `PayHistory`: the months of the payer's certificate (Z-3, Z-3a), the
quarterly and annual bonuses, full-time work, the start of insurance, the pay in the contract.

The rules:
- the base is the average monthly pay (an employee) or income (a non-employee: the base of the
  sickness contribution) of the 12 calendar months before the month the right arose, less 13,71%
  (art. 36 ust. 1, art. 48 ust. 1, art. 3 pkt 3-4; Załącznik);
- insured for a shorter time: the full calendar months of insurance with this payer (art. 36
  ust. 2 and 4); the right before a full calendar month of insurance: the monthly pay set in the
  contract, or the pay for the days worked topped up to the days of the month (art. 37); a
  contract of mandate: the income set in the contract (art. 49 ust. 1 pkt 2);
- an employee's month worked less than half (a justified absence) is left out, a month worked at
  least half is topped up: the fixed pay in full from the contract, the variable pay divided by
  the days worked and multiplied by the days required, overtime, night work and commission as
  paid; when every month was worked less than half, all of them count, topped up (art. 37 ust. 2,
  art. 38; Załącznik). A non-employee's month of activity less than half is left out, at least
  half taken as it is; every month reduced: all count (art. 50);
- quarterly bonuses of the four quarters before the month, and annual pay of the year before it,
  enter as one twelfth (art. 42 ust. 2-3);
- no new base when the parent's previous benefit, or the employer's sick pay in pregnancy, ended
  less than a calendar month before (art. 43; KP art. 92 § 2): sick leave in pregnancy straight
  into maternity leave keeps the base of the month the sick leave began;
- full-time work: not lower than the minimum wage less 13,71% (art. 45 ust. 1; the minimum wage
  from the Załącznik); a non-employee's contribution base counts up to the cap of the voluntary
  sickness contribution (Załącznik: 23 550,00 zł, which gives a base of 20 321,30 zł).

Not computed (no amounts; a warning says why): a business insured for less than 12 full months or
in its first month, whose base needs the lowest contribution base (art. 48a, art. 49 ust. 1 pkt 1),
which is not in the materials; the right before a full month without the pay in the contract;
the pay in the contract alone after the first month; an insurance that begins after the right.

Our readings, not settled by the materials (CLAUDE.md, open questions):
- the right to the maternity benefit arises on the first day of the parent's first paid period
  (or of the sick leave or benefit it follows);
- a break shorter than a calendar month: the next benefit starts before the same day of the next
  month, counted from the day after the previous one ended (31 January -> end of February);
- the employer's sick pay in pregnancy keeps the base like a benefit (KP art. 92 § 2: it is
  computed on the rules of the sickness benefit base);
- months given outside the 12 do not count; months not given are not guessed: the average comes
  from the months given (an expected child: months still to come cannot be given yet);
- `PayHistory.insured_from` (or, for the mother, the start of her insurance from the pregnancy
  interview) tells a shorter insurance from months not given;
- a later break of a month or more between one parent's periods would set a new base; we keep
  the first one, later earnings are not known;
- rounding: a topped-up month, the average, each twelfth and the base to the grosz, half up.
"""

import calendar
import datetime as dt
from collections.abc import Iterator, Sequence
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Literal

from app.engine.amounts import cents, dec, percent, pln
from app.engine.draft import DAY, merge_sources
from app.engine.models import (
    BaseMonth,
    BaseMonthStatus,
    BaseStep,
    BenefitBase,
    CaseNote,
    PayHistory,
    PayMonth,
    Scenario,
    Segment,
    SourceRef,
    Timeline,
    Work,
)
from app.engine.params import Params
from app.engine.pregnancy import JOB_LOSS_SEGMENT, SEGMENT_IDS
from app.engine.wording import fmt

Parent = Literal["mother", "father"]
Month = tuple[int, int]
"""(year, month)"""

PAID_WORK: tuple[Work, ...] = ("employment", "contract", "business")
SICK = tuple(SEGMENT_IDS.values())
"""The sick leave in pregnancy: the employer's sick pay and the sickness benefit (pregnancy.py;
"-2" may follow an id)."""
FOLLOWS = (*SICK, JOB_LOSS_SEGMENT)
"""Periods on the mother's lane a later benefit keeps the base of: the sick leave in pregnancy
and the benefit after losing the job."""

_NOMINATIVE = [
    "styczeń",
    "luty",
    "marzec",
    "kwiecień",
    "maj",
    "czerwiec",
    "lipiec",
    "sierpień",
    "wrzesień",
    "październik",
    "listopad",
    "grudzień",
]
_GENITIVE = [
    "stycznia",
    "lutego",
    "marca",
    "kwietnia",
    "maja",
    "czerwca",
    "lipca",
    "sierpnia",
    "września",
    "października",
    "listopada",
    "grudnia",
]


@dataclass(frozen=True)
class NoBase:
    """The amounts cannot be computed from what the parent gave; `reason` says why, in Polish."""

    parent: Parent
    reason: str


def benefit_base(
    scenario: Scenario,
    parent: Parent,
    params: Params,
    right_from: dt.date,
    segments: Sequence[Segment] = (),
) -> BenefitBase | NoBase | None:
    """The parent's monthly benefit base for the right to the benefit that arises on
    `right_from`, the first day of the parent's first paid period. `segments`: the timeline so
    far, for an earlier benefit the right follows (art. 43). None when there is nothing to compute
    from (no paid work; no amount, no months and no pay in the contract that applies)."""
    mother = parent == "mother"
    work = scenario.mothers_work if mother else scenario.fathers_work
    if work not in PAID_WORK:
        return None
    history = scenario.mother_pay_history if mother else scenario.father_pay_history
    given = scenario.mother_pay if mother else scenario.father_pay
    pay = dec(given) if isinstance(given, float | int) else None
    history = history or PayHistory()
    if not history.months and pay is None and history.contract_pay is None:
        return None
    insured_from = history.insured_from or (scenario.insured_since if mother else None)
    day, follows = _followed(right_from, parent, segments)
    computation = _Base(parent, work, params, history, pay, insured_from, day)
    return computation.compute(right_from, follows)


@dataclass
class _Base:
    """One computation; the steps are collected as the rules apply."""

    parent: Parent
    work: Work
    params: Params
    history: PayHistory
    pay: Decimal | None
    insured_from: dt.date | None
    day: dt.date
    """The day the right arose that the base is set for."""
    steps: list[BaseStep] = field(default_factory=list)
    rows: list[BaseMonth] = field(default_factory=list)
    capped: bool = False

    @property
    def employee(self) -> bool:
        return self.work == "employment"

    def step(self, text: str, *groups: list[SourceRef]) -> None:
        self.steps.append(BaseStep(text=text, sources=merge_sources(*groups)))

    def no(self, why: str) -> NoBase:
        who = "mamy" if self.parent == "mother" else "taty"
        return NoBase(self.parent, f"Kwot zasiłku {who} nie liczymy: {why}")

    def compute(self, right_from: dt.date, follows: Segment | None) -> BenefitBase | NoBase:
        p, m = self.params.benefit_base, self.params.money
        month = (self.day.year, self.day.month)
        first, last = _shift(month, -p.months.value), _shift(month, -1)
        rule = (m.base_employee if self.employee else m.base_non_employee).sources
        since = self.insured_from
        start = first
        if since is not None:
            begins = (since.year, since.month)
            start = max(first, begins if since.day == 1 else _shift(begins, 1))
        when = (
            f"Prawo do zasiłku powstaje {fmt(self.day)}: podstawą jest przeciętna z "
            f"{p.months.value} miesięcy kalendarzowych przed miesiącem, w którym powstało prawo, "
            f"czyli {_span(first, last)}."
        )
        if follows is not None:
            after, began = _follows_words(follows)
            self.step(
                f"Zasiłek od {fmt(right_from)} następuje {after} {fmt(self.day)}, bez przerwy albo "
                "po przerwie krótszej niż miesiąc kalendarzowy: podstawy wymiaru nie ustala się "
                "na nowo.",
                p.same_base.sources,
            )
            when = (
                f"Podstawą jest przeciętna z {p.months.value} miesięcy kalendarzowych przed "
                f"miesiącem, w którym {began}: {_span(first, last)}."
            )
        if since is not None and since > self.day:
            return self.no(
                f"początek ubezpieczenia ({fmt(since)}) wypada po dniu, w którym powstaje prawo "
                f"do zasiłku ({fmt(self.day)}). Sprawdź tę datę."
            )
        if since is not None and start > last:
            return self._first_month(since, month)
        if since is not None and start > first:
            if self.work == "business":
                return self.no(
                    f"ubezpieczenie chorobowe z własnej firmy trwa od {fmt(since)}, krócej niż "
                    f"{p.months.value} pełnych miesięcy kalendarzowych. Podstawę liczy się wtedy "
                    "z najniższej podstawy wymiaru składek (art. 48a ustawy zasiłkowej), a tej "
                    "kwoty nie ma w naszych materiałach."
                )
            n = _count(start, last)
            when += (
                f" Ubezpieczenie trwa od {fmt(since)}, więc liczą się pełne miesiące kalendarzowe "
                f"ubezpieczenia: {_span(start, last)} ({n} {_months_count(n)})."
            )
        # The 12 months: the employee's rule and the Załącznik's row for employees; a
        # non-employee's own rule (art. 48 ust. 1) says 12 months too.
        months = p.months.sources if self.employee else []
        shorter = p.shorter.sources if start > first else []
        if shorter and not self.employee:
            shorter = merge_sources(shorter, p.non_employee_rules.sources)
        if self.history.months:
            self.step(when, rule, months, shorter)
            average = self._months(first, start, last)
            if isinstance(average, NoBase):
                return average
        elif self.pay is None:
            return self.no(
                "wynagrodzenie z umowy liczy się tylko wtedy, gdy prawo powstaje przed upływem "
                "pełnego miesiąca ubezpieczenia. Podstawą jest przeciętna z miesięcy "
                f"{_span(start, last)}: podaj kwotę miesięczną albo zarobki z tych miesięcy."
            )
        else:
            self.step(
                f"{when} Podaną kwotę, {pln(self.pay)}, traktujemy jako tę przeciętną.",
                rule,
                months,
                shorter,
            )
            average = self._cap(self.pay)
            if self.capped:
                self._cap_step("z podanej kwoty")
        return self._finish(average, _key(start), _key(last))

    def _first_month(self, since: dt.date, month: Month) -> BenefitBase | NoBase:
        """The right arises before a full calendar month of insurance (art. 37, art. 49)."""
        p = self.params.benefit_base
        before = (
            f"Prawo do zasiłku powstaje {fmt(self.day)}, przed upływem pełnego miesiąca "
            f"kalendarzowego ubezpieczenia (od {fmt(since)})"
        )
        if self.work == "business":
            return self.no(
                "prawo do zasiłku powstaje w pierwszym miesiącu ubezpieczenia chorobowego "
                "z własnej firmy. Podstawą jest wtedy najniższa podstawa wymiaru składek (art. 49 "
                "ust. 1 pkt 1 ustawy zasiłkowej), a tej kwoty nie ma w naszych materiałach."
            )
        contract = None if self.history.contract_pay is None else dec(self.history.contract_pay)
        if not self.employee:
            amount = contract if contract is not None else self.pay
            if amount is None:
                return self.no(
                    "prawo powstaje przed upływem pełnego miesiąca ubezpieczenia, a podstawą jest "
                    "wtedy kwota przychodu określona w umowie zlecenia. Podaj ją asystentowi."
                )
            self.step(
                f"{before}: podstawą jest kwota przychodu określona w umowie za ten miesiąc, "
                f"{pln(amount)}.",
                p.first_month_contract.sources,
            )
            average = self._cap(amount)
            if self.capped:
                self._cap_step("z tej kwoty")
            return self._finish(average, None, None)
        if contract is not None:
            self.step(
                f"{before}: podstawą jest wynagrodzenie miesięczne określone w umowie, "
                f"{pln(contract)}.",
                p.first_month.sources,
            )
            return self._finish(contract, None, None)
        partial = [
            pm
            for pm in self.history.months
            if _month(pm.month) <= month and _partial(pm) and pm.days_worked
        ]
        if partial:
            pm = partial[-1]
            topped, formula = _topped(pm)
            self._row(pm, topped, "topped-up")
            self.step(
                f"{before}: podstawą jest wynagrodzenie za pełny miesiąc. {_name(pm.month, True)} "
                f"(przepracowane {pm.days_worked} z {pm.days_required} dni) uzupełniamy do "
                f"pełnego miesiąca: {formula} = {pln(topped)}.",
                p.first_month_by_days.sources,
            )
            return self._finish(topped, None, None)
        if self.pay is not None:
            self.step(
                f"{before}: podstawą jest wynagrodzenie za pełny miesiąc określone w umowie. "
                f"Podaną kwotę, {pln(self.pay)}, traktujemy jako to wynagrodzenie.",
                p.first_month.sources,
            )
            return self._finish(self.pay, None, None)
        return self.no(
            "prawo powstaje przed upływem pełnego miesiąca ubezpieczenia, a podstawą jest wtedy "
            "wynagrodzenie miesięczne określone w umowie. Podaj je asystentowi."
        )

    def _months(self, first: Month, start: Month, last: Month) -> Decimal | NoBase:
        """The months the parent gave: which count and how (art. 38, art. 50, art. 42 ust. 1)."""
        p = self.params.benefit_base
        inside = [pm for pm in self.history.months if start <= _month(pm.month) <= last]
        for pm in self.history.months:
            if not start <= _month(pm.month) <= last:
                before = first <= _month(pm.month) < start
                self._row(pm, None, "before-insurance" if before else "outside")
        every = bool(inside) and all(_less_than_half(pm) for pm in inside)
        sentences: list[str] = []
        sources: list[list[SourceRef]] = [p.average.sources]
        if not self.employee:
            sources.append(p.non_employee_rules.sources)
        if every:
            sentences.append(
                "W każdym miesiącu przepracowano mniej niż połowę obowiązującego czasu pracy, "
                "więc liczą się wszystkie po uzupełnieniu."
                if self.employee
                else "W każdym miesiącu praca lub działalność trwała mniej niż połowę miesiąca, "
                "więc liczą się wszystkie, tak jak je podano."
            )
            sources.append(
                p.every_month_short.sources if self.employee else p.non_employee_months.sources
            )
        counted: list[tuple[PayMonth, Decimal]] = []
        full: list[Decimal] = []
        for pm in inside:
            amount = self._cap(dec(pm.amount))
            if not _partial(pm):
                counted.append((pm, amount))
                full.append(amount)
                self._row(pm, amount, "full")
                continue
            days = f"przepracowane {pm.days_worked} z {pm.days_required} dni"
            name = _name(pm.month, True)
            if not self.employee:
                sources.append(p.non_employee_months.sources)
                if _less_than_half(pm) and not every:
                    self._row(pm, None, "skipped")
                    sentences.append(
                        f"{name}: {days}, mniej niż połowa miesiąca — tego miesiąca nie liczymy."
                    )
                    continue
                counted.append((pm, amount))
                self._row(pm, amount, "full")
                if not every:
                    sentences.append(
                        f"{name}: {days}, co najmniej połowa miesiąca — przychód liczymy tak, "
                        "jak go podano."
                    )
                continue
            if (_less_than_half(pm) and not every) or not (pm.days_worked or pm.fixed is not None):
                self._row(pm, None, "skipped")
                sentences.append(
                    f"{name}: {days}, mniej niż połowa obowiązującego czasu pracy — tego "
                    "miesiąca nie liczymy."
                )
                sources.append(p.half_skipped.sources)
                continue
            topped, formula = _topped(pm)
            counted.append((pm, topped))
            self._row(pm, topped, "topped-up")
            least = "" if every else ", co najmniej połowa obowiązującego czasu pracy"
            sentences.append(
                f"{name}: {days}{least} — wynagrodzenie uzupełniamy do pełnego miesiąca: "
                f"{formula} = {pln(topped)}."
            )
            sources.append(p.half_topped.sources)
            if pm.not_topped:
                sources.append(p.not_topped.sources)
        if full:
            n = len(full)
            if self.employee:
                label = "Miesiąc przepracowany" if n == 1 else "Miesiące przepracowane"
            else:
                label = "Miesiąc uwzględniony" if n == 1 else "Miesiące uwzględnione"
            sentences.insert(0, f"{label} w całości ({n}): razem {pln(sum(full, Decimal(0)))}.")
        skipped = [r for r in self.rows if r.status in ("outside", "before-insurance")]
        if skipped:
            sentences.append(
                f"Nie liczymy: {', '.join(_name(r.month) for r in skipped)} — poza miesiącami, "
                "z których liczy się podstawa."
            )
        given = {_month(pm.month) for pm in self.history.months}
        missing = [_key(m) for m in _months_between(start, last) if m not in given]
        if missing and counted:
            sentences.append(
                f"Brakuje zarobków z miesięcy: {', '.join(_name(m) for m in missing)}. Liczymy "
                "z podanych; gdy je dodasz, podstawa się przeliczy."
            )
        self.rows.sort(key=lambda r: r.month)
        if not counted:
            return self.no(
                f"żaden z podanych miesięcy nie wchodzi do podstawy. Liczy się {_span(start, last)}"
                ": podaj zarobki z tych miesięcy."
            )
        if self.capped:
            months = [_name(pm.month) for pm, amount in counted if amount < dec(pm.amount)]
            self._cap_step(f"za {', '.join(months)}")
        self.step(" ".join(sentences), *sources)
        total = sum((amount for _, amount in counted), Decimal(0))
        average = cents(total / len(counted))
        what = (
            "Przeciętne miesięczne wynagrodzenie"
            if self.employee
            else "Przeciętny miesięczny przychód (podstawa składki)"
        )
        self.step(
            f"{what}: {pln(total)} / {len(counted)} = {pln(average)}.",
            p.average.sources,
            [] if self.employee else p.non_employee_rules.sources,
        )
        return average

    def _row(self, pm: PayMonth, counted: Decimal | None, status: BaseMonthStatus) -> None:
        self.rows.append(
            BaseMonth(month=pm.month, amount=dec(pm.amount), counted=counted, status=status)
        )

    def _cap(self, amount: Decimal) -> Decimal:
        """A non-employee's contribution base counts up to the cap of the voluntary insurance."""
        cap = dec(self.params.benefit_base.voluntary_cap.value)
        if self.employee or amount <= cap:
            return amount
        self.capped = True
        return cap

    def _cap_step(self, where: str) -> None:
        cap = self.params.benefit_base.voluntary_cap
        self.step(
            "Podstawa składki na dobrowolne ubezpieczenie chorobowe nie może przekraczać "
            f"{pln(dec(cap.value))} miesięcznie, więc {where} liczymy {pln(dec(cap.value))}.",
            cap.sources,
        )

    def _finish(
        self, average: Decimal, months_from: str | None, months_to: str | None
    ) -> BenefitBase:
        """The bonuses, the contributions and the minimum: the base."""
        p, m = self.params.benefit_base, self.params.money
        bonuses = Decimal(0)
        for amount, rule, what in (
            (
                self.history.quarterly_bonuses,
                p.quarterly,
                "Premie i nagrody kwartalne wypłacone za cztery kwartały przed miesiącem, "
                "w którym powstało prawo",
            ),
            (
                self.history.annual_bonus,
                p.annual,
                "Składniki roczne (np. trzynastka, nagroda roczna) wypłacone za rok przed "
                "miesiącem, w którym powstało prawo",
            ),
        ):
            if amount:
                part = cents(dec(amount) / p.bonus_twelfth.value)
                bonuses += part
                self.step(
                    f"{what}: {pln(dec(amount))}; do podstawy wchodzi jedna dwunasta, {pln(part)}.",
                    rule.sources,
                    p.bonus_twelfth.sources,
                )
        gross = average + bonuses
        deducted = dec(m.contributions_percent.value)
        raw = cents(gross * (100 - deducted) / 100)
        article = "art. 3 pkt 3" if self.employee else "art. 3 pkt 4"
        contributions = [s for s in m.contributions_percent.sources if s.article == article]
        which = (
            " (składki na ubezpieczenia emerytalne, rentowe i chorobowe)" if self.employee else ""
        )
        self.step(
            f"{'Razem ' if bonuses else ''}{pln(gross)} pomniejszone o {percent(deducted)}{which}: "
            f"{pln(raw)}.",
            contributions,
            (p.deduction_employee if self.employee else p.deduction_non_employee).sources,
        )
        base = raw
        if self.employee:
            wage = dec(p.minimum_wage.value)
            least = cents(wage * (100 - deducted) / 100)
            rule = merge_sources(p.minimum.sources, p.minimum_wage.sources)
            if raw < least and self.history.full_time:
                base = least
                self.step(
                    "Przy pracy w pełnym wymiarze czasu pracy podstawa nie może być niższa od "
                    f"minimalnego wynagrodzenia ({pln(wage)}) po odliczeniu {percent(deducted)}, "
                    f"czyli od {pln(least)}: podstawą jest {pln(least)}.",
                    rule,
                )
            elif raw < least and self.history.full_time is None:
                self.step(
                    "Jeśli to praca w pełnym wymiarze czasu pracy, podstawa nie może być niższa "
                    f"niż {pln(least)} (minimalne wynagrodzenie {pln(wage)} po odliczeniu "
                    f"{percent(deducted)}). Napisz o tym asystentowi, a przeliczymy.",
                    rule,
                )
        return BenefitBase(
            parent=self.parent,
            work=self.work,
            right_from=self.day,
            months_from=months_from,
            months_to=months_to,
            pay=gross,
            deducted=deducted,
            base=base,
            detailed=bool(self.history.months),
            summary=self._summary(gross, raw, base, bool(bonuses), months_from is None),
            steps=self.steps,
            months=self.rows,
            sources=merge_sources(*(s.sources for s in self.steps)),
        )

    def _summary(
        self, gross: Decimal, raw: Decimal, base: Decimal, bonuses: bool, contract: bool
    ) -> str:
        """After "Podstawa wymiaru zasiłku: "."""
        deducted = percent(dec(self.params.money.contributions_percent.value))
        what = (
            "wynagrodzenia brutto"
            if self.employee
            else "podstawy składki na ubezpieczenie chorobowe"
        )
        counted = [r for r in self.rows if r.counted is not None]
        extra = []
        if contract:
            extra.append("za pełny miesiąc" if counted else "z umowy")
        elif self.history.months:
            extra.append(f"z {len(counted)} {_months_genitive(len(counted))}")
        if bonuses:
            extra.append("z premiami")
        if self.capped:
            extra.append(f"najwyżej {pln(dec(self.params.benefit_base.voluntary_cap.value))}")
        if not extra and base == raw:
            return f"{pln(gross)} {what} pomniejszone o {deducted}, czyli {pln(base)} miesięcznie."
        detail = f" ({', '.join(extra)})" if extra else ""
        end = f"czyli {pln(base)} miesięcznie."
        if base != raw:
            end = (
                f"czyli {pln(raw)}; przy pełnym etacie podstawa nie może być niższa, więc "
                f"{pln(base)} miesięcznie."
            )
        average = "" if contract else "przeciętnie "
        return f"{average}{pln(gross)} {what} miesięcznie{detail} pomniejszone o {deducted}, {end}"


def _followed(
    right_from: dt.date, parent: Parent, segments: Sequence[Segment]
) -> tuple[dt.date, Segment | None]:
    """Art. 43: the day the base is set for. Going back from `right_from` over the parent's sick
    leave and benefits that ended less than a calendar month before the next one began; returns
    the first day of the earliest and that period (None: no such period)."""
    earlier = sorted(
        (
            s
            for s in segments
            if s.lane == parent
            and s.tone == "leave"
            and s.id.startswith(FOLLOWS)
            and s.start < right_from
        ),
        key=lambda s: s.start,
        reverse=True,
    )
    day, follows = right_from, None
    for segment in earlier:
        if day >= month_later(segment.end + DAY):
            break
        day, follows = segment.start, segment
    return day, follows


def _follows_words(segment: Segment) -> tuple[str, str]:
    """("po zwolnieniu lekarskim w ciąży, które zaczęło się", "zaczęło się zwolnienie")."""
    if segment.id.startswith(SICK):
        return "po zwolnieniu lekarskim w ciąży, które zaczęło się", "zaczęło się zwolnienie"
    return (
        "po zasiłku w wysokości zasiłku macierzyńskiego, wypłacanym od",
        "zaczął się ten zasiłek",
    )


def month_later(day: dt.date) -> dt.date:
    """The same day a month later; the last day of a shorter month (31.01 -> 28.02)."""
    year, month = _shift((day.year, day.month), 1)
    return dt.date(year, month, min(day.day, calendar.monthrange(year, month)[1]))


def _topped(pm: PayMonth) -> tuple[Decimal, str]:
    """A month worked in part, topped up to a full month (art. 37 ust. 2 pkt 1-2; Załącznik):
    the fixed pay from the contract in full, the variable pay divided by the days worked and
    multiplied by the days required, the rest as paid. Returns the amount and how."""
    worked, required = pm.days_worked or 0, pm.days_required or 0
    kept = dec(pm.not_topped or 0)
    if pm.fixed is not None:
        variable = dec(pm.variable or 0)
        part = variable / worked * required if worked else Decimal(0)
        total = cents(dec(pm.fixed) + part + kept)
        formula = f"{pln(dec(pm.fixed))} stałego wynagrodzenia z umowy"
        if variable and worked:
            formula += f" + {pln(variable)} zmiennego / {worked} × {required}"
    else:
        rest = dec(pm.amount) - kept
        total = cents(rest / worked * required + kept)
        formula = f"{pln(rest)} / {worked} × {required}"
    if kept:
        formula += f" + {pln(kept)} bez uzupełniania"
    return total, formula


def _partial(pm: PayMonth) -> bool:
    return pm.days_worked is not None and pm.days_worked < (pm.days_required or 0)


def _less_than_half(pm: PayMonth) -> bool:
    return _partial(pm) and 2 * (pm.days_worked or 0) < (pm.days_required or 0)


def _month(text: str) -> Month:
    year, month = text.split("-")
    return int(year), int(month)


def _key(month: Month) -> str:
    return f"{month[0]:04d}-{month[1]:02d}"


def _shift(month: Month, by: int) -> Month:
    index = month[0] * 12 + month[1] - 1 + by
    return index // 12, index % 12 + 1


def _months_between(first: Month, last: Month) -> Iterator[Month]:
    month = first
    while month <= last:
        yield month
        month = _shift(month, 1)


def _count(first: Month, last: Month) -> int:
    return (last[0] - first[0]) * 12 + last[1] - first[1] + 1


def _name(key: str, capital: bool = False) -> str:
    """ "listopad 2025" ("Listopad 2025" at the start of a sentence)."""
    year, month = _month(key)
    name = f"{_NOMINATIVE[month - 1]} {year}"
    return name.capitalize() if capital else name


def _span(first: Month, last: Month) -> str:
    """ "od listopada 2025 do października 2026", or one month: "listopad 2026"."""
    if first == last:
        return _name(_key(first))
    return f"od {_GENITIVE[first[1] - 1]} {first[0]} do {_GENITIVE[last[1] - 1]} {last[0]}"


def _months_count(n: int) -> str:
    """After a number: "1 miesiąc", "3 miesiące", "5 miesięcy"."""
    if n == 1:
        return "miesiąc"
    if n % 10 in (2, 3, 4) and n % 100 not in (12, 13, 14):
        return "miesiące"
    return "miesięcy"


def _months_genitive(n: int) -> str:
    """After "z" and a number: "z 1 miesiąca", "z 12 miesięcy"."""
    return "miesiąca" if n == 1 else "miesięcy"


# The case explanation and our assumptions (CLAUDE.md, "Wyjaśnianie przypadku").


def add_base_notes(notes: list[CaseNote], timeline: Timeline, before: str) -> list[CaseNote]:
    """How each parent's base was computed, right before the note `before` (the amounts), when it
    took more than the amount given less the contributions."""
    seen: dict[str, int] = {}

    def note_id(parent: str) -> str:
        seen[parent] = seen.get(parent, 0) + 1
        return f"base-{parent}" + (f"-{seen[parent]}" if seen[parent] > 1 else "")

    extra = [
        CaseNote(
            id=note_id(b.parent),
            kind="computed",
            title=f"Podstawa wymiaru zasiłku {'mamy' if b.parent == 'mother' else 'taty'}: "
            f"{pln(b.base)}",
            text=" ".join(s.text for s in b.steps),
            sources=b.sources,
        )
        for b in timeline.bases
        if len(b.steps) > 2
    ]
    if not extra:
        return notes
    at = next((i for i, n in enumerate(notes) if n.id == before), len(notes))
    return [*notes[:at], *extra, *notes[at:]]


def base_assumptions(timeline: Timeline) -> list[str]:
    """What we assume about the bases, and where the materials leave a gap."""
    bases = timeline.bases
    if not bases:
        return []
    found = [
        "Za miesiąc, w którym powstało prawo do zasiłku, przyjmujemy miesiąc pierwszego dnia "
        "zasiłku (albo zwolnienia lekarskiego lub zasiłku, po którym następuje bez przerwy)."
    ]
    if any(not b.detailed for b in bases):
        found.append(
            "Podaną kwotę miesięczną traktujemy jako przeciętną z miesięcy, z których liczy się "
            "podstawa: tak jest, gdy przez cały ten czas była taka sama. Gdy się zmieniała "
            "(miesiące z nieobecnością, premie kwartalne i roczne, krótsze ubezpieczenie), podaj "
            "zarobki z kolejnych miesięcy, np. z zaświadczenia płatnika składek (Z-3 albo Z-3a): "
            "policzymy podstawę dokładnie."
        )
    if any(b.detailed for b in bases):
        found.append(
            "Miesięcy, których nie podano, nie zgadujemy: przeciętna jest z podanych miesięcy. "
            "Miesiąc uzupełniony do pełnego, przeciętną i jedną dwunastą premii zaokrąglamy do "
            "pełnych groszy."
        )
    if any(b.employee for b in bases):
        found.append(
            "Od wynagrodzenia brutto pracownika odejmujemy 13,71%: tyle wynoszą jego składki na "
            "ubezpieczenia emerytalne, rentowe i chorobowe według Załącznika ZUS. Wyciąg "
            "z ustawy wymienia te składki, ale nie podaje ich stawek."
        )
    if any(not b.employee for b in bases):
        found.append(
            "Przy umowie zlecenia i własnej firmie liczymy z podstawy składki na dobrowolne "
            "ubezpieczenie chorobowe, najwyżej 23 550,00 zł miesięcznie (Załącznik ZUS)."
        )
    first_paid = {
        parent: min((p.start for p in timeline.payments if p.lane == parent), default=None)
        for parent in ("mother", "father")
    }
    if any(first_paid[b.parent] not in (None, b.right_from) for b in bases):
        found.append(
            "Przerwę krótszą niż miesiąc kalendarzowy liczymy od dnia po końcu poprzedniego "
            "okresu do tego samego dnia następnego miesiąca. Wynagrodzenie chorobowe od "
            "pracodawcy traktujemy przy tym jak zasiłek: oblicza się je według zasad podstawy "
            "zasiłku chorobowego (art. 92 § 2 Kodeksu pracy)."
        )
    for parent, who in (("mother", "mamy"), ("father", "taty")):
        paid = sorted((p for p in timeline.payments if p.lane == parent), key=lambda p: p.start)
        if any(b.start >= month_later(a.end + DAY) for a, b in zip(paid, paid[1:], strict=False)):
            found.append(
                f"Między okresami zasiłku {who} jest przerwa co najmniej miesiąca: ZUS ustala "
                "wtedy podstawę na nowo, z miesięcy przed nowym okresem. Liczymy wszystkie okresy "
                "z pierwszej podstawy, bo późniejszych zarobków nie znamy."
            )
    return found
