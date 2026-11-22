"""Requests, who pays and the protection for a child taken in for upbringing: guide section D
with A.4 (page 6), page 1 footnote 1 (who pays) and section I (page 10); Labour Code art. 177
§ 1-§ 1¹, art. 183 § 3¹ (art. 180² § 4), § 5 (art. 182¹ᵈ § 1), § 6 and art. 182³ § 2.

Applied on the finished timeline of a child taken in (timeline.py, after the money), as
applications.py and forms.py are for a birth, whose helpers it uses:
- who pays: every period on the lane of an insured parent who works says it (applications.
  `payer_line`: the payer of contributions that reports more than 20 insured, else ZUS; with a
  business ZUS);
- an employee's requests, each with its Labour Code deadline (`Document.deadline`): the leave on
  the terms of maternity leave within 7 days of taking the child in (art. 183 § 6), supplementary
  leave at least 21 days before that leave ends (art. 183 § 3¹ with art. 180² § 4), parental
  leave at least 21 days before it starts (art. 183 § 5 with art. 182¹ᵈ § 1), paternity leave at
  least 7 days before (art. 182³ § 2); each with its form (rozp_wnioski § 18, § 14 ust. 3-4,
  § 15 ust. 3-4, § 17 with ust. 2 pkt 2: the copy of the final adoption ruling) and its letter;
- a parent who is not an employee files ZAM (guide A.4), with the documents of rozp_zasilki § 16
  (the leave on the terms of maternity leave), § 30 ust. 1 (the other parent's parental leave)
  and § 33 ust. 1 (paternity leave); for supplementary, parental and paternity leave the request
  is filed before the benefit starts (§ 26, § 29, § 30, § 32, § 33: the reading of
  applications.py, the day before);
- the protection: an employee who takes the leave is protected from the request for it until it
  ends, and from the request for each further leave (guide I; art. 177 § 1, § 1¹); the marker is
  the last day of the leave that follows on from it on the timeline.

Our readings (CLAUDE.md, open questions):
- "w terminie 7 dni od dnia przyjęcia dziecka" (art. 183 § 6): the last day is the day of taking
  in + 7; for adoption that day is the later of taking in and the application to court;
- supplementary leave: "21 dni przed zakończeniem korzystania z urlopu macierzyńskiego" (art.
  180² § 4) counts back from the end of the leave on the terms of maternity leave;
- parental leave after taking a child in: rozp_wnioski § 15 ust. 3 applies only ust. 1 (what the
  request contains) to it and names art. 183 § 4-4²; the attachments are those of ust. 4, and with
  "Za życiem" (§ 4³-4⁵) the regulation says nothing more;
- passing the rest of the leave to the other parent (art. 183 § 2 with art. 180 § 8-9,
  rozp_wnioski § 3 ust. 3, § 5 ust. 3-4) has no request on the timeline yet.
"""

import datetime as dt
from collections.abc import Callable

from app.engine.adoption import (
    PERSON,
    cover_of,
    other,
    parental_total,
    taken_in_leave,
    taker,
    work_of,
)
from app.engine.applications import (
    WHO,
    WHOSE,
    WORKING,
    Parent,
    _applications_line,
    _by,
    _leave_name,
    payer_line,
    who_pays,
)
from app.engine.draft import DAY, merge_sources
from app.engine.forms import Attach, Fill, Forms, _day, _days, _name, _period, _whose
from app.engine.insurance import NOT_INSURED, coverage
from app.engine.models import (
    CaseNote,
    Document,
    FormNote,
    HrMessage,
    Letter,
    Marker,
    RequestForm,
    Role,
    Scenario,
    Segment,
    SourceRef,
    Timeline,
)
from app.engine.params import FormTemplate, Params
from app.engine.request_letters import (
    Draft,
    Letters,
    date_r,
    duration,
    period,
    request,
    statement,
    token,
)
from app.engine.wording import fmt, long_date

TAKEN_IN_REQUEST = "taken-in-request"
"""An employee's request for the leave on the terms of maternity leave."""
LEAVE, PASSED = "adoption-leave", "adoption-leave-other"
ZAM = {"mother": "maternity-request", "father": "father-benefit-request"}
"""A non-employee's ZAM, by the ids of the birth path (applications.py)."""
PARENTAL = {"mother": "parental", "father": "parental-father"}
PARENTAL_REQUEST = {"mother": "parental-request", "father": "parental-father-request"}
EMPLOYER = {"mother": "pracodawcy", "father": "swojemu pracodawcy"}
"""After "składa go", as on the birth path (applications.py)."""
FORMS = {
    TAKEN_IN_REQUEST: "taken-in",
    "supplementary-request": "taken-in-supplementary",
    "parental-request": "taken-in-parental",
    "parental-father-request": "taken-in-parental",
    "paternity-request": "taken-in-paternity",
    "maternity-request": "taken-in-zam",
    "father-benefit-request": "taken-in-zam",
}
"""The documents of this module with a form: the template (params.taken_in.forms)."""
REASON = {
    "adoption": "przyjęcie na wychowanie dziecka i wystąpienie do sądu opiekuńczego w sprawie jego "
    "przysposobienia",
    "foster": "przyjęcie na wychowanie dziecka w ramach rodziny zastępczej (innej niż zawodowa)",
}
"""ZAM (annex 6 pkt 8): what the request is about."""


def add_taken_in_applications(timeline: Timeline, scenario: Scenario, params: Params) -> None:
    """Who pays on every period, the requests and their forms, the end of the protection."""
    today = timeline.today
    timeline.segments = [_with_payer(s, scenario, params) for s in timeline.segments]
    timeline.documents += _requests(scenario, timeline, params, today)
    protection = _protection_end(scenario, timeline, params)
    if protection is not None:
        timeline.markers = sorted([*timeline.markers, protection], key=lambda m: m.date)
    _add_forms(timeline, scenario, params)
    timeline.assumptions += _assumptions(scenario, timeline)


def covered(scenario: Scenario, parent: Parent) -> bool:
    """Insured and working: who pays and what to file are known."""
    return cover_of(scenario, parent) not in NOT_INSURED and work_of(scenario, parent) in WORKING


def _segment(timeline: Timeline, segment_id: str) -> Segment | None:
    return next((s for s in timeline.segments if s.id == segment_id), None)


def _with_payer(segment: Segment, scenario: Scenario, params: Params) -> Segment:
    if segment.lane not in ("mother", "father"):
        return segment
    parent: Parent = "mother" if segment.lane == "mother" else "father"
    if not covered(scenario, parent):
        return segment
    line, sources = payer_line(scenario, parent, params)
    return segment.model_copy(
        update={
            "details": [*segment.details, line],
            "sources": merge_sources(segment.sources, sources),
        }
    )


# Requests.


def _requests(
    scenario: Scenario, timeline: Timeline, params: Params, today: dt.date
) -> list[Document]:
    documents: list[Document] = []
    for parent in ("mother", "father"):
        lane = [s for s in timeline.segments if s.lane == parent]
        if not lane or not covered(scenario, parent):
            continue
        if work_of(scenario, parent) == "employment":
            documents += _employee(scenario, timeline, params, today, parent)
        else:
            documents += _zam(scenario, lane, params, today, parent)
    return documents


def _taken_documents(scenario: Scenario, params: Params, template: str) -> tuple[str, SourceRef]:
    """The document that shows the child was taken in, in words for a rule, and its quote."""
    item = params.taken_in.forms[template].attachments[_kind_documents(scenario)]
    return item.label[0].lower() + item.label[1:], item.sources[0]


def _kind_documents(scenario: Scenario) -> str:
    return "adoption-documents" if scenario.taken_in == "adoption" else "foster-documents"


def _employee(
    scenario: Scenario, timeline: Timeline, params: Params, today: dt.date, parent: Parent
) -> list[Document]:
    a = params.applications
    t = params.taken_in
    documents = []
    leave = _segment(timeline, LEAVE)
    taken = scenario.taken_in_on
    assert taken is not None
    if leave is not None and leave.lane == parent and leave.end >= today:
        days = t.request_days.value
        deadline = taken + days * DAY
        when = (
            f"Najpóźniej {fmt(deadline)}: w terminie {days} dni od dnia przyjęcia dziecka."
            if deadline >= today
            else f"Termin minął {fmt(deadline)}: wniosek składa się w terminie {days} dni od dnia "
            "przyjęcia dziecka."
        )
        attach, attach_source = _taken_documents(scenario, params, "taken-in")
        rule = [
            f"{WHO[parent]} składa go {EMPLOYER[parent]}. {when} Urlop zaczyna się w dniu "
            f"wskazanym we wniosku, nie później niż {t.latest_start_days.value} dni od dnia "
            "przyjęcia dziecka.",
            f"Do wniosku dołącza się: {attach}"
            + (
                ", a także kopię decyzji o odroczeniu obowiązku szkolnego."
                if scenario.school_postponed
                else "."
            ),
        ]
        sources = [t.request_days.sources, t.latest_start_days.sources, [attach_source]]
        if scenario.school_postponed:
            school = t.forms["taken-in"].attachments["school-postponed-decision"]
            sources.append(school.sources)
        payer, payer_sources = payer_line(scenario, parent, params)
        documents.append(
            Document(
                id=TAKEN_IN_REQUEST,
                label="Wniosek: urlop na warunkach macierzyńskiego",
                title="Wniosek o urlop na warunkach urlopu macierzyńskiego",
                needed_by=deadline,
                done=False,
                rule=" ".join([*rule, payer]),
                segment_id=LEAVE,
                sources=merge_sources(*sources, payer_sources),
                deadline=deadline,
            )
        )
    supplementary = _segment(timeline, "supplementary")
    if supplementary is not None and supplementary.lane == parent and supplementary.end >= today:
        days = a.supplementary_days_before_end.value
        leave_end = supplementary.start - DAY
        deadline = leave_end - days * DAY
        needed_by, when = _by(
            deadline,
            days,
            f"przed końcem urlopu na warunkach urlopu macierzyńskiego ({fmt(leave_end)})",
            today,
            movable=False,
        )
        attach, attach_source = _taken_documents(scenario, params, "taken-in-supplementary")
        documents.append(
            Document(
                id="supplementary-request",
                label="Wniosek: urlop uzupełniający",
                title="Wniosek o uzupełniający urlop macierzyński",
                needed_by=needed_by,
                done=False,
                rule=(
                    f"{WHO[parent]} składa go {EMPLOYER[parent]}. {when} Do wniosku dołącza się "
                    f"zaświadczenie ze szpitala, w którym przebywało dziecko, oraz {attach}."
                ),
                segment_id="supplementary",
                sources=merge_sources(
                    t.supplementary.sources,
                    a.supplementary_days_before_end.sources,
                    a.supplementary_hospital_certificate.sources,
                    [attach_source],
                ),
                deadline=deadline,
            )
        )
    parental = _segment(timeline, PARENTAL[parent])
    if parental is not None and parental.end >= today:
        days = a.parental_days_before.value
        deadline = parental.start - days * DAY
        needed_by, when = _by(
            deadline,
            days,
            f"przed rozpoczęciem urlopu ({fmt(parental.start)})",
            today,
            movable=True,
        )
        documents.append(
            Document(
                id=PARENTAL_REQUEST[parent],
                label="Wniosek: urlop rodzicielski"
                if parent == "mother"
                else "Wniosek taty: rodzicielski",
                title="Wniosek o urlop rodzicielski"
                if parent == "mother"
                else "Wniosek taty o urlop rodzicielski",
                needed_by=needed_by,
                done=False,
                rule=f"{WHO[parent]} składa go {EMPLOYER[parent]}. {when}",
                segment_id=parental.id,
                sources=merge_sources(t.parental.sources, a.parental_days_before.sources),
                deadline=deadline,
            )
        )
    paternity = _segment(timeline, "paternity")
    if parent == "father" and paternity is not None and paternity.end >= today:
        days = a.paternity_days_before.value
        deadline = paternity.start - days * DAY
        needed_by, when = _by(
            deadline,
            days,
            f"przed rozpoczęciem urlopu ({fmt(paternity.start)})",
            today,
            movable=True,
        )
        documents.append(
            Document(
                id="paternity-request",
                label="Wniosek: urlop ojcowski",
                title="Wniosek o urlop ojcowski",
                needed_by=needed_by,
                done=False,
                rule=(
                    f"Tata składa go swojemu pracodawcy. {when} Przy adopcji do wniosku dołącza "
                    "się kopię prawomocnego postanowienia sądu o przysposobieniu dziecka."
                ),
                segment_id="paternity",
                sources=merge_sources(
                    a.paternity_days_before.sources,
                    t.forms["taken-in-paternity"].attachments["adoption-ruling"].sources,
                ),
                deadline=deadline,
            )
        )
    return documents


def _zam(
    scenario: Scenario, lane: list[Segment], params: Params, today: dt.date, parent: Parent
) -> list[Document]:
    """ZAM for this parent's first period still ahead or under way (no deadline in the
    materials), then a ZAM before each later period starts."""
    a = params.applications
    periods = sorted((s for s in lane if s.end >= today), key=lambda s: s.start)
    if not periods:
        return []
    first = periods[0]
    business = work_of(scenario, parent) == "business"
    payer, payer_sources = payer_line(scenario, parent, params)
    attachments = [
        params.taken_in.forms["taken-in-zam"].attachments.get(a_id)
        or params.forms.templates["zam"].attachments[a_id]
        for a_id in _zam_attachments(scenario, periods, parent)
    ]
    rule = [
        f"{WHO[parent]} nie jest pracownikiem, więc nie składa wniosku o urlop, tylko wniosek "
        "o zasiłek macierzyński (ZAM).",
        payer,
        "Materiały nie podają terminu tego wniosku: pokazujemy go na dzień, od którego "
        "przysługuje zasiłek."
        + (
            " Za dalsze okresy wniosek składa się przed ich rozpoczęciem: terminy są osobno na osi."
            if len(periods) > 1
            else ""
        ),
    ]
    if attachments:
        names = [item.label[0].lower() + item.label[1:] for item in attachments]
        rule.append(f"Do wniosku dołącza się: {'; '.join(names)}.")
    documents = [
        Document(
            id=ZAM[parent],
            label="Wniosek ZAM" if parent == "mother" else "Wniosek ZAM taty",
            title="Wniosek o zasiłek macierzyński (ZAM)"
            if parent == "mother"
            else "Wniosek taty o zasiłek macierzyński (ZAM)",
            needed_by=first.start,
            done=False,
            rule=" ".join(rule),
            segment_id=first.id,
            sources=merge_sources(
                (a.non_employee_zam if business else a.contract_zam).sources,
                payer_sources,
                a.zam_form.sources,
                *(item.sources for item in attachments),
            ),
        )
    ]
    for segment in periods[1:]:
        found = _later_zam(scenario, segment, params, today, parent)
        if found is not None:
            documents.append(found)
    return documents


def _zam_attachments(scenario: Scenario, periods: list[Segment], parent: Parent) -> list[str]:
    """The documents for the benefit (rozp_zasilki): § 16 for the leave on the terms of
    maternity leave, § 30 ust. 1 for the other parent's parental leave, § 33 ust. 1 for
    paternity leave, § 26 for supplementary leave; the "Za życiem" certificate (guide A.4)."""
    ids = {s.id for s in periods}
    adoption = scenario.taken_in == "adoption"
    found = []
    if ids & {LEAVE, PASSED}:
        found += (
            ["adoption-statement", "court-certificate"]
            if adoption
            else ["foster-ruling", "child-age-document"]
        )
        if scenario.school_postponed and not adoption:
            found.append("school-postponed-decision")
    elif PARENTAL[parent] in ids:
        found.append("parental-adoption-documents" if adoption else "parental-foster-documents")
        if scenario.school_postponed and not adoption:
            found.append("parental-school-postponed-decision")
    if "supplementary" in ids:
        found += ["hospital-certificate", "supplementary-other-parent"]
    if "paternity" in ids:
        found += ["adoption-ruling", "paternity-statement"]
    if scenario.za_zyciem:
        found.append("za-zyciem-certificate")
    return found


def _later_zam(
    scenario: Scenario, segment: Segment, params: Params, today: dt.date, parent: Parent
) -> Document | None:
    """rozp_zasilki: a non-employee files the request for supplementary leave before the benefit
    for the leave on the terms of maternity leave ends (§ 26 pkt 3), for parental and paternity
    leave before the benefit starts (§ 29 pkt 3, § 30 ust. 1 pkt 4, § 32 ust. 1 pkt 3, § 33
    ust. 1 pkt 3). The latest day: the day before."""
    a = params.applications
    if segment.start < today:
        return None
    if segment.id == "supplementary":
        day = segment.start - DAY
        deadline = day - DAY
        what = "uzupełniający urlop macierzyński"
        before = (
            f"przed końcem zasiłku za okres urlopu na warunkach urlopu macierzyńskiego ({fmt(day)})"
        )
        rule = a.zam_supplementary_before
    elif segment.id == PARENTAL[parent]:
        deadline = segment.start - DAY
        what = "urlop rodzicielski"
        before = f"przed rozpoczęciem korzystania z zasiłku ({fmt(segment.start)})"
        if parent == taker(scenario):
            rule = a.zam_parental_before
        elif parent == "father" and coverage(scenario) in NOT_INSURED:
            rule = a.zam_parental_before_father
        else:
            rule = a.zam_parental_before_other
    elif segment.id == "paternity":
        deadline = segment.start - DAY
        what = "urlop ojcowski"
        before = f"przed rozpoczęciem korzystania z zasiłku ({fmt(segment.start)})"
        rule = a.zam_paternity_before
    else:
        return None
    if deadline >= today:
        needed_by, when = deadline, f"Najpóźniej {fmt(deadline)}: wniosek składa się {before}."
    else:
        needed_by = today
        when = (
            f"Wniosek składa się {before}, więc dla tego dnia termin minął {fmt(deadline)}. "
            f"Złożony dziś jest w terminie dla zasiłku od {fmt(today + DAY)}."
        )
    whose = "" if parent == "mother" else " taty"
    return Document(
        id=f"zam-{segment.id}",
        label=f"ZAM{whose}: {what}",
        title=f"Wniosek{whose} o zasiłek macierzyński za okres: {what} (ZAM)",
        needed_by=needed_by,
        done=False,
        rule=(
            f"{WHO[parent]} nie jest pracownikiem: wniosek o zasiłek za ten okres składa "
            f"płatnikowi zasiłku (ZUS albo płatnikowi składek, jak ZAM). {when}"
        ),
        segment_id=segment.id,
        sources=merge_sources(rule.sources, a.zam_form.sources),
        deadline=deadline,
    )


# The protection.


def _protection_end(scenario: Scenario, timeline: Timeline, params: Params) -> Marker | None:
    """Guide I; art. 177 § 1, § 1¹: the employee who takes the leave on the terms of maternity
    leave is protected from the request for it, and for each further leave, until it ends. The
    marker is the last day of the leave that follows on from it on the timeline."""
    role = taker(scenario)
    if work_of(scenario, role) != "employment" or not covered(scenario, role):
        return None
    a = params.applications
    leave = sorted((s for s in timeline.segments if s.lane == role), key=lambda s: s.start)
    if not leave or leave[0].id != LEAVE:
        return None
    chain = [leave[0]]
    for segment in leave[1:]:
        if segment.start == chain[-1].end + DAY:
            chain.append(segment)
    end = chain[-1].end
    if end < timeline.today:
        return None
    later = [s for s in leave if s not in chain]
    details = [
        "Wyjątek: przyczyny uzasadniające rozwiązanie umowy bez wypowiedzenia z winy pracownika, "
        "gdy zgodzi się na to reprezentująca go zakładowa organizacja związkowa."
    ]
    options = [_leave_name(s) for s in chain if s.tone == "option"]
    if options:
        details.append(
            f"{' i '.join(dict.fromkeys(options)).capitalize()}: do wyboru. Ochrona obejmuje "
            f"{'go' if len(set(options)) == 1 else 'je'} od dnia złożenia wniosku o urlop."
        )
    if later:
        details.append(
            f"Później ochrona wraca od dnia złożenia wniosku o {_leave_name(later[0])} do dnia "
            "jego zakończenia."
        )
    part, early, _ = a.protection_early_request_days.value
    details.append(
        "Jeśli wniosek zostanie złożony wcześniej niż w terminie z Kodeksu pracy, zakaz zaczyna "
        f"obowiązywać {part} dni przed częścią urlopu na warunkach urlopu macierzyńskiego, a "
        f"{early} dni przed urlopem uzupełniającym albo rodzicielskim."
    )
    whom = "mamą" if role == "mother" else "tatą"
    return Marker(
        id="protection-end",
        lane="child",
        label="Ochrona do",
        title=f"Koniec ochrony {WHOSE[role]} przed zwolnieniem",
        date=end,
        summary=(
            "Od dnia złożenia wniosku o urlop na warunkach urlopu macierzyńskiego do dnia jego "
            "zakończenia, a także od dnia złożenia wniosku o kolejny urlop do dnia jego "
            "zakończenia, pracodawca nie może wypowiedzieć ani rozwiązać umowy o pracę "
            f"z {whom} ani prowadzić do tego przygotowań. Przy urlopach jak na osi ochrona trwa "
            f"do {fmt(end)}."
        ),
        details=details,
        sources=merge_sources(
            a.protection.sources,
            params.taken_in.protection.sources,
            a.protection_early_request_days.sources,
        ),
    )


# The forms and the letters.


def with_templates(params: Params) -> Params:
    """The parameters with the templates of a child taken in among the forms' templates: one
    that `extends` a template gets its provisions, fields and attachments too."""
    templates = dict(params.forms.templates)
    for kind, own in params.taken_in.forms.items():
        base = templates[own.extends] if own.extends else None
        basis = [*(base.basis if base else []), *own.basis]
        templates[kind] = FormTemplate(
            basis=[s for i, s in enumerate(basis) if s not in basis[:i]],
            fields={**(base.fields if base else {}), **own.fields},
            attachments={**(base.attachments if base else {}), **own.attachments},
        )
    forms = params.forms.model_copy(update={"templates": templates})
    return params.model_copy(update={"forms": forms})


def _add_forms(timeline: Timeline, scenario: Scenario, params: Params) -> None:
    mine = [d for d in timeline.documents if d.id in FORMS]
    if not mine:
        return
    extended = with_templates(params)
    forms = {d.id: TakenInForms(d, timeline, scenario, extended).form() for d in mine}
    timeline.documents = [
        d.model_copy(update={"form": forms[d.id]}) if d.id in forms else d
        for d in timeline.documents
    ]


class TakenInForms(Forms):
    """The forms of a child taken in: rozp_wnioski § 18, § 14 ust. 3-4, § 15 ust. 3-4, § 17;
    ZAM with the documents of rozp_zasilki § 16, § 30 ust. 1, § 33 ust. 1."""

    def form(self) -> RequestForm:
        document = self.document
        match document.id:
            case "maternity-request":
                return self.taken_in_zam("mother")
            case "father-benefit-request":
                return self.taken_in_zam("father")
            case "supplementary-request":
                return self.taken_in_supplementary()
            case "paternity-request":
                return self.taken_in_paternity()
            case "parental-request" | "parental-father-request":
                parent: Role = "mother" if document.id == "parental-request" else "father"
                return self.taken_in_parental(parent)
            case _:
                return self.taken_in()

    def letter(self, kind: str, form: RequestForm) -> tuple[Letter, HrMessage]:
        return TakenInLetters(
            kind, form, self.document, self.timeline, self.scenario, self.params
        ).build()

    def child_birth(self) -> Fill:
        birth = self.scenario.birth_date
        return _day(birth, "Z wywiadu.") if birth else Fill(hint="Data urodzenia dziecka.")

    def taken_attachments(self) -> list[Attach]:
        """The document that shows the child was taken in; the decision on postponed schooling
        (rozp_wnioski § 14 ust. 4, § 15 ust. 4, § 18 ust. 2)."""
        found = [Attach(_kind_documents(self.scenario))]
        if self.scenario.school_postponed:
            found.append(Attach("school-postponed-decision"))
        return found

    def taken_in(self) -> RequestForm:
        """§ 18: the child's name and date of birth, the period of the leave."""
        leave = self.segment(LEAVE)
        assert leave is not None
        parent: Role = "father" if leave.lane == "father" else "mother"
        return self.build(
            "taken-in",
            applicant=parent,
            addressee=self.employer(parent),
            fills={"child-birth-date": self.child_birth(), "leave-period": _period(leave)},
            attachments=self.taken_attachments(),
            notes=[self.personal_files()],
            start=leave.start,
            end=leave.end,
        )

    def taken_in_supplementary(self) -> RequestForm:
        """§ 14 ust. 3-4: § 14 ust. 1-2 applied to the leave on the terms of maternity leave, and
        the document that shows the child was taken in."""
        leave = self.segment("supplementary")
        assert leave is not None
        parent: Role = "father" if leave.lane == "father" else "mother"
        return self.build(
            "taken-in-supplementary",
            applicant=parent,
            addressee=self.employer(parent),
            fills={
                "maternity-end": _day(
                    leave.start - DAY,
                    "Dzień przed początkiem urlopu uzupełniającego na osi czasu.",
                ),
                "leave-period": _period(leave),
            },
            attachments=[
                Attach("hospital-certificate"),
                Attach("other-parent-statement"),
                Attach(_kind_documents(self.scenario)),
            ],
            notes=[self.personal_files()],
            start=leave.start,
            end=leave.end,
        )

    def taken_in_parental(self, parent: Role) -> RequestForm:
        """§ 15 ust. 3-4: what § 15 ust. 1 asks (the parental leave used so far, the period),
        with the attachments of ust. 4."""
        leave = self.segment(PARENTAL[parent])
        assert leave is not None
        before = self.parental_before(leave)
        if before:
            used = Fill(
                "Na osi przed tym okresem: "
                + "; ".join(f"{_whose(x)}: {_days(x.start, x.end)}" for x in before)
                + f". Części: {len(before)}.",
                hint="Urlop rodzicielski obojga rodziców z osi czasu; wpisz to, co naprawdę "
                "wykorzystaliście.",
            )
        else:
            used = Fill("Brak: to pierwsza część urlopu rodzicielskiego.", hint="Z osi czasu.")
        notes = [self.personal_files()]
        if self.scenario.za_zyciem:
            notes.insert(
                0,
                FormNote(
                    text=(
                        "Rozporządzenie podaje treść wniosku o urlop rodzicielski po przyjęciu "
                        "dziecka w wymiarze bez zaświadczenia „Za życiem”; o dłuższym urlopie "
                        "z tym zaświadczeniem nie mówi. Pokazujemy te same dane."
                    ),
                    sources=self.params.forms.templates["taken-in-parental"].basis[-1:],
                ),
            )
        return self.build(
            "taken-in-parental",
            applicant=parent,
            addressee=self.employer(parent),
            fills={"used-so-far": used, "leave-period": _period(leave)},
            attachments=self.taken_attachments(),
            notes=notes,
            start=leave.start,
            end=leave.end,
        )

    def taken_in_paternity(self) -> RequestForm:
        """§ 17, for an adopted child also the copy of the final adoption ruling (ust. 2
        pkt 2)."""
        leave = self.segment("paternity")
        assert leave is not None
        return self.build(
            "taken-in-paternity",
            applicant="father",
            addressee=self.employer("father"),
            fills={"leave-period": _period(leave)},
            attachments=[
                Attach("birth-certificate"),
                Attach("adoption-ruling"),
                Attach("paternity-statement"),
            ],
            notes=[self.personal_files()],
            start=leave.start,
            end=leave.end,
        )

    def taken_in_zam(self, parent: Role) -> RequestForm:
        """ZAM (annex 6): what the request is about, the child's date of birth, the periods on
        the timeline; the documents for the benefit after taking a child in."""
        s = self.scenario
        periods = [x for x in self.timeline.segments if x.lane == parent]
        periods = sorted(
            (x for x in periods if x.end >= self.timeline.today), key=lambda x: x.start
        )
        start = min((x.start for x in periods), default=None)
        end = max((x.end for x in periods), default=None)
        lines = [f"{_name(x)}: {_days(x.start, x.end)}" for x in periods]
        assert s.taken_in is not None
        fills: dict[str, Fill] = {
            "child-birth-date": self.child_birth(),
            "benefit-period": Fill(
                f"Zasiłek macierzyński za okres: {'; '.join(lines)}." if lines else None,
                start,
                end,
                "Okresy z osi czasu.",
            ),
            "reason": Fill(REASON[s.taken_in]),
        }
        skip = {"due-date", "employer-situation", "mother-situation"}
        if s.za_zyciem is not None:
            fills["za-zyciem"] = Fill("tak" if s.za_zyciem else "nie")
        if self.supplementary_of(parent) is not None:
            fills["hospital"] = Fill(self.hospital_line())
        else:
            skip.add("hospital")
        theirs: Role = "father" if parent == "mother" else "mother"
        used = [
            x
            for x in self.timeline.segments
            if x.lane == theirs and (x.id.startswith("parental") or x.id == "supplementary")
        ]
        if used:
            fills["other-parent-use"] = Fill(
                "Na osi: " + "; ".join(f"{_whose(x)}: {_days(x.start, x.end)}" for x in used) + ".",
                hint="Z osi czasu; wpisz to, z czego drugi rodzic naprawdę korzysta.",
            )
        else:
            skip.add("other-parent-use")
        parts = self.parts_line(parent)
        if parts is not None:
            fills["parts"] = Fill(parts, hint="Z osi czasu.")
        attachments = [Attach(a_id) for a_id in _zam_attachments(s, periods, parent)]
        return self.build(
            "taken-in-zam",
            applicant=parent,
            addressee=self.zus_or_payer(parent),
            fills=fills,
            attachments=attachments,
            skip=skip,
            notes=[self.zus_forms("ZAM")],
            start=start,
            end=end,
            official_form="ZAM",
        )


class TakenInLetters(Letters):
    """The letters to the employer after taking a child in, citing only Labour Code provisions
    we quote (art. 183, art. 180² § 1, art. 182³ § 1)."""

    def more_drafts(self) -> dict[str, Callable[[], Draft]]:
        return {
            "taken-in": self.taken_in,
            "taken-in-supplementary": self.taken_in_supplementary,
            "taken-in-parental": self.taken_in_parental,
            "taken-in-paternity": self.taken_in_paternity,
        }

    def child(self) -> str:
        """ "dziecka {{child-name}}, urodzonego w dniu 10.05.2024 r." """
        birth = self.scenario.birth_date
        day = date_r(birth) if birth else token("child-birth-date")
        child = token("child-name")
        if self.count == 1:
            return f"dziecka {child}, urodzonego w dniu {day}"
        return f"dzieci {child} (najmłodsze urodzone w dniu {day})"

    def taken(self) -> str:
        """ "w związku z przyjęciem w dniu … na wychowanie dziecka …" """
        taken = self.scenario.taken_in_on
        assert taken is not None
        if self.scenario.taken_in == "adoption":
            return (
                f"w związku z przyjęciem w dniu {date_r(taken)} na wychowanie {self.child()} "
                "i wystąpieniem do sądu opiekuńczego z wnioskiem o wszczęcie postępowania "
                "w sprawie przysposobienia"
            )
        return (
            f"w związku z przyjęciem w dniu {date_r(taken)} na wychowanie jako rodzina zastępcza "
            f"{self.child()}"
        )

    def taken_in(self) -> Draft:
        """rozp_wnioski § 18: the child, the period (art. 183 § 1 or § 1¹)."""
        start, end = self.field_dates("leave-period")
        assert end is not None
        article = "art. 183 § 1¹" if self.scenario.taken_in == "adoption" else "art. 183 § 1"
        text = (
            f"Na podstawie {article} Kodeksu pracy wnoszę o udzielenie mi urlopu na warunkach "
            f"urlopu macierzyńskiego w wymiarze {duration((end - start).days + 1)}, w okresie "
            f"{period(start, end)}, {self.taken()}."
        )
        return Draft(
            "Wniosek o udzielenie urlopu na warunkach urlopu macierzyńskiego",
            [request(text)],
            [article],
            period(start, end),
        )

    def taken_in_supplementary(self) -> Draft:
        """rozp_wnioski § 14 ust. 3: art. 183 § 3¹ with art. 180² § 1; the other parent's
        statement (§ 14 ust. 2 pkt 2)."""
        start, end = self.field_dates("leave-period")
        leave_end, _ = self.field_dates("maternity-end")
        assert end is not None
        text = (
            "Na podstawie art. 183 § 3¹ w związku z art. 180² § 1 Kodeksu pracy wnoszę "
            "o udzielenie mi uzupełniającego urlopu macierzyńskiego w wymiarze "
            f"{duration((end - start).days + 1)}, w okresie {period(start, end)}, w związku "
            f"z pobytem w szpitalu {self.child()}, po przyjęciu go na wychowanie. Urlop na "
            f"warunkach urlopu macierzyńskiego kończy się {date_r(leave_end)}."
        )
        return Draft(
            "Wniosek o udzielenie uzupełniającego urlopu macierzyńskiego",
            [
                request(text),
                statement(
                    "Oświadczam, że drugi z rodziców dziecka nie zamierza korzystać "
                    "z uzupełniającego urlopu macierzyńskiego ani z zasiłku macierzyńskiego za "
                    "okres odpowiadający okresowi tego urlopu."
                ),
            ],
            ["art. 183 § 3¹", "art. 180² § 1"],
            period(start, end),
        )

    def taken_in_parental(self) -> Draft:
        """rozp_wnioski § 15 ust. 3: the period (art. 183 § 4-§ 4⁵) and the parental leave used
        so far (§ 15 ust. 1 pkt 2)."""
        assert self.document.segment_id is not None
        leave = self.segment(self.document.segment_id)
        assert leave is not None
        found = taken_in_leave(self.scenario, self.params)
        assert found is not None
        article = str(parental_total(self.scenario, self.params, found).sources[0].article)
        text = (
            f"Na podstawie {article} Kodeksu pracy wnoszę o udzielenie mi urlopu rodzicielskiego "
            f"w wymiarze {duration(leave.days)}, w okresie {period(leave.start, leave.end)}, "
            f"{self.taken()}."
        )
        return Draft(
            "Wniosek o udzielenie urlopu rodzicielskiego",
            [request(text), self.used_so_far(leave)],
            [article],
            period(leave.start, leave.end),
        )

    def taken_in_paternity(self) -> Draft:
        """rozp_wnioski § 17 (art. 182³ § 1 pkt 2): the letter of paternity leave, for an
        adopted child."""
        draft = self.paternity()
        start, end = self.field_dates("leave-period")
        assert end is not None
        final = self.scenario.adoption_final_on
        ruling = (
            f", postanowienie o przysposobieniu uprawomocniło się w dniu {date_r(final)}"
            if final
            else ""
        )
        draft.body[0] = request(
            "Na podstawie art. 182³ § 1 Kodeksu pracy wnoszę o udzielenie mi urlopu ojcowskiego "
            f"w wymiarze {duration((end - start).days + 1)}, w okresie {period(start, end)}, "
            f"w związku z przysposobieniem {self.child()}{ruling}."
        )
        return draft


# The case explanation: what to file, who pays, the protection.


def taken_in_application_notes(
    scenario: Scenario, timeline: Timeline, params: Params
) -> list[CaseNote]:
    """After "Co policzyliśmy": the protection, who pays, what to file and by when."""
    notes = [
        _protection_note(scenario, timeline, params),
        _payer_note(scenario, timeline, params),
        _applications_note(scenario, timeline),
    ]
    return [note for note in notes if note is not None]


def _has_leave(timeline: Timeline, parent: Parent) -> bool:
    return any(s.lane == parent for s in timeline.segments)


def _protection_note(scenario: Scenario, timeline: Timeline, params: Params) -> CaseNote | None:
    a = params.applications
    role = taker(scenario)
    partner = other(role)
    work = work_of(scenario, role)
    theirs = (
        work_of(scenario, partner) == "employment"
        and covered(scenario, partner)
        and _has_leave(timeline, partner)
    )
    also = (
        f" {PERSON[partner].capitalize()}, który pracuje na umowie o pracę, chroni to samo od dnia "
        "złożenia wniosku o urlop do dnia jego zakończenia."
        if partner == "father"
        else f" {PERSON[partner].capitalize()}, która pracuje na umowie o pracę, chroni to samo od "
        "dnia złożenia wniosku o urlop do dnia jego zakończenia."
    )
    her = role == "mother"
    if work == "employment" and covered(scenario, role) and _has_leave(timeline, role):
        marker = next((m for m in timeline.markers if m.id == "protection-end"), None)
        own = _segment(timeline, LEAVE)
        first = (
            "wniosku o urlop na warunkach urlopu macierzyńskiego do dnia jego zakończenia, a także "
            "od dnia złożenia wniosku o kolejny urlop"
            if own is not None and own.lane == role
            else "wniosku o urlop"
        )
        text = (
            f"{PERSON[role].capitalize()} pracuje na umowie o pracę, więc od dnia złożenia {first} "
            "do dnia jego zakończenia pracodawca nie "
            f"może wypowiedzieć ani rozwiązać z {'nią' if her else 'nim'} umowy ani się do tego "
            f"przygotowywać (wyjątek: rozwiązanie umowy z {'jej' if her else 'jego'} winy za "
            "zgodą związku zawodowego)."
        )
        if marker is not None:
            text += f" Przy urlopach jak na osi ochrona trwa do {long_date(marker.date)}."
        return CaseNote(
            id="protection",
            kind="right",
            title="Ochrona przed zwolnieniem",
            text=text + (also if theirs else ""),
            sources=merge_sources(a.protection.sources, params.taken_in.protection.sources),
        )
    if work in ("contract", "business") and covered(scenario, role):
        how = "pracuje na umowie zlecenia" if work == "contract" else "prowadzi własną firmę"
        return CaseNote(
            id="protection",
            kind="risk",
            title="Bez szczególnej ochrony z Kodeksu pracy",
            text=(
                "Szczególna ochrona przed wypowiedzeniem umowy w czasie urlopu dotyczy "
                f"pracowników. {PERSON[role].capitalize()} {how}, więc "
                f"{'jej' if her else 'go'} nie obejmuje." + (also if theirs else "")
            ),
            sources=merge_sources(
                a.protection_employees_only.sources, a.protection.sources if theirs else []
            ),
        )
    if theirs:
        return CaseNote(
            id="protection",
            kind="right",
            title=f"Ochrona {WHOSE[partner]} przed zwolnieniem",
            text=(
                f"{PERSON[partner].capitalize()} pracuje na umowie o pracę: od dnia złożenia "
                "wniosku o urlop do dnia jego zakończenia pracodawca nie może wypowiedzieć ani "
                f"rozwiązać z {'nim' if partner == 'father' else 'nią'} umowy ani się do tego "
                "przygotowywać."
            ),
            sources=a.protection.sources,
        )
    return None


def _payer_note(scenario: Scenario, timeline: Timeline, params: Params) -> CaseNote | None:
    a = params.applications
    parents: list[Parent] = [
        p for p in (taker(scenario), other(taker(scenario))) if covered(scenario, p)
    ]
    parents = [p for p in parents if _has_leave(timeline, p)]
    if not parents:
        return None
    lines = []
    sources = []
    for parent in parents:
        line, line_sources = payer_line(scenario, parent, params)
        lines.append(line)
        sources.append(line_sources)
    if any(who_pays(scenario, p) == "payer-or-zus" for p in parents):
        lines.append(
            "Liczbę ubezpieczonych ustala się według stanu na 30 listopada poprzedniego roku."
        )
        sources.append(a.payer_count_day.sources)
    if len(parents) == 1:
        parent = parents[0]
        title = {
            "payer": f"Zasiłek {WHOSE[parent]} wypłaca "
            + ("pracodawca" if work_of(scenario, parent) == "employment" else "płatnik składek"),
            "zus": f"Zasiłek {WHOSE[parent]} wypłaca ZUS",
            "payer-or-zus": f"Kto wypłaca zasiłek {WHOSE[parent]}",
        }[who_pays(scenario, parent)]
    else:
        title = "Kto wypłaca zasiłek"
    return CaseNote(
        id="payer",
        kind="computed",
        title=title,
        text=" ".join(lines),
        sources=merge_sources(*sources),
    )


def _applications_note(scenario: Scenario, timeline: Timeline) -> CaseNote | None:
    documents = sorted(
        (d for d in timeline.documents if d.id in FORMS and not d.done),
        key=lambda d: d.needed_by,
    )
    if not documents:
        return None
    lines = [_applications_line(d, scenario, timeline.today) for d in documents]
    return CaseNote(
        id="applications",
        kind="computed",
        title="Co złożyć i do kiedy",
        text=" ".join(lines) + " Szczegóły każdego wniosku są na osi czasu, w ścieżce dokumentów.",
        sources=merge_sources(*(d.sources for d in documents)),
    )


def _assumptions(scenario: Scenario, timeline: Timeline) -> list[str]:
    shown = {d.id for d in timeline.documents}
    found = []
    if TAKEN_IN_REQUEST in shown:
        found.append(
            "Termin „7 dni od dnia przyjęcia dziecka” na wniosek o urlop na warunkach urlopu "
            "macierzyńskiego liczymy tak: ostatni dzień to 7. dzień po dniu przyjęcia."
        )
    if any(d.deadline is not None for d in timeline.documents if d.id != TAKEN_IN_REQUEST):
        found.append(
            "Termin „nie krótszy niż 21 dni przed” rozpoczęciem urlopu liczymy tak: wniosek "
            "trzeba złożyć najpóźniej 21. dnia przed pierwszym dniem urlopu (tak samo przy 7 "
            "dniach)."
        )
    if "supplementary-request" in shown:
        found.append(
            "Wniosek o uzupełniający urlop macierzyński składa się co najmniej 21 dni przed "
            "zakończeniem urlopu macierzyńskiego; po przyjęciu dziecka liczymy to od końca urlopu "
            "na warunkach urlopu macierzyńskiego."
        )
    if shown & set(ZAM.values()):
        found.append(
            "Terminu wniosku ZAM za okres urlopu na warunkach urlopu macierzyńskiego materiały "
            "nie podają: pokazujemy go na dzień, od którego przysługuje zasiłek. Gdzie składa go "
            "osoba, która nie jest pracownikiem, Przewodnik mówi przy mamie; dla taty przyjmujemy "
            "to samo."
        )
    if "business" in (scenario.mothers_work, scenario.fathers_work) and shown & set(ZAM.values()):
        found.append(
            "Przy własnej firmie wniosek ZAM składa się bezpośrednio do ZUS, więc przyjmujemy, "
            "że zasiłek wypłaca ZUS."
        )
    if any(s.id == PASSED for s in timeline.segments):
        found.append(
            "Wniosków o przekazanie dalszej części urlopu na warunkach urlopu macierzyńskiego "
            "drugiemu rodzicowi (rezygnacja i wniosek drugiego rodzica) oś jeszcze nie pokazuje."
        )
    return found
