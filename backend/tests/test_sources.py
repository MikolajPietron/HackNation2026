"""What the timeline shows must come from the guide, word for word."""

import datetime as dt

from app.assistant.guide import guide_sections
from app.assistant.prompts import STATIC_INSTRUCTIONS
from app.engine import Scenario, build_timeline
from app.services.params import load_params

PARAMS = load_params()
SECTIONS = guide_sections()


def test_section_a1_is_the_documents_own_text() -> None:
    section = SECTIONS["A.1"]
    assert section.page == 5
    assert section.text.startswith(
        "Kobieta może rozpocząć urlop macierzyński maksymalnie 6 tygodni"
    )
    assert section.text.endswith("rozpocząć zasiłek po urodzeniu dziecka.")


def test_every_quote_in_params_is_literal() -> None:
    for source in PARAMS.sources():
        section = SECTIONS[source.section]
        assert source.page == section.page, source.quote
        assert section.contains(source.quote), source.quote


def test_every_timeline_element_has_a_literal_source() -> None:
    today, due = dt.date(2026, 11, 21), dt.date(2027, 3, 15)
    for weeks in (None, 0, 3, 6):
        scenario = Scenario(due_date=due, leave_before_birth_weeks=weeks)
        for element in build_timeline(scenario, PARAMS, today).elements():
            assert element.sources, element.id
            for source in element.sources:
                assert SECTIONS[source.section].contains(source.quote), element.id


def test_the_model_always_has_the_section_text() -> None:
    assert SECTIONS["A.1"].text in STATIC_INSTRUCTIONS
