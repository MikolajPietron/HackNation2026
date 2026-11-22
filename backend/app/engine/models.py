"""Engine input (Scenario) and output (Timeline). The same models are the API schema.

Phases covered: section A of the guide (pages 5-6): 1 "Przygotowanie do porodu", 2 "Urodzenie
dziecka" and 3 "Szczególna sytuacja" (stillbirth or death of the child); and section B (pages 7-8),
the father: paternity leave, his part of parental leave, taking over maternity leave. With the
Labour Code provisions behind them. Section G (page 9), the amount of the benefit, with the
ustawa zasiłkowa behind it: `Payment`; the benefit base in detail (ustawa art. 36-52, the ZUS
Załącznik): `PayHistory` in, `BenefitBase` out.
"""

import datetime as dt
from decimal import Decimal
from fractions import Fraction
from typing import Annotated, Literal, Self

from pydantic import BaseModel, BeforeValidator, Field, PlainSerializer, model_validator

Lane = Literal["mother", "father", "child", "documents"]
Tone = Literal["leave", "work", "option"]
"""leave = leave the mother takes, work = she keeps working, option = possible, not decided yet."""

Role = Literal["mother", "father"]
Work = Literal["employment", "contract", "business", "none"]
Earnings = Literal["under-5k", "5k-8k", "8k-12k", "over-12k", "unknown"]
BirthWeek = Literal["before-28", "28-37", "after-37"]
"""When the child was born, as the Labour Code art. 180² § 1 divides it: before the end of the
28th week of pregnancy, after it but before the end of the 37th, or after the 37th."""
TakenIn = Literal["adoption", "foster"]
"""Guide section D: adoption = took the child in and asked the guardianship court to start
adoption proceedings; foster = a non-professional foster family (rodzina zastępcza
niezawodowa)."""


class SourceRef(BaseModel):
    """A literal quote: from the guide (section and pages), from the Labour Code ("kp") or from
    the ustawa zasiłkowa ("ustawa"; both: article), or from the ZUS Załącznik to the challenge
    ("zalacznik": section, as named in zalacznik.json). The request forms also quote two
    regulations (article: "§ 15 ust. 1", "zał. 6"): "rozp_wnioski", of 11 March 2025, on the
    leave requests and their attachments, and "rozp_zasilki", of 27 September 2026, on the
    documents for the benefits (assistant/rozporzadzenia.json). "poradnik": the ZUS Poradnik for
    parents (2026), source no. 4, only where the others are silent; `page` (and `page_to`) is the
    number printed on the page (assistant/poradnik.json)."""

    doc: Literal[
        "przewodnik", "kp", "ustawa", "zalacznik", "rozp_wnioski", "rozp_zasilki", "poradnik"
    ]
    quote: str
    section: str | None = None
    page: int | None = None
    page_to: int | None = None
    """Set when the quote runs over a page break: it starts on `page` and ends on `page_to`."""
    article: str | None = None


MotherEventKind = Literal["incapacity", "hospital", "death", "abandonment"]
"""Guide section B, "Sytuacje szczególne": the mother has a certificate of inability to live
independently, is in hospital, died, or abandoned the child."""


class MotherEvent(BaseModel):
    """A special situation in which the father takes over maternity leave early."""

    kind: MotherEventKind
    start: dt.date
    """Incapacity: the day the father takes over (when the mother had no sickness insurance:
    the day her incapacity arose, art. 180 § 15); hospital: the first day in hospital; death,
    abandonment: the day it happened."""
    end: dt.date | None = None
    """Hospital only: the last day in hospital; None = still there."""

    @model_validator(mode="after")
    def end_only_for_hospital(self) -> Self:
        if self.end is not None and self.kind != "hospital":
            raise ValueError("Datę końca podaje się tylko przy pobycie mamy w szpitalu.")
        if self.end is not None and self.end < self.start:
            raise ValueError("Pobyt w szpitalu nie może skończyć się przed jego początkiem.")
        return self


class ChildLoss(BaseModel):
    """A child of this birth was stillborn or died."""

    stillborn: bool = False
    died_on: dt.date | None = None
    """Date of death of a child born alive; None for a stillborn child."""

    @model_validator(mode="after")
    def date_matches_kind(self) -> Self:
        if self.stillborn and self.died_on is not None:
            raise ValueError("Przy martwym urodzeniu nie podaje się osobnej daty śmierci.")
        if not self.stillborn and self.died_on is None:
            raise ValueError("Potrzebna jest data śmierci dziecka.")
        return self


class HospitalStay(BaseModel):
    """One stay of the child in hospital after the birth. Dates are inclusive."""

    start: dt.date
    end: dt.date | None = None
    """None = the child is still in hospital."""

    @model_validator(mode="after")
    def ends_after_it_starts(self) -> Self:
        if self.end is not None and self.end < self.start:
            raise ValueError("Pobyt w szpitalu nie może skończyć się przed jego początkiem.")
        return self


JobLossReason = Literal["bankruptcy", "liquidation", "employer-death", "unlawful", "other"]
"""Why the mother's work ended in pregnancy. The guide (page 4) names the employer's bankruptcy,
liquidation or death, and a termination that broke the law; "other" is any other end of work
(e.g. a contract that ended, a business closed), guide section H, risk 3."""


class JobLoss(BaseModel):
    """The mother's work ended in pregnancy. Recorded only when the parent says so."""

    ended_on: dt.date
    """The last day of the employment (or of the contract or business)."""
    reason: JobLossReason
    court_confirmed: bool | None = None
    """Unlawful termination only: a final court judgment confirmed it. None = not known."""

    @model_validator(mode="after")
    def court_only_for_unlawful(self) -> Self:
        if self.court_confirmed is not None and self.reason != "unlawful":
            raise ValueError("Wyrok sądu dotyczy tylko rozwiązania umowy z naruszeniem prawa.")
        return self


RehabStatus = Literal["applied", "granted", "refused"]
"""The rehabilitation benefit (świadczenie rehabilitacyjne) after the sickness benefit in
pregnancy, as the parent told it: applied for and not decided yet, granted, or refused."""


class FosterBefore(BaseModel):
    """Adoption after foster care (Labour Code art. 183 § 7-§ 8): before asking the court to
    start adoption proceedings, the person had the child as a non-professional foster family and
    used leave for it. Recorded only when the parent says so."""

    leave_start: dt.date | None = None
    leave_end: dt.date | None = None
    """The leave on the terms of maternity leave used as a foster family: first and last day.
    None = no such leave."""
    parental_weeks: int | None = Field(default=None, ge=0)
    """Weeks of parental leave used as a foster family. None = none."""

    @model_validator(mode="after")
    def both_dates_or_none(self) -> Self:
        if (self.leave_start is None) != (self.leave_end is None):
            raise ValueError(
                "Potrzebny jest pierwszy i ostatni dzień urlopu w rodzinie zastępczej."
            )
        if self.leave_start and self.leave_end and self.leave_end < self.leave_start:
            raise ValueError("Urlop nie może skończyć się przed swoim początkiem.")
        return self


def _exact_fraction(value: object) -> object:
    """A part of full time as written: 0.4 is 2/5 (not the binary float), "40%" and "0,4" too."""
    if isinstance(value, float):
        return Fraction(str(value))
    if isinstance(value, str):
        text = value.strip().replace(",", ".")
        if text.endswith("%"):
            return Fraction(text[:-1].strip()) / 100
        return text
    return value


WorkFraction = Annotated[Fraction, BeforeValidator(_exact_fraction)]
"""Part-time work as a part of full time: "1/2", "2/5", 0.25, "40%"."""


class ParentalPart(BaseModel):
    """One part of parental leave as the parents plan it (guide B.3 and E; Labour Code
    art. 182¹ᶜ, 182¹ᵉ, 182¹ᶠ). Validated against the rules by the engine (parental_plan.py)."""

    parent: Role
    weeks: int = Field(ge=1)
    """Weeks of leave this part takes from the pool, without the extension from working."""
    start: dt.date | None = None
    """None = right after the previous part of the plan (the first part: where the timeline
    shows that parent's parental leave without a plan)."""
    with_previous: bool = False
    """Starts on the same day as the previous part of the plan: both parents at once."""
    work_fraction: WorkFraction | None = None
    """Part-time work during this part, as a part of full time (at most 1/2)."""
    work_weeks: int | None = Field(default=None, ge=1)
    """Weeks of this part combined with work, from its first day; None = the whole part."""


Pay = Annotated[float, Field(gt=0)]
"""A monthly amount in PLN."""


class ScenarioError(ValueError):
    """The scenario breaks a rule. Polish message, shown to the parent or the assistant."""


PayerSize = Literal["over-20", "up-to-20", "unknown"]
"""How many people the payer of contributions (the employer, or the principal of a contract of
mandate) reports to sickness insurance: more than 20 = it pays the benefit itself, otherwise ZUS
does (guide page 1, footnote 1). "unknown" = the parent does not know."""


# The benefit base in detail (ustawa zasiłkowa art. 36-52, the ZUS Załącznik; engine/base.py):
# the data of the payer's certificate (Z-3 for an employee, Z-3a for a contract), typed by the
# user.

YearMonth = Annotated[str, Field(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")]
"""A calendar month: "2026-03"."""


class PayMonth(BaseModel):
    """One calendar month of a parent's pay before the right to the benefit, as the payer's
    certificate (or a payslip, or the declared contribution base) gives it."""

    month: YearMonth
    amount: float = Field(ge=0)
    """In PLN. Employee: the gross pay for that month (the base of the sickness contribution),
    monthly components only: quarterly and annual ones go to `PayHistory`. Contract, business:
    the base of the sickness contribution for that month."""
    days_required: int | None = Field(default=None, ge=1)
    """A month not worked in full: the days the parent was obliged to work that month (a
    non-employee: the days of the month). None = worked in full."""
    days_worked: int | None = Field(default=None, ge=0)
    """The days actually worked that month (the rest: a justified absence, e.g. sick leave)."""
    fixed: float | None = Field(default=None, ge=0)
    """Employee, a month not worked in full: the fixed monthly pay set in the contract, taken in
    full. None = the whole `amount` is topped up by days."""
    variable: float | None = Field(default=None, ge=0)
    """Employee, with `fixed`: the variable pay for the days worked, topped up by days."""
    not_topped: float | None = Field(default=None, ge=0)
    """Employee: the part of `amount` taken as paid, never topped up (overtime, night work
    allowance, commission)."""

    @model_validator(mode="after")
    def days_make_sense(self) -> Self:
        if (self.days_worked is None) != (self.days_required is None):
            raise ValueError(
                "Przy miesiącu przepracowanym w części podaj oba: dni obowiązujące do "
                "przepracowania i dni przepracowane."
            )
        if (self.days_worked or 0) > (self.days_required or 0):
            raise ValueError("Dni przepracowanych nie może być więcej niż dni obowiązujących.")
        if (self.not_topped or 0) > self.amount:
            raise ValueError("Część nieuzupełniana nie może być większa niż kwota za miesiąc.")
        return self


class PayHistory(BaseModel):
    """What a parent's benefit base is computed from, in detail. Without `months` the monthly
    amount (`mother_pay`, `father_pay`) stands for the average of the months; the other fields
    apply either way."""

    months: list[PayMonth] = []
    quarterly_bonuses: float | None = Field(default=None, ge=0)
    """Employee: quarterly bonuses and awards paid for the four quarters before the month the
    right arose, together."""
    annual_bonus: float | None = Field(default=None, ge=0)
    """Employee: annual pay (e.g. the thirteenth salary, an annual award) paid for the year
    before the month the right arose."""
    full_time: bool | None = None
    """Employee: works full time, so the base is not lower than the minimum."""
    insured_from: dt.date | None = None
    """The first day of the uninterrupted sickness insurance with this payer (on this contract,
    in this business). None = not known: the months given are taken as they are."""
    contract_pay: float | None = Field(default=None, gt=0)
    """The monthly pay set in the contract: the base when the right arises before a full
    calendar month of insurance."""

    @model_validator(mode="after")
    def one_entry_per_month(self) -> Self:
        months = [m.month for m in self.months]
        if len(months) != len(set(months)):
            raise ValueError("Każdy miesiąc można podać tylko raz.")
        self.months = sorted(self.months, key=lambda m: m.month)
        return self


class Scenario(BaseModel):
    """What the onboarding and the interview have established. None = not known yet."""

    # The person filling in (onboarding). Work and earnings are that person's own: the
    # father's when the father fills in. Phase 2 uses the mother's work; earnings wait.
    role: Role | None = None
    work: Work | None = None
    earnings: Earnings | None = None
    mother_work: Work | None = None
    """How the mother works, asked when somebody else fills in. See `mothers_work`."""
    father_work: Work | None = None
    """How the father works, asked when somebody else fills in. See `fathers_work`."""

    # The child.
    child_born: bool | None = None
    due_date: dt.date | None = None
    """Expected due date (przewidywana data porodu)."""
    birth_date: dt.date | None = None
    """Actual date of birth, once the child is born."""
    children_count: int | None = Field(default=None, ge=1, le=10)
    """Children born in one delivery (twins = 2)."""

    # Phase 1.
    leave_before_birth_weeks: int | None = Field(default=None, ge=0)
    """Weeks of maternity leave before the birth; 0 = the mother works until the birth."""
    has_medical_certificate: bool | None = None
    """Medical certificate of the expected due date, needed for leave before the birth."""
    leave_start: dt.date | None = None
    """The first day of maternity leave before the birth, as a date. Set when an expected child
    is born and the planned leave (weeks before the due date) had already started: the birth
    rarely falls on the due date. For a born child it wins over `leave_before_birth_weeks`."""

    # Phase 2.
    mother_insured: bool | None = None
    """Voluntary sickness insurance of a mother on a contract or with her own business."""
    za_zyciem: bool | None = None
    """The child has the "Za życiem" certificate. None = nobody said so (counted as no)."""
    hospital_care: bool | None = None
    """Born child: premature, or in hospital after the birth. None = not asked yet."""
    birth_week: BirthWeek | None = None
    birth_weight_up_to_1000g: bool | None = None
    """Birth weight not above 1000 g (the lightest child of a multiple birth)."""
    hospital_stays: list[HospitalStay] = []
    """Stays in hospital after the birth (of the child that stayed longest)."""

    # Phase 3.
    losses: list[ChildLoss] = []
    """Children of this birth who were stillborn or died. Recorded only when the parent says so."""

    # Section B: the father.
    father_insured: bool | None = None
    """Voluntary sickness insurance of a father on a contract or with his own business."""
    father_takes_over: bool | None = None
    """The mother leaves the rest of maternity leave to the father after at least 14 weeks."""
    mother_weeks_before_takeover: int | None = Field(default=None, ge=1)
    """Weeks after the birth the mother uses before the father takes over (default 14)."""
    mother_event: MotherEvent | None = None

    # Applications and protection (guide A.4, I)
    mother_payer_size: PayerSize | None = None
    """The mother's employer (or principal): does it report more than 20 people? None = not
    asked yet. Not asked for a business: the mother files ZAM straight with ZUS."""
    father_payer_size: PayerSize | None = None
    """The same for the father's employer (or principal)."""
    # Pregnancy (guide: sickness benefit, job loss, risks)
    sick_leave: bool | None = None
    """The mother is (or was) on sick leave in this pregnancy. None = not asked."""
    sick_leave_start: dt.date | None = None
    sick_leave_end: dt.date | None = None
    """The last day of the sick leave; None = until the birth."""
    insured_since: dt.date | None = None
    """The first day of the mother's uninterrupted sickness insurance (the 30 or 90 days)."""
    insured_in_pregnancy: bool | None = None
    """Her contract or business began during this pregnancy (guide section H, risk 1)."""
    mother_over_50: bool | None = None
    """An employed mother turned 50 before the calendar year of the sick leave."""
    contribution_base_raised: bool | None = None
    """She raised the base of her contributions in pregnancy (section H, risk 2)."""
    job_loss: JobLoss | None = None
    # Parental leave with work (guide section E)
    parental_parts: list[ParentalPart] = []
    """How the parents split parental leave, in the order they take it, and where they combine
    it with part-time work. Recorded only when the parent says so. Empty = no plan: the timeline
    shows each parent's share as an option."""
    mother_parental_after_first_year: bool | None = None
    """The mother takes no day of parental leave in the child's first year: she is back at work
    after maternity leave (or after the father took it over) and leaves her share for later, or
    unused. Her share is then drawn from the first birthday, and after the request for 81,5%
    the benefit for maternity leave is topped up once to 100% (ustawa art. 31 ust. 3g-4).
    Recorded only when the parent says so; None = not said."""
    # Adoption and foster care (guide section D)
    taken_in: TakenIn | None = None
    """The child was taken in for upbringing. Then `birth_date` is the child's date of birth
    (the youngest child's, when several are taken in at once), `children_count` the children
    taken in at once, and nothing about pregnancy or the birth applies."""
    taken_in_on: dt.date | None = None
    """The day the child was taken in; for adoption the day the child was taken in and the court
    asked to start adoption proceedings (the later of the two)."""
    school_postponed: bool | None = None
    """Foster care: compulsory schooling of the child was postponed."""
    adoption_final: bool | None = None
    """Adoption: the court's adoption ruling is final (prawomocne)."""
    adoption_final_on: dt.date | None = None
    """The day the adoption ruling became final."""
    # Amounts (guide section G).
    mother_pay: Pay | Literal["unknown"] | None = None
    """The mother's monthly amount the benefit base comes from, in PLN, as she gave it: gross
    salary for an employee, the base of the sickness contribution on a contract or with a
    business; the average of the last 12 months. "unknown" = she did not give it (no amounts).
    Never taken from the onboarding range (`earnings`)."""
    father_pay: Pay | Literal["unknown"] | None = None
    """The same for the father."""
    rate_815: bool | None = None
    """The mother files (or filed) the written request for 81,5% within 21 days after the
    birth: True = 81,5% for maternity and parental leave, False = 100% and 70%."""
    # The rehabilitation benefit after 270 days of sick leave in pregnancy (ustawa art. 18-19).
    rehab_benefit: RehabStatus | None = None
    """What the parent said about it; recorded only when the parent says so, never asked."""
    rehab_benefit_end: dt.date | None = None
    """The last day of the period it was granted (or applied) for, when the parent gave it."""
    # Adoption and foster care, edge cases (Labour Code art. 183 § 2, § 7-§ 8).
    taken_in_handover: bool | None = None
    """The person on leave on the terms of maternity leave passes the rest of it to the other
    parent (art. 183 § 2 with art. 180 § 4-5). Recorded only when the parent says so."""
    taken_in_handover_after_weeks: int | None = Field(default=None, ge=1)
    """Weeks of that leave used before passing it on; None = the minimum (14)."""
    foster_before: FosterBefore | None = None
    """Adoption after foster care: the leave already used as a foster family."""
    # The benefit base in detail (engine/base.py).
    mother_pay_history: PayHistory | None = None
    """The mother's pay month by month and the rest of what her base depends on, as the user
    typed it (e.g. from the payer's certificate Z-3 or Z-3a). Months given win over
    `mother_pay`."""
    father_pay_history: PayHistory | None = None
    """The same for the father."""
    # --- Contribution debt (engine/debt.py; ustawa zasiłkowa art. 2a) ---
    mother_contribution_debt: float | None = Field(default=None, ge=0)
    """The mother runs a business: her debt of social insurance contributions on the day the
    right to the benefit arises, in PLN, as a ZUS document states it. None = not known (not
    asked in the interview; read from an example case)."""
    father_contribution_debt: float | None = Field(default=None, ge=0)
    """The same for the father."""
    # --- end contribution debt ---

    @property
    def anchor_date(self) -> dt.date | None:
        """The date the timeline counts from: the actual birth once born, else the due date;
        for a child taken in, the day of taking in."""
        if self.taken_in is not None:
            return self.taken_in_on
        return self.birth_date if self.child_born else self.due_date

    def prenatal_days(self, birth: dt.date) -> int:
        """Days of maternity leave before the actual birth (0 = none)."""
        if self.child_born and self.leave_start is not None:
            return max(0, (birth - self.leave_start).days)
        return (self.leave_before_birth_weeks or 0) * 7

    @property
    def mothers_work(self) -> Work | None:
        """The mother's work: her own answer when she fills in, otherwise what was said of her."""
        return self.work if self.role == "mother" else self.mother_work

    @property
    def fathers_work(self) -> Work | None:
        """The father's work: his own answer when he fills in, otherwise what was said of him."""
        return self.work if self.role == "father" else self.father_work


# F9 "Zostawiacie na stole" and F10 "Punkty bez powrotu" (ZADANIA B.8; engine/leftover.py).


class Irreversible(BaseModel):
    """F10, a point of no return: after the marker's day something is lost for good, as the
    sources say."""

    lost: str
    """What is lost after that day, in one Polish sentence."""
    days_left: int
    """Days from today to that day: 0 = today is the last day, negative = it has passed."""
    sources: list[SourceRef]
    """The quotes that say so, taken from the marker's own sources."""


LeftoverKind = Literal["leave", "choice"]
"""leave = days of leave (or of the benefit for that time) not used yet; choice = an option that
closes on its last day (the request for 81,5%)."""


class Leftover(BaseModel):
    """F9: something the family can still use and loses if they do nothing (leftover.py)."""

    id: str
    """"left-" + the period's id ("left-parental-father"), "left-parental-pool" (weeks a plan
    leaves out) or "left-rate-815"."""
    kind: LeftoverKind
    parent: Role | None
    """Whose right; None = either parent."""
    title: str
    text: str
    days: int | None
    """Days that can still be used; None for a choice."""
    amount: float | None
    """PLN lost if nothing is done: the benefit for those days, as the payments give it; for a
    choice, how much more the other option pays for the periods on the timeline (0 when it pays
    no more). None = no base is known yet."""
    last_day: dt.date
    """The last day it can still be used (for a choice: the request filed)."""
    start_by: dt.date | None
    """The last day to start so that all `days` fit before `last_day`."""
    segment_id: str | None = None
    marker_id: str | None = None
    """The point of no return on the timeline (F10), when there is one."""
    sources: list[SourceRef]


class Segment(BaseModel):
    """A period on the timeline. Dates are inclusive."""

    id: str
    lane: Lane
    tone: Tone
    title: str
    start: dt.date
    end: dt.date
    days: int
    summary: str
    details: list[str] = []
    sources: list[SourceRef]


class Marker(BaseModel):
    """A single day that matters."""

    id: str
    lane: Lane
    label: str
    title: str
    date: dt.date
    summary: str
    details: list[str] = []
    sources: list[SourceRef]
    irreversible: Irreversible | None = None
    """F10: after this day a right is lost for good (leftover.py)."""


# Request forms (ZADANIA B.3): each request on the timeline as a form to fill in, filled from
# the scenario and the timeline (engine/forms.py). Only what the sources name: the regulation on
# the leave requests (rozp_wnioski), the annexes of the regulation on the benefit documents
# (rozp_zasilki: annex 6 is the data of the ZAM request, annex 1 of the sickness benefit) and the
# guide. The ZUS forms themselves (ZAM, ZAS-53) are on www.zus.pl, not in our materials. A
# checker of filled requests (ZADANIA B.9, F23) reads fields by `id`.

FormFieldKind = Literal["text", "date", "period", "statement"]
"""text = words or numbers; date = one day (`start`); period = from `start` to `end`;
statement = a declaration the person makes in the request (`value` says what it is about)."""

Addressee = Literal["employer", "payer", "zus", "payer-or-zus"]
"""Who the request goes to: the employer; the payer of contributions (the principal of a
contract of mandate) that pays the benefit itself; ZUS; the payer or ZUS, by how many people the
payer reports to sickness insurance (not known yet)."""


class FormField(BaseModel):
    """One piece of a request, as its source names it."""

    id: str
    """Stable within the form (e.g. "employee-name", "leave-period", "child-birth-date")."""
    label: str
    kind: FormFieldKind
    value: str | None = None
    """Filled in by the app, in Polish (dates DD.MM.RRRR). None = the person types it in."""
    start: dt.date | None = None
    end: dt.date | None = None
    """The filled value as dates: kind "date" — `start`; kind "period" — `start` to `end`."""
    personal: bool = False
    """Personal data (names, PESEL, addresses, NIP, bank account, signature): the app never
    fills it in and never asks for it; the person types it in the form."""
    required: bool = True
    """False = only in the case the source names (e.g. the other parent's data "jeżeli są
    niezbędne")."""
    hint: str | None = None
    """Where the value comes from, or what to write in."""
    sources: list[SourceRef]


class FormAttachment(BaseModel):
    """A document attached to the request."""

    id: str
    label: str
    required: bool = True
    """False = only in the case `hint` describes (e.g. when the payer, not ZUS, pays)."""
    hint: str | None = None
    sources: list[SourceRef]


class FormNote(BaseModel):
    """A line about the whole request, e.g. that the ZUS form is on www.zus.pl."""

    text: str
    sources: list[SourceRef] = []


# The request as a letter (engine/request_letters.py): what an employee hands the employer,
# laid out by the front on an A4 page. Personal data never reaches the server, so every piece of
# it is a placeholder: `{{field-id}}` in any string of the letter (and of `HrMessage`), where
# `field-id` is one of `Letter.fields` — the form's own field id when the form has that field
# ("employee-name", "father-name", "child-name", "child-birth-date"), otherwise a letter field
# ("letter-place", "letter-date", "applicant-address", "employer"). The front replaces each token
# with what the parent typed, or with a dotted line to fill in by hand.

LetterMeaning = Literal[
    "applicant-name",
    "applicant-address",
    "employer",
    "child-name",
    "child-birth-date",
    "place",
    "date",
]
"""What a placeholder stands for, so values typed once fill every letter: the applicant is
`RequestForm.applicant` (the mother or the father), "employer" is the applicant's employer."""


class LetterField(BaseModel):
    """A placeholder of the letter: `{{id}}` in its text."""

    id: str
    label: str
    """In Polish: "Imię i nazwisko pracownicy", "Nazwa i adres pracodawcy"."""
    meaning: LetterMeaning
    personal: bool
    """Names, addresses, the employer, the place: typed in the browser, never sent anywhere."""


class LetterParagraph(BaseModel):
    """One paragraph of the letter's body, in the order printed."""

    kind: Literal["request", "statement", "choice"]
    """request = the operative paragraph ("Na podstawie … wnoszę o …"); statement = a
    declaration the regulation requires, filled from the timeline; choice = a declaration the
    parent decides: `text` is the lead-in, `options` the answers to tick one of."""
    text: str
    options: list[str] = []


class Letter(BaseModel):
    """The request as an employee writes it to the employer. Our wording of what the sources
    require (the quotes stay in the form); the dates come from the timeline."""

    place_date: str
    """Top right: "{{letter-place}}, dnia {{letter-date}}"."""
    applicant: list[str]
    """Top left, one line each: the applicant's name and address (placeholders)."""
    addressee: list[str]
    """Right, below: "Pracodawca" and the employer's name and address (a placeholder)."""
    title: str
    body: list[LetterParagraph]
    attachments: list[str]
    """"Załączniki:", numbered; empty = no list."""
    signature: str
    """Under the signature line: "(czytelny podpis pracownicy)"."""
    legal_basis: str
    """Small print at the bottom: "Podstawa prawna: art. … Kodeksu pracy; § … rozporządzenia …"."""
    fields: list[LetterField]
    """Every placeholder used in the letter and in `RequestForm.hr_message`, in order."""


class HrMessage(BaseModel):
    """A short e-mail to the employer's HR with the request attached; placeholders as in the
    letter."""

    subject: str
    body: str
    """Lines separated by "\\n"."""


class OfficialForm(BaseModel):
    """A ZUS form the parent fills in on www.zus.pl: our materials give its data (the form's
    `fields`, printed as `sheet_title`), not the form itself."""

    code: str
    """ "ZAM", "ZAS-53"."""
    name: str
    """ "wniosek o zasiłek macierzyński" — as the guide names it."""
    where: str
    """The guide's own words: "www.zus.pl (w zakładce Wzory formularzy, Zasiłki)"."""
    url: str
    """ "https://www.zus.pl" — the guide gives no deeper address."""
    sheet_title: str
    """ "Dane do wpisania do formularza ZAM"."""
    sources: list[SourceRef]


class RequestForm(BaseModel):
    """A request on the timeline as a form: who files it, with whom, on what legal basis, what
    it contains and what goes with it."""

    title: str
    applicant: Role
    addressee: Addressee
    addressee_label: str
    """In Polish: "Pracodawca mamy", "ZUS", "Płatnik składek (zleceniodawca) albo ZUS"."""
    official_form: str | None = None
    """The ZUS form ("ZAM", "ZAS-53"), on www.zus.pl. None = a request the employee writes:
    the regulation gives its content, not a template."""
    legal_basis: list[SourceRef]
    """The provisions that name this request and say what it contains."""
    start: dt.date | None = None
    end: dt.date | None = None
    """The period on the timeline the request is for."""
    fields: list[FormField] = []
    attachments: list[FormAttachment] = []
    notes: list[FormNote] = []
    letter: Letter | None = None
    """The request as a letter to the employer; only for requests filed with the employer."""
    hr_message: HrMessage | None = None
    """An e-mail to HR with the letter attached; only with `letter`."""
    official: OfficialForm | None = None
    """Where the ZUS form is (with `official_form`); the fields are the data to copy into it."""


class Document(BaseModel):
    """A document the parent needs by a given day."""

    id: str
    label: str
    title: str
    needed_by: dt.date
    done: bool
    rule: str
    segment_id: str | None = None
    sources: list[SourceRef]
    # Deadlines and forms (ZADANIA B.3, B.4).
    deadline: dt.date | None = None
    """The last day to file it under a deadline of the Labour Code ("w terminie nie krótszym niż
    N dni przed") or of the benefit act (the request for 81,5%, art. 30a: "nie później niż 21 dni
    po porodzie"), counted for the day on the timeline; it may have passed (then `needed_by` is
    today for an option the parents can still move, and `rule` says from when a request filed
    today is in time). None = the materials give no deadline: `needed_by` is only the day the
    leave, the benefit or the sick leave it is for starts, never a deadline."""
    form: RequestForm | None = None
    """The request as a form to fill in; None for documents that are not requests."""


class Payment(BaseModel):
    """The money for one period on the timeline: the "Pieniądze" lane. The maternity benefit
    (guide section G) and in pregnancy the employer's sick pay, the sickness benefit and the
    benefit equal to the maternity benefit (money.py, `PAID`). Amounts in PLN, rounded to grosze.
    `segment_id` is the period it pays for; dates and days are that period's, or a piece of it
    when the rate changes within it (part-time work, the other parent's own weeks)."""

    id: str
    """"pay-" + `segment_id`; a later piece of the same period adds "-part-<n>"."""
    segment_id: str
    lane: Literal["mother", "father"]
    """Whose benefit: the parent on that period's lane."""
    title: str
    start: dt.date
    end: dt.date
    days: int
    rate: float
    """Percent of the benefit base (of the pay, for sick pay): 100, 70 or 81.5."""
    base: float
    """Monthly benefit base (podstawa wymiaru zasiłku)."""
    monthly: float
    """`base` × `rate`: the benefit for a whole month; while parental leave is combined with
    part-time work, less in proportion to the working time."""
    daily: float
    """One thirtieth of the monthly benefit."""
    total: float
    """`daily` × `days`: the benefit for the whole period."""
    summary: str
    details: list[str] = []
    """The calculation, step by step."""
    sources: list[SourceRef]
    one_off: bool = False
    """A single payment, not a period: the one-off top-up of the benefit for maternity leave to
    100% (ustawa art. 31 ust. 4; money.py). Then `start` = `end` = the day it is shown on (the
    child's first birthday), `segment_id` is the maternity leave it tops up, `days` its days,
    `rate` the difference of the rates (100 − 81,5), `daily` and `monthly` the difference per
    day and per month, and `total` = `daily` × `days`, all of it in the month of `start`."""


Amount = Annotated[Decimal, PlainSerializer(float, return_type=float, when_used="json")]
"""PLN, exact in the engine (Decimal), a number in the API."""


class BaseStep(BaseModel):
    """One step of computing a benefit base ("Dlaczego tyle?"), with the rules it applies."""

    text: str
    sources: list[SourceRef] = []


BaseMonthStatus = Literal["full", "topped-up", "skipped", "outside", "before-insurance"]
"""full = taken as paid; topped-up = worked at least half, topped up to a full month; skipped =
worked less than half; outside = not among the 12 months before the month of the right;
before-insurance = before the insurance (with this payer) began."""


class BaseMonth(BaseModel):
    """A month the parent gave, and what the base takes from it."""

    month: str
    amount: Amount
    counted: Amount | None
    """What enters the average (topped up, capped); None = not counted."""
    status: BaseMonthStatus


class BenefitBase(BaseModel):
    """One parent's monthly benefit base (podstawa wymiaru zasiłku) and how it was computed,
    step by step, each step with its sources (engine/base.py)."""

    parent: Role
    work: Work
    right_from: dt.date
    """The day the right arose that the base is set for: the first day of the parent's first
    paid period, or of an earlier benefit it follows without a break of a month."""
    months_from: str | None
    months_to: str | None
    """The calendar months the base comes from ("2025-11" to "2026-10"); None = from the
    contract (the right arose before a full month of insurance)."""
    pay: Amount
    """The monthly average before the deduction: gross pay (or the contribution base), with a
    twelfth of quarterly and annual bonuses."""
    deducted: Amount
    """Percent of `pay` deducted for the contributions."""
    base: Amount
    """The monthly benefit base."""
    detailed: bool
    """Computed from the months the parent gave, not from one monthly amount."""
    summary: str
    """The base in one sentence, after "Podstawa wymiaru zasiłku: "."""
    steps: list[BaseStep]
    months: list[BaseMonth] = []
    sources: list[SourceRef]
    """Every step's sources, each quote once."""

    @property
    def employee(self) -> bool:
        return self.work == "employment"


# F4 "Ile wpływa w którym miesiącu i kto płaci" (ZADANIA B.12; engine/monthly.py).

PaidBy = Literal["employer", "payer", "zus", "payer-or-zus"]
"""Who pays the money out: employer = the employer's own sick pay in pregnancy (wynagrodzenie
chorobowe); payer = the payer of contributions pays the benefit itself, as it reports more than
20 people to sickness insurance (an employee's employer, the principal of a contract of
mandate); zus = ZUS; payer-or-zus = the payer or ZUS, by how many people the payer reports (not
known yet)."""


class MonthlyLine(BaseModel):
    """One parent's money in one calendar month from one payer."""

    parent: Role
    payer: PaidBy | None
    """None = the materials do not say who pays it (the rehabilitation benefit)."""
    payer_label: str
    """In Polish: "Pracodawca mamy (wynagrodzenie chorobowe)", "Pracodawca mamy",
    "Zleceniodawca taty albo ZUS", "ZUS"."""
    amount: Amount
    """For each payment in `payment_ids`: its daily amount × its days in this month."""
    payment_ids: list[str]
    """The payments (`Timeline.payments`) with days in this month, the earliest first."""


class MonthlyPayment(BaseModel):
    """The money for the days of one calendar month: every payment's daily amount times its
    days in the month. The months of a payment add up to its `total` exactly."""

    month: str
    """The calendar month, "2027-03"."""
    mother: Amount
    father: Amount
    total: Amount
    """`mother` + `father`; 0 in a month without a paid day (a gap)."""
    lines: list[MonthlyLine] = []
    """Who pays each parent this month: the mother's lines first, then the father's; more than
    one for a parent when the month mixes payers (e.g. the employer's sick pay, then the
    sickness benefit from ZUS). Empty in a gap."""
    payment_ids: list[str] = []
    """Every payment with days in this month, the earliest first."""


class MoneyTotal(BaseModel):
    """All payments on the timeline together: the sum of `Timeline.payments` (and of
    `Timeline.monthly`)."""

    total: Amount
    mother: Amount
    father: Amount


TimelineElement = Segment | Marker | Document | Payment

NoteKind = Literal["situation", "right", "risk", "choice", "relief", "computed"]
"""situation = which case this is, right = what the mother is entitled to and why, risk = what
stands in the way of an entitlement, choice = what the family can decide, relief = an easier or
longer path the rules give them, computed = what exactly we calculated."""


class CaseNote(BaseModel):
    """One point of the case explanation, in plain words. Legal claims carry their sources."""

    id: str
    kind: NoteKind
    title: str
    text: str
    sources: list[SourceRef] = []


class Timeline(BaseModel):
    params_version: str
    today: dt.date
    birth_date: dt.date
    """Actual date of birth when `child_born`, otherwise the expected due date."""
    child_born: bool
    children_count: int | None
    segments: list[Segment]
    markers: list[Marker]
    documents: list[Document]
    notes: list[CaseNote] = []
    """The case explanation: situation, options and reliefs, what we computed."""
    warnings: list[str] = []
    assumptions: list[str] = []
    taken_in: TakenIn | None = None
    """Set for a child taken in for upbringing: then `birth_date` is the day of taking in."""
    payments: list[Payment] = []
    """Section G: the benefit for each period, once the parent's monthly amount is known."""
    bases: list[BenefitBase] = []
    """Each parent's benefit base behind `payments`, step by step (engine/base.py)."""
    left_on_table: list[Leftover] = []
    """F9: what the family can still use and loses if they do nothing (leftover.py)."""
    monthly: list[MonthlyPayment] = []
    """F4: `payments` month by month, every calendar month from the first paid day to the last,
    gaps included (monthly.py). Empty without payments."""
    money_total: MoneyTotal | None = None
    """F4: all `payments` together; None without payments."""

    def elements(self) -> list[TimelineElement]:
        return [*self.segments, *self.markers, *self.documents, *self.payments]

    def element(self, element_id: str) -> TimelineElement | None:
        return next((e for e in self.elements() if e.id == element_id), None)
