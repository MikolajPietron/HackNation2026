"""Request forms (ZADANIA B.3, engine/forms.py): each request on the timeline as a form, its
fields as the regulations name them, filled in from the scenario and the timeline.

Sources: the regulation of 11 March 2025 on the leave requests (rozp_wnioski: § 2, § 3, § 4,
§ 5, § 7, § 10-§ 12, § 14, § 15, § 16, § 17, § 22), the regulation of 27 September 2026 on the
benefit documents (rozp_zasilki: § 2, § 12, § 13, § 20, § 22, § 32, § 33, annexes 1 and 6), the
guide (A.4, page 12).

Expected dates were computed by hand, today being 21.11.2026:
- due 15.03.2027, leave 2 weeks before: from 01.03.2027; maternity leave until 18.07.2027; the
  mother's parental leave 19.07.2027-27.02.2028 (32 weeks), the father's 28.02-30.04.2028
  (9 weeks: 28.02.2028 + 62 days, 2028 is a leap year); paternity leave 15.03-28.03.2027;
- born 10.11.2026, no leave before: maternity leave 10.11.2026-29.03.2027 (+139 days);
  the father takes over after 14 weeks: the mother back at work 16.02.2027, his part
  16.02-29.03.2027 (13 + 29 days = 6 weeks); her parental leave (32 weeks) 30.03-08.11.2027;
- born 01.10.2026, 20 days in hospital: maternity leave until 17.02.2027, supplementary leave
  18.02-10.03.2027 (3 weeks);
- born 01.10.2026, the mother (on a contract) in hospital 01.12-20.12.2026, after 8 weeks
  (26.11.2026): the father's part of maternity leave from 01.12.2026;
- born 01.10.2026, the mother's ruling of incapacity, the father from 01.12.2026: her
  resignation at least 7 days before she goes back, by 24.11.2026;
- born 01.10.2026 to a mother without sickness insurance who died (abandoned the child, has a
  ruling) on 15.10.2026: the father's part from the day after, 16.10.2026, to the end of 20
  weeks from the birth, 17.02.2027 (+139 days);
- a business insured from 01.10.2026, sick from 01.11.2026: the right after 90 days, from
  30.12.2026; the benefit until the day before the due date, 14.03.2027 (2 + 31 + 28 + 14 = 75
  days);
- born 10.11.2026, a plan: the mother 20 weeks right after maternity leave 30.03-16.08.2027
  (+139 days), the father 9 weeks at the same time 30.03-31.05.2027 (+62 days), the mother
  12 weeks from 01.06.2028 to 23.08.2028 (+83 days); each request 21 days before its part:
  09.03.2027, 09.03.2027, 11.05.2028;
- born 10.11.2026, a plan with work at 1/2 of full time (ZADANIA B.13): the mother 32 weeks
  from 30.03.2027, working the first 20 (30.03-16.08.2027, +139 days); the extension
  20 × 1/2 = 10 weeks, so the part ends 30.03.2027 + 32 × 7 + 70 - 1 = +293 days = 17.01.2028,
  the extension 09.11.2027-17.01.2028; the father 9 weeks right after, from 18.01.2028, working
  all 9 (18.01-20.03.2028, +62 days, 2028 a leap year); his extension 9 × 7 × 1/2 = 31,5 days,
  so 31; his part ends 18.01.2028 + 63 + 31 - 1 = +93 days = 20.04.2028, the extension
  21.03-20.04.2028. Each request to work 21 days before the work starts (its part's first day):
  30.03.2027 - 21 = 09.03.2027, 18.01.2028 - 21 = 28.12.2027;
- born 01.07.2026, no leave before: maternity leave until 17.11.2026 (+139 days); the mother's
  part with work from 18.11.2026 is under way on 21.11.2026 (no requests any more); the father
  9 weeks at 1/2 from 01.12.2026: request by 01.12.2026 - 21 = 10.11.2026, passed; his work
  01.12.2026-01.02.2027 (+62 days).
"""

import datetime as dt

from app.engine import Scenario, Timeline, build_timeline
from app.engine.models import Document, FormField, RequestForm
from app.services.params import load_params

PARAMS = load_params()
TODAY = dt.date(2026, 11, 21)
BORN = {"child_born": True, "birth_date": "2026-11-10", "leave_before_birth_weeks": 0}
BORN |= {"children_count": 1}
PARENTS = {"role": "mother", "work": "employment", "father_work": "employment"}


def timeline(**answers: object) -> Timeline:
    return build_timeline(Scenario.model_validate(answers), PARAMS, TODAY)


def form(t: Timeline, document_id: str) -> RequestForm:
    document = next(d for d in t.documents if d.id == document_id)
    assert document.form is not None, document_id
    return document.form


def document(t: Timeline, document_id: str) -> Document:
    return next(d for d in t.documents if d.id == document_id)


def field(f: RequestForm, field_id: str) -> FormField:
    return next(x for x in f.fields if x.id == field_id)


def values(f: RequestForm) -> dict[str, str | None]:
    return {x.id: x.value for x in f.fields}


def attachments(f: RequestForm) -> list[tuple[str, bool]]:
    return [(a.id, a.required) for a in f.attachments]


def articles(f: RequestForm) -> list[str | None]:
    return [s.article for s in f.legal_basis if s.doc.startswith("rozp_")]


def expecting() -> Timeline:
    return timeline(
        **PARENTS,
        child_born=False,
        due_date="2027-03-15",
        children_count=1,
        leave_before_birth_weeks=2,
        mother_payer_size="up-to-20",
        has_medical_certificate=True,
    )


def test_the_part_of_maternity_leave_before_the_birth() -> None:
    """§ 2: the employee's name (typed in, never filled) and the first day of the leave; the
    medical certificate goes with it. ZUS pays (20 or fewer insured): no birth certificate,
    the child's data instead (rozp_zasilki § 13 ust. 2-3)."""
    f = form(expecting(), "maternity-request")
    assert (f.applicant, f.addressee, f.addressee_label) == (
        "mother",
        "employer",
        "Pracodawca mamy",
    )
    assert f.official_form is None
    assert articles(f) == ["§ 2 ust. 1"]
    assert (f.start, f.end) == (dt.date(2027, 3, 1), dt.date(2027, 7, 18))
    assert values(f) == {"employee-name": None, "leave-from": "01.03.2027"}
    name, leave_from = f.fields
    assert (name.personal, name.label) == (True, "Imię i nazwisko pracownicy")
    assert (leave_from.kind, leave_from.start, leave_from.personal) == (
        "date",
        dt.date(2027, 3, 1),
        False,
    )
    assert attachments(f) == [("due-date-certificate", True)]
    assert f.attachments[0].hint == "Na osi: zaświadczenie już masz."
    assert f.attachments[0].sources[0].article == "§ 2 ust. 2"
    assert [n.sources[0].article for n in f.notes] == ["§ 13 ust. 2", "§ 22"]


def test_maternity_leave_after_the_birth_has_no_fields_in_the_materials() -> None:
    """The regulation gives the content only of the part before the birth: no fields, the period
    on the timeline and, when the employer pays, the birth certificate."""
    f = form(timeline(**PARENTS, **BORN, mother_payer_size="over-20"), "maternity-request")
    assert f.fields == []
    assert (f.start, f.end) == (dt.date(2026, 11, 10), dt.date(2027, 3, 29))
    assert [s.section for s in f.legal_basis] == ["A.4"]
    assert attachments(f) == [("birth-certificate", True)]
    assert f.notes[0].text.startswith("Rozporządzenie o wnioskach urlopowych podaje")


def test_parental_and_paternity_leave_requests() -> None:
    """§ 15 and § 17: the period from the timeline; the parental leave used so far (none before
    the mother's, hers before the father's); the other parent's statement; the birth
    certificate."""
    t = expecting()
    mother = form(t, "parental-request")
    assert articles(mother) == ["§ 15 ust. 1"]
    assert values(mother) == {
        "employee-name": None,
        "used-so-far": "Brak: to pierwsza część urlopu rodzicielskiego.",
        "leave-period": "od 19.07.2027 do 27.02.2028 (32 tyg.)",
    }
    period = field(mother, "leave-period")
    assert (period.kind, period.start, period.end) == (
        "period",
        dt.date(2027, 7, 19),
        dt.date(2028, 2, 27),
    )
    assert "do wyboru" in (period.hint or "")
    assert attachments(mother) == [("birth-certificate", True), ("other-parent-statement", True)]
    assert mother.attachments[1].hint == (
        "Na osi drugi z rodziców nie ma w tym czasie urlopu rodzicielskiego."
    )

    father = form(t, "parental-father-request")
    assert father.addressee_label == "Pracodawca taty"
    assert values(father)["used-so-far"] == (
        "Na osi przed tym okresem: mama: urlop rodzicielski (do wyboru): od 19.07.2027 do "
        "27.02.2028 (32 tyg.). Części: 1."
    )
    assert values(father)["leave-period"] == "od 28.02.2028 do 30.04.2028 (9 tyg.)"

    paternity = form(t, "paternity-request")
    assert articles(paternity) == ["§ 17 ust. 1"]
    assert values(paternity)["leave-period"] == "od 15.03.2027 do 28.03.2027 (2 tyg.)"
    assert attachments(paternity) == [("birth-certificate", True), ("paternity-statement", True)]


def test_za_zyciem_goes_with_the_parental_leave_request() -> None:
    t = timeline(**PARENTS, **BORN, za_zyciem=True)
    assert ("za-zyciem-certificate", True) in attachments(form(t, "parental-request"))


def test_the_father_takes_over_after_14_weeks() -> None:
    """§ 3: the mother's return to work and a copy of the father's request (he is an employee);
    § 5: the child's birth date, her leave before the birth (none), his part of the leave."""
    t = timeline(**PARENTS, **BORN, father_takes_over=True)
    resignation = form(t, "maternity-resignation")
    assert articles(resignation) == ["§ 3 ust. 1"]
    assert values(resignation) == {"employee-name": None, "return-date": "16.02.2027"}
    assert resignation.attachments[0].hint == (
        "Tata pracuje na umowie o pracę: kopia jego wniosku do pracodawcy."
    )
    his = form(t, "maternity-father-request")
    assert articles(his) == ["§ 5 ust. 1"]
    assert values(his) == {
        "father-name": None,
        "child-name": None,
        "child-birth-date": "10.11.2026",
        "prenatal-leave": "Brak: mama nie korzystała z tego przed porodem.",
        "leave-period": "od 16.02.2027 do 29.03.2027 (6 tyg.)",
    }
    assert {x.id for x in his.fields if x.personal} == {"father-name", "child-name"}
    assert attachments(his) == [
        ("birth-certificate", True),
        ("mother-resignation-statement", True),
    ]


def test_the_father_while_the_mother_on_a_contract_is_in_hospital() -> None:
    """§ 7 (the mother is insured, not an employee): the day she interrupted the benefit, her
    statement, the hospital's certificate of admission, the birth certificate."""
    t = timeline(
        role="mother",
        work="contract",
        mother_insured=True,
        father_work="employment",
        child_born=True,
        birth_date="2026-10-01",
        leave_before_birth_weeks=0,
        children_count=1,
        mother_event={"kind": "hospital", "start": "2026-12-01", "end": "2026-12-20"},
    )
    request = document(t, "maternity-father-request")
    assert request.deadline is None  # art. 180 § 16: no deadline
    his = form(t, "maternity-father-request")
    assert articles(his) == ["§ 7 ust. 1"]
    assert values(his)["leave-from"] == "01.12.2026"
    assert attachments(his) == [
        ("mother-statement", True),
        ("admission-certificate", True),
        ("birth-certificate", True),
    ]
    # Her own request is ZAM, with the payer or ZUS (the size of the payer is not known).
    zam = form(t, "maternity-request")
    assert (zam.official_form, zam.addressee) == ("ZAM", "payer-or-zus")


def test_supplementary_leave_request() -> None:
    """§ 14: the end of maternity leave and the period of supplementary leave; the hospital's
    certificate (art. 180² § 5) and the other parent's statement."""
    t = timeline(
        **PARENTS,
        child_born=True,
        birth_date="2026-10-01",
        leave_before_birth_weeks=0,
        children_count=1,
        hospital_care=True,
        birth_week="28-37",
        birth_weight_up_to_1000g=False,
        hospital_stays=[{"start": "2026-10-01", "end": "2026-10-20"}],
    )
    f = form(t, "supplementary-request")
    assert articles(f) == ["§ 14 ust. 1"]
    assert values(f) == {
        "employee-name": None,
        "maternity-end": "17.02.2027",
        "leave-period": "od 18.02.2027 do 10.03.2027 (3 tyg.)",
    }
    assert attachments(f) == [("hospital-certificate", True), ("other-parent-statement", True)]
    certificate = f.attachments[0]
    assert {(s.doc, s.article) for s in certificate.sources} == {
        ("rozp_wnioski", "§ 14 ust. 2"),
        ("kp", "art. 180² § 5"),
    }


def test_zam_with_her_own_business() -> None:
    """Annex 6 (§ 12): personal data typed in; from the timeline the child's birth date, the
    benefit and its periods, the reason; with a business ZUS pays: no birth certificate."""
    t = timeline(role="mother", work="business", mother_insured=True, father_work="none", **BORN)
    f = form(t, "maternity-request")
    assert (f.official_form, f.addressee, f.addressee_label) == ("ZAM", "zus", "ZUS")
    assert articles(f) == ["§ 12"]
    filled = {k: v for k, v in values(f).items() if v is not None}
    assert filled == {
        "child-birth-date": "10.11.2026",
        "benefit-period": (
            "Zasiłek macierzyński za okres: urlop macierzyński po porodzie: od 10.11.2026 do "
            "29.03.2027 (20 tyg.); urlop rodzicielski (do wyboru): od 30.03.2027 do 08.11.2027 "
            "(32 tyg.)."
        ),
        "reason": "urodzenie dziecka",
    }
    personal = {x.id for x in f.fields if x.personal}
    assert personal == {
        "payer-nip",
        "payer-name",
        "insured-name",
        "insured-pesel",
        "insured-address",
        "child-name",
        "child-pesel",
        "child-birth-place",
        "other-parent",
        "bank-account",
        "signature",
    }
    # Only what applies: no hospital stay, it is the mother's own request.
    assert not {"hospital", "mother-situation", "other-parent-use"} & {x.id for x in f.fields}
    assert all(s.article == "zał. 6" for x in f.fields for s in x.sources)
    # ZAM for parental leave comes with the statement of the benefit for it already paid
    # (rozp_zasilki § 29 pkt 4, § 30 ust. 1 pkt 5): here the first part of it.
    assert attachments(f) == [("parental-benefit-statement", True)]
    statement = f.attachments[0]
    assert {s.article for s in statement.sources} == {"§ 29", "§ 30 ust. 1"}
    assert (
        statement.hint == "Na osi wcześniej nie ma urlopu rodzicielskiego: to pierwsza jego część."
    )
    assert f.notes[0].text.startswith("Formularz ZAM jest na www.zus.pl")
    assert "odpisu aktu urodzenia dziecka się nie przedstawia" in f.notes[1].text


def test_zam_of_the_father_whose_partner_does_not_work() -> None:
    """The father on a contract: his ZAM says why the mother does not have the benefit and has
    the documents of § 32 (no insurance title of the mother) and § 33 (paternity leave)."""
    t = timeline(role="father", work="contract", father_insured=True, mother_work="none", **BORN)
    f = form(t, "father-benefit-request")
    assert (f.applicant, f.official_form, f.addressee) == ("father", "ZAM", "payer-or-zus")
    assert values(f)["mother-situation"] == (
        "Mama nie pracuje, więc nie podlega ubezpieczeniu chorobowemu."
    )
    assert values(f)["parts"] == "Urlop ojcowski (do wyboru): od 21.11.2026 do 04.12.2026 (2 tyg.)."
    # His first period is paternity leave from today: ZAM for it is filed before the benefit
    # starts (§ 33 ust. 1 pkt 3), so it is in time for paternity leave from 22.11.2026. ZAM keeps
    # the timeline's periods and says so.
    benefit = next(x for x in f.fields if x.id == "benefit-period")
    assert benefit.hint == (
        "Okresy z osi czasu. Termin wniosku za okres od 21.11.2026 minął: złożony dziś jest "
        "w terminie dla zasiłku od 22.11.2026."
    )
    # § 32 (his parental leave, the mother without an insurance title) names no statement of
    # the benefit already paid, unlike § 29 pkt 4 and § 30 ust. 1 pkt 5.
    assert attachments(f) == [
        ("birth-certificate", False),
        ("mother-uninsured-statement", True),
        ("paternity-statement", True),
    ]
    assert {s.article for a in f.attachments[1:] for s in a.sources} == {
        "§ 32 ust. 1",
        "§ 33 ust. 1",
    }


def test_the_mother_with_a_ruling_of_incapacity_resigns() -> None:
    """§ 4 (art. 180 § 6, § 8): her return to work, the copy of the father's request and a copy
    of her ruling. Born 01.10.2026, the father from 01.12.2026."""
    t = timeline(
        **PARENTS,
        child_born=True,
        birth_date="2026-10-01",
        leave_before_birth_weeks=0,
        children_count=1,
        mother_event={"kind": "incapacity", "start": "2026-12-01"},
    )
    resignation = form(t, "maternity-resignation")
    assert articles(resignation) == ["§ 4 ust. 1"]
    assert values(resignation) == {"employee-name": None, "return-date": "01.12.2026"}
    assert attachments(resignation) == [
        ("father-request-copy", True),
        ("incapacity-ruling-copy", True),
    ]
    assert {s.article for a in resignation.attachments for s in a.sources} == {"§ 4 ust. 2"}
    assert document(t, "maternity-resignation").deadline == dt.date(2026, 11, 24)


UNINSURED_MOTHER = {
    "role": "father",
    "mother_work": "none",
    "child_born": True,
    "birth_date": "2026-10-01",
    "children_count": 1,
}


def test_the_father_after_the_death_of_an_uninsured_mother() -> None:
    """§ 10 (art. 180 § 15-16): the day of her death and the first day of his part (the day
    after, 16.10.2026); the birth certificate. No deadline."""
    t = timeline(
        **UNINSURED_MOTHER, work="employment", mother_event={"kind": "death", "start": "2026-10-15"}
    )
    assert document(t, "maternity-father-request").deadline is None
    his = form(t, "maternity-father-request")
    assert articles(his) == ["§ 10 ust. 1"]
    assert values(his) == {
        "father-name": None,
        "event-date": "15.10.2026",
        "leave-from": "16.10.2026",
    }
    assert attachments(his) == [("birth-certificate", True)]
    assert (his.start, his.end) == (dt.date(2026, 10, 16), dt.date(2027, 2, 17))


def test_the_father_after_an_uninsured_mother_abandoned_the_child_or_has_a_ruling() -> None:
    """§ 11 (abandonment): the day she abandoned the child; § 12 (incapacity): only the first
    day of his part, with a copy of the ruling."""
    gone = form(
        timeline(
            **UNINSURED_MOTHER,
            work="employment",
            mother_event={"kind": "abandonment", "start": "2026-10-15"},
        ),
        "maternity-father-request",
    )
    assert articles(gone) == ["§ 11 ust. 1"]
    assert values(gone)["event-date"] == "15.10.2026"
    ill = form(
        timeline(
            **UNINSURED_MOTHER,
            work="employment",
            mother_event={"kind": "incapacity", "start": "2026-10-15"},
        ),
        "maternity-father-request",
    )
    assert articles(ill) == ["§ 12 ust. 1"]
    assert values(ill) == {"father-name": None, "leave-from": "16.10.2026"}
    assert attachments(ill) == [("birth-certificate", True), ("incapacity-ruling-copy", True)]


def test_zam_of_the_father_after_an_uninsured_mother() -> None:
    """Rozp_zasilki § 20 ust. 4 (death, abandonment): his statement on the day she died; § 22
    ust. 2 (incapacity): the ruling. Not the certificate of her benefit: she had none."""
    died = form(
        timeline(
            **UNINSURED_MOTHER,
            work="contract",
            father_insured=True,
            mother_event={"kind": "death", "start": "2026-10-15"},
        ),
        "father-benefit-request",
    )
    ids = [a for a, _ in attachments(died)]
    assert "mother-uninsured-event-statement" in ids
    assert "mother-benefit-certificate" not in ids
    statement = next(a for a in died.attachments if a.id == "mother-uninsured-event-statement")
    assert {s.article for s in statement.sources} == {"§ 20 ust. 4"}
    ill = form(
        timeline(
            **UNINSURED_MOTHER,
            work="business",
            father_insured=True,
            mother_event={"kind": "incapacity", "start": "2026-10-15"},
        ),
        "father-benefit-request",
    )
    ruling = next(a for a in ill.attachments if a.id == "incapacity-ruling-uninsured")
    assert {s.article for s in ruling.sources} == {"§ 22 ust. 2"}
    assert "mother-benefit-certificate" not in [a for a, _ in attachments(ill)]


def test_zas53_with_her_own_business() -> None:
    """Annex 1 (§ 2): the period of the sickness benefit from the timeline; the e-ZLA number
    and the rest typed in; ZAS-53 goes to ZUS."""
    t = timeline(
        role="mother",
        work="business",
        mother_insured=True,
        child_born=False,
        due_date="2027-03-15",
        children_count=1,
        leave_before_birth_weeks=0,
        sick_leave=True,
        sick_leave_start="2026-11-01",
        insured_since="2026-10-01",
    )
    f = form(t, "sick-benefit-request")
    assert (f.official_form, f.addressee) == ("ZAS-53", "zus")
    assert (f.start, f.end) == (dt.date(2026, 12, 30), dt.date(2027, 3, 14))
    assert values(f)["sick-period"] == "od 30.12.2026 do 14.03.2027 (75 dni)"
    assert values(f)["insurance-period"] == "w okresie ubezpieczenia chorobowego"
    assert field(f, "certificate-number").personal
    assert all(s.article == "zał. 1" for x in f.fields for s in x.sources)
    assert [n.text.split(" ")[0] for n in f.notes] == ["Formularz", "Zamiast"]


def test_every_part_of_a_parental_plan_is_its_own_request() -> None:
    """Art. 182¹ᵈ § 2: the number of parts is the number of requests; each at least 21 days
    before its part (§ 1). The second part's request counts both parents' parts before it."""
    t = timeline(
        **PARENTS,
        **BORN,
        parental_parts=[
            {"parent": "mother", "weeks": 20},
            {"parent": "father", "weeks": 9, "with_previous": True},
            {"parent": "mother", "weeks": 12, "start": "2028-06-01"},
        ],
    )
    requests = [
        (d.id, d.title, d.segment_id, d.deadline)
        for d in t.documents
        if d.id.startswith(("parental-request-", "parental-father-request-"))
    ]
    assert requests == [
        (
            "parental-request-1",
            "Wniosek o urlop rodzicielski (część 1)",
            "parental-mother-1",
            dt.date(2027, 3, 9),
        ),
        (
            "parental-request-2",
            "Wniosek o urlop rodzicielski (część 2)",
            "parental-mother-2",
            dt.date(2028, 5, 11),
        ),
        (
            "parental-father-request-1",
            "Wniosek taty o urlop rodzicielski (część 1)",
            "parental-father-1",
            dt.date(2027, 3, 9),
        ),
    ]
    assert "art. 182¹ᵈ § 2" in {s.article for s in document(t, "parental-request-2").sources}
    first = form(t, "parental-request-1")
    assert first.attachments[1].hint == (
        "Na osi drugi z rodziców ma w tym czasie urlop rodzicielski: od 30.03.2027 do "
        "31.05.2027 (9 tyg.)."
    )
    second = form(t, "parental-request-2")
    assert values(second)["used-so-far"] == (
        "Na osi przed tym okresem: mama: urlop rodzicielski — część 1: od 30.03.2027 do "
        "16.08.2027 (20 tyg.); tata: urlop rodzicielski: od 30.03.2027 do 31.05.2027 (9 tyg.). "
        "Części: 2."
    )
    assert values(second)["leave-period"] == "od 01.06.2028 do 23.08.2028 (12 tyg.)"
    assert form(t, "parental-father-request-1").applicant == "father"
    told = next(n for n in t.notes if n.id == "applications").text
    assert (
        "Wniosek o urlop rodzicielski (część 2) — do pracodawcy, najpóźniej 11 maja 2028." in told
    )


def test_a_part_with_work_needs_the_request_to_work_during_the_leave() -> None:
    """ZADANIA B.13, art. 182¹ᵉ § 2: work during parental leave starts on a request filed at
    least 21 days before the work; its content is § 16 of the regulation on the requests."""
    t = timeline(
        **PARENTS,
        **BORN,
        parental_parts=[
            {"parent": "mother", "weeks": 32, "work_fraction": "1/2", "work_weeks": 20},
            {"parent": "father", "weeks": 9, "work_fraction": "1/2"},
        ],
    )
    requests = [
        (d.id, d.label, d.title, d.segment_id, d.needed_by, d.deadline)
        for d in t.documents
        if "work-request" in d.id
    ]
    assert requests == [
        (
            "parental-work-request-1",
            "Wniosek: praca w czasie urlopu, cz. 1",
            "Wniosek o łączenie urlopu rodzicielskiego z pracą (część 1)",
            "parental-mother-1",
            dt.date(2027, 3, 9),
            dt.date(2027, 3, 9),
        ),
        (
            "parental-father-work-request-1",
            "Wniosek taty: praca w czasie urlopu, cz. 1",
            "Wniosek taty o łączenie urlopu rodzicielskiego z pracą (część 1)",
            "parental-father-1",
            dt.date(2027, 12, 28),
            dt.date(2027, 12, 28),
        ),
    ]
    mothers = document(t, "parental-work-request-1")
    assert mothers.rule == (
        "W planie mama od 30.03.2027 do 16.08.2027 łączy urlop z pracą na 1/2 etatu. Wniosek "
        "składa pracodawcy, który udziela urlopu. Najpóźniej 09.03.2027: co najmniej 21 dni "
        "przed rozpoczęciem pracy (30.03.2027). Łączyć urlop rodzicielski z pracą może tylko "
        "pracownik, u pracodawcy, który udziela tego urlopu, i najwyżej na 1/2 etatu. Pracodawca "
        "uwzględnia wniosek, chyba że nie pozwala na to organizacja pracy albo rodzaj pracy; "
        "o przyczynie odmowy informuje w ciągu 7 dni od otrzymania wniosku."
    )
    quotes = [s.quote for s in mothers.sources]
    assert quotes[0].endswith(
        "w terminie nie krótszym niż 21 dni przed rozpoczęciem wykonywania pracy."
    )
    assert quotes[1].startswith("Ubezpieczony-pracownik może łączyć")  # guide E: employees only
    assert {s.article for s in mothers.sources} >= {"art. 182¹ᵉ § 1", "art. 182¹ᵉ § 2"}
    assert document(t, "parental-father-work-request-1").rule.startswith(
        "W planie tata od 18.01.2028 do 20.03.2028 łączy urlop z pracą na 1/2 etatu. Wniosek "
        "składa swojemu pracodawcy, który udziela urlopu. Najpóźniej 28.12.2027:"
    )

    f = form(t, "parental-work-request-1")
    assert (f.applicant, f.addressee, f.addressee_label) == (
        "mother",
        "employer",
        "Pracodawca mamy",
    )
    assert articles(f) == ["§ 16"]
    assert (f.start, f.end) == (dt.date(2027, 3, 30), dt.date(2027, 8, 16))
    assert values(f) == {
        "employee-name": None,
        "work-fraction": "1/2 etatu",
        "work-period": "od 30.03.2027 do 16.08.2027 (20 tyg.)",
        "extension-work": (
            "Brak takiego zamiaru: w planie wydłużenie tej części urlopu od 09.11.2027 do "
            "17.01.2028 (10 tyg.) jest bez pracy."
        ),
    }
    assert field(f, "employee-name").personal
    period = field(f, "work-period")
    assert (period.kind, period.start, period.end) == (
        "period",
        dt.date(2027, 3, 30),
        dt.date(2027, 8, 16),
    )
    assert period.hint == (
        "Z planu na osi: pierwsze 20 tyg. tej części urlopu rodzicielskiego, która razem "
        "z wydłużeniem trwa od 30.03.2027 do 17.01.2028 (42 tyg.). Możesz wskazać inne tygodnie."
    )
    assert field(f, "extension-work").kind == "statement"
    assert all(s.article == "§ 16" for x in f.fields for s in x.sources)
    assert f.attachments == []  # § 16 names none
    assert [n.text for n in f.notes] == [
        "Urlop wydłuża się o tygodnie pracy razy wymiar pracy (20 tyg. × 1/2 = 10 tyg.). Za okres "
        "wydłużonego urlopu rodzicielskiego też przysługuje zasiłek macierzyński.",
        "Wniosek składa się w postaci papierowej albo elektronicznej. Pracodawca uwzględnia go, "
        "chyba że nie pozwala na to organizacja pracy albo rodzaj Twojej pracy; o przyczynie "
        "odmowy informuje w ciągu 7 dni od otrzymania wniosku.",
    ]
    assert "art. 182¹ᶠ § 4" not in {s.article for s in f.notes[0].sources}  # whole weeks

    his = form(t, "parental-father-work-request-1")
    assert (his.applicant, his.addressee_label) == ("father", "Pracodawca taty")
    assert values(his)["work-period"] == "od 18.01.2028 do 20.03.2028 (9 tyg.)"
    assert values(his)["extension-work"] == (
        "Brak takiego zamiaru: w planie wydłużenie tej części urlopu od 21.03.2028 do "
        "20.04.2028 (31 dni) jest bez pracy."
    )
    assert his.notes[0].text.startswith(
        "Urlop wydłuża się o tygodnie pracy razy wymiar pracy (9 tyg. × 1/2 = 4,5 tyg., czyli "
        "31,5 dnia; niepełny dzień się pomija, więc 31 dni)."
    )
    assert "art. 182¹ᶠ § 4" in {s.article for s in his.notes[0].sources}

    told = next(n for n in t.notes if n.id == "applications").text
    assert (
        "Wniosek o łączenie urlopu rodzicielskiego z pracą (część 1) — do pracodawcy, "
        "najpóźniej 9 marca 2027." in told
    )
    assert (
        "Wniosek taty o łączenie urlopu rodzicielskiego z pracą (część 1) — do pracodawcy, "
        "najpóźniej 28 grudnia 2027." in told
    )


def test_the_request_to_work_only_for_parts_with_work_still_ahead() -> None:
    """A part under way needs no requests any more; a part without work needs no request to
    work; a passed deadline stays where it was (the plan fixes the day the work starts)."""
    t = timeline(
        **PARENTS,
        child_born=True,
        birth_date="2026-07-01",
        leave_before_birth_weeks=0,
        children_count=1,
        parental_parts=[
            {"parent": "mother", "weeks": 20, "work_fraction": "1/2"},
            {"parent": "father", "weeks": 9, "work_fraction": "1/2", "start": "2026-12-01"},
            {"parent": "mother", "weeks": 12, "start": "2028-06-01"},
        ],
    )
    ids = [d.id for d in t.documents if d.id.startswith("parental-")]
    assert ids == [
        "parental-request-2",
        "parental-father-request-1",
        "parental-father-work-request-1",
    ]
    late = document(t, "parental-father-work-request-1")
    assert (late.needed_by, late.deadline) == (dt.date(2026, 11, 10), dt.date(2026, 11, 10))
    assert (
        "Termin minął 10.11.2026: wniosek składa się co najmniej 21 dni przed rozpoczęciem "
        "pracy (01.12.2026)." in late.rule
    )
    assert values(form(t, "parental-father-work-request-1"))["work-period"] == (
        "od 01.12.2026 do 01.02.2027 (9 tyg.)"
    )
    told = next(n for n in t.notes if n.id == "applications").text
    assert (
        "Wniosek taty o łączenie urlopu rodzicielskiego z pracą (część 1) — do pracodawcy: "
        "termin minął 10 listopada 2026." in told
    )


def test_work_that_adds_no_whole_day_needs_no_statement_on_the_extension() -> None:
    """1 week at 1/8 of full time: 7 × 1/8 = 0,875 day, the incomplete day is dropped (art.
    182¹ᶠ § 4), so there is no extension to work in (§ 16 pkt 4)."""
    t = timeline(
        **PARENTS,
        **BORN,
        parental_parts=[{"parent": "mother", "weeks": 1, "work_fraction": "1/8"}],
    )
    f = form(t, "parental-work-request-1")
    assert values(f) == {
        "employee-name": None,
        "work-fraction": "1/8 etatu",
        "work-period": "od 30.03.2027 do 05.04.2027 (1 tyg.)",
    }
    assert [n.text.split(" ")[0] for n in f.notes] == ["Wniosek"]


def test_documents_that_are_not_requests_have_no_form() -> None:
    t = expecting()
    assert document(t, "medical-certificate").form is None
