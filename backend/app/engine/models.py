"""Engine input (Scenario) and output (Timeline). The same models are the API schema."""

import datetime as dt
from typing import Literal

from pydantic import BaseModel, Field

DocId = Literal["przewodnik", "kp", "ustawa"]
"""przewodnik = challenge guide (page), kp = Kodeks pracy, ustawa = ustawa zasiłkowa (article)."""

Lane = Literal["mother", "father", "child", "applications"]
Parent = Literal["mother", "father"]


class SourceRef(BaseModel):
    doc: DocId
    page: int | None = None
    article: str | None = None
    quote: str | None = None


class ScenarioError(ValueError):
    """The scenario breaks a rule. Polish message, shown to the parent or the assistant."""


class Scenario(BaseModel):
    """Facts and choices of one family. Everything has a default until the parent tells us more."""

    birth_date: dt.date | None = None
    """Actual birth date when `child_born`, otherwise the expected due date."""
    child_born: bool = False
    children_count: int = Field(default=1, ge=1, le=10)
    """Children born in one delivery (twins = 2)."""
    maternity_weeks_before_birth: int = Field(default=0, ge=0)
    flat_rate: bool = False
    """The mother chose 81.5% for the whole maternity and parental leave instead of 100% + 70%."""
    paternity_start: dt.date | None = None
    """None = example plan: paternity leave right after the birth."""


class Segment(BaseModel):
    """A period on the timeline (leave + benefit). Dates are inclusive."""

    id: str
    lane: Lane
    title: str
    start: dt.date
    end: dt.date
    days: int
    rate_percent: float
    benefit: str
    payer: str
    summary: str
    details: list[str] = []
    is_example: bool = False
    """Placement is an example plan the parents can change (the right itself is not an example)."""
    sources: list[SourceRef]


class Marker(BaseModel):
    """A single day that matters: birth, end of a window, a legal limit."""

    id: str
    lane: Lane
    label: str
    title: str
    date: dt.date
    summary: str
    details: list[str] = []
    sources: list[SourceRef]


class Application(BaseModel):
    """An application to file, placed on the timeline at its due date."""

    id: str
    parent: Parent
    label: str
    title: str
    due: dt.date
    is_deadline: bool
    """True: `due` is the last legal day. False: when it is needed (no legal deadline)."""
    rule: str
    where: str
    segment_id: str | None = None
    passed: bool = False
    sources: list[SourceRef]


TimelineElement = Segment | Marker | Application


class Stat(BaseModel):
    """One headline number for the summary tiles, e.g. 20 weeks of maternity leave."""

    id: str
    label: str
    value: int
    unit: str
    lane: Lane
    segment_ids: list[str]


class Timeline(BaseModel):
    params_version: str
    today: dt.date
    birth_date: dt.date
    child_born: bool
    children_count: int
    summary: list[Stat] = []
    segments: list[Segment]
    markers: list[Marker]
    applications: list[Application]
    warnings: list[str] = []
    assumptions: list[str] = []

    def elements(self) -> list[TimelineElement]:
        return [*self.segments, *self.markers, *self.applications]

    def element(self, element_id: str) -> TimelineElement | None:
        return next((e for e in self.elements() if e.id == element_id), None)
