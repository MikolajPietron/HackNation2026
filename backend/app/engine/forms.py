"""Request forms (ZADANIA B.3): every request on the timeline as a form to fill in.

Applied after the applications (timeline.py, `add_forms`): each request document gets
`Document.form`, built from a template in `params.forms` (the fields and attachments its sources
name, each with its quote) and filled in from the scenario and the timeline:
- an employee's leave requests follow the regulation of 11 March 2025 on the requests
  (rozp_wnioski): § 2 the part of maternity leave before the birth, § 3 the mother's
  resignation, § 5-§ 9 the father's part of maternity leave (taking over or the mother's
  incapacity, her stay in hospital, death, abandonment), § 14 supplementary, § 15 parental
  (also each part of the parents' plan), § 16 combining a part of the plan with work, § 17
  paternity leave; § 22: nothing the employer keeps in the personal files is attached;
- ZAM (a parent who is not an employee, or a mother whose employment ended in pregnancy) follows
  annex 6 of the regulation of 27 September 2026 on the benefit documents (rozp_zasilki, § 12):
  the data of the request for the maternity benefit; its attachments: § 13 (the birth), § 20,
  § 22, § 23 (the father after the mother), § 26 (supplementary leave), § 32 (a mother without
  insurance), § 33 (paternity leave). The ZAM form itself is on www.zus.pl (guide page 12);
- the documents for the sickness benefit follow annex 1 of the same regulation (§ 2).

The attachments for the maternity benefit (§ 13, guide A.4) go with the employee mother's
request for maternity leave too: her employer determines the benefit on its basis (guide A.4).

Personal data (names, PESEL, addresses, NIP and REGON, bank account, signature) is never filled
in: the person types it in. Dates and periods are read from the finished timeline, not computed.

Our readings, not settled by the materials (CLAUDE.md, open questions):
- the regulation gives the content of the employee's request for maternity leave only for the
  part before the birth (§ 2): without that part the form has no fields, only the period on the
  timeline and the attachments for the benefit;
- "okres dotychczas wykorzystanego urlopu rodzicielskiego" (§ 15 ust. 1 pkt 2): the parental
  leave of either parent on the timeline before this period (the limit of 5 parts counts both
  parents together, parental_plan.py);
- "termin zakończenia urlopu macierzyńskiego" (§ 14 ust. 1 pkt 2): the day before supplementary
  leave starts, since it starts right after maternity leave;
- the request to combine parental leave with work (§ 16): the period of work is the first weeks
  of the part (parental_plan.py), and the statement on the extension says "no": on the timeline
  the extension is added at the end of the part, without work.
"""

import datetime as dt
from dataclasses import dataclass

from app.engine.after_insurance import after_job_loss
from app.engine.applications import MOTHER_LEAVE, PLAN_REQUESTS, WORK_REQUESTS, who_pays
from app.engine.draft import DAY, days_between, merge_sources
from app.engine.insurance import coverage
from app.engine.models import (
    Addressee,
    Document,
    FormAttachment,
    FormField,
    FormFieldKind,
    FormNote,
    RequestForm,
    Role,
    Scenario,
    Segment,
    Timeline,
)
from app.engine.params import Params
from app.engine.parental_plan import formula, fraction, planned_parts, work_end, work_weeks
from app.engine.pregnancy import SEGMENT_IDS
from app.engine.wording import fmt, weeks_or_days

KINDS: dict[str, FormFieldKind] = {
    "leave-from": "date",
    "return-date": "date",
    "child-birth-date": "date",
    "due-date": "date",
    "maternity-end": "date",
    "event-date": "date",
    "leave-period": "period",
    "benefit-period": "period",
    "sick-period": "period",
    "work-period": "period",
    "prenatal-leave": "statement",
    "discharge-commitment": "statement",
    "used-so-far": "statement",
    "za-zyciem": "statement",
    "extension-work": "statement",
}
"""Field kinds by id; any other field is text."""

WHOSE = {"mother": "mamy", "father": "taty"}
EVENT_TEMPLATE = {
    "hospital": "father-hospital",
    "death": "father-death",
    "abandonment": "father-abandonment",
}
JOB_LOSS = {
    "bankruptcy": "tak: pracodawca ogłosił upadłość",
    "liquidation": "tak: likwidacja pracodawcy",
    "employer-death": "tak: pracodawca zmarł",
    "unlawful": "tak: rozwiązanie umowy o pracę z naruszeniem przepisów prawa",
}
BIRTH_WEEK = {
    "before-28": "przed ukończeniem 28. tygodnia ciąży",
    "28-37": "po 28. tygodniu, przed ukończeniem 37. tygodnia ciąży",
    "after-37": "po 37. tygodniu ciąży",
}


@dataclass
class Fill:
    """What the app writes in a field."""

    value: str | None = None
    start: dt.date | None = None
    end: dt.date | None = None
    hint: str | None = None
    required: bool = True


@dataclass
class Attach:
    """An attachment of the template this form includes, and when."""

    id: str
    required: bool = True
    hint: str | None = None


def add_forms(timeline: Timeline, scenario: Scenario, params: Params) -> None:
    """Every request on the timeline gets its form."""
    timeline.documents = [
        document.model_copy(update={"form": form})
        if (form := request_form(document, timeline, scenario, params)) is not None
        else document
        for document in timeline.documents
    ]


def request_form(
    document: Document, timeline: Timeline, scenario: Scenario, params: Params
) -> RequestForm | None:
    """The form for one document on the timeline; None for a document that is not a request."""
    build = Forms(document, timeline, scenario, params)
    match document.id:
        case "maternity-request" if _employee(scenario, "mother"):
            return build.maternity()
        case "maternity-request":
            return build.zam("mother")
        case "father-benefit-request":
            return build.zam("father")
        case "supplementary-request":
            return build.supplementary()
        case "parental-request" | "parental-father-request" if document.segment_id:
            parent: Role = "mother" if document.id == "parental-request" else "father"
            return build.parental(parent, document.segment_id)
        case work if work.startswith(WORK_REQUESTS) and document.segment_id:
            parent = "father" if work.startswith(WORK_REQUESTS[1]) else "mother"
            return build.parental_work(parent, document.segment_id)
        case part if part.startswith(PLAN_REQUESTS) and document.segment_id:
            parent = "father" if part.startswith(PLAN_REQUESTS[1]) else "mother"
            return build.parental(parent, document.segment_id)
        case "maternity-resignation":
            return build.resignation()
        case "maternity-father-request":
            return build.father_maternity()
        case "paternity-request":
            return build.paternity()
        case "sick-benefit-request":
            return build.sick()
        case _:
            return None


def _employee(scenario: Scenario, parent: Role) -> bool:
    if parent == "father":
        return scenario.fathers_work == "employment"
    return scenario.mothers_work == "employment" and after_job_loss(scenario) is None


def _days(start: dt.date, end: dt.date) -> str:
    return f"od {fmt(start)} do {fmt(end)} ({weeks_or_days(days_between(start, end))})"


def _name(segment: Segment) -> str:
    """ "urlop rodzicielski (do wyboru)", from "Urlop rodzicielski — do wyboru"."""
    name = segment.title.replace(" — do wyboru", "")
    name = name[0].lower() + name[1:]
    return f"{name} (do wyboru)" if segment.tone == "option" else name


def _whose(segment: Segment) -> str:
    """ "tata: urlop rodzicielski (do wyboru)", for lists of both parents' leave."""
    who = {"mother": "mama", "father": "tata"}.get(segment.lane)
    name = _name(segment).replace(" taty", "").replace(" mamy", "")
    return f"{who}: {name}" if who else name


def _period(segment: Segment) -> Fill:
    hint = "Okres z osi czasu."
    if segment.tone == "option":
        hint = "Okres z osi czasu; ten urlop jest do wyboru, więc możesz wpisać inny."
    return Fill(_days(segment.start, segment.end), segment.start, segment.end, hint)


def _day(day: dt.date, hint: str | None = None) -> Fill:
    return Fill(fmt(day), day, hint=hint)


class Forms:
    """The forms of one timeline: one method per kind of request."""

    def __init__(
        self, document: Document, timeline: Timeline, scenario: Scenario, params: Params
    ) -> None:
        self.document = document
        self.timeline = timeline
        self.scenario = scenario
        self.params = params

    # Helpers.

    def segment(self, segment_id: str) -> Segment | None:
        return next((s for s in self.timeline.segments if s.id == segment_id), None)

    def build(
        self,
        kind: str,
        *,
        applicant: Role,
        addressee: tuple[Addressee, str],
        fills: dict[str, Fill],
        attachments: list[Attach],
        skip: set[str] | None = None,
        notes: list[FormNote] | None = None,
        start: dt.date | None = None,
        end: dt.date | None = None,
        official_form: str | None = None,
    ) -> RequestForm:
        template = self.params.forms.templates[kind]
        unknown = set(fills) - set(template.fields)
        assert not unknown, f"{kind}: no such fields {unknown}"
        fields = []
        for field_id, item in template.fields.items():
            if field_id in (skip or set()):
                continue
            fill = fills.get(field_id, Fill())
            assert not (item.personal and fill.value), f"{kind}: {field_id} is personal"
            fields.append(
                FormField(
                    id=field_id,
                    label=item.label,
                    kind=KINDS.get(field_id, "text"),
                    value=fill.value,
                    start=fill.start,
                    end=fill.end,
                    personal=item.personal,
                    required=fill.required,
                    hint=fill.hint,
                    sources=item.sources,
                )
            )
        return RequestForm(
            title=self.document.title,
            applicant=applicant,
            addressee=addressee[0],
            addressee_label=addressee[1],
            official_form=official_form,
            legal_basis=template.basis,
            start=start,
            end=end,
            fields=fields,
            attachments=[
                FormAttachment(
                    id=a.id,
                    label=template.attachments[a.id].label,
                    required=a.required,
                    hint=a.hint,
                    sources=template.attachments[a.id].sources,
                )
                for a in attachments
            ],
            notes=notes or [],
        )

    def employer(self, parent: Role) -> tuple[Addressee, str]:
        return "employer", f"Pracodawca {WHOSE[parent]}"

    def zus_or_payer(self, parent: Role) -> tuple[Addressee, str]:
        """Where a parent who is not an employee files: straight with ZUS with a business (or
        after losing the job); on a contract of mandate the payer that pays the benefit itself,
        otherwise ZUS (guide A.4)."""
        work = self.scenario.mothers_work if parent == "mother" else self.scenario.fathers_work
        if work == "business" or (parent == "mother" and after_job_loss(self.scenario)):
            return "zus", "ZUS"
        match who_pays(self.scenario, parent):
            case "payer":
                return "payer", "Płatnik składek (zleceniodawca)"
            case "zus":
                return "zus", "ZUS"
            case _:
                return "payer-or-zus", "Płatnik składek (zleceniodawca) albo ZUS"

    def personal_files(self) -> FormNote:
        return FormNote(
            text=(
                "Dokumentów, które pracodawca ma już w aktach osobowych, nie trzeba dołączać "
                "do wniosku."
            ),
            sources=self.params.forms.personal_files.sources,
        )

    def zus_forms(self, form: str) -> FormNote:
        return FormNote(
            text=(
                f"Formularz {form} jest na www.zus.pl (Wzory formularzy, Zasiłki). Nasze "
                "materiały podają, jakie dane zawiera wniosek, ale nie jego wygląd: pola niżej "
                "to zakres danych z rozporządzenia, a nie kopia formularza."
            ),
            sources=self.params.forms.zus_forms.sources,
        )

    def birth_date(self) -> Fill:
        if self.timeline.child_born:
            return _day(self.timeline.birth_date, "Z osi czasu.")
        return Fill(hint="Wpiszesz po porodzie.")

    def benefit_attachments(self, parent: Role) -> tuple[list[Attach], list[FormNote]]:
        """The documents for the maternity benefit from the birth (rozp_zasilki § 13, guide
        A.4): the birth certificate, unless ZUS pays; the stillbirth certificate, the hospital's
        certificate for supplementary leave, the "Za życiem" certificate."""
        attachments = []
        notes = []
        later = "" if self.timeline.child_born else " Dostarczysz go po porodzie."
        match who_pays(self.scenario, parent):
            case "zus":
                notes.append(
                    FormNote(
                        text=(
                            "Zasiłek wypłaca ZUS, więc odpisu aktu urodzenia dziecka się nie "
                            "przedstawia: ZUS dostaje dane dziecka (imię i nazwisko, PESEL, datę "
                            "i miejsce urodzenia) i dane rodzica, który składa wniosek."
                        ),
                        sources=self.params.forms.zus_birth_data.sources,
                    )
                )
            case "payer":
                attachments.append(
                    Attach("birth-certificate", hint=f"Za okres od dnia porodu.{later}".strip())
                )
            case _:
                attachments.append(
                    Attach(
                        "birth-certificate",
                        required=False,
                        hint=(
                            "Potrzebny, gdy zasiłek wypłaca płatnik składek; gdy wypłaca ZUS, "
                            f"odpisu się nie przedstawia.{later}"
                        ),
                    )
                )
        if parent == "mother" and any(loss.stillborn for loss in self.scenario.losses):
            attachments.append(
                Attach(
                    "stillbirth-certificate",
                    required=False,
                    hint="Gdy nie sporządzono aktu urodzenia dziecka: zamiast odpisu.",
                )
            )
        if self.supplementary_of(parent) is not None:
            attachments.append(Attach("hospital-certificate"))
        if self.scenario.za_zyciem:
            attachments.append(Attach("za-zyciem-certificate"))
        return attachments, notes

    def supplementary_of(self, parent: Role) -> Segment | None:
        supplementary = self.segment("supplementary")
        return supplementary if supplementary and supplementary.lane == parent else None

    def parental_before(self, segment: Segment) -> list[Segment]:
        """Parental leave of either parent on the timeline that ends before `segment`."""
        return [
            s
            for s in self.timeline.segments
            if s.id.startswith("parental") and s.end < segment.start
        ]

    def prenatal_statement(self) -> Fill:
        prenatal = self.segment("maternity-prenatal")
        what = (
            "Urlop macierzyński" if _employee(self.scenario, "mother") else "Zasiłek macierzyński"
        )
        if prenatal is None:
            return Fill("Brak: mama nie korzystała z tego przed porodem.", hint="Z osi czasu.")
        return Fill(
            f"{what} przed porodem {_days(prenatal.start, prenatal.end)}",
            prenatal.start,
            prenatal.end,
            "Z osi czasu.",
        )

    # The forms.

    def maternity(self) -> RequestForm:
        """The employed mother's request for maternity leave (guide A.4): with a part before
        the birth, its content from § 2; the attachments for the benefit (§ 13)."""
        prenatal = self.segment("maternity-prenatal")
        maternity = self.segment("maternity")
        first = prenatal or maternity
        last = maternity or prenatal
        attachments, notes = self.benefit_attachments("mother")
        fills: dict[str, Fill] = {}
        if prenatal is not None:
            kind = "prenatal"
            fills["leave-from"] = _day(
                prenatal.start, "Pierwszy dzień urlopu przed porodem na osi czasu."
            )
            done = self.scenario.has_medical_certificate
            attachments.insert(
                0,
                Attach(
                    "due-date-certificate",
                    hint="Na osi: zaświadczenie już masz." if done else None,
                ),
            )
        else:
            kind = "maternity"
            notes.insert(
                0,
                FormNote(
                    text=(
                        "Rozporządzenie o wnioskach urlopowych podaje, co zawiera wniosek tylko "
                        "o część urlopu macierzyńskiego przed porodem. Wniosek o urlop po porodzie "
                        "pracownica składa pracodawcy, ale materiały nie podają jego pól: "
                        "pokazujemy okres z osi czasu i załączniki."
                    ),
                    sources=self.params.applications.employee_request.sources,
                ),
            )
        return self.build(
            kind,
            applicant="mother",
            addressee=self.employer("mother"),
            fills=fills,
            attachments=attachments,
            notes=[*notes, self.personal_files()],
            start=first.start if first else None,
            end=last.end if last else None,
        )

    def zam(self, parent: Role) -> RequestForm:
        """ZAM: the data of annex 6 (§ 12), filled from the timeline; the attachments of § 13,
        § 20-§ 23, § 26, § 32 and § 33 for the situation on the timeline."""
        s = self.scenario
        if parent == "mother":
            periods = [x for x in self.timeline.segments if x.lane == "mother"]
            periods = [x for x in periods if x.id in MOTHER_LEAVE]
        else:
            periods = [x for x in self.timeline.segments if x.lane == "father"]
        periods = [x for x in periods if x.end >= self.timeline.today]
        start = min((x.start for x in periods), default=None)
        end = max((x.end for x in periods), default=None)
        lines = [f"{_name(x)}: {_days(x.start, x.end)}" for x in periods]
        fills: dict[str, Fill] = {
            "child-birth-date": self.birth_date(),
            "benefit-period": Fill(
                f"Zasiłek macierzyński za okres: {'; '.join(lines)}." if lines else None,
                start,
                end,
                "Okresy z osi czasu.",
            ),
            "reason": Fill("urodzenie dziecka"),
        }
        skip = set()
        if s.za_zyciem is not None:
            fills["za-zyciem"] = Fill("tak" if s.za_zyciem else "nie")
        if s.due_date is not None:
            fills["due-date"] = _day(s.due_date)
        loss = after_job_loss(s) if parent == "mother" else None
        if loss is not None:
            fills["employer-situation"] = Fill(JOB_LOSS[loss.reason])
        supplementary = self.supplementary_of(parent)
        if supplementary is not None:
            fills["hospital"] = Fill(self.hospital_line())
        else:
            skip.add("hospital")
        situation = self.mother_situation() if parent == "father" else None
        if situation is not None:
            fills["mother-situation"] = Fill(situation)
        else:
            skip.add("mother-situation")
        other: Role = "father" if parent == "mother" else "mother"
        used = [
            x
            for x in self.timeline.segments
            if x.lane == other and (x.id.startswith("parental") or x.id == "supplementary")
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
        attachments, notes = self.benefit_attachments(parent)
        if parent == "mother":
            if self.segment("maternity-prenatal") is not None:
                attachments.insert(0, Attach("due-date-certificate"))
            elif self.segment("prenatal-window") is not None:
                attachments.insert(
                    0,
                    Attach(
                        "due-date-certificate",
                        required=False,
                        hint="Tylko jeśli mama weźmie zasiłek za okres przed porodem.",
                    ),
                )
        if supplementary is not None:
            attachments.append(Attach("supplementary-other-parent"))
        if parent == "father":
            attachments += self.father_attachments()
        return self.build(
            "zam",
            applicant=parent,
            addressee=self.zus_or_payer(parent),
            fills=fills,
            attachments=attachments,
            skip=skip,
            notes=[self.zus_forms("ZAM"), *notes],
            start=start,
            end=end,
            official_form="ZAM",
        )

    def hospital_line(self) -> str:
        s = self.scenario
        parts = []
        if s.birth_week is not None:
            parts.append(f"urodzenie {BIRTH_WEEK[s.birth_week]}")
        if s.birth_weight_up_to_1000g is not None:
            parts.append(f"masa ciała do 1000 g: {'tak' if s.birth_weight_up_to_1000g else 'nie'}")
        for stay in s.hospital_stays:
            until = f"do {fmt(stay.end)}" if stay.end else "nadal trwa"
            parts.append(f"pobyt w szpitalu od {fmt(stay.start)} {until}")
        return "; ".join(parts).capitalize() + "." if parts else "Dane ze szpitala."

    def mother_situation(self) -> str | None:
        """For the father's ZAM: what about the mother gives him the benefit."""
        s = self.scenario
        his = self.segment("maternity-father")
        event = s.mother_event
        if event is not None:
            match event.kind:
                case "incapacity":
                    return "Mama ma orzeczenie o niezdolności do samodzielnej egzystencji" + (
                        f"; tata przejmuje urlop od {fmt(his.start)}." if his else "."
                    )
                case "hospital":
                    until = f" do {fmt(event.end)}" if event.end else ""
                    return f"Mama przebywa w szpitalu od {fmt(event.start)}{until}."
                case "death":
                    return f"Mama zmarła {fmt(event.start)}."
                case "abandonment":
                    return f"Mama porzuciła dziecko {fmt(event.start)}."
        if s.father_takes_over and his is not None:
            weeks = (
                s.mother_weeks_before_takeover or self.params.maternity.mother_personal_weeks.value
            )
            return (
                f"Mama rezygnuje z dalszej części zasiłku macierzyńskiego po {weeks} tygodniach "
                f"po porodzie; tata przejmuje go od {fmt(his.start)}."
            )
        match coverage(s):
            case "not-working":
                return "Mama nie pracuje, więc nie podlega ubezpieczeniu chorobowemu."
            case "not-registered":
                return "Mama nie jest zgłoszona do dobrowolnego ubezpieczenia chorobowego."
        return None

    def parts_line(self, parent: Role) -> str | None:
        """The parts of parental leave in this parent's plan, and paternity leave."""
        lines = []
        parts = [x for x in self.timeline.segments if x.id.startswith(f"parental-{parent}-")]
        for number, part in enumerate(parts, 1):
            lines.append(f"urlop rodzicielski, część {number}: {_days(part.start, part.end)}")
        paternity = self.segment("paternity") if parent == "father" else None
        if paternity is not None:
            lines.append(f"{_name(paternity)}: {_days(paternity.start, paternity.end)}")
        return ("; ".join(lines) + ".").capitalize() if lines else None

    def father_attachments(self) -> list[Attach]:
        """The father who is not an employee: the documents for the situation on the timeline
        (rozp_zasilki § 20, § 22, § 23, § 32, § 33)."""
        s = self.scenario
        attachments = []
        his = self.segment("maternity-father")
        event = s.mother_event
        if his is not None:
            if event is not None and event.kind == "hospital":
                attachments += [
                    Attach("mother-benefit-certificate-hospital"),
                    Attach("mother-hospital-certificates"),
                ]
            else:
                attachments.append(Attach("mother-benefit-certificate"))
                if event is not None and event.kind in ("death", "abandonment"):
                    attachments.append(Attach("mother-event-statement"))
                if event is not None and event.kind == "incapacity":
                    attachments.append(Attach("incapacity-ruling"))
        parental = any(
            x.lane == "father" and x.id.startswith("parental") for x in self.timeline.segments
        )
        if parental and s.mothers_work == "none":
            attachments.append(Attach("mother-uninsured-statement"))
        if self.segment("paternity") is not None:
            attachments.append(Attach("paternity-statement"))
        return attachments

    def supplementary(self) -> RequestForm:
        """§ 14: the end of maternity leave and the period of supplementary leave."""
        leave = self.segment("supplementary")
        assert leave is not None
        parent: Role = "father" if leave.lane == "father" else "mother"
        maternity_end = leave.start - DAY
        return self.build(
            "supplementary",
            applicant=parent,
            addressee=self.employer(parent),
            fills={
                "maternity-end": _day(
                    maternity_end, "Dzień przed początkiem urlopu uzupełniającego na osi czasu."
                ),
                "leave-period": _period(leave),
            },
            attachments=[Attach("hospital-certificate"), Attach("other-parent-statement")],
            notes=[self.personal_files()],
            start=leave.start,
            end=leave.end,
        )

    def parental(self, parent: Role, segment_id: str) -> RequestForm:
        """§ 15: the parental leave used so far and the period asked for; the other parent's
        statement says what the timeline shows of their parental leave at that time."""
        leave = self.segment(segment_id)
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
        other: Role = "father" if parent == "mother" else "mother"
        overlap = [
            x
            for x in self.timeline.segments
            if x.lane == other
            and x.id.startswith("parental")
            and x.start <= leave.end
            and x.end >= leave.start
        ]
        statement = (
            "Na osi drugi z rodziców ma w tym czasie urlop rodzicielski: "
            + "; ".join(_days(x.start, x.end) for x in overlap)
            + "."
            if overlap
            else "Na osi drugi z rodziców nie ma w tym czasie urlopu rodzicielskiego."
        )
        attachments = [
            Attach("birth-certificate"),
            Attach("other-parent-statement", hint=statement),
        ]
        if self.scenario.za_zyciem:
            attachments.append(Attach("za-zyciem-certificate"))
        return self.build(
            "parental",
            applicant=parent,
            addressee=self.employer(parent),
            fills={"used-so-far": used, "leave-period": _period(leave)},
            attachments=attachments,
            notes=[self.personal_files()],
            start=leave.start,
            end=leave.end,
        )

    def parental_work(self, parent: Role, segment_id: str) -> RequestForm:
        """§ 16: the part of full time, the period of work and the statement on working during
        the extension, from the plan. Nothing to attach: § 16 names no attachments."""
        leave = self.segment(segment_id)
        part = planned_parts(self.scenario).get(segment_id)
        assert leave is not None and part is not None and part.work_fraction is not None
        pp = self.params.parental_plan
        share = fraction(part.work_fraction)
        until = work_end(part, leave.start)
        fills: dict[str, Fill] = {
            "work-fraction": Fill(f"{share} etatu", hint="Z planu na osi czasu."),
            "work-period": Fill(
                _days(leave.start, until),
                leave.start,
                until,
                f"Z planu na osi: pierwsze {work_weeks(part)} tyg. tej części urlopu "
                "rodzicielskiego, która razem z wydłużeniem trwa "
                f"{_days(leave.start, leave.end)}. Możesz wskazać inne tygodnie.",
            ),
        }
        skip: set[str] = set()
        notes: list[FormNote] = []
        extension = leave.days - part.weeks * 7
        if extension > 0:
            first = leave.end - (extension - 1) * DAY
            fills["extension-work"] = Fill(
                "Brak takiego zamiaru: w planie wydłużenie tej części urlopu "
                f"{_days(first, leave.end)} jest bez pracy.",
                hint=(
                    "Z planu na osi. Jeśli chcesz pracować także w czasie wydłużenia, wpisz to "
                    "z wymiarem pracy; oś tego nie liczy."
                ),
            )
            notes.append(
                FormNote(
                    text=(
                        "Urlop wydłuża się o tygodnie pracy razy wymiar pracy "
                        f"({formula(part)}). Za okres wydłużonego urlopu rodzicielskiego też "
                        "przysługuje zasiłek macierzyński."
                    ),
                    sources=merge_sources(
                        pp.extension.sources,
                        pp.extension_in_days.sources if extension % 7 else [],
                        pp.extension_paid.sources,
                    ),
                )
            )
        else:
            skip.add("extension-work")  # the incomplete day is dropped: no extension
        notes.append(
            FormNote(
                text=(
                    "Wniosek składa się w postaci papierowej albo elektronicznej. Pracodawca "
                    "uwzględnia go, chyba że nie pozwala na to organizacja pracy albo rodzaj "
                    "Twojej pracy; o przyczynie odmowy informuje w ciągu "
                    f"{pp.employer_answer_days.value} dni od otrzymania wniosku."
                ),
                sources=merge_sources(
                    pp.work_request_days.sources, pp.employer_answer_days.sources
                ),
            )
        )
        return self.build(
            "parental-work",
            applicant=parent,
            addressee=self.employer(parent),
            fills=fills,
            attachments=[],
            skip=skip,
            notes=notes,
            start=leave.start,
            end=until,
        )

    def resignation(self) -> RequestForm:
        """§ 3: the mother's return to work, the copy of the father's request (an employee) or
        of his statement (not an employee)."""
        maternity = self.segment("maternity")
        assert maternity is not None
        back = maternity.end + DAY
        match self.scenario.fathers_work:
            case "employment":
                hint = "Tata pracuje na umowie o pracę: kopia jego wniosku do pracodawcy."
            case "contract" | "business":
                hint = "Tata nie jest pracownikiem: kopia jego oświadczenia."
            case _:
                hint = None
        return self.build(
            "resignation",
            applicant="mother",
            addressee=self.employer("mother"),
            fills={
                "return-date": _day(
                    back, "Dzień po ostatnim dniu urlopu macierzyńskiego mamy na osi czasu."
                )
            },
            attachments=[Attach("father-request-copy", hint=hint)],
            notes=[self.personal_files()],
            start=back,
        )

    def father_maternity(self) -> RequestForm:
        """§ 5 (taking over, the mother's incapacity), § 6-§ 7 (her stay in hospital: employee or
        not), § 8 (death), § 9 (abandonment)."""
        s = self.scenario
        his = self.segment("maternity-father")
        assert his is not None
        event = s.mother_event
        employee = _employee(s, "mother")
        fills: dict[str, Fill] = {"prenatal-leave": self.prenatal_statement()}
        if event is None or event.kind == "incapacity":
            kind = "father-takeover"
            fills["child-birth-date"] = self.birth_date()
            fills["leave-period"] = _period(his)
            statement = (
                "Mama pracuje na umowie o pracę: jej oświadczenie o rezygnacji z urlopu."
                if employee
                else "Mama nie jest pracownicą: jej oświadczenie o rezygnacji z zasiłku."
            )
            attachments = [
                Attach("birth-certificate"),
                Attach("mother-resignation-statement", hint=statement),
            ]
        else:
            kind = EVENT_TEMPLATE[event.kind]
            if event.kind == "hospital":
                kind += "-employee" if employee else "-insured"
                fills["leave-from"] = _day(his.start, "Dzień, od którego mama przerwała urlop.")
                attachments = [
                    Attach("mother-statement", hint=f"Na osi: od {fmt(his.start)}."),
                    Attach("admission-certificate"),
                    Attach("birth-certificate"),
                ]
            else:
                fills["event-date"] = _day(event.start, "Data podana w rozmowie.")
                fills["leave-from"] = _day(his.start, "Z osi czasu.")
                attachments = [Attach("birth-certificate")]
        return self.build(
            kind,
            applicant="father",
            addressee=self.employer("father"),
            fills=fills,
            attachments=attachments,
            notes=[self.personal_files()],
            start=his.start,
            end=his.end,
        )

    def paternity(self) -> RequestForm:
        """§ 17: the period of paternity leave."""
        leave = self.segment("paternity")
        assert leave is not None
        return self.build(
            "paternity",
            applicant="father",
            addressee=self.employer("father"),
            fills={"leave-period": _period(leave)},
            attachments=[Attach("birth-certificate"), Attach("paternity-statement")],
            notes=[self.personal_files()],
            start=leave.start,
            end=leave.end,
        )

    def sick(self) -> RequestForm:
        """Annex 1 (§ 2): the documents for the sickness benefit in pregnancy, for the periods of
        the benefit on the timeline that are still ahead or under way."""
        today = self.timeline.today
        benefit = [
            x
            for x in self.timeline.segments
            if x.lane == "mother" and x.id.startswith(SEGMENT_IDS["benefit"]) and x.end >= today
        ]
        start = min(x.start for x in benefit)
        end = max(x.end for x in benefit)
        business = self.scenario.mothers_work == "business"
        notes = [
            FormNote(
                text=(
                    "Zamiast tego dokumentu ZUS przyjmuje też wydruk zaświadczenia lekarskiego "
                    "albo zaświadczenie płatnika składek."
                ),
                sources=self.params.forms.sick_alternatives.sources,
            )
        ]
        if business:
            notes.insert(0, self.zus_forms("ZAS-53"))
        return self.build(
            "sick",
            applicant="mother",
            addressee=("zus", "ZUS") if business else self.zus_or_payer("mother"),
            fills={
                "sick-period": Fill(
                    "; ".join(_days(x.start, x.end) for x in benefit),
                    start,
                    end,
                    "Zasiłek chorobowy na osi czasu.",
                ),
                "insurance-period": Fill(
                    "w okresie ubezpieczenia chorobowego",
                    hint="Na osi zasiłek chorobowy przypada w czasie ubezpieczenia.",
                ),
            },
            attachments=[],
            notes=notes,
            start=start,
            end=end,
            official_form="ZAS-53" if business else None,
        )
