"""What the timeline shows must come from the documents, word for word."""

import datetime as dt
from typing import Any

import pytest

from app.assistant.guide import guide_sections
from app.assistant.law import (
    ROZPORZADZENIA,
    kp_articles,
    kp_contains,
    rozporzadzenie_contains,
    rozporzadzenie_provisions,
    ustawa_articles,
    ustawa_contains,
    zalacznik_available,
    zalacznik_contains,
    zalacznik_sections,
)
from app.assistant.prompts import STATIC_INSTRUCTIONS
from app.engine import Scenario, build_timeline
from app.engine.models import SourceRef
from app.services.params import load_params

PARAMS = load_params()
SECTIONS = guide_sections()
TODAY = dt.date(2026, 11, 21)


def is_literal(source: SourceRef) -> bool:
    """The quote is a fragment of its source, and for the guide it is on the pages it names."""
    if source.doc == "kp":
        return source.article is not None and kp_contains(source.article, source.quote)
    if source.doc == "ustawa":
        return source.article is not None and ustawa_contains(source.article, source.quote)
    if source.doc == "zalacznik":
        # The Załącznik's text is not in git (a ZUS document): checked where it was built.
        if not zalacznik_available():
            return source.section is not None
        return source.section is not None and zalacznik_contains(source.section, source.quote)
    if source.doc in ROZPORZADZENIA:
        return source.article is not None and rozporzadzenie_contains(
            source.doc, source.article, source.quote
        )
    assert source.section is not None
    pages = SECTIONS[source.section].pages_of(source.quote)
    return pages == (source.page, source.page_to or source.page)


def test_guide_sections_are_the_documents_own_text() -> None:
    a1, a2 = SECTIONS["A.1"], SECTIONS["A.2"]
    assert a1.text.startswith("Kobieta może rozpocząć urlop macierzyński maksymalnie 6 tygodni")
    assert a1.text.endswith("rozpocząć zasiłek po urodzeniu dziecka.")
    assert a2.text.startswith("Po porodzie kobieta ubezpieczona nabywa prawo do zasiłku")
    assert a2.text.endswith("rodzicielskiego za który przysługuje zasiłek macierzyński.")
    assert (a2.page, a2.last_page) == (5, 6)
    assert SECTIONS["C"].text.endswith("Przysługuje bezpośrednio po urlopie macierzyńskim.")
    assert SECTIONS["ZM"].text.endswith("na tych samych zasadach co do wymiaru i wysokości.")


def test_a_sentence_over_a_page_break_is_whole_and_knows_its_pages() -> None:
    a2 = SECTIONS["A.2"]
    sentence = (
        "Udzielany jest jednorazowo albo nie więcej niż w 5 częściach, nie później niż do "
        "zakończenia roku kalendarzowego, w którym dziecko kończy 6 rok życia."
    )
    assert a2.pages_of(sentence) == (5, 6)
    assert a2.pages_of("Pierwsze 14 tygodni po porodzie matka musi wykorzystać osobiście.") == (
        5,
        5,
    )
    assert a2.pages_of("w którym dziecko kończy 6 rok życia") == (6, 6)
    assert a2.pages_of("w którym dziecko kończy 7 rok życia") is None
    # The footnote printed between the two halves is not part of the sentence.
    assert "wydawane jest na podstawie" not in a2.text


def test_labour_code_provisions() -> None:
    assert set(kp_articles()) == {
        "art. 177 § 1",
        "art. 177 § 1¹",
        "art. 177 § 3",
        "art. 92 § 1",
        "art. 92 § 2",
        "art. 92 § 3",
        "art. 92 § 4",
        "art. 92 § 5",
        "art. 180 § 1",
        "art. 180 § 2",
        "art. 180 § 3",
        "art. 180 § 4",
        "art. 180 § 5",
        "art. 180 § 6",
        "art. 180 § 8",
        "art. 180 § 9",
        "art. 180 § 10",
        "art. 180 § 11",
        "art. 180 § 12",
        "art. 180 § 13",
        "art. 180 § 14",
        "art. 180 § 16",
        "art. 180¹ § 1",
        "art. 180¹ § 2",
        "art. 180² § 1",
        "art. 180² § 2",
        "art. 180² § 3",
        "art. 180² § 4",
        "art. 180² § 5",
        "art. 180² § 7",
        "art. 182¹ᵃ § 1",
        "art. 182¹ᵃ § 2",
        "art. 182¹ᵃ § 3",
        "art. 182¹ᵃ § 4",
        "art. 182¹ᵃ § 6",
        "art. 182¹ᵃ § 7",
        "art. 182¹ᶜ",
        "art. 182¹ᵈ § 1",
        "art. 182¹ᵈ § 2",
        "art. 182¹ᵉ § 1",
        "art. 182¹ᵉ § 2",
        "art. 182¹ᶠ § 1",
        "art. 182¹ᶠ § 1¹",
        "art. 182¹ᶠ § 2",
        "art. 182¹ᶠ § 3",
        "art. 182¹ᶠ § 4",
        "art. 182¹ᶠ § 5",
        "art. 182¹ᵍ",
        "art. 182³ § 1",
        "art. 182³ § 1¹",
        "art. 182³ § 2",
        "art. 182³ § 3",
        "art. 183 § 1",
        "art. 183 § 1¹",
        "art. 183 § 2",
        "art. 183 § 3",
        "art. 183 § 3¹",
        "art. 183 § 4",
        "art. 183 § 4¹",
        "art. 183 § 4²",
        "art. 183 § 4³",
        "art. 183 § 4⁴",
        "art. 183 § 4⁵",
        "art. 183 § 4⁶",
        "art. 183 § 5",
        "art. 183 § 6",
        "art. 183 § 7",
        "art. 183 § 8",
        "art. 183¹ § 1",
        "art. 183¹ § 2",
    }
    assert "nie więcej niż 6 tygodni" in kp_articles()["art. 180 § 2"]
    # The excerpt's "(…)" and the next chapter's heading are not part of § 5.
    assert kp_articles()["art. 92 § 5"].endswith("ukończył 50 rok życia.")
    assert "nie większą niż 1000 g" in kp_articles()["art. 180² § 1"]
    assert "nie później niż do zakończenia roku" in kp_articles()["art. 182¹ᶜ"]
    # Article numbers inside the text carry their superscripts again.
    assert kp_articles()["art. 182¹ᵍ"].endswith("art. 183¹ § 1.")
    assert "art. 183¹ § 1 stosuje się odpowiednio" in kp_articles()["art. 180² § 7"]
    # Paragraphs of art. 183 referred to inside it carry their superscripts again too.
    assert "pracownik, o którym mowa w § 1¹, który" in kp_articles()["art. 183 § 3"]
    assert "art. 182¹ᵃ § 3-7" in kp_articles()["art. 183 § 5"]
    assert "nie później niż 21 dni" in kp_articles()["art. 183 § 6"]
    assert "art. 180² § 4, art. 182¹ᵈ § 1, art. 182³ § 2 oraz" in kp_articles()["art. 177 § 1¹"]
    assert kp_articles()["art. 182¹ᵈ § 1"].count("art. 186⁸ᵃ") == 1
    assert "nie krótszym niż 7 dni przed przystąpieniem do pracy" in kp_articles()["art. 180 § 8"]


def test_applications_and_protection_sections() -> None:
    """Who pays (page 1 and footnote 1), the documents (A.4), the forms (page 12) and the
    special protection (section I)."""
    assert SECTIONS["W"].text.endswith("w którym dokonali takiego zgłoszenia).")
    assert "powyżej 20 ubezpieczonych" in SECTIONS["W"].text
    a4 = SECTIONS["A.4"]
    assert a4.text.startswith("Kobieta będąca pracownikiem występuje do pracodawcy")
    assert a4.text.endswith("podstawę do uzupełniającego urlopu macierzyńskiego).")
    assert (a4.page, a4.last_page) == (6, 6)
    assert SECTIONS["I"].text.endswith("prowadzących pozarolniczą działalność.")
    assert "Formularz ZAO od 24 października 2026 r." in SECTIONS["F"].text

    assert "w wymiarze nie wyższym niż połowa" in kp_articles()["art. 182¹ᵉ § 1"]
    assert "o którym mowa w § 1 albo § 1¹, odbywa się" in kp_articles()["art. 182¹ᶠ § 3"]


def test_ustawa_zasilkowa_provisions() -> None:
    """Guide section G rests on these; the text is the excerpt's own, footnotes and page headers
    left out."""
    assert set(ustawa_articles()) == {
        "art. 3 pkt 3",
        "art. 3 pkt 4",
        "art. 7",
        "art. 8 ust. 2",
        "art. 11 ust. 2",
        "art. 11 ust. 4",
        "art. 11 ust. 5",
        "art. 18 ust. 1",
        "art. 18 ust. 2",
        "art. 18 ust. 3",
        "art. 18 ust. 4",
        "art. 18 ust. 6",
        "art. 19 ust. 1",
        "art. 22",
        "art. 13 ust. 1",
        "art. 29a ust. 1",
        "art. 30 ust. 1",
        "art. 30 ust. 3",
        "art. 30 ust. 4",
        "art. 30a ust. 1",
        "art. 30a ust. 2",
        "art. 30a ust. 3",
        "art. 31 ust. 1",
        "art. 31 ust. 2",
        "art. 31 ust. 3",
        "art. 31 ust. 3a",
        "art. 31 ust. 3f",
        "art. 31 ust. 3g",
        "art. 31 ust. 4",
        "art. 31 ust. 4a",
        "art. 31 ust. 5",
        "art. 36 ust. 1",
        "art. 36 ust. 3",
        "art. 47",
        "art. 48 ust. 1",
        "art. 52",
        "art. 61 ust. 1",
        # The benefit base in detail (engine/base.py).
        "art. 36 ust. 2",
        "art. 36 ust. 4",
        "art. 37 ust. 1",
        "art. 37 ust. 2",
        "art. 38 ust. 1",
        "art. 38 ust. 2",
        "art. 38 ust. 3",
        "art. 42 ust. 1",
        "art. 42 ust. 2",
        "art. 42 ust. 3",
        "art. 43",
        "art. 45 ust. 1",
        "art. 45 ust. 2",
        "art. 48 ust. 2",
        "art. 48a ust. 1",
        "art. 49 ust. 1",
        "art. 50 ust. 1",
        "art. 50 ust. 2",
        # Contribution debt of a business (engine/debt.py).
        "art. 2",
        "art. 2a ust. 1",
        "art. 2a ust. 2",
        "art. 64 ust. 3",
    }
    texts = ustawa_articles()
    assert texts["art. 30a ust. 1"].startswith("Ubezpieczona - matka dziecka, nie później niż 21")
    assert "art. 182¹ᵃ § 4 Kodeksu pracy" in texts["art. 31 ust. 3f"]
    assert texts["art. 3 pkt 3"].startswith("wynagrodzenie - przychód pracownika")
    assert "13,71%" in texts["art. 3 pkt 4"]
    assert texts["art. 31 ust. 5"].endswith("art. 12 ust. 1 i ust. 2 pkt 1 i 3.")
    # The rehabilitation benefit: the excerpt's "(…)" after art. 22 is not part of it.
    assert texts["art. 22"].endswith("art. 13 ust. 1, art. 15 i 17.")
    assert "nie dłużej jednak niż przez 12 miesięcy" in texts["art. 18 ust. 2"]
    assert "w okresie ciąży - 100% tej podstawy" in texts["art. 19 ust. 1"]
    assert all("Legalis" not in t and "ROZDZIAŁ" not in t for t in texts.values())
    assert SECTIONS["G.3"].text.startswith("Jeżeli ubezpieczona-matka, niepóźnej niż 21 dni")
    # A paragraph keeps its points; the next paragraph or article is not part of it.
    assert "3) kwota zmiennych składników" in texts["art. 37 ust. 2"]
    assert texts["art. 38 ust. 2"].endswith("co najmniej połowę obowiązującego go czasu pracy.")
    assert texts["art. 43"].endswith("krótsza niż miesiąc kalendarzowy.")
    assert texts["art. 49 ust. 1"].endswith(
        "na rzecz danego płatnika składek za miesiąc, w którym "
        "powstało prawo do zasiłku - dla osób wykonujących "
        "pracę nakładczą."
    )


def test_the_two_regulations_on_requests() -> None:
    """The request forms quote the regulation on the leave requests (11 March 2025) and the one
    on the benefit documents (27 September 2026): their own text, page headers and footnotes
    left out, superscripts in article numbers restored."""
    wnioski = rozporzadzenie_provisions("rozp_wnioski")
    zasilki = rozporzadzenie_provisions("rozp_zasilki")
    assert set(wnioski) == {
        *(f"§ {n} ust. {u}" for n in (2, 3, 5, 6, 7, 8, 9, 14, 15, 17) for u in (1, 2)),
        "§ 22",
    }
    assert set(zasilki) == {
        "§ 2",
        "§ 12",
        "§ 13 ust. 1",
        "§ 13 ust. 2",
        "§ 13 ust. 3",
        "§ 20 ust. 1",
        "§ 20 ust. 3",
        "§ 22 ust. 1",
        "§ 23 ust. 1",
        "§ 26",
        "§ 29",
        "§ 30 ust. 1",
        "§ 32 ust. 1",
        "§ 33 ust. 1",
        "zał. 1",
        "zał. 6",
    }
    assert wnioski["§ 2 ust. 1"].endswith(
        "1) imię i nazwisko pracownicy; 2) wskazanie daty, od której ma być udzielona część "
        "urlopu macierzyńskiego."
    )
    # The footnote printed at the bottom of page 1 is not part of § 3.
    assert wnioski["§ 3 ust. 2"].endswith("który pozostał do końca urlopu macierzyńskiego.")
    assert wnioski["§ 14 ust. 1"].startswith("Wniosek, o którym mowa w art. 180² § 4 Kodeksu pracy")
    assert "art. 182¹ᵈ § 1" in wnioski["§ 15 ust. 1"]
    assert "art. 182¹ᵃ § 2 Kodeksu pracy" in wnioski["§ 15 ust. 2"]
    assert all("Legalis" not in t for t in (*wnioski.values(), *zasilki.values()))
    assert zasilki["zał. 6"].startswith("1) NIP i REGON płatnika składek")
    assert zasilki["zał. 6"].endswith("19) pouczenie dotyczące zasiłku macierzyńskiego.")
    assert zasilki["zał. 1"].endswith("10) pouczenie dotyczące zasiłku chorobowego.")
    assert "art. 180² § 5 Kodeksu pracy" in zasilki["§ 26"]


def test_the_forms_quote_only_what_the_regulations_and_the_guide_say() -> None:
    templates = PARAMS.forms.templates
    for template in templates.values():
        for source in template.basis:
            assert is_literal(source), source.quote
        for item in (*template.fields.values(), *template.attachments.values()):
            for source in item.sources:
                assert is_literal(source), (item.label, source.quote)
    assert "Wzory formularzy, Zasiłki)." in SECTIONS["F"].text


@pytest.mark.skipif(
    not zalacznik_available(), reason="zalacznik.json is built locally from the ZUS materials"
)
def test_zalacznik_sections() -> None:
    """The chapter of the ZUS Załącznik on the benefit base, its own text; table rows keep their
    cells separated by " | "."""
    sections = zalacznik_sections()
    assert set(sections) == {
        "Podstawa wymiaru zasiłków dla pracowników",
        "Okres uwzględniany w podstawie wymiaru zasiłku",
        "Minimalna podstawa wymiaru zasiłku w 2026 roku",
        "Składniki wynagrodzenia w podstawie wymiaru zasiłku",
        "Uzupełnianie wynagrodzenia za niepełny miesiąc",
        "Podstawa wymiaru zasiłków dla nie pracowników",
    }
    period = sections["Okres uwzględniany w podstawie wymiaru zasiłku"]
    assert period.startswith("Sytuacja pracownika | Sposób ustalenia podstawy wymiaru zasiłku")
    assert "(4 806 zł brutto)" in sections["Minimalna podstawa wymiaru zasiłku w 2026 roku"]
    cap = "wynosi 23 550,00 zł (co po odjęciu 13,71% daje limit podstawy zasiłku 20 321,30 zł)"
    assert cap in sections["Podstawa wymiaru zasiłków dla nie pracowników"]
    # The original's typo stays.
    components = sections["Składniki wynagrodzenia w podstawie wymiaru zasiłku"]
    assert "(gdy przysługuje w czasie zawonienia)" in components


def test_every_quote_in_params_is_literal() -> None:
    for source in PARAMS.sources():
        assert is_literal(source), source.quote


def scenarios() -> list[dict[str, Any]]:
    """Every kind of case the phases cover: who is insured, born or not, leave before the birth,
    number of children, "Za życiem" and the hospital cases."""
    base = {"due_date": "2027-03-15", "birth_date": "2026-10-01"}
    cases: list[dict[str, Any]] = [
        {**base, "child_born": child_born, "leave_before_birth_weeks": weeks} | children
        for child_born in (False, True)
        for weeks in (None, 0, 3, 6)
        for children in ({}, {"children_count": 1}, {"children_count": 2})
    ]
    insurance = [
        {"role": "mother", "work": "employment"},
        {"role": "mother", "work": "contract"},
        {"role": "mother", "work": "business", "mother_insured": True},
        {"role": "mother", "work": "contract", "mother_insured": False},
        {"role": "mother", "work": "none"},
        {"role": "father", "work": "employment"},
        {"role": "father", "work": "none", "mother_work": "employment"},
        {"role": "father", "work": "business", "mother_work": "none"},
    ]
    cases += [
        {**base, "child_born": child_born, "children_count": 1} | who
        for child_born in (False, True)
        for who in insurance
    ]
    cases += [
        {**base, "child_born": child_born, "children_count": children, "za_zyciem": True}
        for child_born in (False, True)
        for children in (1, 2)
    ]
    born = {**base, "child_born": True, "leave_before_birth_weeks": 0, "hospital_care": True}
    stay = [{"start": "2026-10-01", "end": "2026-10-20"}]
    cases += [
        {**born, "children_count": 1},
        {**born, "children_count": 1, "hospital_care": False},
        {**born, "children_count": 1, "birth_week": "before-28", "birth_weight_up_to_1000g": True}
        | {"hospital_stays": stay},
        {**born, "children_count": 2, "birth_week": "28-37", "birth_weight_up_to_1000g": False}
        | {"hospital_stays": [{"start": "2026-10-01", "end": None}]},
        {**born, "children_count": 1, "birth_week": "after-37", "birth_weight_up_to_1000g": False}
        | {"hospital_stays": stay},
        {**born, "children_count": 1, "birth_week": "after-37", "birth_weight_up_to_1000g": False}
        | {"hospital_stays": [{"start": "2026-10-01", "end": "2026-10-03"}]},
        {**born, "children_count": 1, "birth_week": "28-37", "birth_weight_up_to_1000g": False},
    ]
    # Stillbirth or death: early, late, during parental leave, twins, after leave before birth.
    lost = {**base, "child_born": True, "role": "mother", "work": "employment"}
    for birth, losses, children, weeks in [
        ("2026-11-10", [{"stillborn": True}], 1, 0),
        ("2026-11-10", [{"stillborn": True}], 1, 6),
        ("2026-09-20", [{"died_on": "2026-11-13"}], 1, 0),
        ("2026-07-01", [{"died_on": "2026-10-01"}], 1, None),
        ("2026-01-05", [{"died_on": "2026-08-01"}], 1, 0),
        ("2026-11-10", [{"stillborn": True}], 2, 0),
        ("2026-01-01", [{"died_on": "2026-06-01"}], 2, 0),
        ("2026-11-10", [{"stillborn": True}, {"stillborn": True}], 2, 0),
    ]:
        cases.append(
            lost
            | {"birth_date": birth, "losses": losses, "children_count": children}
            | {"leave_before_birth_weeks": weeks}
        )
    return (
        cases
        + father_scenarios()
        + application_scenarios()
        + pregnancy_scenarios()
        + taken_in_scenarios()
        + money_scenarios()
        + base_scenarios()
    )


def money_scenarios() -> list[dict[str, Any]]:
    """Guide section G: amounts for either parent, employed or not, the choice of rate, the
    father taking over, an uninsured mother, an unknown amount, the deadline passed."""
    cases: list[dict[str, Any]] = []
    for child_born in (False, True):
        base = {"due_date": "2027-03-15", "birth_date": "2026-11-10", "child_born": child_born}
        base |= {"role": "mother", "children_count": 1}
        for work in ("employment", "contract", "business"):
            for rate in (None, True, False):
                cases.append(
                    base
                    | {"work": work, "mother_insured": True, "mother_pay": 6000.5}
                    | {"father_work": "employment", "father_pay": 9000, "rate_815": rate}
                    | {"leave_before_birth_weeks": 2}
                )
        cases += [
            base | {"work": "employment", "mother_pay": "unknown", "father_pay": "unknown"},
            base | {"work": "none", "father_work": "business", "father_pay": 5000},
            base
            | {"work": "employment", "rate_815": True, "father_takes_over": True}
            | {"mother_pay": 7000, "father_work": "employment", "father_pay": 8000},
        ]
    born = {"child_born": True, "role": "mother", "work": "employment", "children_count": 1}
    cases += [
        born | {"birth_date": "2026-10-01", "mother_pay": 7000},  # the deadline has passed
        born
        | {"birth_date": "2026-10-01", "mother_pay": 7000, "hospital_care": True}
        | {"birth_week": "28-37", "birth_weight_up_to_1000g": False, "rate_815": True}
        | {"hospital_stays": [{"start": "2026-10-01", "end": "2026-10-20"}]},
        born | {"birth_date": "2026-11-10", "mother_pay": 7000, "losses": [{"stillborn": True}]},
        born
        | {"birth_date": "2026-10-01", "mother_pay": 7000, "father_pay": 7000}
        | {"mother_event": {"kind": "death", "start": "2026-11-15"}, "rate_815": True},
    ]
    return cases + every_paid_period_scenarios()


def every_paid_period_scenarios() -> list[dict[str, Any]]:
    """Every paid period: part-time work, the father's shared weeks, the first year, a child
    taken in, sick leave, losing the job (ustawa art. 30) and sick leave after it ended."""
    pays = {"mother_pay": 8000, "father_work": "employment", "father_pay": 6000}
    born = {"child_born": True, "role": "mother", "work": "employment", "children_count": 1}
    born |= {"birth_date": "2026-11-10", "leave_before_birth_weeks": 0} | pays
    cases: list[dict[str, Any]] = [
        born
        | {"rate_815": rate}
        | {"parental_parts": [{"parent": "mother", "weeks": 20, "work_fraction": "1/2"}]}
        for rate in (None, True)
    ]
    cases += [
        born | {"rate_815": True, "parental_parts": [{"parent": "father", "weeks": 12}]},
        born
        | {"rate_815": True}
        | {"parental_parts": [{"parent": "mother", "weeks": 32, "start": "2027-11-15"}]},
    ]
    taken = {"child_born": True, "taken_in_on": "2026-11-02", "birth_date": "2024-05-10"}
    taken |= {"children_count": 1, "work": "employment"} | pays
    cases += [
        taken | {"taken_in": kind, "role": role, "mother_work": "employment", "rate_815": rate}
        for kind in ("adoption", "foster")
        for role in ("mother", "father")
        for rate in (None, True, False)
    ]
    expecting = {"due_date": "2027-03-15", "child_born": False, "children_count": 1}
    expecting |= {"role": "mother", "work": "employment"} | pays
    ended = "2026-11-30"
    for reason in ("bankruptcy", "liquidation", "employer-death", "unlawful", "other"):
        for extra in ({}, {"leave_before_birth_weeks": 6}, {"rate_815": True}):
            cases.append(expecting | {"job_loss": {"ended_on": ended, "reason": reason}} | extra)
    cases += [
        expecting
        | {"job_loss": {"ended_on": ended, "reason": "unlawful", "court_confirmed": True}},
        born | {"job_loss": {"ended_on": "2026-08-31", "reason": "employer-death"}},
        born
        | {"leave_before_birth_weeks": 2}
        | {"job_loss": {"ended_on": "2026-10-31", "reason": "liquidation"}},
    ]
    other = expecting | {"job_loss": {"ended_on": ended, "reason": "other"}, "sick_leave": True}
    cases += [
        other | sick
        for sick in (
            {"sick_leave_start": "2026-10-01"},
            {"sick_leave_start": "2026-12-05"},
            {"sick_leave_start": "2026-12-20"},
            {"sick_leave_start": "2026-12-05", "sick_leave_end": "2026-12-20"},
            {"sick_leave_start": "2026-11-15", "insured_since": "2026-11-10"},
        )
    ]
    cases.append(expecting | {"sick_leave": True, "sick_leave_start": "2026-11-01"})
    return cases


def base_scenarios() -> list[dict[str, Any]]:
    """The benefit base in detail: months in full, worked in part (less and at least half, fixed
    pay), every month short, bonuses, a shorter insurance, the first month, the minimum, the cap,
    sick leave straight into maternity leave, an expected child, either parent."""
    born = {"child_born": True, "birth_date": "2026-11-10", "children_count": 1}
    born |= {"role": "mother", "leave_before_birth_weeks": 0}
    year = [{"month": month, "amount": 8000} for month in _months("2025-11", 12)]
    partial = [
        *year[:4],
        {"month": "2026-03", "amount": 3000, "days_required": 21, "days_worked": 8},
        {"month": "2026-04", "amount": 4400, "days_required": 22, "days_worked": 11},
        {"month": "2026-05", "amount": 7400, "days_required": 21, "days_worked": 14}
        | {"fixed": 6000, "variable": 1400, "not_topped": 300},
        *year[7:],
    ]
    short = [
        {"month": month, "amount": 2000, "days_required": 21, "days_worked": 5}
        for month in ("2026-08", "2026-09", "2026-10")
    ]
    first_month = [{"month": "2026-11", "amount": 1600, "days_required": 6, "days_worked": 4}]
    histories: list[dict[str, Any]] = [
        {"months": year},
        {"months": partial, "quarterly_bonuses": 6000, "annual_bonus": 9600},
        {"months": short, "insured_from": "2026-08-01"},
        {"months": year[5:], "insured_from": "2026-03-15", "full_time": True},
        {"insured_from": "2026-11-02", "contract_pay": 6000},
        {"months": first_month, "insured_from": "2026-11-02"},
        {"full_time": True},
    ]
    cases: list[dict[str, Any]] = [
        born | {"work": "employment", "mother_pay": 4000, "mother_pay_history": history}
        for history in histories
    ]
    cases += [
        born | {"work": work, "mother_insured": True, "mother_pay_history": history}
        for work in ("contract", "business")
        for history in (
            {"months": [month | {"amount": 25000} for month in year]},
            {"months": short, "insured_from": "2026-08-01"},
            {"insured_from": "2026-11-02", "contract_pay": 5000},
        )
    ]
    cases += [
        born
        | {"work": "employment", "sick_leave": True, "sick_leave_start": "2026-06-01"}
        | {"sick_leave_end": end, "mother_pay_history": {"months": year}}
        for end in (None, "2026-08-31")
    ]
    cases += [
        {"child_born": False, "due_date": "2027-03-15", "children_count": 1, "role": "mother"}
        | {"work": "employment", "mother_pay_history": {"months": year}}
        | {"father_work": "business", "father_pay_history": {"months": year}},
        born
        | {"work": "none", "father_work": "employment"}
        | {"father_pay_history": {"months": partial, "full_time": False}},
    ]
    return cases


def _months(first: str, count: int) -> list[str]:
    """ "2025-11", 3 -> ["2025-11", "2025-12", "2026-01"]"""
    year, month = (int(part) for part in first.split("-"))
    index = year * 12 + month - 1
    return [f"{(index + i) // 12}-{(index + i) % 12 + 1:02d}" for i in range(count)]


def father_scenarios() -> list[dict[str, Any]]:
    """Section B: how the father works, paternity leave near its deadline, his parental leave
    with an insured or uninsured mother, taking over, and every special situation."""
    cases: list[dict[str, Any]] = []
    fathers = [
        {},
        {"father_work": "employment"},
        {"father_work": "contract"},
        {"father_work": "business", "father_insured": True},
        {"father_work": "contract", "father_insured": False},
        {"father_work": "none"},
    ]
    mothers = [
        {"role": "mother", "work": "employment"},
        {"role": "mother", "work": "none"},
        {"role": "mother", "work": "contract", "mother_insured": False},
    ]
    for child_born in (False, True):
        base = {"due_date": "2027-03-15", "birth_date": "2026-11-10", "child_born": child_born}
        cases += [
            base | mother | father | {"children_count": children}
            for mother in mothers
            for father in fathers
            for children in (1, 2)
        ]
        cases += [
            base
            | {"role": "mother", "work": "employment", "children_count": 1}
            | {"father_takes_over": True}
            | father
            for father in ({}, {"father_work": "none"}, {"father_work": "contract"})
        ]
    born = {"child_born": True, "children_count": 1, "role": "mother", "work": "employment"}
    # Paternity leave cut short, too short to show, and expired; parental leave cut short by
    # its deadline and expired, with an uninsured mother.
    cases += [born | {"birth_date": day} for day in ("2025-11-30", "2025-11-26", "2025-11-20")]
    cases += [{**born, "work": "none", "birth_date": day} for day in ("2020-06-01", "2019-06-01")]
    cases += [
        born
        | {"birth_date": "2026-11-10", "father_takes_over": True}
        | {"mother_weeks_before_takeover": 16, "za_zyciem": True},
        born
        | {"birth_date": "2026-11-10", "father_takes_over": True, "children_count": 2}
        | {"losses": [{"stillborn": True}]},
    ]
    # Special situations: each kind, the father insured or not, after the leave, the mother
    # uninsured, no living child, and a premature child whose supplementary leave passes on.
    special = born | {"birth_date": "2026-10-01", "leave_before_birth_weeks": 0}
    events = [
        {"kind": "incapacity", "start": "2026-12-01"},
        {"kind": "incapacity", "start": "2027-01-10"},
        {"kind": "hospital", "start": "2026-12-01", "end": "2026-12-20"},
        {"kind": "hospital", "start": "2026-12-01"},
        {"kind": "hospital", "start": "2026-12-01", "end": "2027-03-01"},
        {"kind": "hospital", "start": "2027-03-01"},
        {"kind": "death", "start": "2026-11-15"},
        {"kind": "abandonment", "start": "2026-11-10"},
    ]
    cases += [
        special | {"mother_event": e} | father
        for e in events
        for father in ({}, {"father_work": "none"}, {"father_work": "business"})
    ]
    cases += [special | {"mother_event": e, "work": "none"} for e in events[:1] + events[6:7]]
    cases += [special | {"mother_event": e, "losses": [{"stillborn": True}]} for e in events[2:3]]
    cases += [
        special
        | {"mother_event": e, "hospital_care": True, "birth_week": "28-37"}
        | {"birth_weight_up_to_1000g": False}
        | {"hospital_stays": [{"start": "2026-10-01", "end": "2026-10-20"}]}
        for e in events[6:8]
    ]
    later = born | {"birth_date": "2026-01-05", "leave_before_birth_weeks": 0}
    cases += [
        later | {"mother_event": {"kind": kind, "start": "2026-08-01"}} | father
        for kind in ("death", "abandonment")
        for father in ({}, {"father_work": "none"})
    ]
    return cases


def application_scenarios() -> list[dict[str, Any]]:
    """Applications and protection: how each parent works and how many people the payer reports,
    a passed deadline, attachments, taking over and the special situations."""
    cases: list[dict[str, Any]] = []
    works = [
        {"work": "employment"},
        {"work": "contract"},
        {"work": "business", "mother_insured": True},
    ]
    fathers = [
        {"father_work": "employment"},
        {"father_work": "contract"},
        {"father_work": "business"},
        {"father_work": "none"},
    ]
    for child_born in (False, True):
        base = {"due_date": "2027-03-15", "birth_date": "2026-11-10", "child_born": child_born}
        cases += [
            base
            | {"role": "mother", "children_count": 1, "leave_before_birth_weeks": weeks}
            | work
            | father
            | {"mother_payer_size": size, "father_payer_size": size}
            for work in works
            for father in fathers
            for size in ("over-20", "up-to-20", "unknown", None)
            for weeks in (0, 2)
        ]
    born = {"child_born": True, "role": "mother", "work": "employment", "children_count": 1}
    born |= {"father_work": "employment", "leave_before_birth_weeks": 0}
    cases += [
        born | {"birth_date": "2026-11-10", "father_takes_over": True},
        born | {"birth_date": "2026-11-10", "za_zyciem": True, "work": "contract"},
        born | {"birth_date": "2026-11-10", "losses": [{"stillborn": True}]},
        born | {"birth_date": "2026-11-10", "losses": [{"stillborn": True}], "work": "business"},
        born
        | {"birth_date": "2026-06-20", "hospital_care": True, "birth_week": "28-37"}
        | {"birth_weight_up_to_1000g": False}
        | {"hospital_stays": [{"start": "2026-06-20", "end": "2026-07-20"}]},
    ]
    events = [
        {"kind": "incapacity", "start": "2026-12-01"},
        {"kind": "hospital", "start": "2026-12-01", "end": "2026-12-20"},
        {"kind": "death", "start": "2026-11-15"},
        {"kind": "abandonment", "start": "2026-11-10"},
    ]
    cases += [
        born | {"birth_date": "2026-10-01", "mother_event": e} | father
        for e in events
        for father in ({}, {"father_work": "contract"}, {"father_work": "business"})
    ]
    return cases


def pregnancy_scenarios() -> list[dict[str, Any]]:
    """Sick leave in pregnancy for every kind of work, before the right arises, over 270 days and
    into maternity leave; every way of losing the job; the risks of section H."""
    cases: list[dict[str, Any]] = []
    works = [
        {"role": "mother", "work": "employment"},
        {"role": "mother", "work": "employment", "mother_over_50": True},
        {"role": "mother", "work": "contract", "mother_insured": True},
        {"role": "mother", "work": "business"},
        {"role": "mother", "work": "contract", "mother_insured": False},
        {"role": "mother", "work": "none"},
        {"role": "father", "work": "employment"},
    ]
    sick = [
        {"sick_leave_start": "2026-06-01"},
        {"sick_leave_start": "2026-11-01", "sick_leave_end": "2026-11-20"},
        {"sick_leave_start": "2026-11-01", "insured_since": "2026-10-25"},
        {"sick_leave_start": "2026-11-01", "sick_leave_end": "2026-11-20"}
        | {"insured_since": "2026-10-25"},
        {"sick_leave_start": "2026-12-20", "insured_since": "2026-09-01"},
    ]
    for child_born in (False, True):
        base = {"due_date": "2027-03-15", "birth_date": "2027-01-10", "child_born": child_born}
        cases += [
            base | who | {"children_count": 1, "sick_leave": True} | answers | weeks
            for who in works
            for answers in sick
            for weeks in ({}, {"leave_before_birth_weeks": 0}, {"leave_before_birth_weeks": 1})
        ]
    expecting = {"due_date": "2027-03-15", "child_born": False, "children_count": 1}
    employed = expecting | {"role": "mother", "work": "employment"}
    losses = [
        {"ended_on": "2026-11-30", "reason": reason}
        for reason in ("bankruptcy", "liquidation", "employer-death", "unlawful", "other")
    ] + [{"ended_on": "2026-11-30", "reason": "unlawful", "court_confirmed": True}]
    cases += [
        employed | {"job_loss": loss} | sick
        for loss in losses
        for sick in (
            {},
            *[
                {"sick_leave": True, "sick_leave_start": "2026-10-01"},
                {"sick_leave": True, "sick_leave_start": "2026-12-05"},
            ],
        )
    ]
    cases += [
        expecting
        | {"role": "mother", "work": work, "mother_insured": True}
        | {"insured_in_pregnancy": True, "contribution_base_raised": True}
        for work in ("contract", "business", "employment")
    ]
    # The rehabilitation benefit after the 270 days: not told, applied for, granted (with an
    # end), refused; before the leave before the birth; after the birth; a short sick leave.
    long_sick = {"sick_leave": True, "sick_leave_start": "2026-06-01"}
    for status in (None, "applied", "granted", "refused"):
        for extra in (
            {"leave_before_birth_weeks": 0},
            {"leave_before_birth_weeks": 1},
            {"rehab_benefit_end": "2027-03-05", "leave_before_birth_weeks": 0},
        ):
            cases.append(employed | long_sick | {"rehab_benefit": status} | extra)
    cases += [
        employed | {"due_date": "2027-03-01"} | long_sick | {"rehab_benefit": "granted"},
        employed
        | {"sick_leave": True, "sick_leave_start": "2026-05-01", "rehab_benefit": "granted"}
        | {"job_loss": {"ended_on": "2027-02-10", "reason": "liquidation"}},
        {"due_date": "2027-03-15", "birth_date": "2027-03-01", "child_born": True}
        | {"role": "mother", "work": "business", "mother_insured": True, "children_count": 1}
        | long_sick
        | {"rehab_benefit": "applied"},
        employed
        | {"sick_leave": True, "sick_leave_start": "2026-11-02"}
        | {"rehab_benefit": "applied"},
    ]
    return cases


def taken_in_scenarios() -> list[dict[str, Any]]:
    """Section D: adoption and foster care, who fills in and how they work, the age limits
    (cut, the 9-week minimum, too old, postponed schooling), more children, "Za życiem" and the
    adoption ruling."""
    base = {"child_born": True, "taken_in_on": "2026-11-02", "children_count": 1}
    people = [
        {"role": "mother", "work": "employment", "father_work": "employment"},
        {"role": "mother", "work": "contract", "mother_insured": True},
        {"role": "mother", "work": "business"},
        {"role": "mother", "work": "none", "father_work": "employment"},
        {"role": "father", "work": "employment", "mother_work": "contract"},
        {"role": "father", "work": "contract", "father_insured": False},
        {},
    ]
    births = ["2024-05-10", "2020-03-15", "2012-12-01", "2018-01-01", None]
    cases: list[dict[str, Any]] = [
        base | person | {"taken_in": kind, "birth_date": birth}
        for kind in ("adoption", "foster")
        for person in people
        for birth in births
    ]
    cases += [
        base | {"taken_in": kind, "birth_date": "2023-01-01", "children_count": count} | extra
        for kind in ("adoption", "foster")
        for count in (2, 5)
        for extra in ({}, {"za_zyciem": True})
    ]
    cases += [
        base | {"taken_in": "foster", "birth_date": "2020-03-15", "school_postponed": True},
        base | {"taken_in": "foster", "children_count": None, "birth_date": "2024-05-10"},
    ]
    ruling = {"taken_in": "adoption", "role": "father", "work": "employment"}
    cases += [
        base | ruling | {"birth_date": birth, "adoption_final": True} | {"adoption_final_on": final}
        for birth in ("2024-05-10", "2012-12-01")
        for final in ("2026-11-15", "2026-11-20")
    ]
    cases.append(base | ruling | {"birth_date": "2024-05-10", "adoption_final": False})
    # Art. 183 edge cases: the uninsured person's partner takes the leave, passing the leave on
    # (to an insured or uninsured parent), supplementary leave, adoption after foster care.
    cases += [
        base
        | {"taken_in": kind, "birth_date": "2024-05-10"}
        | {"role": role, "work": "none"}
        | ({"father_work": work} if role == "mother" else {"mother_work": work})
        for kind in ("adoption", "foster")
        for role in ("mother", "father")
        for work in ("employment", "business", "none")
    ]
    cases += [
        base
        | {"taken_in": kind, "birth_date": "2024-05-10", "role": "father", "work": "employment"}
        | {"mother_work": work, "taken_in_handover": True, "taken_in_handover_after_weeks": weeks}
        for kind in ("adoption", "foster")
        for work in ("employment", "contract", "none")
        for weeks in (None, 16)
    ]
    newborn = base | {"taken_in_on": "2026-09-20", "birth_date": "2026-09-01", "role": "mother"}
    newborn |= {"work": "employment", "father_work": "employment", "hospital_care": True}
    cases += [
        newborn
        | {"taken_in": kind, "birth_week": week, "birth_weight_up_to_1000g": light}
        | {"hospital_stays": stays}
        for kind in ("adoption", "foster")
        for week, light in (("before-28", True), ("28-37", False), ("after-37", False))
        for stays in (
            [{"start": "2026-09-01", "end": "2026-10-10"}],
            [{"start": "2026-09-01", "end": "2026-09-15"}],
            [{"start": "2026-10-01", "end": None}],
        )
    ]
    cases.append(newborn | {"taken_in": "adoption", "hospital_care": None})
    adopted = base | {"taken_in": "adoption", "taken_in_on": "2026-10-01"}
    adopted |= {"birth_date": "2020-03-15", "role": "mother", "work": "employment"}
    adopted |= {"father_work": "employment"}
    cases += [
        adopted | {"foster_before": before}
        for before in (
            {"leave_start": "2026-08-03", "leave_end": "2026-12-31"},
            {"leave_start": "2026-01-05", "leave_end": "2026-05-24", "parental_weeks": 10},
            {"parental_weeks": 38},
            {"leave_start": "2026-08-03", "leave_end": "2026-09-30", "parental_weeks": 2},
        )
    ]
    cases.append(adopted | {"za_zyciem": True, "foster_before": {"parental_weeks": 5}})
    return cases


@pytest.mark.parametrize("answers", scenarios())
def plan_scenarios() -> list[dict[str, Any]]:
    """Guide E and B.3: parental leave split between the parents, in parts, with work: whole
    weeks and days, at once and one after the other, either parent alone, "Za życiem"."""
    base = {"role": "mother", "work": "employment", "children_count": 1}
    worked = {"weeks": 32, "work_fraction": "1/2", "work_weeks": 20}
    plans: list[list[dict[str, Any]]] = [
        [{"parent": "mother"} | worked],
        [{"parent": "father", "weeks": 9, "work_fraction": "1/2"}],
        [
            {"parent": "mother", "weeks": 20, "work_fraction": "1/4"},
            {"parent": "father", "weeks": 9, "with_previous": True},
            {"parent": "mother", "weeks": 12, "start": "2028-06-01"},
        ],
        [{"parent": "father", "weeks": 20}],
        # F9: weeks of the pool the plan leaves out (some of them the father's alone).
        [{"parent": "mother", "weeks": 20}, {"parent": "father", "weeks": 5}],
    ]
    cases = [
        base
        | {"child_born": born, "due_date": "2027-03-15", "birth_date": "2026-11-10"}
        | {"parental_parts": plan}
        | extra
        for born in (False, True)
        for plan in plans
        for extra in ({}, {"za_zyciem": True}, {"father_work": "contract"})
        # Only an employee combines parental leave with work.
        if "father_work" not in extra or plan is not plans[1]
    ]
    cases.append(
        {"role": "father", "work": "employment", "mother_work": "none", "children_count": 2}
        | {"child_born": True, "birth_date": "2026-11-10"}
        | {"parental_parts": [{"parent": "father", "weeks": 34, "work_fraction": "2/5"}]}
    )
    return cases


@pytest.mark.parametrize("answers", scenarios() + plan_scenarios())
def test_every_timeline_element_has_a_literal_source(answers: dict[str, Any]) -> None:
    timeline = build_timeline(Scenario.model_validate(answers), PARAMS, TODAY)
    for element in timeline.elements():
        assert element.sources, element.id
        quotes = [(s.doc, s.quote) for s in element.sources]
        assert len(quotes) == len(set(quotes)), element.id  # the UI lists each quote once
        for source in element.sources:
            assert is_literal(source), (element.id, source.quote)
    # Case notes: the situation note may only describe our calculation; every other note
    # states rules and must quote them.
    for note in timeline.notes:
        assert note.sources or note.id == "situation", note.id
        for source in note.sources:
            assert is_literal(source), (note.id, source.quote)
    assert len({note.id for note in timeline.notes}) == len(timeline.notes)
    # The benefit base, step by step (engine/base.py): every step quotes its rules.
    for base in timeline.bases:
        for step in base.steps:
            assert step.sources, (base.parent, step.text)
            for source in step.sources:
                assert is_literal(source), (base.parent, source.quote)
    # F10 (leftover.py): a point of no return quotes what its marker already quotes.
    for marker in timeline.markers:
        if marker.irreversible is not None:
            assert marker.irreversible.sources, marker.id
            assert all(s in marker.sources for s in marker.irreversible.sources), marker.id
    # F9: everything left on the table quotes its rules.
    for item in timeline.left_on_table:
        assert item.sources, item.id
        for source in item.sources:
            assert is_literal(source), (item.id, source.quote)
    # The request forms (engine/forms.py): every field and attachment quotes the words that
    # name it; personal data is never filled in.
    for document in timeline.documents:
        form = document.form
        if form is None:
            continue
        assert form.legal_basis, document.id
        for source in form.legal_basis:
            assert is_literal(source), (document.id, source.quote)
        for part in (*form.fields, *form.attachments, *form.notes):
            for source in part.sources:
                assert is_literal(source), (document.id, source.quote)
        for field in form.fields:
            assert field.sources, (document.id, field.id)
            assert not (field.personal and field.value), (document.id, field.id)


def test_the_model_always_has_the_source_text() -> None:
    for section in SECTIONS.values():
        assert section.text in STATIC_INSTRUCTIONS
    for text in kp_articles().values():
        assert text in STATIC_INSTRUCTIONS
    for text in ustawa_articles().values():
        assert text in STATIC_INSTRUCTIONS
    for text in zalacznik_sections().values():
        assert text in STATIC_INSTRUCTIONS


def test_the_sick_benefit_rules_stay_with_the_sick_benefit() -> None:
    """The sick-benefit chapter (pages 2-4) is in scope now, so the model sees its 30 and 90
    days; it is told they are a sick-benefit rule and never reach the maternity benefit."""
    assert SECTIONS["ZC"].contains("prawo do zasiłku co do zasady powstaje po 30 dniach")
    assert (SECTIONS["ZC"].page, SECTIONS["ZC"].last_page) == (2, 4)
    rule = next(line for line in STATIC_INSTRUCTIONS.splitlines() if "30 albo 90 dni" in line)
    assert rule.startswith("- Zasady zasiłku chorobowego ze s. 2–4")
    assert rule.endswith("Nigdy nie stosuj ich do zasiłku macierzyńskiego.")
