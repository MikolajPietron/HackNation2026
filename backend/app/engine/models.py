"""Engine input (Scenario) and output (Timeline). The same models are the API schema.

Phases covered: 1 "Przygotowanie do porodu" and 2a (length of maternity leave, 14 weeks after
the birth) from guide section A, page 5, with the Labour Code provisions behind them.
"""

import datetime as dt
from typing import Literal

from pydantic import BaseModel, Field

Lane = Literal["mother", "child", "documents"]
Tone = Literal["leave", "work", "option"]
"""leave = leave the mother takes, work = she keeps working, option = possible, not decided yet."""

Role = Literal["mother", "father"]
Work = Literal["employment", "contract", "business", "none"]
Earnings = Literal["under-5k", "5k-8k", "8k-12k", "over-12k", "unknown"]


class SourceRef(BaseModel):
    """A literal quote: from the guide (section and page) or from the Labour Code (article)."""

    doc: Literal["przewodnik", "kp"]
    quote: str
    section: str | None = None
    page: int | None = None
    article: str | None = None


class ScenarioError(ValueError):
    """The scenario breaks a rule. Polish message, shown to the parent or the assistant."""


class Scenario(BaseModel):
    """What the onboarding and the interview have established. None = not known yet."""

    # The person filling in (onboarding). Work and earnings are that person's own: the
    # father's when the father fills in. No phase uses them yet; they are kept for later ones.
    role: Role | None = None
    work: Work | None = None
    earnings: Earnings | None = None

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

    @property
    def anchor_date(self) -> dt.date | None:
        """The date the timeline counts from: the actual birth once born, else the due date."""
        return self.birth_date if self.child_born else self.due_date


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

NoteKind = Literal["situation", "choice", "relief", "computed"]
"""situation = which case this is, choice = what the family can decide, relief = an easier or
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
