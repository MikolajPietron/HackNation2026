"""Engine input (Scenario) and output (Timeline). The same models are the API schema.

Phase 1 covers one point of the guide: section A, "Przygotowanie do porodu" (page 5).
"""

import datetime as dt
from typing import Literal

from pydantic import BaseModel, Field

Lane = Literal["mother", "child", "documents"]
Tone = Literal["leave", "work", "option"]
"""leave = leave the mother takes, work = she keeps working, option = possible, not decided yet."""


class SourceRef(BaseModel):
    """A literal quote from the guide: which section, which page."""

    doc: Literal["przewodnik"]
    section: str
    page: int
    quote: str


class ScenarioError(ValueError):
    """The scenario breaks a rule. Polish message, shown to the parent or the assistant."""


class Scenario(BaseModel):
    """What the interview has established so far. None = not asked or not decided yet."""

    due_date: dt.date | None = None
    """Expected due date (przewidywana data porodu)."""
    leave_before_birth_weeks: int | None = Field(default=None, ge=0)
    """Weeks of maternity leave before the due date; 0 = the mother works until the birth."""
    has_medical_certificate: bool | None = None
    """Medical certificate of the expected due date, needed for leave before the birth."""


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


class Timeline(BaseModel):
    params_version: str
    today: dt.date
    due_date: dt.date
    segments: list[Segment]
    markers: list[Marker]
    documents: list[Document]
    warnings: list[str] = []
    assumptions: list[str] = []

    def elements(self) -> list[TimelineElement]:
        return [*self.segments, *self.markers, *self.documents]

    def element(self, element_id: str) -> TimelineElement | None:
        return next((e for e in self.elements() if e.id == element_id), None)
