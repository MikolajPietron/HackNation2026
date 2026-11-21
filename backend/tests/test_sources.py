"""What the timeline shows must come from the documents, word for word."""

import datetime as dt

import pytest

from app.assistant.guide import guide_sections
from app.assistant.law import kp_articles, kp_contains
from app.assistant.prompts import STATIC_INSTRUCTIONS
from app.engine import Scenario, build_timeline
from app.engine.models import SourceRef
from app.services.params import load_params

PARAMS = load_params()
SECTIONS = guide_sections()


def is_literal(source: SourceRef) -> bool:
    if source.doc == "kp":
        return source.article is not None and kp_contains(source.article, source.quote)
    assert source.section is not None
    section = SECTIONS[source.section]
    return source.page == section.page and section.contains(source.quote)


def test_guide_sections_are_the_documents_own_text() -> None:
    a1, a2 = SECTIONS["A.1"], SECTIONS["A.2"]
    assert a1.text.startswith("Kobieta może rozpocząć urlop macierzyński maksymalnie 6 tygodni")
    assert a1.text.endswith("rozpocząć zasiłek po urodzeniu dziecka.")
    assert a2.text.startswith("Wymiar zasiłku macierzyńskiego za okres urlopu macierzyńskiego")
    assert a2.text.endswith("Pierwsze 14 tygodni po porodzie matka musi wykorzystać osobiście.")


def test_labour_code_provisions() -> None:
    assert set(kp_articles()) == {
        "art. 180 § 1",
        "art. 180 § 2",
        "art. 180 § 3",
        "art. 183¹ § 1",
        "art. 183¹ § 2",
    }
    assert "nie więcej niż 6 tygodni" in kp_articles()["art. 180 § 2"]


def test_every_quote_in_params_is_literal() -> None:
    for source in PARAMS.sources():
        assert is_literal(source), source.quote


@pytest.mark.parametrize("child_born", [False, True])
@pytest.mark.parametrize("weeks", [None, 0, 3, 6])
@pytest.mark.parametrize("children", [None, 1, 2])
def test_every_timeline_element_has_a_literal_source(
    child_born: bool, weeks: int | None, children: int | None
) -> None:
    scenario = Scenario(
        child_born=child_born,
        due_date=dt.date(2027, 3, 15),
        birth_date=dt.date(2026, 11, 10),
        children_count=children,
        leave_before_birth_weeks=weeks,
    )
    timeline = build_timeline(scenario, PARAMS, dt.date(2026, 11, 21))
    for element in timeline.elements():
        assert element.sources, element.id
        for source in element.sources:
            assert is_literal(source), (element.id, source.quote)
    # Case notes: the situation note may only describe our calculation; every other note
    # states rules and must quote them.
    for note in timeline.notes:
        assert note.sources or note.id == "situation", note.id
        for source in note.sources:
            assert is_literal(source), (note.id, source.quote)


def test_the_model_always_has_the_source_text() -> None:
    for section in SECTIONS.values():
        assert section.text in STATIC_INSTRUCTIONS
    for text in kp_articles().values():
        assert text in STATIC_INSTRUCTIONS
