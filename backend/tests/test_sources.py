"""What the timeline shows must come from the documents, word for word."""

import datetime as dt
from typing import Any

import pytest

from app.assistant.guide import guide_sections
from app.assistant.law import kp_articles, kp_contains, ustawa_articles, ustawa_contains
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
        "art. 180 § 1",
        "art. 180 § 2",
        "art. 180 § 3",
        "art. 180 § 4",
        "art. 180 § 5",
        "art. 180 § 6",
        "art. 180 § 10",
        "art. 180 § 11",
        "art. 180 § 12",
        "art. 180 § 13",
        "art. 180 § 14",
        "art. 180¹ § 1",
        "art. 180¹ § 2",
        "art. 180² § 1",
        "art. 180² § 2",
        "art. 180² § 3",
        "art. 180² § 7",
        "art. 182¹ᵃ § 1",
        "art. 182¹ᵃ § 2",
        "art. 182¹ᵃ § 3",
        "art. 182¹ᵃ § 4",
        "art. 182¹ᵃ § 6",
        "art. 182¹ᶜ",
        "art. 182¹ᵍ",
        "art. 182³ § 1",
        "art. 182³ § 1¹",
        "art. 182³ § 3",
        "art. 183¹ § 1",
        "art. 183¹ § 2",
    }
    assert "nie więcej niż 6 tygodni" in kp_articles()["art. 180 § 2"]
    assert "nie większą niż 1000 g" in kp_articles()["art. 180² § 1"]
    assert "nie później niż do zakończenia roku" in kp_articles()["art. 182¹ᶜ"]
    # Article numbers inside the text carry their superscripts again.
    assert kp_articles()["art. 182¹ᵍ"].endswith("art. 183¹ § 1.")
    assert "art. 183¹ § 1 stosuje się odpowiednio" in kp_articles()["art. 180² § 7"]


def test_ustawa_zasilkowa_provisions() -> None:
    """Guide section G rests on these; the text is the excerpt's own, footnotes and page headers
    left out."""
    assert set(ustawa_articles()) == {
        "art. 3 pkt 3",
        "art. 3 pkt 4",
        "art. 11 ust. 4",
        "art. 30a ust. 1",
        "art. 31 ust. 1",
        "art. 31 ust. 2",
        "art. 31 ust. 3",
        "art. 31 ust. 3a",
        "art. 31 ust. 3f",
        "art. 31 ust. 3g",
        "art. 31 ust. 4",
        "art. 31 ust. 5",
        "art. 36 ust. 1",
        "art. 36 ust. 3",
        "art. 47",
        "art. 48 ust. 1",
        "art. 52",
    }
    texts = ustawa_articles()
    assert texts["art. 30a ust. 1"].startswith("Ubezpieczona - matka dziecka, nie później niż 21")
    assert "art. 182¹ᵃ § 4 Kodeksu pracy" in texts["art. 31 ust. 3f"]
    assert texts["art. 3 pkt 3"].startswith("wynagrodzenie - przychód pracownika")
    assert "13,71%" in texts["art. 3 pkt 4"]
    assert texts["art. 31 ust. 5"].endswith("art. 12 ust. 1 i ust. 2 pkt 1 i 3.")
    assert all("Legalis" not in t and "ROZDZIAŁ" not in t for t in texts.values())
    assert SECTIONS["G.3"].text.startswith("Jeżeli ubezpieczona-matka, niepóźnej niż 21 dni")


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
    return cases + father_scenarios() + money_scenarios()


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
    return cases


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


@pytest.mark.parametrize("answers", scenarios())
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


def test_the_model_always_has_the_source_text() -> None:
    for section in SECTIONS.values():
        assert section.text in STATIC_INSTRUCTIONS
    for text in kp_articles().values():
        assert text in STATIC_INSTRUCTIONS
    for text in ustawa_articles().values():
        assert text in STATIC_INSTRUCTIONS


def test_the_model_does_not_see_the_sick_benefit_waiting_periods() -> None:
    """Page 3 is quoted only for the two kinds of sickness insurance: the 30 and 90 days there
    are a sick-benefit rule and must not reach an answer about the maternity benefit."""
    assert "30 dniach" not in STATIC_INSTRUCTIONS
    assert "90 dniach" not in STATIC_INSTRUCTIONS
