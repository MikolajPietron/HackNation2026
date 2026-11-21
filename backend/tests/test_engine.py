"""Phase 1 rules: preparing for the birth (guide section A.1, page 5).

Expected dates were computed by hand: 6 weeks before 15.03.2027 is 01.02.2027.
"""

import datetime as dt

import pytest

from app.engine import Scenario, ScenarioError, Timeline, build_timeline, changed_element_ids
from app.services.params import load_params

PARAMS = load_params()
TODAY = dt.date(2026, 11, 21)
DUE = dt.date(2027, 3, 15)


def build(**answers: object) -> Timeline:
    return build_timeline(Scenario.model_validate({"due_date": DUE, **answers}), PARAMS, TODAY)


def ids(timeline: Timeline) -> list[str]:
    return [e.id for e in timeline.elements()]


def test_undecided_shows_the_six_week_window() -> None:
    t = build()
    assert ids(t) == ["prenatal-window", "due-date"]
    window = t.segments[0]
    assert (window.tone, window.start, window.end, window.days) == (
        "option",
        dt.date(2027, 2, 1),
        dt.date(2027, 3, 14),
        42,
    )
    assert t.markers[0].date == DUE


def test_leave_before_birth_starts_that_many_weeks_before_the_due_date() -> None:
    t = build(leave_before_birth_weeks=2)
    assert ids(t) == ["maternity-prenatal", "earliest-start", "due-date", "medical-certificate"]
    leave = t.segments[0]
    assert (leave.tone, leave.start, leave.end, leave.days) == (
        "leave",
        dt.date(2027, 3, 1),
        dt.date(2027, 3, 14),
        14,
    )
    assert t.element("earliest-start").date == dt.date(2027, 2, 1)  # type: ignore[union-attr]


def test_full_six_weeks_needs_no_earliest_start_marker() -> None:
    t = build(leave_before_birth_weeks=6)
    assert t.segments[0].start == dt.date(2027, 2, 1)
    assert "earliest-start" not in ids(t)


def test_more_than_six_weeks_is_rejected() -> None:
    with pytest.raises(ScenarioError, match="maksymalnie 6 tyg"):
        build(leave_before_birth_weeks=7)


def test_leave_before_birth_needs_a_medical_certificate() -> None:
    needed = build(leave_before_birth_weeks=4).documents[0]
    assert (needed.id, needed.needed_by, needed.done) == (
        "medical-certificate",
        dt.date(2027, 2, 15),
        False,
    )
    assert needed.segment_id == "maternity-prenatal"
    assert build(leave_before_birth_weeks=4, has_medical_certificate=True).documents[0].done


def test_working_until_birth_needs_no_certificate() -> None:
    t = build(leave_before_birth_weeks=0)
    assert ids(t) == ["work-until-birth", "due-date"]
    assert t.segments[0].tone == "work"
    assert t.segments[0].end == dt.date(2027, 3, 14)
    assert "Po urodzeniu dziecka zaczyna się zasiłek" in t.markers[0].summary


def test_due_date_in_the_past_is_flagged() -> None:
    t = build_timeline(Scenario(due_date=dt.date(2026, 11, 1)), PARAMS, TODAY)
    assert any("już minęła" in w for w in t.warnings)
    assert not build().warnings


def test_changed_elements_after_a_decision() -> None:
    undecided, two_weeks = build(), build(leave_before_birth_weeks=2)
    changed = set(changed_element_ids(undecided, two_weeks))
    assert {"maternity-prenatal", "earliest-start", "medical-certificate"} <= changed
    assert "due-date" not in changed
    with_certificate = build(leave_before_birth_weeks=2, has_medical_certificate=True)
    assert changed_element_ids(two_weeks, with_certificate) == ["medical-certificate"]
    assert changed_element_ids(None, undecided) == []


def test_missing_due_date() -> None:
    with pytest.raises(ScenarioError):
        build_timeline(Scenario(), PARAMS, TODAY)
