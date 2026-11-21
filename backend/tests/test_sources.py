"""What the timeline shows must come from the documents, word for word."""

import datetime as dt
from typing import Any

import pytest

from app.assistant.guide import guide_sections
from app.assistant.law import kp_articles, kp_contains
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
        "art. 183 § 3",
        "art. 183 § 4",
        "art. 183 § 4¹",
        "art. 183 § 4²",
        "art. 183 § 4³",
        "art. 183 § 4⁴",
        "art. 183 § 4⁵",
        "art. 183 § 4⁶",
        "art. 183 § 5",
        "art. 183 § 6",
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
    )


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


def test_the_model_always_has_the_source_text() -> None:
    for section in SECTIONS.values():
        assert section.text in STATIC_INSTRUCTIONS
    for text in kp_articles().values():
        assert text in STATIC_INSTRUCTIONS


def test_the_sick_benefit_rules_stay_with_the_sick_benefit() -> None:
    """The sick-benefit chapter (pages 2-4) is in scope now, so the model sees its 30 and 90
    days; it is told they are a sick-benefit rule and never reach the maternity benefit."""
    assert SECTIONS["ZC"].contains("prawo do zasiłku co do zasady powstaje po 30 dniach")
    assert (SECTIONS["ZC"].page, SECTIONS["ZC"].last_page) == (2, 4)
    rule = next(line for line in STATIC_INSTRUCTIONS.splitlines() if "30 albo 90 dni" in line)
    assert rule.startswith("- Zasady zasiłku chorobowego ze s. 2–4")
    assert rule.endswith("Nigdy nie stosuj ich do zasiłku macierzyńskiego.")
