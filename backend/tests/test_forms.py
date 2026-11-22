"""Request forms (ZADANIA B.3, engine/forms.py): each request on the timeline as a form, its
fields as the regulations name them, filled in from the scenario and the timeline.

Sources: the regulation of 11 March 2025 on the leave requests (rozp_wnioski: § 2, § 3, § 5,
§ 7, § 14, § 15, § 17, § 22), the regulation of 27 September 2026 on the benefit documents
(rozp_zasilki: § 2, § 12, § 13, § 32, § 33, annexes 1 and 6), the guide (A.4, page 12).

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
- a business insured from 01.10.2026, sick from 01.11.2026: the right after 90 days, from
  30.12.2026; the benefit until the day before the due date, 14.03.2027 (2 + 31 + 28 + 14 = 75
  days);
- born 10.11.2026, a plan: the mother 20 weeks right after maternity leave 30.03-16.08.2027
  (+139 days), the father 9 weeks at the same time 30.03-31.05.2027 (+62 days), the mother
  12 weeks from 01.06.2028 to 23.08.2028 (+83 days); each request 21 days before its part:
  09.03.2027, 09.03.2027, 11.05.2028.
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
    assert f.attachments == []
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
    assert attachments(f) == [
        ("birth-certificate", False),
        ("mother-uninsured-statement", True),
        ("paternity-statement", True),
    ]
    assert {s.article for a in f.attachments[1:] for s in a.sources} == {
        "§ 32 ust. 1",
        "§ 33 ust. 1",
    }


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


def test_documents_that_are_not_requests_have_no_form() -> None:
    t = expecting()
    assert document(t, "medical-certificate").form is None
