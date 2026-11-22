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

Sick leave in pregnancy (guide page 3), due 15.03.2027 without leave before the birth, so the
sick leave runs until 14.03.2027:
- an employee from 1.12.2026: the employer pays 31 days of December and, in the new calendar
  year, 33 more (1.01-2.02.2027); the benefit 3.02-14.03.2027. She informs her employer on
  1.12.2026, the first day;
- an employee from 1.10.2026: the employer 1.10-2.11.2026 (31 + 2 days), the benefit
  3.11-31.12.2026, the employer again 1.01-2.02.2027, the benefit 3.02-14.03.2027;
- a business insured from 1.10.2026: the right after 90 days, from 30.12.2026 (30 + 31 + 29
  days); ZAS-53 shown on 30.12.2026;
- the job ended unlawfully on 30.11.2026: the benefit (and the court judgment) from 1.12.2026.
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
    # No deadline in the materials: the day on the timeline is not called one (ZADANIA B.4).
    assert request.deadline is None
    assert (
        "Wniosek o zasiłek macierzyński (ZAM) — do ZUS. Terminu materiały nie podają; na osi jest "
        "na 10 listopada 2026, dzień, od którego przysługuje zasiłek."
    ) in note(t, "applications").text


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
    # "Najpóźniej" only where the Labour Code gives a deadline; the request for maternity leave
    # has none in the materials, so its day is the first day of the leave (ZADANIA B.4).
    assert told.text.startswith(
        "Wniosek o urlop macierzyński — do pracodawcy. Terminu materiały nie podają; na osi jest "
        "na 1 marca 2027, dzień, w którym zaczyna się urlop. Wniosek o urlop ojcowski — do "
        "pracodawcy, najpóźniej 8 marca 2027. Wniosek o urlop rodzicielski — do pracodawcy, "
        "najpóźniej 28 czerwca 2027."
    )
    deadlines = {d.id: d.deadline for d in t.documents}
    assert deadlines == {
        "medical-certificate": None,
        "maternity-request": None,
        "parental-request": dt.date(2027, 6, 28),
        "paternity-request": dt.date(2027, 3, 8),
        "parental-father-request": dt.date(2028, 2, 7),
    }
    assert note(t, "payer").title == "Kto wypłaca zasiłek"


# Sick leave in pregnancy (guide page 3): who pays, informing the employer, the forms.


def sick(timeline: Timeline) -> list[tuple[str, dt.date, dt.date]]:
    return [(s.id, s.start, s.end) for s in timeline.segments if s.id.startswith("sick-")]


def test_an_employee_informs_her_employer_before_the_sick_leave() -> None:
    t = expecting(
        **MOTHER,
        children_count=1,
        leave_before_birth_weeks=0,
        mother_payer_size="up-to-20",
        sick_leave=True,
        sick_leave_start="2026-12-01",
    )
    # 31 days of December and 33 of the new year from the employer, then the benefit.
    assert sick(t) == [
        ("sick-pay", dt.date(2026, 12, 1), dt.date(2027, 2, 2)),
        ("sick-benefit", dt.date(2027, 2, 3), dt.date(2027, 3, 14)),
    ]
    notice = document(t, "sick-leave-notice")
    assert (notice.needed_by, notice.segment_id, notice.done) == (
        dt.date(2026, 12, 1),
        "sick-pay",
        False,
    )
    assert "powinna poinformować pracodawcę o nieobecności w pracy" in notice.rule
    assert "trafia bezpośrednio do ZUS i na profil pracodawcy na PUE/eZUS" in notice.rule
    assert "zaświadczenie płatnika składek Z-3 (na dalszy okres ZAS-12)" in notice.rule
    assert sections(notice) >= {"ZC", "W"}
    # The benefit after the employer's days: ZUS, the employer sends Z-3 (ZAS-12 later).
    benefit = segment(t, "sick-benefit")
    assert benefit.details[-1] == (
        "Zasiłek chorobowy mamy wypłaca ZUS: jej pracodawca zgłasza do ubezpieczenia "
        "chorobowego nie więcej niż 20 osób, więc przekazuje do ZUS wniosek o wypłatę zasiłku, "
        "zaświadczenie płatnika składek Z-3 (na dalszy okres ZAS-12)."
    )
    assert "ZC" in sections(benefit)
    # The employer's days say who pays in their summary already: no line added.
    assert not any("wypłaca ZUS" in line for line in segment(t, "sick-pay").details)
    payer = note(t, "payer")
    assert payer.text.startswith(
        "Za zwolnienie lekarskie w ciąży wynagrodzenie chorobowe za pierwsze 33 dni "
        "niezdolności do pracy w roku kalendarzowym wypłaca mamie pracodawca. Zasiłek chorobowy "
        "mamy wypłaca ZUS"
    )
    assert note(t, "applications").text.startswith(
        "Informacja dla pracodawcy o nieobecności w pracy — pierwszego dnia zwolnienia, "
        "1 grudnia 2026."
    )
    assert any("pierwszy dzień zwolnienia" in a for a in t.assumptions)


def test_a_sick_leave_already_under_way_needs_no_notice() -> None:
    t = expecting(
        **MOTHER,
        children_count=1,
        leave_before_birth_weeks=0,
        mother_payer_size="over-20",
        sick_leave=True,
        sick_leave_start="2026-10-01",
    )
    # 33 days from 1.10.2026: 31 of October and 2 of November.
    assert sick(t) == [
        ("sick-pay", dt.date(2026, 10, 1), dt.date(2026, 11, 2)),
        ("sick-benefit", dt.date(2026, 11, 3), dt.date(2026, 12, 31)),
        ("sick-pay-2", dt.date(2027, 1, 1), dt.date(2027, 2, 2)),
        ("sick-benefit-2", dt.date(2027, 2, 3), dt.date(2027, 3, 14)),
    ]
    assert "sick-leave-notice" not in {d.id for d in t.documents}
    line = (
        "Zasiłek chorobowy mamy wypłaca jej pracodawca na podstawie zaświadczenia e-ZLA: "
        "zgłasza do ubezpieczenia chorobowego więcej niż 20 osób."
    )
    assert segment(t, "sick-benefit").details[-1] == line
    assert segment(t, "sick-benefit-2").details[-1] == line


def test_on_a_contract_of_mandate_the_payer_sends_z3a() -> None:
    t = expecting(
        role="mother",
        work="contract",
        mother_insured=True,
        children_count=1,
        leave_before_birth_weeks=0,
        sick_leave=True,
        sick_leave_start="2026-12-07",
    )
    # Not an employee: the benefit from the first day, until the day before the due date.
    assert sick(t) == [("sick-benefit", dt.date(2026, 12, 7), dt.date(2027, 3, 14))]
    request = document(t, "sick-benefit-request")
    assert (request.title, request.needed_by, request.segment_id) == (
        "Dokumenty do zasiłku chorobowego",
        dt.date(2026, 12, 7),
        "sick-benefit",
    )
    assert "złożyć odpowiednie dokumenty do ZUS albo do płatnika składek" in request.rule
    assert "zaświadczenie płatnika składek Z-3a, i zasiłek wypłaca ZUS" in request.rule
    assert "Materiały nie podają terminu" in request.rule
    assert "ZC" in sections(request)
    assert (
        "Dokumenty do zasiłku chorobowego — do płatnika składek albo do ZUS. Terminu materiały "
        "nie podają; na osi jest na 7 grudnia 2026, dzień, od którego przysługuje zasiłek."
    ) in note(t, "applications").text
    # The size of the payer is not known yet: the day the number of insured is counted on.
    assert "według stanu na 30 listopada poprzedniego roku" in note(t, "payer").text


def test_with_a_business_zas53_goes_to_zus() -> None:
    t = expecting(
        role="mother",
        work="business",
        mother_insured=True,
        children_count=1,
        leave_before_birth_weeks=0,
        sick_leave=True,
        sick_leave_start="2026-11-01",
        insured_since="2026-10-01",
    )
    # 90 days of voluntary insurance from 1.10.2026: the right from 30.12.2026.
    assert sick(t) == [("sick-benefit", dt.date(2026, 12, 30), dt.date(2027, 3, 14))]
    request = document(t, "sick-benefit-request")
    assert (request.title, request.needed_by) == (
        "Wniosek o zasiłek chorobowy (ZAS-53)",
        dt.date(2026, 12, 30),
    )
    assert "złożyć do ZUS wniosek o zasiłek chorobowy ZAS-53" in request.rule
    assert segment(t, "sick-benefit").details[-1] == (
        "Zasiłek chorobowy mamy wypłaca ZUS: przy własnej firmie wniosek o zasiłek chorobowy "
        "(ZAS-53) składa się do ZUS."
    )
    payer = note(t, "payer")
    assert payer.title == "Zasiłek mamy wypłaca ZUS"
    assert "Liczbę ubezpieczonych" not in payer.text
    assert (
        "Wniosek o zasiłek chorobowy (ZAS-53) — do ZUS. Terminu materiały nie podają; na osi jest "
        "na 30 grudnia 2026, dzień, od którego przysługuje zasiłek."
    ) in note(t, "applications").text
    assert any("zasiłek chorobowy wypłaca ZUS" in a for a in t.assumptions)


def test_no_sick_benefit_documents_after_the_sick_leave_ended() -> None:
    t = expecting(
        role="mother",
        work="contract",
        mother_insured=True,
        children_count=1,
        sick_leave=True,
        sick_leave_start="2026-10-01",
        sick_leave_end="2026-10-31",
    )
    assert sick(t) == [("sick-benefit", dt.date(2026, 10, 1), dt.date(2026, 10, 31))]
    assert "sick-benefit-request" not in {d.id for d in t.documents}


def test_sick_leave_forms_wait_for_how_the_mother_works() -> None:
    t = expecting(children_count=1, sick_leave=True, sick_leave_start="2026-12-01")
    assert not {"sick-leave-notice", "sick-benefit-request"} & {d.id for d in t.documents}
    assert not any("W" in sections(s) for s in t.segments if s.id.startswith("sick-"))


# The benefit after losing the job (guide page 4): the court judgment.


def test_an_unlawful_termination_needs_a_final_court_judgment() -> None:
    pending = expecting(
        **MOTHER, children_count=1, job_loss={"ended_on": "2026-11-30", "reason": "unlawful"}
    )
    judgment = document(pending, "court-judgment")
    # The benefit would start the day after the employment ended.
    assert (judgment.needed_by, judgment.segment_id, judgment.done) == (
        dt.date(2026, 12, 1),
        "job-loss-benefit",
        False,
    )
    assert "potwierdzi prawomocny wyrok sądu" in judgment.rule
    assert sections(judgment) == {"ZC.s"}
    assert note(pending, "applications").text.startswith(
        "Prawomocny wyrok sądu o naruszeniu prawa przy rozwiązaniu umowy: bez niego zasiłek "
        "w wysokości zasiłku macierzyńskiego nie przysługuje."
    )
    assert any("Do kiedy musi zapaść wyrok sądu" in a for a in pending.assumptions)

    confirmed = expecting(
        **MOTHER,
        children_count=1,
        job_loss={"ended_on": "2026-11-30", "reason": "unlawful", "court_confirmed": True},
    )
    assert document(confirmed, "court-judgment").done
    assert "wyrok" not in note(confirmed, "applications").text


def test_bankruptcy_of_the_employer_needs_no_judgment() -> None:
    t = expecting(
        **MOTHER, children_count=1, job_loss={"ended_on": "2026-11-30", "reason": "bankruptcy"}
    )
    assert "court-judgment" not in {d.id for d in t.documents}
    # The guide does not say what to file for this benefit or who pays it.
    assert any("Przewodnik nie podaje, więc oś tego nie pokazuje" in a for a in t.assumptions)
