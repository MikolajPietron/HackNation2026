"""Engine input (Scenario) and output (Timeline). The same models are the API schema.

Phases covered: section A of the guide (pages 5-6): 1 "Przygotowanie do porodu", 2 "Urodzenie
dziecka" and 3 "Szczególna sytuacja" (stillbirth or death of the child); and section B (pages 7-8),
the father: paternity leave, his part of parental leave, taking over maternity leave. With the
Labour Code provisions behind them.
"""

import datetime as dt
from fractions import Fraction
from typing import Annotated, Literal, Self

from pydantic import BaseModel, BeforeValidator, Field, model_validator

Lane = Literal["mother", "father", "child", "documents"]
Tone = Literal["leave", "work", "option"]
"""leave = leave the mother takes, work = she keeps working, option = possible, not decided yet."""

Role = Literal["mother", "father"]
Work = Literal["employment", "contract", "business", "none"]
Earnings = Literal["under-5k", "5k-8k", "8k-12k", "over-12k", "unknown"]
BirthWeek = Literal["before-28", "28-37", "after-37"]
"""When the child was born, as the Labour Code art. 180² § 1 divides it: before the end of the
28th week of pregnancy, after it but before the end of the 37th, or after the 37th."""


class SourceRef(BaseModel):
    """A literal quote: from the guide (section and pages) or from the Labour Code (article)."""

    doc: Literal["przewodnik", "kp"]
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
    """Incapacity: the day the father takes over; hospital: the first day in hospital; death,
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


class ScenarioError(ValueError):
    """The scenario breaks a rule. Polish message, shown to the parent or the assistant."""


PayerSize = Literal["over-20", "up-to-20", "unknown"]
"""How many people the payer of contributions (the employer, or the principal of a contract of
mandate) reports to sickness insurance: more than 20 = it pays the benefit itself, otherwise ZUS
does (guide page 1, footnote 1). "unknown" = the parent does not know."""


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

    @property
    def anchor_date(self) -> dt.date | None:
        """The date the timeline counts from: the actual birth once born, else the due date."""
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


TimelineElement = Segment | Marker | Document

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

    def elements(self) -> list[TimelineElement]:
        return [*self.segments, *self.markers, *self.documents]

    def element(self, element_id: str) -> TimelineElement | None:
        return next((e for e in self.elements() if e.id == element_id), None)
