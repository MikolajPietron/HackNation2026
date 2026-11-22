"""Request letters (engine/request_letters.py): every request an employee files with the employer
as the letter an employee writes, with an e-mail to HR; ZUS forms (ZAM, ZAS-53) say where the
guide puts them.

Sources: the regulation of 11 March 2025 on the leave requests (rozp_wnioski: § 2, § 3, § 5-§ 9,
§ 14-§ 17), the Labour Code provisions the letters cite (art. 180, 180¹, 180², 182¹ᵃ, 182¹ᵉ,
182¹ᶠ, 182³, 183¹), the guide (A.4; page 12: the ZUS forms on www.zus.pl).

Expected dates were computed by hand, today being 21.11.2026:
- due 15.03.2027, leave 2 weeks before: from 15.03.2027 - 14 days = 01.03.2027; paternity leave
  15.03-28.03.2027 (14 days);
- born 10.11.2026, no leave before: maternity leave 10.11.2026 + 139 days = 29.03.2027 (Nov 20
  days left, Dec 31, Jan 31, Feb 28, Mar 29), 20 weeks; the mother's parental leave (41 - 9 = 32
  weeks, 224 days) 30.03.2027 + 223 days = 08.11.2027;
- twins: 31 weeks = 217 days, 10.11.2026 + 216 days = 14.06.2027; a stillbirth: 8 weeks = 56
  days, 10.11.2026 + 55 days = 04.01.2027;
- the father takes over after 14 weeks (98 days): the mother back at work 10.11.2026 + 98 days
  = 16.02.2027; his part 16.02-29.03.2027 = 13 + 29 = 42 days = 6 weeks;
- born 01.10.2026, the mother in hospital from 01.12.2026 (after 8 weeks: 01.10 + 55 days =
  25.11.2026 is the last day of the 8th week): the father's part from 01.12.2026;
- born 01.10.2026, maternity leave until 01.10.2026 + 139 days = 17.02.2027; the mother died on
  15.11.2026: the father's part 16.11.2026-17.02.2027 = 15 + 31 + 31 + 17 = 94 days = 13 weeks
  and 3 days;
- born 01.09.2026, maternity leave until 01.09.2026 + 139 days = 18.01.2027; the mother
  abandoned the child on 15.11.2026 (8 weeks ended 26.10.2026): the father's part
  16.11.2026-18.01.2027 = 15 + 31 + 18 = 64 days = 9 weeks and 1 day;
- born 01.10.2026, 20 days in hospital: supplementary leave 18.02-10.03.2027 (3 weeks: 11 days
  of February 2027, 10 of March), maternity leave ends 17.02.2027;
- a plan with work at 1/2: the mother 32 weeks from 30.03.2027, working the first 20 weeks
  (30.03 + 139 days = 16.08.2027); the extension 20 × 1/2 = 10 weeks, so 42 weeks = 294 days,
  30.03.2027 + 293 days = 17.01.2028, the extension 17.01.2028 - 69 days = 09.11.2027;
- a plan in parts: the mother 20 weeks 30.03-16.08.2027, the father 9 weeks at the same time
  30.03.2027 + 62 days = 31.05.2027, the mother 12 weeks from 01.06.2028 (+83 days =
  23.08.2028).
"""

import datetime as dt
import re
from typing import Any

import pytest

from app.engine import Scenario, Timeline, build_timeline
from app.engine.models import Letter, RequestForm
from app.services.params import load_params
from tests.test_sources import cited_articles

PARAMS = load_params()
TODAY = dt.date(2026, 11, 21)
PARENTS = {"role": "mother", "work": "employment", "father_work": "employment"}
BORN = {"child_born": True, "birth_date": "2026-11-10", "leave_before_birth_weeks": 0}
BORN |= {"children_count": 1}
EXPECTING = {"child_born": False, "due_date": "2027-03-15", "children_count": 1}
REGULATION = (
    "rozporządzenia Ministra Rodziny, Pracy i Polityki Społecznej z dnia 11 marca 2025 r. "
    "w sprawie wniosków dotyczących uprawnień pracowników związanych z rodzicielstwem oraz "
    "dokumentów dołączanych do takich wniosków (Dz.U. z 2025 r. poz. 322)."
)
TOKEN = re.compile(r"\{\{([a-z0-9-]+)\}\}")


def timeline(**answers: object) -> Timeline:
    return build_timeline(Scenario.model_validate(answers), PARAMS, TODAY)


def form(t: Timeline, document_id: str) -> RequestForm:
    document = next(d for d in t.documents if d.id == document_id)
    assert document.form is not None, document_id
    return document.form


def letter(t: Timeline, document_id: str) -> Letter:
    found = form(t, document_id).letter
    assert found is not None, document_id
    return found


def operative(found: Letter) -> str:
    """The operative paragraph: the first of the body, and the only "request" one."""
    assert [p.kind for p in found.body].count("request") == 1
    assert found.body[0].kind == "request"
    return found.body[0].text


def statements(found: Letter) -> list[str]:
    return [p.text for p in found.body[1:]]


def texts(f: RequestForm) -> list[str]:
    """Every string of the letter and of the e-mail to HR."""
    assert f.letter is not None and f.hr_message is not None
    found = f.letter
    return [
        found.place_date,
        *found.applicant,
        *found.addressee,
        found.title,
        *(p.text for p in found.body),
        *(o for p in found.body for o in p.options),
        *found.attachments,
        found.signature,
        found.legal_basis,
        f.hr_message.subject,
        f.hr_message.body,
    ]


def expecting() -> Timeline:
    return timeline(
        **PARENTS,
        **EXPECTING,
        leave_before_birth_weeks=2,
        mother_payer_size="up-to-20",
        has_medical_certificate=True,
    )


# One test per kind of request: the operative paragraph with the timeline's dates.


def test_the_part_of_maternity_leave_before_the_birth() -> None:
    """§ 2: the date the part before the birth starts (art. 180 § 2); the medical certificate
    with the due date is the only attachment (ZUS pays: no birth certificate)."""
    f = form(expecting(), "maternity-request")
    found = letter(expecting(), "maternity-request")
    assert found.title == (
        "Wniosek o udzielenie części urlopu macierzyńskiego przed przewidywaną datą porodu"
    )
    assert operative(found) == (
        "Na podstawie art. 180 § 2 Kodeksu pracy wnoszę o udzielenie mi części urlopu "
        "macierzyńskiego przed przewidywaną datą porodu, od dnia 01.03.2027 r. Przewidywana data "
        "porodu, określona w zaświadczeniu lekarskim, którego kopię załączam, to 15.03.2027 r. "
        "Pozostałą część urlopu macierzyńskiego wykorzystam po porodzie."
    )
    assert statements(found) == []
    assert found.attachments == ["Kopia zaświadczenia lekarskiego o przewidywanej dacie porodu"]
    assert found.place_date == "{{letter-place}}, dnia {{letter-date}}"
    assert found.applicant == ["{{employee-name}}", "{{applicant-address}}"]
    assert found.addressee == ["Pracodawca", "{{employer}}"]
    assert found.signature == "(czytelny podpis pracownicy)"
    assert found.legal_basis == f"Podstawa prawna: art. 180 § 2 Kodeksu pracy; § 2 {REGULATION}"
    assert [(x.id, x.label, x.meaning, x.personal) for x in found.fields] == [
        ("letter-place", "Miejscowość", "place", True),
        ("letter-date", "Data", "date", False),
        ("employee-name", "Imię i nazwisko pracownicy", "applicant-name", True),
        ("applicant-address", "Adres zamieszkania", "applicant-address", True),
        ("employer", "Nazwa i adres pracodawcy", "employer", True),
    ]
    assert f.hr_message is not None
    assert f.hr_message.subject == (
        "Wniosek o udzielenie części urlopu macierzyńskiego przed przewidywaną datą porodu od "
        "dnia 01.03.2027 r."
    )


def test_maternity_leave_from_the_birth() -> None:
    """The employed mother's request without a part before the birth (guide A.4): the period
    and its length (art. 180 § 1); before the birth, from the day of birth (art. 183¹ § 2), and
    the birth certificate comes later; twins: 31 weeks; a stillbirth: 8 weeks (art. 180¹ § 1)."""
    born = letter(timeline(**PARENTS, **BORN, mother_payer_size="over-20"), "maternity-request")
    assert born.title == "Wniosek o udzielenie urlopu macierzyńskiego"
    assert operative(born) == (
        "Na podstawie art. 180 § 1 Kodeksu pracy wnoszę o udzielenie mi urlopu macierzyńskiego "
        "w wymiarze 20 tygodni, w okresie od 10.11.2026 r. do 29.03.2027 r., w związku "
        "z urodzeniem dziecka {{child-name}} w dniu 10.11.2026 r."
    )
    assert born.attachments == ["Odpis skrócony aktu urodzenia dziecka"]
    assert born.legal_basis == "Podstawa prawna: art. 180 § 1 Kodeksu pracy."

    ahead = timeline(
        **PARENTS, **EXPECTING, leave_before_birth_weeks=0, mother_payer_size="over-20"
    )
    found = letter(ahead, "maternity-request")
    assert operative(found) == (
        "Na podstawie art. 180 § 1 i art. 183¹ § 2 Kodeksu pracy wnoszę o udzielenie mi urlopu "
        "macierzyńskiego w wymiarze 20 tygodni od dnia porodu. Przewidywana data porodu to "
        "15.03.2027 r."
    )
    assert statements(found) == ["Odpis skrócony aktu urodzenia dziecka dostarczę po porodzie."]
    assert found.attachments == []

    twins = letter(timeline(**PARENTS, **BORN | {"children_count": 2}), "maternity-request")
    assert operative(twins) == (
        "Na podstawie art. 180 § 1 Kodeksu pracy wnoszę o udzielenie mi urlopu macierzyńskiego "
        "w wymiarze 31 tygodni, w okresie od 10.11.2026 r. do 14.06.2027 r., w związku "
        "z urodzeniem dwojga dzieci ({{child-name}}) przy jednym porodzie w dniu 10.11.2026 r."
    )
    assert next(x for x in twins.fields if x.id == "child-name").label == (
        "Imiona i nazwiska dzieci"
    )
    assert twins.attachments == ["Odpisy skrócone aktów urodzenia dzieci (jeżeli dotyczy)"]

    lost = timeline(**PARENTS, **BORN, losses=[{"stillborn": True}])
    found = letter(lost, "maternity-request")
    assert operative(found) == (
        "Na podstawie art. 180¹ § 1 Kodeksu pracy wnoszę o udzielenie mi urlopu macierzyńskiego "
        "w wymiarze 8 tygodni, w okresie od 10.11.2026 r. do 04.01.2027 r., w związku z porodem "
        "w dniu 10.11.2026 r."
    )
    assert "child-name" not in {x.id for x in found.fields}


def test_the_mothers_resignation() -> None:
    """§ 3: the day of return to work after 14 weeks (art. 180 § 4); the father's request (he
    is an employee) or his statement (not an employee) — art. 180 § 4 pkt 1-2."""
    t = timeline(**PARENTS, **BORN, father_takes_over=True)
    found = letter(t, "maternity-resignation")
    assert found.title == (
        "Wniosek w sprawie rezygnacji z pozostałej części urlopu macierzyńskiego i powrotu do pracy"
    )
    assert operative(found) == (
        "Na podstawie art. 180 § 4 Kodeksu pracy rezygnuję z pozostałej części urlopu "
        "macierzyńskiego po wykorzystaniu po porodzie 14 tygodni tego urlopu i wnoszę "
        "o umożliwienie mi powrotu do pracy od dnia 16.02.2027 r."
    )
    assert statements(found) == [
        "Oświadczam, że pozostałą część urlopu macierzyńskiego wykorzysta ojciec wychowujący "
        "dziecko, który jest pracownikiem (kopia jego wniosku o udzielenie tej części urlopu "
        "w załączeniu)."
    ]
    assert found.attachments == [
        "Kopia wniosku ojca dziecka o udzielenie pozostałej części urlopu macierzyńskiego"
    ]
    assert found.legal_basis == (
        f"Podstawa prawna: art. 180 § 4, art. 180 § 8 Kodeksu pracy; § 3 {REGULATION}"
    )
    contract = timeline(
        **PARENTS | {"father_work": "contract"}, **BORN, father_insured=True, father_takes_over=True
    )
    assert statements(letter(contract, "maternity-resignation")) == [
        "Oświadczam, że przez okres, który pozostał do końca urlopu macierzyńskiego, osobistą "
        "opiekę nad dzieckiem będzie sprawował ojciec dziecka, który w tym celu przerwał "
        "działalność zarobkową (kopia jego oświadczenia w załączeniu)."
    ]


def test_the_father_takes_over_the_rest_of_maternity_leave() -> None:
    """§ 5: his part and its length, why (the mother resigns after 14 weeks, art. 180 § 4), the
    child's name and date of birth, the mother's leave before the birth (none)."""
    t = timeline(**PARENTS, **BORN, father_takes_over=True)
    found = letter(t, "maternity-father-request")
    assert found.title == "Wniosek o udzielenie pozostałej części urlopu macierzyńskiego"
    assert operative(found) == (
        "Na podstawie art. 180 § 4 Kodeksu pracy wnoszę o udzielenie mi pozostałej części "
        "urlopu macierzyńskiego w wymiarze 6 tygodni, w okresie od 16.02.2027 r. do 29.03.2027 "
        "r., w związku z rezygnacją matki dziecka z pozostałej części urlopu macierzyńskiego po "
        "wykorzystaniu przez nią po porodzie 14 tygodni tego urlopu. Wniosek dotyczy dziecka "
        "{{child-name}}, urodzonego w dniu 10.11.2026 r."
    )
    assert statements(found) == [
        "Oświadczam, że matka dziecka nie korzystała z urlopu macierzyńskiego przed porodem."
    ]
    assert found.attachments == [
        "Odpis skrócony aktu urodzenia dziecka",
        "Oświadczenie matki dziecka o zamiarze rezygnacji z pozostałej części urlopu "
        "macierzyńskiego",
    ]
    assert found.applicant == ["{{father-name}}", "{{applicant-address}}"]
    assert found.signature == "(czytelny podpis pracownika)"
    # The form's own fields give the ids and labels of the father's and the child's names.
    assert [(x.id, x.label) for x in found.fields if x.meaning.endswith("-name")] == [
        ("father-name", "Imię i nazwisko taty"),
        ("child-name", "Imię i nazwisko dziecka"),
    ]


@pytest.mark.parametrize(
    ("work", "article", "stopped", "before"),
    [
        (
            "employment",
            "art. 180 § 10",
            "urlop macierzyński",
            "nie korzystała z urlopu macierzyńskiego przed porodem",
        ),
        (
            "contract",
            "art. 180 § 11",
            "pobieranie zasiłku macierzyńskiego",
            "nie pobierała zasiłku macierzyńskiego za okres odpowiadający części urlopu "
            "macierzyńskiego przed porodem",
        ),
    ],
)
def test_the_father_while_the_mother_is_in_hospital(
    work: str, article: str, stopped: str, before: str
) -> None:
    """§ 6 (the mother an employee) and § 7 (insured, not an employee): from the day she
    interrupted the leave or the benefit; her leave before the birth; his commitment to tell
    the employer when she leaves hospital."""
    t = timeline(
        role="mother",
        work=work,
        mother_insured=True if work == "contract" else None,
        father_work="employment",
        child_born=True,
        birth_date="2026-10-01",
        leave_before_birth_weeks=0,
        children_count=1,
        mother_event={"kind": "hospital", "start": "2026-12-01", "end": "2026-12-20"},
    )
    found = letter(t, "maternity-father-request")
    assert found.title == "Wniosek o udzielenie części urlopu macierzyńskiego"
    assert operative(found) == (
        f"Na podstawie {article} Kodeksu pracy wnoszę o udzielenie mi części urlopu "
        "macierzyńskiego od dnia 01.12.2026 r., to jest od dnia, od którego matka dziecka "
        f"przerwała {stopped} na okres pobytu w szpitalu ze względu na stan zdrowia "
        "uniemożliwiający jej sprawowanie osobistej opieki nad dzieckiem. Wniosek dotyczy "
        "dziecka {{child-name}}, urodzonego w dniu 01.10.2026 r."
    )
    assert statements(found) == [
        f"Oświadczam, że matka dziecka {before}.",
        "Zobowiązuję się poinformować pracodawcę o dacie opuszczenia przez matkę dziecka szpitala.",
    ]
    assert found.attachments == [
        "Oświadczenie matki dziecka wskazujące datę, od której przerwała "
        f"{stopped} na okres pobytu w szpitalu",
        "Zaświadczenie szpitala o terminie przyjęcia matki dziecka",
        "Odpis skrócony aktu urodzenia dziecka",
    ]
    assert found.legal_basis.startswith(f"Podstawa prawna: {article}, art. 180 § 16 Kodeksu")


def test_the_father_after_the_mothers_death() -> None:
    """§ 8: the father's part after her death (art. 180 § 12), the date of death, her leave
    before the birth."""
    t = timeline(
        **PARENTS,
        child_born=True,
        birth_date="2026-10-01",
        leave_before_birth_weeks=0,
        children_count=1,
        mother_event={"kind": "death", "start": "2026-11-15"},
    )
    found = letter(t, "maternity-father-request")
    assert operative(found) == (
        "Na podstawie art. 180 § 12 Kodeksu pracy wnoszę o udzielenie mi części urlopu "
        "macierzyńskiego w wymiarze 13 tygodni i 3 dni, w okresie od 16.11.2026 r. do "
        "17.02.2027 r., w związku ze zgonem matki dziecka. Wniosek dotyczy dziecka "
        "{{child-name}}, urodzonego w dniu 01.10.2026 r."
    )
    assert statements(found) == [
        "Oświadczam, że matka dziecka zmarła w dniu 15.11.2026 r.",
        "Oświadczam, że matka dziecka nie korzystała z urlopu macierzyńskiego przed porodem.",
    ]
    assert found.attachments == ["Odpis skrócony aktu urodzenia dziecka"]


def test_the_father_after_the_mother_abandoned_the_child() -> None:
    """§ 9: the father's part after the abandonment (art. 180 § 13), its date."""
    t = timeline(
        **PARENTS,
        child_born=True,
        birth_date="2026-09-01",
        leave_before_birth_weeks=0,
        children_count=1,
        mother_event={"kind": "abandonment", "start": "2026-11-15"},
    )
    found = letter(t, "maternity-father-request")
    assert operative(found) == (
        "Na podstawie art. 180 § 13 Kodeksu pracy wnoszę o udzielenie mi części urlopu "
        "macierzyńskiego w wymiarze 9 tygodni i 1 dnia, w okresie od 16.11.2026 r. do "
        "18.01.2027 r., w związku z porzuceniem dziecka przez matkę dziecka. Wniosek dotyczy "
        "dziecka {{child-name}}, urodzonego w dniu 01.09.2026 r."
    )
    assert (
        statements(found)[0]
        == "Oświadczam, że matka dziecka porzuciła dziecko w dniu 15.11.2026 r."
    )


def test_supplementary_leave() -> None:
    """§ 14: the period (art. 180² § 1) and the end of maternity leave; the statement that the
    other parent will not use it is in the letter, the hospital's certificate attached."""
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
    found = letter(t, "supplementary-request")
    assert found.title == "Wniosek o udzielenie uzupełniającego urlopu macierzyńskiego"
    assert operative(found) == (
        "Na podstawie art. 180² § 1 Kodeksu pracy wnoszę o udzielenie mi uzupełniającego urlopu "
        "macierzyńskiego w wymiarze 3 tygodni, w okresie od 18.02.2027 r. do 10.03.2027 r., "
        "w związku z pobytem w szpitalu dziecka {{child-name}}, urodzonego w dniu 01.10.2026 r. "
        "Urlop macierzyński kończy się 17.02.2027 r."
    )
    assert statements(found) == [
        "Oświadczam, że drugi z rodziców dziecka nie zamierza korzystać z uzupełniającego urlopu "
        "macierzyńskiego ani z zasiłku macierzyńskiego za okres odpowiadający okresowi tego "
        "urlopu."
    ]
    assert found.attachments == ["Zaświadczenie ze szpitala, w którym przebywało dziecko"]
    assert found.legal_basis.startswith("Podstawa prawna: art. 180² § 1, art. 180² § 4 Kodeksu")


def test_parental_leave() -> None:
    """§ 15: the period (art. 182¹ᵃ § 1, "Za życiem" § 2), the leave used so far and the number
    of parts, the other parent's leave in this period; the e-mail to HR."""
    t = timeline(**PARENTS, **BORN)
    f = form(t, "parental-request")
    found = letter(t, "parental-request")
    assert found.title == "Wniosek o udzielenie urlopu rodzicielskiego"
    assert operative(found) == (
        "Na podstawie art. 182¹ᵃ § 1 Kodeksu pracy wnoszę o udzielenie mi urlopu rodzicielskiego "
        "w wymiarze 32 tygodni, w okresie od 30.03.2027 r. do 08.11.2027 r., w związku "
        "z urodzeniem dziecka {{child-name}} w dniu 10.11.2026 r."
    )
    assert statements(found) == [
        "Oświadczam, że dotychczas nie był wykorzystany urlop rodzicielski ani zasiłek "
        "macierzyński za okres odpowiadający okresowi tego urlopu; liczba wykorzystanych części "
        "urlopu rodzicielskiego: 0.",
        "Oświadczam, że drugi z rodziców dziecka nie zamierza korzystać z urlopu rodzicielskiego "
        "ani z zasiłku macierzyńskiego za okres odpowiadający okresowi urlopu rodzicielskiego "
        "w okresie wskazanym we wniosku.",
    ]
    assert found.attachments == ["Odpis skrócony aktu urodzenia dziecka"]
    assert found.legal_basis == (
        f"Podstawa prawna: art. 182¹ᵃ § 1, art. 182¹ᵈ § 1 Kodeksu pracy; § 15 {REGULATION}"
    )
    assert cited_articles(found) == ["art. 182¹ᵃ § 1", "art. 182¹ᵃ § 1", "art. 182¹ᵈ § 1"]
    assert f.hr_message is not None
    assert f.hr_message.subject == (
        "Wniosek o udzielenie urlopu rodzicielskiego od 30.03.2027 r. do 08.11.2027 r."
    )
    assert f.hr_message.body == (
        "Dzień dobry,\n\nw załączeniu przesyłam wniosek o udzielenie urlopu rodzicielskiego od "
        "30.03.2027 r. do 08.11.2027 r. wraz z załącznikami. Proszę o potwierdzenie jego "
        "otrzymania.\n\nZ poważaniem\n{{employee-name}}"
    )
    za_zyciem = letter(timeline(**PARENTS, **BORN, za_zyciem=True), "parental-request")
    assert operative(za_zyciem).startswith("Na podstawie art. 182¹ᵃ § 2 Kodeksu pracy")
    assert za_zyciem.attachments[-1] == "Kopia zaświadczenia „Za życiem”"


def test_parts_of_parental_leave_and_the_other_parents_leave() -> None:
    """Each part is its own request (art. 182¹ᵈ § 2): the second counts both parents' parts
    before it; the other parent's leave within the period asked for."""
    t = timeline(
        **PARENTS,
        **BORN,
        parental_parts=[
            {"parent": "mother", "weeks": 20},
            {"parent": "father", "weeks": 9, "with_previous": True},
            {"parent": "mother", "weeks": 12, "start": "2028-06-01"},
        ],
    )
    first = letter(t, "parental-request-1")
    assert first.title == "Wniosek o udzielenie części urlopu rodzicielskiego"
    assert operative(first) == (
        "Na podstawie art. 182¹ᵃ § 1 Kodeksu pracy wnoszę o udzielenie mi części urlopu "
        "rodzicielskiego w wymiarze 20 tygodni, w okresie od 30.03.2027 r. do 16.08.2027 r., "
        "w związku z urodzeniem dziecka {{child-name}} w dniu 10.11.2026 r."
    )
    assert statements(first)[1] == (
        "Oświadczam, że drugi z rodziców dziecka zamierza korzystać z urlopu rodzicielskiego "
        "(albo z zasiłku macierzyńskiego za okres odpowiadający okresowi tego urlopu) w okresie "
        "objętym wnioskiem: od 30.03.2027 r. do 31.05.2027 r."
    )
    second = letter(t, "parental-request-2")
    assert operative(second).startswith(
        "Na podstawie art. 182¹ᵃ § 1 Kodeksu pracy wnoszę o udzielenie mi części urlopu "
        "rodzicielskiego w wymiarze 12 tygodni, w okresie od 01.06.2028 r. do 23.08.2028 r.,"
    )
    assert statements(second)[0] == (
        "Oświadczam, że dotychczas urlop rodzicielski (albo zasiłek macierzyński za okres "
        "odpowiadający okresowi tego urlopu) został wykorzystany: przeze mnie od 30.03.2027 r. "
        "do 16.08.2027 r.; przez drugiego z rodziców od 30.03.2027 r. do 31.05.2027 r.; liczba "
        "wykorzystanych części urlopu rodzicielskiego: 2."
    )


def test_work_during_parental_leave() -> None:
    """§ 16: the part of full time and the period of work (art. 182¹ᵉ § 1), the statement on
    the extension (the plan has no work in it); the part itself is longer (art. 182¹ᶠ § 1)."""
    t = timeline(
        **PARENTS,
        **BORN,
        parental_parts=[
            {"parent": "mother", "weeks": 32, "work_fraction": "1/2", "work_weeks": 20}
        ],
    )
    work = form(t, "parental-work-request-1")
    found = letter(t, "parental-work-request-1")
    assert found.title == (
        "Wniosek o łączenie korzystania z urlopu rodzicielskiego z wykonywaniem pracy"
    )
    assert operative(found) == (
        "Na podstawie art. 182¹ᵉ § 1 Kodeksu pracy wnoszę o umożliwienie mi łączenia korzystania "
        "z urlopu rodzicielskiego, przypadającego od dnia 30.03.2027 r., z wykonywaniem pracy "
        "u pracodawcy w wymiarze 1/2 pełnego wymiaru czasu pracy, w okresie od 30.03.2027 r. do "
        "16.08.2027 r."
    )
    assert statements(found) == [
        "Oświadczam, że nie zamierzam łączyć z pracą części urlopu rodzicielskiego powstałej "
        "w wyniku proporcjonalnego wydłużenia tego urlopu (od 09.11.2027 r. do 17.01.2028 r.)."
    ]
    assert found.attachments == []
    assert work.hr_message is not None
    assert work.hr_message.body == (
        "Dzień dobry,\n\nw załączeniu przesyłam wniosek o łączenie korzystania z urlopu "
        "rodzicielskiego z wykonywaniem pracy w okresie od 30.03.2027 r. do 16.08.2027 r. Proszę "
        "o potwierdzenie jego otrzymania.\n\nZ poważaniem\n{{employee-name}}"
    )
    part = letter(t, "parental-request-1")
    assert operative(part) == (
        "Na podstawie art. 182¹ᵃ § 1 Kodeksu pracy wnoszę o udzielenie mi części urlopu "
        "rodzicielskiego w wymiarze 32 tygodni, od dnia 30.03.2027 r., w związku z urodzeniem "
        "dziecka {{child-name}} w dniu 10.11.2026 r. W związku z łączeniem urlopu z pracą "
        "(osobny wniosek) urlop wydłuża się proporcjonalnie do 42 tygodni i trwa do 17.01.2028 "
        "r. (art. 182¹ᶠ § 1 Kodeksu pracy)."
    )


def test_paternity_leave() -> None:
    """§ 17: the period (art. 182³ § 1); before the birth its date is a placeholder; whether the
    father already used paternity leave stays with both options."""
    t = expecting()
    found = letter(t, "paternity-request")
    assert found.title == "Wniosek o udzielenie urlopu ojcowskiego"
    assert operative(found) == (
        "Na podstawie art. 182³ § 1 Kodeksu pracy wnoszę o udzielenie mi urlopu ojcowskiego "
        "w wymiarze 2 tygodni, w okresie od 15.03.2027 r. do 28.03.2027 r., w związku "
        "z urodzeniem dziecka {{child-name}} w dniu {{child-birth-date}}."
    )
    choice = found.body[1]
    assert (choice.kind, choice.text, choice.options) == (
        "choice",
        "Oświadczam, że:",
        [
            "nie korzystałem z urlopu ojcowskiego ani z jego części",
            "korzystałem z urlopu ojcowskiego albo z jego części",
        ],
    )
    assert found.attachments == ["Odpis skrócony aktu urodzenia dziecka"]
    birth = next(x for x in found.fields if x.id == "child-birth-date")
    assert (birth.meaning, birth.personal) == ("child-birth-date", False)
    assert found.signature == "(czytelny podpis pracownika)"


# ZUS forms: where the form is, and the data to copy into it.


def test_zus_forms_say_where_the_guide_puts_them() -> None:
    """ZAM and ZAS-53 are on www.zus.pl (guide page 12): no letter, no e-mail to HR; the
    form's fields are the data to copy into it (annex 6 and annex 1)."""
    t = timeline(role="mother", work="business", mother_insured=True, father_work="none", **BORN)
    zam = form(t, "maternity-request")
    assert (zam.letter, zam.hr_message) == (None, None)
    assert zam.official is not None
    assert zam.official.model_dump(exclude={"sources"}) == {
        "code": "ZAM",
        "name": "wniosek o zasiłek macierzyński",
        "where": "www.zus.pl (w zakładce Wzory formularzy, Zasiłki)",
        "url": "https://www.zus.pl",
        "sheet_title": "Dane do wpisania do formularza ZAM",
    }
    assert [(s.section, s.page) for s in zam.official.sources] == [("F", 12), ("F", 12)]
    assert zam.fields
    sick = form(
        timeline(
            role="mother",
            work="business",
            mother_insured=True,
            **EXPECTING,
            leave_before_birth_weeks=0,
            sick_leave=True,
            sick_leave_start="2026-11-01",
            insured_since="2026-10-01",
        ),
        "sick-benefit-request",
    )
    assert sick.official is not None and sick.letter is None
    assert (sick.official.code, sick.official.name) == ("ZAS-53", "wniosek o zasiłek chorobowy")
    assert sick.official.sheet_title == "Dane do wpisania do formularza ZAS-53"
    # An employee's request has no ZUS form.
    assert form(expecting(), "maternity-request").official is None


# No personal value is ever filled in.

CASES: list[dict[str, Any]] = [
    {**PARENTS, **EXPECTING, "leave_before_birth_weeks": 2, "mother_payer_size": "over-20"},
    {**PARENTS, **EXPECTING, "leave_before_birth_weeks": 0},
    {**PARENTS, **BORN, "father_takes_over": True},
    {**PARENTS, **BORN, "children_count": 3, "za_zyciem": True},
    {**PARENTS, **BORN, "losses": [{"stillborn": True}]},
    {**PARENTS, **BORN, "mother_event": {"kind": "incapacity", "start": "2027-01-10"}},
    {**PARENTS, **BORN, "father_work": None, "father_takes_over": True},
    {
        **PARENTS,
        **BORN,
        "parental_parts": [
            {"parent": "mother", "weeks": 20, "work_fraction": "1/4"},
            {"parent": "father", "weeks": 9, "with_previous": True, "work_fraction": "1/2"},
        ],
    },
    {
        **PARENTS,
        **BORN | {"birth_date": "2026-10-01"},
        "hospital_care": True,
        "birth_week": "before-28",
        "birth_weight_up_to_1000g": True,
        "hospital_stays": [{"start": "2026-10-01", "end": "2026-11-20"}],
    },
]
PERSONAL = {"applicant-name", "applicant-address", "employer", "child-name", "place"}


@pytest.mark.parametrize("answers", CASES)
def test_no_personal_value_is_ever_filled_in(answers: dict[str, Any]) -> None:
    """Names, addresses, the employer and the place are only `{{field-id}}` placeholders: every
    placeholder is a letter field, every personal meaning is marked personal, the applicant and
    the employer are nothing but placeholders, and the form's personal fields stay empty."""
    t = timeline(**answers)
    letters = 0
    for document in t.documents:
        f = document.form
        if f is None or f.letter is None:
            continue
        letters += 1
        found = f.letter
        ids = {x.id for x in found.fields}
        used = {m for text in texts(f) for m in TOKEN.findall(text)}
        assert used == ids, document.id
        for x in found.fields:
            assert x.personal == (x.meaning in PERSONAL), (document.id, x.id)
        name = next(x.id for x in found.fields if x.meaning == "applicant-name")
        assert found.applicant == [f"{{{{{name}}}}}", "{{applicant-address}}"]
        assert found.addressee == ["Pracodawca", "{{employer}}"]
        assert f.hr_message is not None
        assert f.hr_message.body.endswith(f"Z poważaniem\n{{{{{name}}}}}")
        for field in f.fields:
            if field.personal:
                assert field.value is None, (document.id, field.id)
                if field.id in ids:
                    assert any(f"{{{{{field.id}}}}}" in text for text in texts(f))
        assert f.official is None  # a letter to the employer is not a ZUS form
        for article in cited_articles(found):
            assert article.startswith("art. "), article
    assert letters
