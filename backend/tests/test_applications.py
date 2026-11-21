"""Applications and protection (guide A.4 page 6, page 1 footnote 1, page 12, section I page 10;
Labour Code art. 177, 180 § 8-9 and § 16, 180² § 4-5, 182¹ᵈ § 1, 182³ § 2).

Expected dates were computed by hand, today being 21.11.2026:
- due 15.03.2027, leave 2 weeks before: from 1.03.2027; maternity leave ends 18.07.2027, parental
  leave 19.07.2027-27.02.2028 (32 weeks); its request 21 days before: 28.06.2027;
- due 15.03.2027 without leave before the birth: maternity leave until 1.08.2027, the mother's
  parental leave until 12.03.2028, the father's from 13.03.2028; his request: 21.02.2028 (2028 is
  a leap year); his paternity leave from 15.03.2027, its request 7 days before: 8.03.2027;
- born 10.11.2026: paternity leave shown from today (21.11.2026); 7 days before was 14.11.2026,
  so the request is due today and is in time for leave from 28.11.2026;
- born 10.11.2026, the father takes over after 14 weeks: the mother back at work 16.02.2027,
  her resignation 7 days before: 9.02.2027; the father's request 14 days before: 2.02.2027;
- born 1.10.2026, 20 days in hospital: maternity leave until 17.02.2027, supplementary leave
  18.02-10.03.2027; its request 21 days before the end of maternity leave: 27.01.2027;
- born 20.06.2026, 31 days in hospital: maternity leave until 6.11.2026, supplementary leave
  7.11-11.12.2026 (5 weeks); the request was due 16.10.2026.
"""

import datetime as dt

from app.engine import Scenario, Timeline, build_timeline
from app.engine.models import CaseNote, Document, Marker, Segment
from app.services.params import load_params

PARAMS = load_params()
TODAY = dt.date(2026, 11, 21)
DUE = dt.date(2027, 3, 15)
BORN = dt.date(2026, 11, 10)
MOTHER = {"role": "mother", "work": "employment"}
PARENTS = {**MOTHER, "father_work": "employment"}


def expecting(**answers: object) -> Timeline:
    scenario = Scenario.model_validate({"child_born": False, "due_date": DUE, **answers})
    return build_timeline(scenario, PARAMS, TODAY)


def born(birth: dt.date = BORN, **answers: object) -> Timeline:
    scenario = Scenario.model_validate(
        {"child_born": True, "birth_date": birth, "leave_before_birth_weeks": 0, **answers}
    )
    return build_timeline(scenario, PARAMS, TODAY)


def document(timeline: Timeline, document_id: str) -> Document:
    return next(d for d in timeline.documents if d.id == document_id)


def segment(timeline: Timeline, segment_id: str) -> Segment:
    return next(s for s in timeline.segments if s.id == segment_id)


def marker(timeline: Timeline, marker_id: str) -> Marker:
    return next(m for m in timeline.markers if m.id == marker_id)


def note(timeline: Timeline, note_id: str) -> CaseNote:
    return next(n for n in timeline.notes if n.id == note_id)


def documents(timeline: Timeline) -> list[tuple[str, dt.date]]:
    return [(d.id, d.needed_by) for d in timeline.documents]


def articles(element: Document | Marker | Segment | CaseNote) -> set[str | None]:
    return {s.article for s in element.sources if s.doc == "kp"}


def sections(element: Document | Marker | Segment | CaseNote) -> set[str | None]:
    return {s.section for s in element.sources if s.doc == "przewodnik"}


# Nothing to file until it is known how the parent works.


def test_no_requests_while_the_work_is_unknown() -> None:
    t = expecting(children_count=1, leave_before_birth_weeks=2)
    assert documents(t) == [("medical-certificate", dt.date(2027, 3, 1))]
    assert not {"protection", "payer", "applications"} & {n.id for n in t.notes}
    assert "protection-end" not in {m.id for m in t.markers}


# The employed mother: requests to the employer.


def test_the_employed_mother_asks_her_employer() -> None:
    t = expecting(**MOTHER, children_count=1, leave_before_birth_weeks=2)
    assert documents(t) == [
        ("medical-certificate", dt.date(2027, 3, 1)),
        ("maternity-request", dt.date(2027, 3, 1)),
        ("parental-request", dt.date(2027, 6, 28)),
    ]
    request = document(t, "maternity-request")
    assert request.segment_id == "maternity-prenatal"
    assert "Mama składa go pracodawcy." in request.rule
    # One request for both leaves when parental leave follows maternity leave (A.4).
    assert "może złożyć jeden wniosek o oba urlopy" in request.rule
    # No deadline in the materials: on the first day of the leave (CLAUDE.md, open questions).
    assert "materiały nie podają terminu tego wniosku" in request.rule
    assert sections(request) >= {"A.4", "W"}
    parental = document(t, "parental-request")
    assert parental.segment_id == "parental"
    assert "Najpóźniej 28.06.2027: co najmniej 21 dni przed rozpoczęciem urlopu (19.07.2027)." in (
        parental.rule
    )
    assert articles(parental) == {"art. 182¹ᵈ § 1"}
    assert any("21. dnia przed pierwszym dniem urlopu" in a for a in t.assumptions)


def test_without_leave_before_the_birth_the_request_is_for_the_due_date() -> None:
    t = expecting(**MOTHER, children_count=1, leave_before_birth_weeks=0)
    request = document(t, "maternity-request")
    assert (request.needed_by, request.segment_id) == (DUE, "maternity")


def test_za_zyciem_is_attached_to_the_parental_leave_request() -> None:
    t = expecting(**MOTHER, children_count=1, leave_before_birth_weeks=0, za_zyciem=True)
    assert "Do wniosku dołącza się zaświadczenie „Za życiem”." in (
        document(t, "parental-request").rule
    )


def test_a_stillborn_child_needs_its_certificate_with_the_request() -> None:
    t = born(**MOTHER, children_count=1, losses=[{"stillborn": True}])
    request = document(t, "maternity-request")
    assert (request.needed_by, request.segment_id) == (BORN, "maternity")
    assert "Urlop zaczął się 10.11.2026" in request.rule
    assert "Do wniosku dołącza się: zaświadczenie o martwym urodzeniu." in request.rule
    assert "parental-request" not in {d.id for d in t.documents}


def test_supplementary_leave_request_three_weeks_before_maternity_leave_ends() -> None:
    t = born(
        dt.date(2026, 10, 1),
        **MOTHER,
        children_count=1,
        hospital_care=True,
        birth_week="28-37",
        birth_weight_up_to_1000g=False,
        hospital_stays=[{"start": "2026-10-01", "end": "2026-10-20"}],
    )
    assert segment(t, "maternity").end == dt.date(2027, 2, 17)
    assert segment(t, "supplementary").start == dt.date(2027, 2, 18)
    request = document(t, "supplementary-request")
    assert (request.needed_by, request.segment_id) == (dt.date(2027, 1, 27), "supplementary")
    assert "przed końcem urlopu macierzyńskiego (17.02.2027)" in request.rule
    assert "zaświadczenie ze szpitala" in request.rule
    assert articles(request) == {"art. 180² § 4", "art. 180² § 5"}


def test_a_passed_deadline_for_supplementary_leave_stays_where_it_was() -> None:
    t = born(
        dt.date(2026, 6, 20),
        **MOTHER,
        children_count=1,
        hospital_care=True,
        birth_week="28-37",
        birth_weight_up_to_1000g=False,
        hospital_stays=[{"start": "2026-06-20", "end": "2026-07-20"}],
    )
    assert (segment(t, "supplementary").start, segment(t, "supplementary").end) == (
        dt.date(2026, 11, 7),
        dt.date(2026, 12, 11),
    )
    request = document(t, "supplementary-request")
    assert request.needed_by == dt.date(2026, 10, 16)
    assert request.rule.startswith("Mama składa go pracodawcy. Termin minął 16.10.2026")
    # Maternity leave is over: nothing more to file for it.
    assert "maternity-request" not in {d.id for d in t.documents}


# Who pays (page 1, footnote 1; A.4).


def test_who_pays_follows_the_number_of_insured() -> None:
    lines = {
        size: segment(
            expecting(**MOTHER, children_count=1, mother_payer_size=size), "maternity"
        ).details[-1]
        for size in ("over-20", "up-to-20", "unknown")
    }
    assert lines["over-20"] == (
        "Zasiłek mamy wypłaca jej pracodawca: zgłasza do ubezpieczenia chorobowego więcej niż "
        "20 osób."
    )
    assert lines["up-to-20"] == (
        "Zasiłek mamy wypłaca ZUS: jej pracodawca zgłasza do ubezpieczenia chorobowego nie więcej "
        "niż 20 osób, więc przesyła do ZUS zaświadczenie płatnika składek Z-3."
    )
    assert lines["unknown"] == (
        "Zasiłek mamy wypłaca jej pracodawca, jeśli zgłasza do ubezpieczenia chorobowego więcej "
        "niż 20 osób; jeśli nie, wypłaca go ZUS, a pracodawca przesyła do ZUS zaświadczenie "
        "płatnika składek Z-3."
    )
    t = expecting(**MOTHER, children_count=1)
    payer = note(t, "payer")
    assert (payer.kind, payer.title) == ("computed", "Kto wypłaca zasiłek mamy")
    assert "według stanu na 30 listopada poprzedniego roku" in payer.text
    assert note(
        expecting(**MOTHER, children_count=1, mother_payer_size="up-to-20"), "payer"
    ).title == ("Zasiłek mamy wypłaca ZUS")
    # Every benefit period of hers says it; the father's not yet: how he works is not known.
    assert all("Zasiłek mamy" in s.details[-1] for s in t.segments if s.lane == "mother")
    assert not any("Zasiłek taty" in d for s in t.segments for d in s.details)


def test_a_mother_on_a_contract_files_zam() -> None:
    t = expecting(role="mother", work="contract", mother_payer_size="up-to-20", children_count=1)
    request = document(t, "maternity-request")
    assert (request.title, request.needed_by) == ("Wniosek o zasiłek macierzyński (ZAM)", DUE)
    assert request.rule.startswith(
        "Mama pracuje na umowie zlecenia i składa wniosek ZAM. Prawo do zasiłku ustala ZUS; "
        "płatnik składek przesyła do ZUS zaświadczenie płatnika składek Z-3a."
    )
    assert "formularz ZUR połączono z nim 24 października 2026 r." in request.rule
    assert sections(request) >= {"A.4", "F"}
    # Not an employee: no requests for each leave, no special protection.
    assert [d.id for d in t.documents] == ["maternity-request"]
    assert "protection-end" not in {m.id for m in t.markers}
    protection = note(t, "protection")
    assert (protection.kind, protection.title) == (
        "risk",
        "Bez szczególnej ochrony z Kodeksu pracy",
    )
    assert sections(protection) == {"I"}


def test_with_her_own_business_the_mother_files_zam_with_zus() -> None:
    t = born(role="mother", work="business", mother_insured=True, children_count=1)
    request = document(t, "maternity-request")
    assert request.rule.startswith(
        "Mama nie jest pracownicą i prowadzi własną firmę, więc składa wniosek o zasiłek "
        "macierzyński (ZAM) bezpośrednio do ZUS."
    )
    assert segment(t, "maternity").details[-1].startswith("Zasiłek mamy wypłaca ZUS")
    assert note(t, "payer").title == "Zasiłek mamy wypłaca ZUS"
    assert "do ZUS, do 10 listopada 2026" in note(t, "applications").text


def test_an_uninsured_mother_has_nothing_to_file() -> None:
    t = expecting(role="mother", work="contract", mother_insured=False, children_count=1)
    assert not [d for d in t.documents if d.id.startswith("maternity")]
    assert "payer" not in {n.id for n in t.notes}


# The father.


def test_the_employed_father_asks_his_employer() -> None:
    t = expecting(**PARENTS, children_count=1, father_payer_size="over-20")
    assert documents(t) == [
        ("maternity-request", DUE),
        ("parental-request", dt.date(2027, 7, 12)),
        ("paternity-request", dt.date(2027, 3, 8)),
        ("parental-father-request", dt.date(2028, 2, 21)),
    ]
    paternity = document(t, "paternity-request")
    assert paternity.rule == (
        "Tata składa go swojemu pracodawcy. Najpóźniej 08.03.2027: co najmniej 7 dni przed "
        "rozpoczęciem urlopu (15.03.2027)."
    )
    assert articles(paternity) == {"art. 182³ § 2"}
    assert "przed rozpoczęciem urlopu (13.03.2028)" in document(t, "parental-father-request").rule
    assert segment(t, "paternity").details[-1] == (
        "Zasiłek taty wypłaca jego pracodawca: zgłasza do ubezpieczenia chorobowego więcej niż "
        "20 osób."
    )


def test_a_passed_deadline_for_paternity_leave_moves_to_today() -> None:
    """Paternity leave is shown from today; a request filed today is in time 7 days later."""
    t = born(**PARENTS, children_count=1)
    request = document(t, "paternity-request")
    assert segment(t, "paternity").start == TODAY
    assert request.needed_by == TODAY
    assert "termin minął 14.11.2026" in request.rule
    assert "Złożony dziś jest w terminie dla urlopu od 28.11.2026." in request.rule


def test_taking_over_needs_two_requests() -> None:
    t = born(**PARENTS, children_count=1, father_takes_over=True)
    resignation = document(t, "maternity-resignation")
    assert resignation.needed_by == dt.date(2027, 2, 9)
    assert "co najmniej 7 dni przed powrotem do pracy (16.02.2027)" in resignation.rule
    assert "Może też od razu wnioskować tylko o 14 tygodni urlopu." in resignation.rule
    assert articles(resignation) == {"art. 180 § 8"}
    assert sections(resignation) == {"B.1"}
    his = document(t, "maternity-father-request")
    assert (his.needed_by, his.segment_id) == (dt.date(2027, 2, 2), "maternity-father")
    assert articles(his) == {"art. 180 § 9"}
    # The mother's protection ends with her part; it comes back with parental leave.
    protection = marker(t, "protection-end")
    assert protection.date == dt.date(2027, 2, 15)
    assert any("wniosku o urlop rodzicielski" in d for d in protection.details)


def test_the_mother_in_hospital_the_father_asks_without_a_deadline() -> None:
    t = born(
        dt.date(2026, 10, 1),
        **PARENTS,
        children_count=1,
        mother_event={"kind": "hospital", "start": "2026-12-01", "end": "2026-12-20"},
    )
    his = document(t, "maternity-father-request")
    assert his.needed_by == dt.date(2026, 12, 1)
    assert "Kodeks pracy nie podaje w tej sytuacji terminu wniosku." in his.rule
    assert articles(his) == {"art. 180 § 16"}
    assert "maternity-resignation" not in {d.id for d in t.documents}


def test_a_father_with_a_business_files_zam_with_zus() -> None:
    t = expecting(**MOTHER, father_work="business", father_insured=True, children_count=1)
    request = document(t, "father-benefit-request")
    assert (request.needed_by, request.segment_id) == (DUE, "paternity")
    assert "także ojcowskiego (formularze ZUR i ZAO połączono z ZAM)" in request.rule
    assert any("dla taty przyjmujemy to samo" in a for a in t.assumptions)
    assert any("zasiłek wypłaca ZUS" in a for a in t.assumptions)
    assert segment(t, "paternity").details[-1].startswith("Zasiłek taty wypłaca ZUS")


# Protection (section I; art. 177).


def test_the_employed_mother_is_protected_until_her_leave_ends() -> None:
    t = expecting(**MOTHER, children_count=1, leave_before_birth_weeks=2)
    protection = marker(t, "protection-end")
    assert (protection.date, protection.lane) == (dt.date(2028, 2, 27), "child")
    assert "pracodawca nie może wypowiedzieć ani rozwiązać umowy" in protection.summary
    assert articles(protection) == {"art. 177 § 1", "art. 177 § 1¹"}
    assert sections(protection) == {"I"}
    assert any(
        "zakaz zaczyna obowiązywać 21 dni przed tym urlopem" in d for d in protection.details
    )
    # A fixed-term contract is extended until the birth (art. 177 § 3).
    due = marker(t, "due-date")
    assert any("umowa przedłuża się do dnia porodu" in d for d in due.details)
    assert "art. 177 § 3" in articles(due)
    told = note(t, "protection")
    assert (told.kind, told.title) == ("right", "Ochrona przed zwolnieniem")
    assert "ochrona trwa do 27 lutego 2028" in told.text
    assert "przedłuża się do dnia porodu" in told.text


def test_once_the_child_is_born_no_word_about_the_fixed_term_contract() -> None:
    t = born(**MOTHER, children_count=1)
    assert "przedłuża się do dnia porodu" not in note(t, "protection").text
    assert "due-date" not in {m.id for m in t.markers}


def test_the_employed_father_is_protected_from_his_request() -> None:
    t = expecting(role="father", work="employment", mother_work="none", children_count=1)
    protection = note(t, "protection")
    assert (protection.kind, protection.title) == ("right", "Ochrona taty przed zwolnieniem")
    assert "protection-end" not in {m.id for m in t.markers}


# The explanation: after "Co policzyliśmy", the protection, who pays, what to file.


def test_the_notes_end_with_what_to_file() -> None:
    t = expecting(**PARENTS, children_count=1, leave_before_birth_weeks=2)
    assert [n.id for n in t.notes][-4:] == ["computed", "protection", "payer", "applications"]
    told = note(t, "applications")
    assert (told.kind, told.title) == ("computed", "Co złożyć i do kiedy")
    assert told.text.startswith(
        "Wniosek o urlop macierzyński — do pracodawcy, do 1 marca 2027. Wniosek o urlop "
        "ojcowski — do pracodawcy, do 8 marca 2027. Wniosek o urlop rodzicielski — do "
        "pracodawcy, do 28 czerwca 2027."
    )
    assert note(t, "payer").title == "Kto wypłaca zasiłek"
