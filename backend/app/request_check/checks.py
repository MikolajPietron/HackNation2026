"""The deterministic checks of a filled request (F23). No AI: each problem says what is wrong in
plain Polish, and a problem about a rule carries the rule's literal sources (the parameters or
the timeline element it comes from).

- the form: ZUR, ZAO and Z-3b are abolished from 24 October 2026 (guide page 12);
- the fields: required fields left empty; the leave ending before it starts; dates that do not
  give the weeks asked for (a week of leave is 7 calendar days);
- the deadline: the Labour Code days before the leave, or before the work during parental leave
  (the same parameters as `engine/applications.py`), counted from the request's own date or,
  without one, the request's document on the timeline;
- the timeline: parental leave of the mother before her maternity leave ends, supplementary leave
  not right after it, leave after its last possible day, the 81,5% request after 21 days from the
  birth, dates other than the plan;
- the attachments of guide A.4 (stillbirth, "Za życiem", the hospital's certificate) and the
  medical certificate for leave before the birth (A.1);
- the addressee: a request for leave goes to the employer; ZAM with a business goes to ZUS.
"""

import datetime as dt
from collections.abc import Callable
from dataclasses import dataclass

from app.documents.forms import abolished_on, abolished_text, find_forms
from app.engine import Params, Scenario, Timeline
from app.engine.draft import DAY, merge_sources
from app.engine.insurance import NOT_INSURED, coverage
from app.engine.models import Document, Marker, Segment, SourceRef
from app.engine.params import Param, Rule
from app.engine.wording import fmt

from .adapter import KIND_LABELS, ReadRequest, plain, read_request
from .models import (
    CheckKind,
    FilledRequest,
    RequestCheckResult,
    RequestKind,
    RequestProblem,
    Severity,
)

LEAVE_KINDS: tuple[RequestKind, ...] = (
    "maternity-request",
    "maternity-father-request",
    "maternity-resignation",
    "supplementary-request",
    "parental-request",
    "parental-father-request",
    "paternity-request",
)
"""Requests for leave: filed with the employer."""
PARENTAL: tuple[RequestKind, ...] = ("parental-request", "parental-father-request")
ORDER: dict[Severity, int] = {"error": 0, "warning": 1, "info": 2}


@dataclass
class Found:
    check: CheckKind
    severity: Severity
    message: str
    sources: list[SourceRef]
    field: str | None = None
    element_id: str | None = None


@dataclass
class Context:
    request: ReadRequest
    params: Params
    scenario: Scenario | None
    timeline: Timeline | None


# The form and its fields.


def abolished_forms(ctx: Context) -> list[Found]:
    r, p = ctx.request, ctx.params
    if r.filed_on < abolished_on(p):
        return []
    found = []
    for form in find_forms(r.text, p):
        if not form.abolished:
            continue
        then = f" Złóż wniosek {form.merged_into}." if form.merged_into else ""
        found.append(Found("form-abolished", "error", abolished_text(form, p) + then, form.sources))
    return found


def empty_fields(ctx: Context) -> list[Found]:
    return [
        Found("field-empty", "error", f"Pole „{label}” jest puste.", [], field=label)
        for label in ctx.request.empty
    ]


def dates_order(ctx: Context) -> list[Found]:
    r = ctx.request
    if r.start is None or r.end is None or r.end >= r.start:
        return []
    return [
        Found(
            "dates-order",
            "error",
            f"Koniec urlopu ({fmt(r.end)}) wypada przed jego początkiem ({fmt(r.start)}).",
            [],
            field=r.labels.get("end") or r.labels.get("period"),
        )
    ]


def _week_rule(ctx: Context) -> Rule | None:
    """A week of this leave is 7 calendar days (Labour Code art. 183¹ § 1 for maternity leave;
    the guide for parental and supplementary leave)."""
    p = ctx.params
    match ctx.request.kind:
        case "maternity-request" | "maternity-father-request":
            return p.rules.week_is_7_days
        case "parental-request" | "parental-father-request":
            return p.parental.week_is_7_days
        case "supplementary-request":
            return p.supplementary.week_is_7_days
        case _:
            return None


def weeks_mismatch(ctx: Context) -> list[Found]:
    r = ctx.request
    rule = _week_rule(ctx)
    if rule is None or r.start is None or r.end is None or r.weeks is None or r.end < r.start:
        return []
    days = (r.end - r.start).days + 1
    if days == r.weeks * 7:
        return []
    return [
        Found(
            "weeks-mismatch",
            "warning",
            f"Od {fmt(r.start)} do {fmt(r.end)} to {days} dni, a we wniosku jest {r.weeks} tyg. "
            "Tydzień urlopu to 7 dni kalendarzowych.",
            rule.sources,
            field=r.labels.get("weeks"),
        )
    ]


# The deadline (Labour Code; the same parameters as engine/applications.py).


@dataclass(frozen=True)
class Deadline:
    days: Param[int]
    anchor: Callable[[ReadRequest], dt.date | None]
    before: str
    """Completes "co najmniej N dni …"."""
    movable: bool
    """The parent can still move the leave: say from which day a request filed now is in time."""


def _deadlines(p: Params) -> dict[RequestKind, Deadline]:
    a = p.applications
    start = "przed rozpoczęciem urlopu"

    def supplementary(r: ReadRequest) -> dt.date | None:
        # Supplementary leave starts right after maternity leave (art. 180² § 1).
        return r.maternity_end or (r.start - DAY if r.start else None)

    return {
        "parental-request": Deadline(a.parental_days_before, lambda r: r.start, start, True),
        "parental-father-request": Deadline(a.parental_days_before, lambda r: r.start, start, True),
        "paternity-request": Deadline(a.paternity_days_before, lambda r: r.start, start, True),
        "supplementary-request": Deadline(
            a.supplementary_days_before_end,
            supplementary,
            "przed końcem urlopu macierzyńskiego",
            False,
        ),
        "maternity-resignation": Deadline(
            a.resignation_days_before, lambda r: r.return_to_work, "przed powrotem do pracy", False
        ),
        "maternity-father-request": Deadline(
            a.father_maternity_days_before,
            lambda r: r.start,
            "przed rozpoczęciem tej części urlopu",
            False,
        ),
        # Art. 182¹ᵉ § 2: the request to combine parental leave with work, before the work.
        "parental-work-request": Deadline(
            p.parental_plan.work_request_days, lambda r: r.start, "przed rozpoczęciem pracy", False
        ),
    }


def _document(ctx: Context, document_id: str) -> Document | None:
    if ctx.timeline is None:
        return None
    return next((d for d in ctx.timeline.documents if d.id == document_id), None)


def deadline_passed(ctx: Context) -> list[Found]:
    r = ctx.request
    rule = _deadlines(ctx.params).get(r.kind)
    if rule is None:
        return []
    event = ctx.scenario.mother_event if ctx.scenario else None
    uninsured = ctx.scenario is not None and coverage(ctx.scenario) in NOT_INSURED
    if r.kind == "maternity-father-request" and event and (event.kind != "incapacity" or uninsured):
        # Art. 180 § 16: the mother in hospital, dead or gone, or (§ 15) a mother without
        # sickness insurance — no deadline.
        return []
    document = _document(ctx, r.kind)
    element = document.id if document else None
    anchor = rule.anchor(r)
    if anchor is None:
        # No date in the request: the request's document on the timeline (applications.py).
        if document is None or r.filed_on <= document.needed_by:
            return []
        message = (
            f"Według osi wniosek trzeba złożyć najpóźniej {fmt(document.needed_by)}: ten termin "
            "minął."
        )
        return [Found("deadline-passed", "error", message, document.sources, None, element)]
    days = rule.days.value
    deadline = anchor - days * DAY
    if r.filed_on <= deadline:
        return []
    message = (
        f"Termin minął {fmt(deadline)}: wniosek składa się co najmniej {days} dni "
        f"{rule.before} ({fmt(anchor)})."
    )
    if rule.movable:
        message += (
            f" Złożony {fmt(r.filed_on)} jest w terminie dla urlopu od "
            f"{fmt(r.filed_on + days * DAY)}."
        )
    label = r.labels.get("start") or r.labels.get("period")
    if r.kind == "maternity-resignation":
        label = r.labels.get("return_to_work")
    elif r.kind == "supplementary-request":
        label = r.labels.get("maternity_end") or label
    return [Found("deadline-passed", "error", message, rule.days.sources, label, element)]


# Against the timeline.


def _segments(timeline: Timeline, *ids: str) -> list[Segment]:
    """The segments with these ids, or numbered pieces of them ("parental-mother-2")."""
    return [s for s in timeline.segments if any(s.id == i or s.id.startswith(f"{i}-") for i in ids)]


def _maternity_end(timeline: Timeline) -> Segment | None:
    leave = [s for s in timeline.segments if s.id in ("maternity", "maternity-resumed")]
    return max(leave, key=lambda s: s.end, default=None)


def leave_order(ctx: Context) -> list[Found]:
    r, t, p = ctx.request, ctx.timeline, ctx.params
    if t is None or r.start is None:
        return []
    maternity = _maternity_end(t)
    if maternity is None:
        return []
    label = r.labels.get("start") or r.labels.get("period")
    if r.kind == "parental-request" and r.start <= maternity.end:
        return [
            Found(
                "leave-order",
                "error",
                f"Urlop rodzicielski we wniosku zaczyna się {fmt(r.start)}, a urlop macierzyński "
                f"trwa do {fmt(maternity.end)}. Urlop rodzicielski przysługuje po wykorzystaniu "
                "urlopu macierzyńskiego.",
                p.parental.after_maternity.sources,
                label,
                maternity.id,
            )
        ]
    first_day = maternity.end + DAY
    if r.kind == "supplementary-request" and r.start != first_day:
        return [
            Found(
                "leave-order",
                "error",
                "Uzupełniający urlop macierzyński przysługuje bezpośrednio po urlopie "
                f"macierzyńskim: według osi od {fmt(first_day)}, a we wniosku od {fmt(r.start)}.",
                p.supplementary.once_after_maternity.sources,
                label,
                maternity.id,
            )
        ]
    return []


def _marker(timeline: Timeline | None, marker_id: str) -> Marker | None:
    if timeline is None:
        return None
    return next((m for m in timeline.markers if m.id == marker_id), None)


def after_limit(ctx: Context) -> list[Found]:
    r = ctx.request
    if r.kind == "paternity-request":
        marker, name = _marker(ctx.timeline, "paternity-deadline"), "urlop ojcowski"
    elif r.kind in PARENTAL:
        marker, name = _marker(ctx.timeline, "parental-deadline"), "urlop rodzicielski"
    else:
        return []
    last = r.end or r.start
    if marker is None or last is None or last <= marker.date:
        return []
    return [
        Found(
            "after-limit",
            "error",
            f"Urlop we wniosku trwa do {fmt(last)}, a {name} można wykorzystać najpóźniej do "
            f"{fmt(marker.date)}.",
            marker.sources,
            r.labels.get("end") or r.labels.get("period") or r.labels.get("start"),
            marker.id,
        )
    ]


def rate_815_late(ctx: Context) -> list[Found]:
    r = ctx.request
    if r.kind != "rate-815" and not r.rate_815:
        return []
    marker = _marker(ctx.timeline, "rate-815-deadline")
    if marker is None or r.filed_on <= marker.date:
        return []
    days = ctx.params.money.request_days.value
    return [
        Found(
            "rate-815-late",
            "error",
            f"Wniosek o zasiłek 81,5% składa się najpóźniej {days} dni po porodzie, czyli do "
            f"{fmt(marker.date)}: ten termin minął.",
            marker.sources,
            r.labels.get("rate_815"),
            marker.id,
        )
    ]


PLAN_SEGMENTS: dict[RequestKind, tuple[str, ...]] = {
    "maternity-request": ("maternity-prenatal", "maternity"),
    "maternity-father-request": ("maternity-father",),
    "supplementary-request": ("supplementary",),
    "parental-request": ("parental-mother", "parental"),
    "parental-father-request": ("parental-father",),
    "paternity-request": ("paternity",),
}


def differs_from_plan(ctx: Context) -> list[Found]:
    r, t = ctx.request, ctx.timeline
    ids = PLAN_SEGMENTS.get(r.kind)
    if t is None or ids is None or r.start is None:
        return []
    planned = _segments(t, *ids)
    if r.kind != "supplementary-request":  # either parent may take supplementary leave
        planned = [s for s in planned if s.lane == r.parent]
    if not planned or any(s.start == r.start for s in planned):
        return []
    closest = min(planned, key=lambda s: abs((s.start - r.start).days))
    name = closest.title.split(" —")[0]
    message = f"Na osi „{name}” zaczyna się {fmt(closest.start)}, a we wniosku {fmt(r.start)}."
    if closest.tone == "option":
        message += " Na osi to propozycja do wyboru, więc sprawdź, czy taka data jest zamierzona."
    else:
        message += " Sprawdź, która data jest właściwa."
    label = r.labels.get("start") or r.labels.get("period")
    return [Found("differs-from-plan", "info", message, [], label, closest.id)]


# Attachments and the addressee.


@dataclass(frozen=True)
class Needed:
    name: str
    words: tuple[str, ...]
    """Any of these (plain, see `adapter.plain`) in an attachment's name means it is there."""
    sources: list[SourceRef]


def _needed(ctx: Context) -> list[Needed]:
    r, s, t, a = ctx.request, ctx.scenario, ctx.timeline, ctx.params.applications
    needed = []
    supplementary = _segments(t, "supplementary") if t else []
    own_lane = any(seg.lane == r.parent for seg in supplementary)
    if r.kind == "supplementary-request" or (r.kind == "zam" and own_lane):
        needed.append(
            Needed(
                "zaświadczenie ze szpitala, w którym przebywało dziecko",
                ("szpital",),
                merge_sources(a.supplementary_hospital_certificate.sources, a.attachments.sources),
            )
        )
    if s is None:
        return needed
    mothers = r.parent == "mother" and r.kind in ("maternity-request", "zam")
    if mothers and any(loss.stillborn for loss in s.losses):
        needed.append(
            Needed("zaświadczenie o martwym urodzeniu", ("martw",), a.attachments.sources)
        )
    if s.za_zyciem and r.kind in ("maternity-request", "zam", *PARENTAL):
        needed.append(Needed("zaświadczenie „Za życiem”", ("za zyciem",), a.attachments.sources))
    birth = s.birth_date if s.child_born else s.due_date
    if r.kind == "maternity-request" and r.start and birth and r.start < birth:
        needed.append(
            Needed(
                "zaświadczenie lekarskie o przewidywanej dacie porodu",
                ("lekarsk",),
                ctx.params.rules.medical_certificate.sources,
            )
        )
    return needed


def attachments_missing(ctx: Context) -> list[Found]:
    attached = [plain(name) for name in ctx.request.attachments]
    return [
        Found(
            "attachment-missing",
            "warning",
            f"Do wniosku dołącza się {need.name}: nie ma go na liście załączników.",
            need.sources,
        )
        for need in _needed(ctx)
        if not any(word in name for name in attached for word in need.words)
    ]


def _leave_rule(ctx: Context) -> Rule | Param[int] | None:
    """The rule that says this request for leave goes to the employer."""
    a = ctx.params.applications
    return {
        "maternity-request": a.employee_request,
        "maternity-father-request": a.father_maternity_days_before,
        "maternity-resignation": a.resignation_days_before,
        "supplementary-request": a.supplementary_days_before_end,
        "parental-request": a.parental_days_before,
        "parental-father-request": a.parental_days_before,
        "paternity-request": a.paternity_days_before,
    }.get(ctx.request.kind)


def wrong_addressee(ctx: Context) -> list[Found]:
    r, s, a = ctx.request, ctx.scenario, ctx.params.applications
    to = plain(r.addressee or "")
    to_zus = "zus" in to.split() or "zaklad ubezpieczen" in to
    rule = _leave_rule(ctx)
    if rule is not None and to_zus:
        return [
            Found(
                "wrong-addressee",
                "warning",
                "Wniosek o urlop składa się pracodawcy, a nie do ZUS.",
                rule.sources,
            )
        ]
    if r.kind != "zam" or s is None:
        return []
    work = s.mothers_work if r.parent == "mother" else s.fathers_work
    if work == "business" and to and not to_zus:
        return [
            Found(
                "wrong-addressee",
                "warning",
                "Przy własnej firmie wniosek o zasiłek macierzyński (ZAM) składa się bezpośrednio "
                "do ZUS.",
                a.non_employee_zam.sources,
            )
        ]
    if work == "employment" and r.parent == "mother" and s.job_loss is None:
        return [
            Found(
                "wrong-addressee",
                "info",
                "Mama pracuje na umowie o pracę: występuje do pracodawcy z wnioskiem o urlop "
                "macierzyński. Wniosek ZAM bezpośrednio do ZUS składa kobieta, która nie jest "
                "pracownikiem.",
                merge_sources(a.employee_request.sources, a.non_employee_zam.sources),
            )
        ]
    return []


CHECKS: list[tuple[CheckKind, Callable[[Context], list[Found]], bool]] = [
    ("form-abolished", abolished_forms, False),
    ("field-empty", empty_fields, False),
    ("dates-order", dates_order, False),
    ("weeks-mismatch", weeks_mismatch, False),
    ("deadline-passed", deadline_passed, False),
    ("leave-order", leave_order, True),
    ("after-limit", after_limit, True),
    ("rate-815-late", rate_815_late, True),
    ("differs-from-plan", differs_from_plan, True),
    ("attachment-missing", attachments_missing, False),
    ("wrong-addressee", wrong_addressee, False),
]
"""Each check, and whether it needs the timeline."""


def check(
    request: FilledRequest,
    *,
    params: Params,
    today: dt.date,
    scenario: Scenario | None = None,
    timeline: Timeline | None = None,
) -> RequestCheckResult:
    read = read_request(request, params, today)
    ctx = Context(read, params, scenario, timeline)
    found: list[Found] = []
    ran: list[CheckKind] = []
    for kind, run, needs_timeline in CHECKS:
        if needs_timeline and timeline is None:
            continue
        ran.append(kind)
        found += run(ctx)
    if read.kind == "unknown":
        found.append(
            Found(
                "unknown-form",
                "info",
                "Nie rozpoznaliśmy rodzaju wniosku: sprawdziliśmy pola, załączniki i formularze, "
                "bez terminów urlopu.",
                [],
            )
        )
    if timeline is None:
        found.append(
            Found(
                "no-timeline",
                "info",
                "Bez osi czasu nie porównaliśmy dat wniosku z planem urlopów.",
                [],
            )
        )
    found.sort(key=lambda f: ORDER[f.severity])
    counts: dict[CheckKind, int] = {}
    problems = []
    for f in found:
        counts[f.check] = counts.get(f.check, 0) + 1
        problems.append(
            RequestProblem(
                id=f"{f.check}-{counts[f.check]}",
                check=f.check,
                severity=f.severity,
                field=f.field,
                message=f.message,
                sources=f.sources,
                element_id=f.element_id,
            )
        )
    return RequestCheckResult(
        kind=read.kind,
        kind_label=KIND_LABELS[read.kind],
        recognized=read.kind != "unknown",
        ok=not any(p.severity == "error" for p in problems),
        problems=problems,
        checks=ran,
        timeline_used=timeline is not None,
        filed_on=read.filed_on,
    )
