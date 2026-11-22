"""Contribution debt of a parent with a business (engine/debt.py; ustawa zasiłkowa art. 2a,
art. 64 ust. 3). Expected values worked out by hand: 1% of the minimum wage of 4 806 zł is
48,06 zł."""

import datetime as dt
from decimal import Decimal

from app.engine import Scenario, build_timeline
from app.engine.debt import debt_limit, expiry, over_limit
from app.services.params import load_params
from tests.test_sources import is_literal

PARAMS = load_params()
TODAY = dt.date(2026, 11, 22)


def timeline(**changes: object):
    base = {
        "role": "mother",
        "work": "business",
        "mother_insured": True,
        "child_born": True,
        "birth_date": dt.date(2026, 3, 10),
        "children_count": 1,
    }
    return build_timeline(Scenario.model_validate(base | changes), PARAMS, TODAY)


def test_the_limit_is_one_percent_of_the_minimum_wage() -> None:
    assert debt_limit(PARAMS) == Decimal("48.06")
    assert not over_limit(48.06, PARAMS), "the debt must exceed the limit"
    assert over_limit(48.07, PARAMS)


def test_the_right_expires_six_months_after_it_arose() -> None:
    assert expiry(dt.date(2026, 4, 1), PARAMS) == dt.date(2026, 10, 1)
    assert expiry(dt.date(2026, 8, 31), PARAMS) == dt.date(2027, 2, 28)


def test_debt_over_the_limit_is_a_risk_right_after_the_mothers_right() -> None:
    notes = timeline(mother_contribution_debt=512.40).notes
    ids = [note.id for note in notes]
    assert ids.index("debt-mother") == ids.index("insurance") + 1
    debt = notes[ids.index("debt-mother")]
    assert debt.kind == "risk"
    assert "512,40 zł" in debt.text
    assert "48,06 zł" in debt.text
    assert "60 dni" in debt.text and "6 miesięcy" in debt.text
    articles = {source.article for source in debt.sources}
    assert {"art. 2a ust. 1", "art. 2a ust. 2", "art. 64 ust. 3", "art. 2"} <= articles
    assert all(is_literal(source) for source in debt.sources)


def test_debt_within_the_limit_does_not_hold_the_benefit_back() -> None:
    notes = timeline(mother_contribution_debt=30).notes
    debt = next(note for note in notes if note.id == "debt-mother")
    assert debt.kind == "right"
    assert "nie wstrzymuje" in debt.text
    assert all(is_literal(source) for source in debt.sources)


def test_no_debt_point_without_a_business_or_without_debt() -> None:
    employee = timeline(work="employment", mother_insured=None, mother_contribution_debt=900)
    assert not any(note.id.startswith("debt-") for note in employee.notes)
    nothing = timeline(mother_contribution_debt=0)
    assert not any(note.id.startswith("debt-") for note in nothing.notes)


def test_the_fathers_debt_follows_his_right() -> None:
    notes = timeline(
        work="employment",
        mother_insured=None,
        father_work="business",
        father_insured=True,
        father_contribution_debt=1250,
    ).notes
    ids = [note.id for note in notes]
    assert ids.index("debt-father") == ids.index("father") + 1
    assert "Tata prowadzi działalność" in notes[ids.index("debt-father")].text
