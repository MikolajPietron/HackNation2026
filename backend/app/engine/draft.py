"""The timeline while the rules build it, shared by the rule modules (timeline.py, father.py)."""

import datetime as dt
from dataclasses import dataclass, field

from app.engine.models import BenefitBase, Document, Marker, Payment, Segment, SourceRef

DAY = dt.timedelta(days=1)
WEEK = dt.timedelta(days=7)


@dataclass
class Draft:
    segments: list[Segment] = field(default_factory=list)
    markers: list[Marker] = field(default_factory=list)
    documents: list[Document] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    payments: list[Payment] = field(default_factory=list)
    bases: list[BenefitBase] = field(default_factory=list)

    def segment(self, segment_id: str) -> Segment | None:
        return next((s for s in self.segments if s.id == segment_id), None)

    def replace(self, segment_id: str, *pieces: Segment) -> None:
        """Put `pieces` where the segment was (nothing when there are none)."""
        index = next(i for i, s in enumerate(self.segments) if s.id == segment_id)
        self.segments[index : index + 1] = list(pieces)


def merge_sources(*groups: list[SourceRef]) -> list[SourceRef]:
    """Sources of several rules in order, each quote once."""
    seen: set[tuple[str, str]] = set()
    merged = []
    for source in (source for group in groups for source in group):
        if (source.doc, source.quote) not in seen:
            seen.add((source.doc, source.quote))
            merged.append(source)
    return merged


def days_between(start: dt.date, end: dt.date) -> int:
    """Days of an inclusive period."""
    return (end - start).days + 1


def one_year_later(day: dt.date) -> dt.date:
    """The same day a year later (29 February becomes 1 March)."""
    try:
        return day.replace(year=day.year + 1)
    except ValueError:
        return dt.date(day.year + 1, 3, 1)
