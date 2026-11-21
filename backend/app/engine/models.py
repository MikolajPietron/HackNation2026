"""Engine input (Scenario) and output (Timeline). The same models are the API schema.

Phases covered: 1 "Przygotowanie do porodu" and 2 "Urodzenie dziecka" from guide section A
(pages 5-6), with the Labour Code provisions behind them.
"""

import datetime as dt
from typing import Literal, Self

from pydantic import BaseModel, Field, model_validator

Lane = Literal["mother", "child", "documents"]
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


class ScenarioError(ValueError):
    """The scenario breaks a rule. Polish message, shown to the parent or the assistant."""


class Scenario(BaseModel):
    """What the onboarding and the interview have established. None = not known yet."""

    # The person filling in (onboarding). Work and earnings are that person's own: the
    # father's when the father fills in. Phase 2 uses the mother's work; earnings wait.
    role: Role | None = None
    work: Work | None = None
    earnings: Earnings | None = None
    mother_work: Work | None = None
    """How the mother works, asked when somebody else fills in. See `mothers_work`."""

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

    @property
    def anchor_date(self) -> dt.date | None:
        """The date the timeline counts from: the actual birth once born, else the due date."""
        return self.birth_date if self.child_born else self.due_date

    @property
    def mothers_work(self) -> Work | None:
        """The mother's work: her own answer when she fills in, otherwise what was said of her."""
        return self.work if self.role == "mother" else self.mother_work


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
