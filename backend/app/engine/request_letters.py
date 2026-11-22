"""Request letters ("Prawdziwe wnioski do pobrania"): every request an employee files with the
employer, as the letter an employee writes, and a short e-mail to HR to send it with.

Built from the finished form (forms.py, `Forms.build`) for each request whose addressee is the
employer: the requests of the regulation of 11 March 2025 (rozp_wnioski: § 2 the part of
maternity leave before the birth, § 3 the mother's resignation, § 5-§ 9 the father's part of
maternity leave, § 14 supplementary, § 15 parental, § 16 work during parental leave, § 17
paternity) and the employed mother's request for maternity leave (guide A.4). The front lays the
letter out on an A4 page and renders the PDF in the browser.

- Personal data never reaches the server: names, addresses, the employer and the place are
  placeholders, `{{field-id}}` (models.py, `Letter`). Nothing personal is ever filled in.
- The letter text is our wording of what the sources require; the quotes stay in the form. Each
  request has its own operative sentence ("Na podstawie art. … Kodeksu pracy wnoszę o …"), citing
  only Labour Code provisions we quote (kodeks_pracy.json; tests/test_sources.py checks it).
- Dates and periods are read from the form's fields and the timeline, not computed again.
- The declarations the regulation requires are paragraphs of the body, filled from the timeline;
  the statements the applicant makes about themselves or the other parent (§ 14 ust. 2 pkt 2,
  § 15 ust. 2 pkt 2, § 17 ust. 2 pkt 3) are written into the letter rather than attached, so the
  attachment list holds only the documents to get from elsewhere. A declaration the timeline
  cannot know (whether the father already used paternity leave) keeps both options to tick.
"""

import datetime as dt
import re
from collections.abc import Callable
from dataclasses import dataclass

from app.engine.after_insurance import after_job_loss
from app.engine.applications import PLAN_REQUESTS
from app.engine.draft import DAY, merge_sources
from app.engine.loss import child_loss
from app.engine.models import (
    Document,
    FormAttachment,
    HrMessage,
    Letter,
    LetterField,
    LetterMeaning,
    LetterParagraph,
    OfficialForm,
    RequestForm,
    Scenario,
    Segment,
    Timeline,
)
from app.engine.params import Params
from app.engine.parental_plan import extension_days, fraction, planned_parts, work_end
from app.engine.wording import children_phrase, fmt

REGULATION = (
    "rozporządzenia Ministra Rodziny, Pracy i Polityki Społecznej z dnia 11 marca 2025 r. "
    "w sprawie wniosków dotyczących uprawnień pracowników związanych z rodzicielstwem oraz "
    "dokumentów dołączanych do takich wniosków (Dz.U. z 2025 r. poz. 322)"
)
NAME_IDS = ("employee-name", "father-name")
"""The form fields with the applicant's name (rozp_wnioski: "imię i nazwisko pracownika")."""
LETTER_FIELDS: dict[str, tuple[str, LetterMeaning, bool]] = {
    "letter-place": ("Miejscowość", "place", True),
    "letter-date": ("Data", "date", False),
    "employee-name": ("Imię i nazwisko", "applicant-name", True),
    "father-name": ("Imię i nazwisko", "applicant-name", True),
    "applicant-address": ("Adres zamieszkania", "applicant-address", True),
    "employer": ("Nazwa i adres pracodawcy", "employer", True),
    "child-name": ("Imię i nazwisko dziecka", "child-name", True),
    "child-birth-date": ("Data urodzenia dziecka", "child-birth-date", False),
}
"""Every placeholder a letter may use: label, meaning, personal. A form field with the same id
gives its own label."""
TOKEN = re.compile(r"\{\{([a-z0-9-]+)\}\}")
FOLDED = {"other-parent-statement", "paternity-statement"}
"""The applicant's own statements: written into the letter, not attached."""
NOT_YET_BORN = {"birth-certificate", "stillbirth-certificate", "hospital-certificate"}
"""Documents that exist only after the birth: not attached to a letter written before it."""
ATTACHMENT_LABELS = {
    "due-date-certificate": "Kopia zaświadczenia lekarskiego o przewidywanej dacie porodu",
    "birth-certificate": "Odpis skrócony aktu urodzenia dziecka",
    "stillbirth-certificate": "Zaświadczenie o martwym urodzeniu dziecka",
    "hospital-certificate": "Zaświadczenie ze szpitala, w którym przebywało dziecko",
    "za-zyciem-certificate": "Kopia zaświadczenia „Za życiem”",
    "admission-certificate": "Zaświadczenie szpitala o terminie przyjęcia matki dziecka",
}
"""The attachments in the words of a letter (the form's labels speak to the parent)."""


def tidy(text: str) -> str:
    """A sentence that ends with a date ends with its "r.": no second full stop."""
    return text.replace("r..", "r.")


def token(field_id: str) -> str:
    return "{{" + field_id + "}}"


def date_r(day: dt.date) -> str:
    """ "15.03.2027 r." """
    return f"{fmt(day)} r."


def duration(days: int) -> str:
    """After "w wymiarze", "po wykorzystaniu", "do": "32 tygodni", "1 tygodnia", "13 tygodni
    i 3 dni", "1 dnia"."""
    weeks, rest = divmod(days, 7)
    parts = []
    if weeks:
        parts.append("1 tygodnia" if weeks == 1 else f"{weeks} tygodni")
    if rest:
        parts.append("1 dnia" if rest == 1 else f"{rest} dni")
    return " i ".join(parts)


def period(start: dt.date, end: dt.date) -> str:
    return f"od {date_r(start)} do {date_r(end)}"


def official_form(code: str, params: Params) -> OfficialForm:
    """A ZUS form: where the guide says it is (page 12), in the guide's own words."""
    known = next(form for form in params.applications.forms if form.code == code)
    rule = params.forms.zus_forms
    quote = rule.sources[0].quote
    where = quote[quote.index("www.zus.pl") :].removesuffix(".")
    return OfficialForm(
        code=code,
        name=known.name,
        where=where,
        url=f"https://{where.split()[0]}",
        sheet_title=f"Dane do wpisania do formularza {code}",
        sources=merge_sources(known.sources, rule.sources),
    )


@dataclass
class Draft:
    """What differs between the requests: the title, the body, the provisions cited, the period
    for the e-mail, the attachments' words where they depend on the case."""

    title: str
    body: list[LetterParagraph]
    articles: list[str]
    when: str
    """After the title in the e-mail: "od 19.07.2027 r. do 27.02.2028 r.", "od dnia …"."""
    labels: dict[str, str] | None = None


def request(text: str) -> LetterParagraph:
    return LetterParagraph(kind="request", text=tidy(text))


def statement(text: str) -> LetterParagraph:
    return LetterParagraph(kind="statement", text=tidy(text))


def request_letter(
    kind: str,
    form: RequestForm,
    document: Document,
    timeline: Timeline,
    scenario: Scenario,
    params: Params,
) -> tuple[Letter, HrMessage]:
    """The letter and the e-mail to HR for a request filed with the employer; `kind` is the
    form's template (params.forms.templates)."""
    return Letters(kind, form, document, timeline, scenario, params).build()


class Letters:
    """The letter of one request: one method per kind of request."""

    def __init__(
        self,
        kind: str,
        form: RequestForm,
        document: Document,
        timeline: Timeline,
        scenario: Scenario,
        params: Params,
    ) -> None:
        self.kind = kind
        self.form = form
        self.document = document
        self.timeline = timeline
        self.scenario = scenario
        self.params = params
        self.name = next((f.id for f in form.fields if f.id in NAME_IDS), "employee-name")
        self.mother_employee = (
            scenario.mothers_work == "employment" and after_job_loss(scenario) is None
        )

    # Helpers.

    def segment(self, segment_id: str) -> Segment | None:
        return next((s for s in self.timeline.segments if s.id == segment_id), None)

    def field_dates(self, field_id: str) -> tuple[dt.date, dt.date | None]:
        field = next(f for f in self.form.fields if f.id == field_id)
        assert field.start is not None, field_id
        return field.start, field.end

    @property
    def count(self) -> int:
        return self.scenario.children_count or 1

    def birth_day(self) -> str:
        """The day of birth, or a placeholder while the child is on the way."""
        if self.timeline.child_born:
            return date_r(self.timeline.birth_date)
        return token("child-birth-date")

    def born(self) -> str:
        """ "w związku z urodzeniem dziecka {{child-name}} w dniu 10.11.2026 r." """
        child = token("child-name")
        if self.count == 1:
            who = f"dziecka {child}"
        else:
            who = f"{children_phrase(self.count)} ({child}) przy jednym porodzie"
        return f"w związku z urodzeniem {who} w dniu {self.birth_day()}"

    def concerns(self) -> str:
        """For the father's part of maternity leave (§ 5: the child's name and date of birth)."""
        child = token("child-name")
        if self.count == 1:
            return f"Wniosek dotyczy dziecka {child}, urodzonego w dniu {self.birth_day()}."
        return f"Wniosek dotyczy dzieci {child}, urodzonych w dniu {self.birth_day()}."

    def prenatal_statement(self) -> LetterParagraph:
        """§ 5-§ 9 pkt 3: the mother's maternity leave (or benefit) before the birth."""
        prenatal = self.segment("maternity-prenatal")
        if self.mother_employee:
            if prenatal is None:
                text = "nie korzystała z urlopu macierzyńskiego przed porodem"
            else:
                text = (
                    "korzystała z urlopu macierzyńskiego przed porodem w okresie "
                    f"{period(prenatal.start, prenatal.end)}"
                )
        elif prenatal is None:
            text = (
                "nie pobierała zasiłku macierzyńskiego za okres odpowiadający części urlopu "
                "macierzyńskiego przed porodem"
            )
        else:
            text = (
                "pobierała zasiłek macierzyński za okres odpowiadający części urlopu "
                f"macierzyńskiego przed porodem, {period(prenatal.start, prenatal.end)}"
            )
        return statement(f"Oświadczam, że matka dziecka {text}.")

    def procedure(self) -> str | None:
        """The Labour Code provision the regulation names for this request ("Wniosek, o którym
        mowa w art. 182¹ᵈ § 1 Kodeksu pracy")."""
        for source in self.form.legal_basis:
            if source.doc == "rozp_wnioski":
                found = re.search(r"mowa w (art\. \S+ § \d+)", source.quote)
                if found:
                    return found.group(1)
        return None

    def basis_line(self, articles: list[str]) -> str:
        cited = list(dict.fromkeys([*articles, *filter(None, [self.procedure()])]))
        line = f"Podstawa prawna: {', '.join(cited)} Kodeksu pracy"
        paragraphs = [s.article for s in self.form.legal_basis if s.doc == "rozp_wnioski"]
        if paragraphs and paragraphs[0]:
            line += f"; {paragraphs[0].split(' ust.')[0]} {REGULATION}"
        return line + "."

    def attachments(self, labels: dict[str, str]) -> list[str]:
        later = not self.timeline.child_born and self.kind in ("prenatal", "maternity")
        return [
            self.attachment(a, labels)
            for a in self.form.attachments
            if a.id not in FOLDED and not (later and a.id in NOT_YET_BORN)
        ]

    def attachment(self, item: FormAttachment, labels: dict[str, str]) -> str:
        label = labels.get(item.id) or ATTACHMENT_LABELS.get(item.id) or item.label
        if item.id == "birth-certificate" and self.count > 1:
            label = "Odpisy skrócone aktów urodzenia dzieci"
        return label if item.required else f"{label} (jeżeli dotyczy)"

    def fields(self, texts: list[str]) -> list[LetterField]:
        own = {f.id: f.label for f in self.form.fields}
        used = dict.fromkeys(m for text in texts for m in TOKEN.findall(text))
        fields = []
        for field_id in used:
            label, meaning, personal = LETTER_FIELDS[field_id]
            if field_id == "child-name" and self.count > 1:
                label = "Imiona i nazwiska dzieci"
            fields.append(
                LetterField(
                    id=field_id, label=own.get(field_id, label), meaning=meaning, personal=personal
                )
            )
        return fields

    def more_drafts(self) -> dict[str, Callable[[], Draft]]:
        """Letters of other kinds of request: a child taken in (adoption_applications.py)."""
        return {}

    # The letter.

    def build(self) -> tuple[Letter, HrMessage]:
        drafts = {
            "prenatal": self.prenatal,
            "maternity": self.maternity,
            "resignation": self.resignation,
            "father-takeover": self.father_takeover,
            "father-hospital-employee": self.father_hospital,
            "father-hospital-insured": self.father_hospital,
            "father-death": self.father_death,
            "father-abandonment": self.father_abandonment,
            "supplementary": self.supplementary,
            "parental": self.parental,
            "parental-work": self.parental_work,
            "paternity": self.paternity,
            **self.more_drafts(),
        }
        draft = drafts[self.kind]()
        mother = self.form.applicant == "mother"
        attachments = self.attachments(draft.labels or {})
        name = token(self.name)
        what = draft.title[0].lower() + draft.title[1:]
        with_attachments = " wraz z załącznikami" if attachments else ""
        hr = HrMessage(
            subject=f"{draft.title} {draft.when}",
            body=tidy(
                f"Dzień dobry,\n\nw załączeniu przesyłam {what} {draft.when}{with_attachments}. "
                f"Proszę o potwierdzenie jego otrzymania.\n\nZ poważaniem\n{name}"
            ),
        )
        letter = Letter(
            place_date=f"{token('letter-place')}, dnia {token('letter-date')}",
            applicant=[name, token("applicant-address")],
            addressee=["Pracodawca", token("employer")],
            title=draft.title,
            body=draft.body,
            attachments=attachments,
            signature=f"(czytelny podpis {'pracownicy' if mother else 'pracownika'})",
            legal_basis=self.basis_line(draft.articles),
            fields=[],
        )
        texts = [
            letter.place_date,
            *letter.applicant,
            *letter.addressee,
            *(p.text for p in letter.body),
            *(o for p in letter.body for o in p.options),
            hr.subject,
            hr.body,
        ]
        letter.fields = self.fields(texts)
        return letter, hr

    # One method per kind of request (params.forms.templates).

    def prenatal(self) -> Draft:
        """§ 2: the date the part before the birth starts; the medical certificate with the due
        date goes with it (art. 180 § 2)."""
        start, _ = self.field_dates("leave-from")
        text = (
            "Na podstawie art. 180 § 2 Kodeksu pracy wnoszę o udzielenie mi części urlopu "
            f"macierzyńskiego przed przewidywaną datą porodu, od dnia {date_r(start)}."
        )
        due = self.scenario.due_date
        if due is not None:
            text += (
                " Przewidywana data porodu, określona w zaświadczeniu lekarskim, którego kopię "
                f"załączam, to {date_r(due)}."
            )
        text += " Pozostałą część urlopu macierzyńskiego wykorzystam po porodzie."
        body = [request(text)]
        if not self.timeline.child_born and any(
            a.id == "birth-certificate" for a in self.form.attachments
        ):
            body.append(statement("Odpis skrócony aktu urodzenia dziecka dostarczę po porodzie."))
        return Draft(
            "Wniosek o udzielenie części urlopu macierzyńskiego przed przewidywaną datą porodu",
            body,
            ["art. 180 § 2"],
            f"od dnia {date_r(start)}",
        )

    def maternity(self) -> Draft:
        """The employed mother's request without a part before the birth (guide A.4): the
        period on the timeline; from the day of birth when she takes nothing before it."""
        assert self.form.start is not None and self.form.end is not None
        start, end = self.form.start, self.form.end
        days = (end - start).days + 1
        title = "Wniosek o udzielenie urlopu macierzyńskiego"
        if not self.timeline.child_born:
            text = (
                "Na podstawie art. 180 § 1 i art. 183¹ § 2 Kodeksu pracy wnoszę o udzielenie mi "
                f"urlopu macierzyńskiego w wymiarze {duration(days)} od dnia porodu."
            )
            if self.scenario.due_date is not None:
                text += f" Przewidywana data porodu to {date_r(self.scenario.due_date)}."
            body = [request(text)]
            if any(a.id == "birth-certificate" for a in self.form.attachments):
                body.append(
                    statement("Odpis skrócony aktu urodzenia dziecka dostarczę po porodzie.")
                )
            return Draft(title, body, ["art. 180 § 1", "art. 183¹ § 2"], "od dnia porodu")
        loss = child_loss(self.scenario, self.params, self.timeline.birth_date, self.timeline.today)
        if loss is not None:
            article = "art. 180¹ § 1" if loss.early else "art. 180¹ § 2"
            reason = f"w związku z porodem w dniu {date_r(self.timeline.birth_date)}"
        else:
            article, reason = "art. 180 § 1", self.born()
        text = (
            f"Na podstawie {article} Kodeksu pracy wnoszę o udzielenie mi urlopu macierzyńskiego "
            f"w wymiarze {duration(days)}, w okresie {period(start, end)}, {reason}."
        )
        return Draft(title, [request(text)], [article], period(start, end))

    def resignation(self) -> Draft:
        """§ 3: the day of return to work; the copy of the father's request (an employee) or of
        his statement (not an employee) — art. 180 § 4 pkt 1-2."""
        back, _ = self.field_dates("return-date")
        maternity = self.segment("maternity")
        assert maternity is not None
        text = (
            "Na podstawie art. 180 § 4 Kodeksu pracy rezygnuję z pozostałej części urlopu "
            f"macierzyńskiego po wykorzystaniu po porodzie {duration(maternity.days)} tego urlopu "
            f"i wnoszę o umożliwienie mi powrotu do pracy od dnia {date_r(back)}."
        )
        employee = (
            "pozostałą część urlopu macierzyńskiego wykorzysta ojciec wychowujący dziecko, który "
            "jest pracownikiem"
        )
        business = (
            "przez okres, który pozostał do końca urlopu macierzyńskiego, osobistą opiekę nad "
            "dzieckiem będzie sprawował ojciec dziecka, który w tym celu przerwał działalność "
            "zarobkową"
        )
        labels = {}
        match self.scenario.fathers_work:
            case "employment":
                father = statement(
                    f"Oświadczam, że {employee} (kopia jego wniosku o udzielenie tej części "
                    "urlopu w załączeniu)."
                )
                labels["father-request-copy"] = (
                    "Kopia wniosku ojca dziecka o udzielenie pozostałej części urlopu "
                    "macierzyńskiego"
                )
            case "contract" | "business":
                father = statement(
                    f"Oświadczam, że {business} (kopia jego oświadczenia w załączeniu)."
                )
                labels["father-request-copy"] = (
                    "Kopia oświadczenia ojca dziecka o przerwaniu działalności zarobkowej "
                    "w celu sprawowania opieki nad dzieckiem"
                )
            case _:
                father = LetterParagraph(
                    kind="choice", text="Oświadczam, że:", options=[employee, business]
                )
                labels["father-request-copy"] = (
                    "Kopia wniosku ojca dziecka o udzielenie pozostałej części urlopu "
                    "macierzyńskiego albo kopia jego oświadczenia o przerwaniu działalności "
                    "zarobkowej"
                )
        return Draft(
            "Wniosek w sprawie rezygnacji z pozostałej części urlopu macierzyńskiego i powrotu "
            "do pracy",
            [request(text), father],
            ["art. 180 § 4"],
            f"od dnia {date_r(back)}",
            labels,
        )

    def father_takeover(self) -> Draft:
        """§ 5: the father takes over after the mother's 14 weeks (art. 180 § 4 pkt 1, § 5) or
        after 8 weeks of a mother with a ruling of incapacity (§ 6 pkt 1, § 7 — not in our
        excerpt, so the request's own art. 180 § 9)."""
        start, end = self.field_dates("leave-period")
        assert end is not None
        his = (end - start).days + 1
        mother = self.segment("maternity")
        used = duration(mother.days) if mother is not None else None
        incapacity = self.scenario.mother_event is not None
        ruling = (
            ", legitymującej się orzeczeniem o niezdolności do samodzielnej egzystencji,"
            if incapacity
            else ""
        )
        if self.mother_employee:
            article = "art. 180 § 6" if incapacity else "art. 180 § 4"
            reason = f"w związku z rezygnacją matki dziecka{ruling} z pozostałej części urlopu "
            reason += "macierzyńskiego"
            if used:
                reason += f" po wykorzystaniu przez nią po porodzie {used} tego urlopu"
            what = "Oświadczenie matki dziecka o zamiarze rezygnacji z pozostałej części urlopu "
            what += "macierzyńskiego"
        else:
            article = "art. 180 § 9" if incapacity else "art. 180 § 5"
            reason = f"w związku z rezygnacją matki dziecka{ruling} z pobierania zasiłku "
            reason += "macierzyńskiego"
            if used:
                reason += f" po wykorzystaniu przez nią tego zasiłku za okres {used} po porodzie"
            what = (
                "Oświadczenie matki dziecka o zamiarze rezygnacji z pobierania zasiłku "
                "macierzyńskiego za okres odpowiadający pozostałej części urlopu macierzyńskiego"
            )
        text = (
            f"Na podstawie {article} Kodeksu pracy wnoszę o udzielenie mi pozostałej części "
            f"urlopu macierzyńskiego w wymiarze {duration(his)}, w okresie {period(start, end)}, "
            f"{reason}. {self.concerns()}"
        )
        return Draft(
            "Wniosek o udzielenie pozostałej części urlopu macierzyńskiego",
            [request(text), self.prenatal_statement()],
            [article],
            period(start, end),
            {"mother-resignation-statement": what},
        )

    def father_hospital(self) -> Draft:
        """§ 6 (the mother is an employee) and § 7 (insured, not an employee): from the day she
        interrupted the leave (the benefit) for her stay in hospital (art. 180 § 10, § 11)."""
        start, _ = self.field_dates("leave-from")
        employee = self.kind.endswith("-employee")
        article = "art. 180 § 10" if employee else "art. 180 § 11"
        stopped = "urlop macierzyński" if employee else "pobieranie zasiłku macierzyńskiego"
        text = (
            f"Na podstawie {article} Kodeksu pracy wnoszę o udzielenie mi części urlopu "
            f"macierzyńskiego od dnia {date_r(start)}, to jest od dnia, od którego matka dziecka "
            f"przerwała {stopped} na okres pobytu w szpitalu ze względu na stan zdrowia "
            f"uniemożliwiający jej sprawowanie osobistej opieki nad dzieckiem. {self.concerns()}"
        )
        mothers = (
            f"Oświadczenie matki dziecka wskazujące datę, od której przerwała {stopped} na okres "
            "pobytu w szpitalu"
        )
        return Draft(
            "Wniosek o udzielenie części urlopu macierzyńskiego",
            [
                request(text),
                self.prenatal_statement(),
                statement(
                    "Zobowiązuję się poinformować pracodawcę o dacie opuszczenia przez matkę "
                    "dziecka szpitala."
                ),
            ],
            [article],
            f"od dnia {date_r(start)}",
            {"mother-statement": mothers},
        )

    def _after_mother(self, article: str, reason: str, event: str) -> Draft:
        """§ 8 (death) and § 9 (abandonment): the date of the event and the father's part."""
        start, _ = self.field_dates("leave-from")
        happened, _ = self.field_dates("event-date")
        his = self.segment("maternity-father")
        assert his is not None
        text = (
            f"Na podstawie {article} Kodeksu pracy wnoszę o udzielenie mi części urlopu "
            f"macierzyńskiego w wymiarze {duration(his.days)}, w okresie "
            f"{period(start, his.end)}, {reason}. {self.concerns()}"
        )
        return Draft(
            "Wniosek o udzielenie części urlopu macierzyńskiego",
            [
                request(text),
                statement(f"Oświadczam, że matka dziecka {event} w dniu {date_r(happened)}."),
                self.prenatal_statement(),
            ],
            [article],
            period(start, his.end),
        )

    def father_death(self) -> Draft:
        return self._after_mother("art. 180 § 12", "w związku ze zgonem matki dziecka", "zmarła")

    def father_abandonment(self) -> Draft:
        return self._after_mother(
            "art. 180 § 13",
            "w związku z porzuceniem dziecka przez matkę dziecka",
            "porzuciła dziecko",
        )

    def supplementary(self) -> Draft:
        """§ 14: the end of maternity leave and the period of supplementary leave (art. 180²
        § 1); the statement that the other parent will not use it (ust. 2 pkt 2)."""
        start, end = self.field_dates("leave-period")
        maternity_end, _ = self.field_dates("maternity-end")
        assert end is not None
        child = token("child-name")
        stay = (
            f"dziecka {child}, urodzonego w dniu {self.birth_day()}"
            if self.count == 1
            else f"dzieci {child}, urodzonych w dniu {self.birth_day()}"
        )
        text = (
            "Na podstawie art. 180² § 1 Kodeksu pracy wnoszę o udzielenie mi uzupełniającego "
            f"urlopu macierzyńskiego w wymiarze {duration((end - start).days + 1)}, w okresie "
            f"{period(start, end)}, w związku z pobytem w szpitalu {stay}. Urlop macierzyński "
            f"kończy się {date_r(maternity_end)}."
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
            ["art. 180² § 1"],
            period(start, end),
        )

    def parental(self) -> Draft:
        """§ 15: the period (art. 182¹ᵃ § 1, with "Za życiem" § 2), the parental leave used so far
        and the number of parts (ust. 1 pkt 2), the other parent's leave in this period (ust. 2
        pkt 2); a part combined with work is longer (art. 182¹ᶠ § 1)."""
        assert self.document.segment_id is not None
        leave = self.segment(self.document.segment_id)
        assert leave is not None
        article = "art. 182¹ᵃ § 2" if self.scenario.za_zyciem else "art. 182¹ᵃ § 1"
        part = self.document.id.startswith(PLAN_REQUESTS)
        what = "części urlopu rodzicielskiego" if part else "urlopu rodzicielskiego"
        planned = planned_parts(self.scenario).get(leave.id)
        articles = [article]
        if planned is not None and extension_days(planned) > 0:
            text = (
                f"Na podstawie {article} Kodeksu pracy wnoszę o udzielenie mi {what} w wymiarze "
                f"{duration(planned.weeks * 7)}, od dnia {date_r(leave.start)}, {self.born()}. "
                "W związku z łączeniem urlopu z pracą (osobny wniosek) urlop wydłuża się "
                f"proporcjonalnie do {duration(leave.days)} i trwa do {date_r(leave.end)} "
                "(art. 182¹ᶠ § 1 Kodeksu pracy)."
            )
            articles.append("art. 182¹ᶠ § 1")
        else:
            text = (
                f"Na podstawie {article} Kodeksu pracy wnoszę o udzielenie mi {what} w wymiarze "
                f"{duration(leave.days)}, w okresie {period(leave.start, leave.end)}, "
                f"{self.born()}."
            )
        return Draft(
            "Wniosek o udzielenie części urlopu rodzicielskiego"
            if part
            else "Wniosek o udzielenie urlopu rodzicielskiego",
            [request(text), self.used_so_far(leave), self.other_parent(leave)],
            articles,
            period(leave.start, leave.end),
        )

    def used_so_far(self, leave: Segment) -> LetterParagraph:
        """Parental leave of either parent on the timeline before this period (our reading of
        § 15 ust. 1 pkt 2, as in the form)."""
        before = [
            s for s in self.timeline.segments if s.id.startswith("parental") and s.end < leave.start
        ]
        if not before:
            return statement(
                "Oświadczam, że dotychczas nie był wykorzystany urlop rodzicielski ani zasiłek "
                "macierzyński za okres odpowiadający okresowi tego urlopu; liczba wykorzystanych "
                "części urlopu rodzicielskiego: 0."
            )
        mine = self.form.applicant
        used = "; ".join(
            f"{'przeze mnie' if s.lane == mine else 'przez drugiego z rodziców'} "
            f"{period(s.start, s.end)}"
            for s in before
        )
        return statement(
            "Oświadczam, że dotychczas urlop rodzicielski (albo zasiłek macierzyński za okres "
            f"odpowiadający okresowi tego urlopu) został wykorzystany: {used}; liczba "
            f"wykorzystanych części urlopu rodzicielskiego: {len(before)}."
        )

    def other_parent(self, leave: Segment) -> LetterParagraph:
        """§ 15 ust. 2 pkt 2: whether the other parent has parental leave in this period, as the
        timeline shows (the part of it within the period asked for)."""
        other = "father" if self.form.applicant == "mother" else "mother"
        overlap = [
            (max(s.start, leave.start), min(s.end, leave.end))
            for s in self.timeline.segments
            if s.lane == other
            and s.id.startswith("parental")
            and s.start <= leave.end
            and s.end >= leave.start
        ]
        if not overlap:
            return statement(
                "Oświadczam, że drugi z rodziców dziecka nie zamierza korzystać z urlopu "
                "rodzicielskiego ani z zasiłku macierzyńskiego za okres odpowiadający okresowi "
                "urlopu rodzicielskiego w okresie wskazanym we wniosku."
            )
        when = " oraz ".join(period(start, end) for start, end in overlap)
        return statement(
            "Oświadczam, że drugi z rodziców dziecka zamierza korzystać z urlopu rodzicielskiego "
            "(albo z zasiłku macierzyńskiego za okres odpowiadający okresowi tego urlopu) "
            f"w okresie objętym wnioskiem: {when}."
        )

    def parental_work(self) -> Draft:
        """§ 16: the part of full time, the period of work (art. 182¹ᵉ § 1) and the statement on
        the extension (pkt 4): the plan has no work in it."""
        assert self.document.segment_id is not None
        leave = self.segment(self.document.segment_id)
        planned = planned_parts(self.scenario).get(self.document.segment_id)
        assert leave is not None and planned is not None and planned.work_fraction is not None
        until = work_end(planned, leave.start)
        share = fraction(planned.work_fraction)
        text = (
            "Na podstawie art. 182¹ᵉ § 1 Kodeksu pracy wnoszę o umożliwienie mi łączenia "
            f"korzystania z urlopu rodzicielskiego, przypadającego od dnia {date_r(leave.start)}, "
            f"z wykonywaniem pracy u pracodawcy w wymiarze {share} pełnego wymiaru czasu pracy, "
            f"w okresie {period(leave.start, until)}."
        )
        body = [request(text)]
        extension = extension_days(planned)
        if extension > 0:
            first = leave.end - (extension - 1) * DAY
            body.append(
                statement(
                    "Oświadczam, że nie zamierzam łączyć z pracą części urlopu rodzicielskiego "
                    "powstałej w wyniku proporcjonalnego wydłużenia tego urlopu "
                    f"({period(first, leave.end)})."
                )
            )
        return Draft(
            "Wniosek o łączenie korzystania z urlopu rodzicielskiego z wykonywaniem pracy",
            body,
            ["art. 182¹ᵉ § 1"],
            f"w okresie {period(leave.start, until)}",
        )

    def paternity(self) -> Draft:
        """§ 17: the period (art. 182³ § 1); whether the father already used paternity leave
        (ust. 2 pkt 3) the timeline cannot know: both options."""
        start, end = self.field_dates("leave-period")
        assert end is not None
        text = (
            "Na podstawie art. 182³ § 1 Kodeksu pracy wnoszę o udzielenie mi urlopu ojcowskiego "
            f"w wymiarze {duration((end - start).days + 1)}, w okresie {period(start, end)}, "
            f"{self.born()}."
        )
        used = LetterParagraph(
            kind="choice",
            text="Oświadczam, że:",
            options=[
                "nie korzystałem z urlopu ojcowskiego ani z jego części",
                "korzystałem z urlopu ojcowskiego albo z jego części",
            ],
        )
        return Draft(
            "Wniosek o udzielenie urlopu ojcowskiego",
            [request(text), used],
            ["art. 182³ § 1"],
            period(start, end),
        )
