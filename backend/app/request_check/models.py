"""A filled request and the problems found in it.

`FilledRequest` takes the shape of the request form the app fills in (`{title, addressee,
fields: [{label, value, source}]}`), plus what a check needs that a form keeps outside its fields:
the attachments, who files it and when. `adapter.py` turns it into what the checks read."""

import datetime as dt
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import BaseModel, BeforeValidator

from app.engine import Scenario
from app.engine.models import Role, SourceRef


def _text(value: Any) -> str | None:
    """A field's value as the form shows it: dates as ISO, yes/no as "tak"/"nie"."""
    if value is None or isinstance(value, str):
        return value
    if isinstance(value, bool):
        return "tak" if value else "nie"
    if isinstance(value, dt.date):
        return value.isoformat()
    return str(value)


FieldValue = Annotated[str | None, BeforeValidator(_text)]

FieldKey = Literal[
    "start",
    "end",
    "period",
    "weeks",
    "return_to_work",
    "maternity_end",
    "birth_date",
    "filed_on",
    "rate_815",
]
"""What a field means for the checks: the first and last day of the leave (or both in one
"period" field), its length in weeks, the day of return to work (giving up maternity leave), the
last day of maternity leave (supplementary leave), the child's date of birth, the day of filing,
the choice of 81,5% in ZAM. Inferred from the label when the form does not say."""


class RequestField(BaseModel):
    label: str
    value: FieldValue = None
    source: str | None = None
    """Where the form took the value from (scenario, timeline, to fill in); not checked."""
    key: FieldKey | None = None
    id: str | None = None
    """The field's id in the timeline's request form (`Document.form.fields[].id`, engine/forms.py),
    when the request comes from it: its meaning is then known, not inferred from the label."""
    required: bool = True
    """An empty required field is a problem."""


class FilledRequest(BaseModel):
    title: str
    """The request's title or form name, e.g. "Wniosek o urlop rodzicielski", "ZAM"."""
    addressee: str | None = None
    fields: list[RequestField] = []
    attachments: list[str] = []
    """The documents attached, by name."""
    form_id: str | None = None
    """The timeline document this request is for (e.g. "parental-request"), when known."""
    parent: Role | None = None
    """Who files it; else read from the title (e.g. "taty")."""
    filed_on: dt.date | None = None
    """The day it is filed; else a "data złożenia" field, else today."""


class RequestCheckRequest(BaseModel):
    request: FilledRequest
    session_id: UUID | None = None
    """The parent's session: its timeline is the plan the dates are checked against."""
    scenario: Scenario | None = None
    """Instead of a session, e.g. a case loaded from the examples."""
    phrase: bool = False
    """Ask the AI (Claude or Gemini) to reword the problems in plain words; it adds no rules."""


RequestKind = Literal[
    "maternity-request",
    "maternity-father-request",
    "maternity-resignation",
    "supplementary-request",
    "parental-request",
    "parental-father-request",
    "parental-work-request",
    "paternity-request",
    "zam",
    "rate-815",
    "zas-53",
    "unknown",
]

CheckKind = Literal[
    "form-abolished",
    "field-empty",
    "dates-order",
    "weeks-mismatch",
    "deadline-passed",
    "leave-order",
    "after-limit",
    "rate-815-late",
    "differs-from-plan",
    "attachment-missing",
    "wrong-addressee",
    "unknown-form",
    "no-timeline",
]
"""form-abolished = ZUR, ZAO, Z-3b after 24.10.2026; field-empty = a required field is empty;
dates-order = the leave ends before it starts; weeks-mismatch = the dates do not give the weeks
asked for; deadline-passed = the Labour Code deadline for the request has passed; leave-order =
parental leave before maternity leave ends, supplementary leave not right after it; after-limit
= after the last day the leave can be taken; rate-815-late = the 81,5% request after 21 days
from the birth; differs-from-plan = other dates than the timeline; attachment-missing = A.4
documents; wrong-addressee = to ZUS instead of the employer or the other way round;
unknown-form, no-timeline = what could not be checked."""

Severity = Literal["error", "warning", "info"]
"""error = the request would be refused or late as it is; warning = likely missing something;
info = worth a look, or a check that could not run."""


class RequestProblem(BaseModel):
    id: str
    """Unique in the result, e.g. "field-empty-2"."""
    check: CheckKind
    severity: Severity
    field: str | None = None
    """The label of the field it is about."""
    message: str
    """Found and worded by the app, without AI."""
    sources: list[SourceRef] = []
    element_id: str | None = None
    """The timeline element it is about, to highlight."""
    phrased: str | None = None
    """The same problem reworded by AI (only with `phrase`); `message` stays the reference."""


class RequestCheckResult(BaseModel):
    kind: RequestKind
    kind_label: str
    recognized: bool
    ok: bool
    """No errors."""
    problems: list[RequestProblem]
    checks: list[CheckKind]
    """The checks that ran."""
    timeline_used: bool
    ai: bool = False
    """True only when AI reworded the problems (the problems themselves are found without AI)."""
    ai_model: str | None = None
    ai_note: str | None = None
    filed_on: dt.date
    """The day the request was checked for."""
