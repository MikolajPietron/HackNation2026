"""Rules of phases 1 and 2a. Expected dates were computed by hand from the rules:
6 weeks before 15.03.2027 is 01.02.2027; 20 weeks from 15.03.2027 end on 01.08.2027;
the 14th week after 15.03.2027 ends on 20.06.2027.
"""

import datetime as dt

import pytest

from app.engine import Scenario, ScenarioError, Timeline, build_timeline, changed_element_ids
from app.services.params import load_params

PARAMS = load_params()
TODAY = dt.date(2026, 11, 21)
DUE = dt.date(2027, 3, 15)
BORN = dt.date(2026, 11, 10)


def expecting(**answers: object) -> Timeline:
    scenario = Scenario.model_validate({"child_born": False, "due_date": DUE, **answers})
    return build_timeline(scenario, PARAMS, TODAY)


def born(**answers: object) -> Timeline:
    scenario = Scenario.model_validate({"child_born": True, "birth_date": BORN, **answers})
    return build_timeline(scenario, PARAMS, TODAY)


def ids(timeline: Timeline) -> list[str]:
    return [e.id for e in timeline.elements()]


def span(timeline: Timeline, segment_id: str) -> tuple[dt.date, dt.date, int]:
    s = next(s for s in timeline.segments if s.id == segment_id)
    return s.start, s.end, s.days


# Phase 1: preparing for the birth.


def test_undecided_shows_the_six_week_window() -> None:
    t = expecting()
    assert ids(t) == ["prenatal-window", "due-date"]
    assert t.segments[0].tone == "option"
    assert span(t, "prenatal-window") == (dt.date(2027, 2, 1), dt.date(2027, 3, 14), 42)


def test_leave_before_birth_starts_that_many_weeks_before_the_due_date() -> None:
    t = expecting(leave_before_birth_weeks=2)
    assert ids(t) == ["maternity-prenatal", "earliest-start", "due-date", "medical-certificate"]
    assert span(t, "maternity-prenatal") == (dt.date(2027, 3, 1), dt.date(2027, 3, 14), 14)
    assert t.element("earliest-start").date == dt.date(2027, 2, 1)  # type: ignore[union-attr]


def test_full_six_weeks_needs_no_earliest_start_marker() -> None:
    t = expecting(leave_before_birth_weeks=6)
    assert span(t, "maternity-prenatal")[0] == dt.date(2027, 2, 1)
    assert "earliest-start" not in ids(t)


def test_more_than_six_weeks_is_rejected() -> None:
    with pytest.raises(ScenarioError, match="maksymalnie 6 tyg"):
        expecting(leave_before_birth_weeks=7)


def test_leave_before_birth_needs_a_medical_certificate() -> None:
    needed = expecting(leave_before_birth_weeks=4).documents[0]
    assert (needed.id, needed.needed_by, needed.done, needed.segment_id) == (
        "medical-certificate",
        dt.date(2027, 2, 15),
        False,
        "maternity-prenatal",
    )
    assert expecting(leave_before_birth_weeks=4, has_medical_certificate=True).documents[0].done


def test_working_until_birth_needs_no_certificate() -> None:
    t = expecting(leave_before_birth_weeks=0)
    assert ids(t) == ["work-until-birth", "due-date"]
    assert t.segments[0].tone == "work"
    assert "Po urodzeniu dziecka zaczyna się zasiłek" in t.markers[0].summary


# Phase 2a: length of maternity leave and the 14 weeks after the birth.


def test_one_child_twenty_weeks_from_the_due_date() -> None:
    t = expecting(children_count=1, leave_before_birth_weeks=0)
    assert span(t, "maternity") == (DUE, dt.date(2027, 8, 1), 140)
    assert t.element("personal-weeks").date == dt.date(2027, 6, 20)  # type: ignore[union-attr]


@pytest.mark.parametrize(
    ("children", "weeks"), [(1, 20), (2, 31), (3, 33), (4, 35), (5, 37), (7, 37)]
)
def test_maternity_weeks_by_children(children: int, weeks: int) -> None:
    t = expecting(children_count=children, leave_before_birth_weeks=0)
    assert span(t, "maternity")[2] == weeks * 7


def test_twins_end_later() -> None:
    assert span(expecting(children_count=2), "maternity") == (DUE, dt.date(2027, 10, 17), 217)


def test_weeks_before_the_birth_count_towards_the_total() -> None:
    t = expecting(children_count=1, leave_before_birth_weeks=2)
    before, after = span(t, "maternity-prenatal"), span(t, "maternity")
    assert after == (DUE, dt.date(2027, 7, 18), 126)
    assert before[2] + after[2] == 20 * 7


def test_undecided_leave_counts_from_the_birth_and_says_it_may_end_earlier() -> None:
    maternity = next(s for s in expecting(children_count=1).segments if s.id == "maternity")
    assert (maternity.start, maternity.end) == (DUE, dt.date(2027, 8, 1))
    assert any("skończy się odpowiednio wcześniej" in d for d in maternity.details)
    assert {s.article for s in maternity.sources if s.doc == "kp"} == {
        "art. 180 § 1",
        "art. 183¹ § 1",
        "art. 180 § 3",
    }


def test_without_children_count_the_maternity_leave_waits() -> None:
    t = expecting(leave_before_birth_weeks=0)
    assert "maternity" not in ids(t)
    assert any("ile dzieci" in a for a in t.assumptions)


# A child who is already born.


def test_born_child_counts_from_the_actual_birth() -> None:
    t = born(children_count=1)
    assert ids(t) == ["maternity", "birth", "personal-weeks"]
    assert span(t, "maternity") == (BORN, dt.date(2027, 3, 29), 140)
    assert t.element("personal-weeks").date == dt.date(2027, 2, 15)  # type: ignore[union-attr]
    assert not t.documents
    assert t.child_born and t.birth_date == BORN


def test_born_child_with_leave_taken_before_the_birth() -> None:
    t = born(children_count=1, leave_before_birth_weeks=2)
    assert span(t, "maternity-prenatal") == (dt.date(2026, 10, 27), dt.date(2026, 11, 9), 14)
    assert span(t, "maternity") == (BORN, dt.date(2027, 3, 15), 126)


def test_finished_leave_is_flagged() -> None:
    t = build_timeline(
        Scenario(child_born=True, birth_date=dt.date(2025, 1, 10), children_count=1),
        PARAMS,
        TODAY,
    )
    assert any("skończył się" in w for w in t.warnings)


def test_due_date_in_the_past_is_flagged() -> None:
    t = build_timeline(Scenario(due_date=dt.date(2026, 11, 1)), PARAMS, TODAY)
    assert any("już minęła" in w for w in t.warnings)
    assert not expecting().warnings


def test_changed_elements_after_twins() -> None:
    one, two = expecting(children_count=1), expecting(children_count=2)
    assert changed_element_ids(one, two) == ["maternity"]
    assert changed_element_ids(expecting(), one) == ["maternity", "personal-weeks"]
    assert changed_element_ids(None, one) == []


def test_missing_date() -> None:
    with pytest.raises(ScenarioError):
        build_timeline(Scenario(children_count=1), PARAMS, TODAY)


# The case explanation (Timeline.notes).


def notes(timeline: Timeline) -> dict[str, str]:
    return {n.id: f"{n.title} | {n.text}" for n in timeline.notes}


def test_explains_the_choice_before_an_expected_birth() -> None:
    explained = notes(expecting(children_count=1))
    assert list(explained) == ["situation", "before-birth", "computed"]
    assert "Dziecko jest w drodze" in explained["situation"]
    assert "nawet 6 tygodni przed porodem" in explained["before-birth"]
    assert "Najwcześniej 1 lutego 2027" in explained["before-birth"]
    assert "po porodzie do 1 sierpnia 2027" in explained["computed"]
    assert "do 20 czerwca 2027" in explained["computed"]


def test_explains_the_chosen_leave_and_the_certificate() -> None:
    explained = notes(expecting(children_count=1, leave_before_birth_weeks=2))
    assert "Urlop od 1 marca 2027, 2 tyg. przed porodem" in explained["before-birth"]
    assert "po porodzie zostaje 18 tyg." in explained["before-birth"]
    assert "Do 1 marca 2027 potrzebne jest zaświadczenie" in explained["before-birth"]
    with_certificate = expecting(
        children_count=1, leave_before_birth_weeks=2, has_medical_certificate=True
    )
    assert "już jest" in notes(with_certificate)["before-birth"]
    assert "Praca do dnia porodu" in notes(expecting(leave_before_birth_weeks=0))["before-birth"]


def test_born_today_is_simpler() -> None:
    today = build_timeline(
        Scenario(child_born=True, birth_date=TODAY, children_count=1), PARAMS, TODAY
    )
    explained = notes(today)
    assert list(explained) == ["situation", "computed"]
    assert explained["situation"].startswith("Dziecko urodziło się dzisiaj | To upraszcza sprawę")
    assert "zaczyna się dziś, w dniu porodu" in explained["situation"]
    assert "po porodzie do 9 kwietnia 2027" in explained["computed"]


def test_twins_get_a_relief_note() -> None:
    explained = notes(expecting(children_count=2))
    assert explained["more-children"] == (
        "Bliźnięta: dłuższy urlop | Przy urodzeniu dwojga dzieci urlop macierzyński trwa "
        "31 tyg. zamiast 20."
    )
    assert "more-children" not in notes(expecting(children_count=1))


def test_finished_leave_and_unknown_children_are_explained() -> None:
    assert (
        "już się skończył"
        in notes(
            build_timeline(
                Scenario(child_born=True, birth_date=dt.date(2025, 2, 1), children_count=1),
                PARAMS,
                TODAY,
            )
        )["computed"]
    )
    assert notes(expecting())["computed"].startswith("Co jeszcze policzymy")
