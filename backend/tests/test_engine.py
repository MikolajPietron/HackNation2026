"""Rules of phases 1 and 2a. Expected dates were computed by hand from the rules:
6 weeks before 15.03.2027 is 01.02.2027; 20 weeks from 15.03.2027 end on 01.08.2027;
the 14th week after 15.03.2027 ends on 20.06.2027.
"""

import datetime as dt

import pytest

from app.engine import (
    Scenario,
    ScenarioError,
    Timeline,
    build_timeline,
    changed_element_ids,
    changed_note_ids,
)
from app.engine.models import CaseNote, Marker, Segment
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
    # Section B adds the father's lane: paternity leave and his part of parental leave.
    assert ids(t) == [
        "maternity",
        "parental",
        "paternity",
        "parental-father",
        "birth",
        "personal-weeks",
        "paternity-deadline",
        "parental-deadline",
    ]
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
    # The father's 9 weeks follow the mother's parental leave; paternity leave stays as it was.
    assert changed_element_ids(one, two) == ["maternity", "parental", "parental-father"]
    assert changed_element_ids(expecting(), one) == [
        "maternity",
        "parental",
        "paternity",
        "parental-father",
        "personal-weeks",
        "paternity-deadline",
        "parental-deadline",
    ]
    assert changed_element_ids(None, one) == []


def test_missing_date() -> None:
    with pytest.raises(ScenarioError):
        build_timeline(Scenario(children_count=1), PARAMS, TODAY)


# The case explanation (Timeline.notes).


def notes(timeline: Timeline) -> dict[str, str]:
    return {n.id: f"{n.title} | {n.text}" for n in timeline.notes}


def test_explains_the_choice_before_an_expected_birth() -> None:
    explained = notes(expecting(children_count=1))
    assert list(explained) == [
        "situation",
        "insurance",
        "before-birth",
        "parental",
        "takeover",
        "father",
        "computed",
    ]
    assert "Dziecko jest w drodze" in explained["situation"]
    assert "nawet 6 tygodni przed przewidywaną datą porodu" in explained["before-birth"]
    assert "Najwcześniej 1 lutego 2027" in explained["before-birth"]
    assert "po porodzie do 1 sierpnia 2027" in explained["computed"]
    assert "do 20 czerwca 2027" in explained["computed"]


def test_explains_the_chosen_leave_and_the_certificate() -> None:
    explained = notes(expecting(children_count=1, leave_before_birth_weeks=2))
    assert (
        "Urlop od 1 marca 2027, 2 tyg. przed przewidywaną datą porodu" in explained["before-birth"]
    )
    assert "po porodzie zostaje 18 tyg." in explained["before-birth"]
    assert (
        "Żeby zacząć urlop 1 marca 2027, potrzebne jest zaświadczenie" in explained["before-birth"]
    )
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
    assert list(explained) == [
        "situation",
        "insurance",
        "parental",
        "takeover",
        "father",
        "computed",
    ]
    assert explained["situation"].startswith("Dziecko urodziło się dzisiaj | To upraszcza sprawę")
    assert "zaczyna się dziś, w dniu porodu" in explained["situation"]
    assert "po porodzie do 9 kwietnia 2027" in explained["computed"]


def test_changed_notes_name_what_an_answer_changed() -> None:
    """Twins bring parental leave onto the timeline, add a relief, the father's notes (they wait
    for the number of children) and change what we computed; the situation stays as it was."""
    before, after = expecting(), expecting(children_count=2)
    assert changed_note_ids(before, after) == [
        "parental",
        "more-children",
        "takeover",
        "father",
        "computed",
    ]
    assert changed_note_ids(after, after) == []
    assert changed_note_ids(None, after) == []


def test_twins_get_a_relief_note() -> None:
    explained = notes(expecting(children_count=2))
    assert explained["more-children"] == (
        "Bliźnięta: dłuższy urlop | Przy urodzeniu dwojga dzieci urlop macierzyński trwa "
        "31 tyg. zamiast 20, a urlop rodzicielski obojga rodziców — do 43 tyg. zamiast 41."
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


# Phase 2: the right of the insured mother to the benefit (guide A.2, pages 3, 4-5 and 10).

MOTHER_EMPLOYED = {"role": "mother", "work": "employment"}


def test_an_employed_mother_is_insured_and_gets_the_benefit() -> None:
    t = expecting(**MOTHER_EMPLOYED, children_count=1)
    insurance = t.notes[1]
    assert (insurance.id, insurance.kind) == ("insurance", "right")
    # Before the birth the right is still to come: it arises after the birth.
    assert insurance.title == "Po porodzie: prawo do zasiłku macierzyńskiego"
    assert born(**MOTHER_EMPLOYED, children_count=1).notes[1].title == (
        "Mama ma prawo do zasiłku macierzyńskiego"
    )
    assert "Umowa o pracę daje obowiązkowe ubezpieczenie chorobowe" in insurance.text
    assert {s.page for s in insurance.sources} == {3, 5, 10}
    maternity = next(s for s in t.segments if s.id == "maternity")
    assert any("ma prawo do zasiłku macierzyńskiego" in d for d in maternity.details)


@pytest.mark.parametrize("work", ["contract", "business"])
def test_contract_or_business_needs_the_voluntary_insurance(work: str) -> None:
    asked = expecting(role="mother", work=work, children_count=1)
    assert asked.notes[1].title == "Zasiłek macierzyński: potrzebne ubezpieczenie chorobowe"
    assert "ubezpieczenie chorobowe jest dobrowolne" in asked.notes[1].text
    assert "maternity" in ids(asked)  # drawn on the assumption that she is insured
    assert any("zakładamy, że mama podlega ubezpieczeniu" in a for a in asked.assumptions)

    insured = expecting(role="mother", work=work, mother_insured=True, children_count=1)
    assert insured.notes[1].kind == "right"
    assert "Nie jest pracownicą, dlatego nie dostaje urlopu" in insured.notes[1].text
    # Every period of leave says she gets the benefit, not leave (guide page 4), also before
    # her insurance is confirmed. The father's lane has its own line (section B).
    for t in (asked, insured):
        leave = [s for s in t.segments if s.tone != "work" and s.lane == "mother"]
        assert [s.id for s in leave] == ["prenatal-window", "maternity", "parental"]
        for segment in leave:
            assert any("nie dostaje urlopu" in d for d in segment.details), segment.id
            assert any(s.page == 4 for s in segment.sources), segment.id
    assert span(insured, "maternity") == span(asked, "maternity")  # the same length
    employed = expecting(**MOTHER_EMPLOYED, children_count=1)
    assert not any("nie dostaje urlopu" in d for s in employed.segments for d in s.details)


@pytest.mark.parametrize(
    "answers",
    [
        {"role": "mother", "work": "contract", "mother_insured": False},
        {"role": "mother", "work": "business", "mother_insured": False},
        {"role": "mother", "work": "none"},
        {"role": "father", "work": "employment", "mother_work": "none"},
    ],
)
def test_without_sickness_insurance_there_are_no_benefit_periods(
    answers: dict[str, object],
) -> None:
    for t in (
        expecting(**answers, children_count=1, leave_before_birth_weeks=2),
        born(**answers, children_count=1),
    ):
        # Nothing on the mother's lane. Section B: the father (insured or assumed so) keeps
        # paternity leave and has the benefit for parental leave.
        assert not [s for s in t.segments if s.lane == "mother"]
        assert [s.id for s in t.segments] == ["paternity", "parental-father"]
        assert t.markers[0].id in ("due-date", "birth")
        # An employed father has his requests, who pays and his protection (guide A.4, I).
        employed = answers.get("role") == "father"
        extra = ["protection", "payer", "applications"] if employed else []
        # F14 (no_right.py): right after "no right", what instead and what would give it.
        assert [n.id for n in t.notes] == [
            "situation",
            "insurance",
            "insurance-way",
            "father",
            "computed",
            *extra,
        ]
        assert t.notes[1].kind == "risk"
        assert t.notes[1].title == "Zasiłek macierzyński wymaga ubezpieczenia chorobowego"
        # Ustawa art. 30 ust. 1: the benefit after the insurance ended follows an employment
        # that ended in pregnancy; it does not concern voluntary insurance never taken out.
        not_working = "none" in (answers.get("work"), answers.get("mother_work"))
        after = "Po ustaniu ubezpieczenia zasiłek macierzyński przysługuje tylko w określonych"
        assert (after in t.notes[1].text) is not_working
        assert "Liczy się, czy w dniu porodu podlega ubezpieczeniu" in t.markers[0].summary
        requests = ["paternity-request", "parental-father-request"] if employed else []
        assert [d.id for d in t.documents] == requests


def test_the_fathers_own_work_says_nothing_about_the_mother() -> None:
    unknown = born(role="father", work="employment", children_count=1)
    assert unknown.notes[1].title == "Zasiłek macierzyński: potrzebne ubezpieczenie chorobowe"
    assert "Zależy to od tego, jak mama pracuje" in unknown.notes[1].text
    known = born(role="father", work="none", mother_work="employment", children_count=1)
    assert {s.page for s in unknown.notes[1].sources} == {3, 4, 5}
    assert known.notes[1].title == "Mama ma prawo do zasiłku macierzyńskiego"


def test_a_mother_not_registered_before_the_birth_hears_that_the_day_of_birth_counts() -> None:
    answers = {"role": "mother", "work": "contract", "mother_insured": False}
    assert "Liczy się dzień porodu: jeśli mama nie będzie wtedy podlegać" in (
        expecting(**answers).notes[1].text
    )
    assert "mama nie była do niego zgłoszona" in born(**answers).notes[1].text


# Phase 2: parental leave after maternity leave (guide A.2 and B; art. 182¹ᵃ, 182¹ᶜ).


def test_parental_leave_follows_maternity_leave() -> None:
    """One child: 41 weeks for both parents, 9 of them the father's alone, so 32 for her."""
    t = expecting(children_count=1)
    assert span(t, "parental") == (dt.date(2027, 8, 2), dt.date(2028, 3, 12), 32 * 7)
    parental = next(s for s in t.segments if s.id == "parental")
    assert parental.tone == "option"
    assert "razem do 41 tyg." in parental.summary
    assert "najwięcej 32 tyg." in parental.summary
    assert any("nie więcej niż 5 częściach" in d for d in parental.details)


def test_parental_leave_with_twins() -> None:
    """Twins: 43 weeks for both, 34 for her, after 31 weeks of maternity leave."""
    t = expecting(children_count=2)
    assert span(t, "parental") == (dt.date(2027, 10, 18), dt.date(2028, 6, 11), 34 * 7)


def test_leave_before_the_birth_moves_parental_leave_earlier() -> None:
    t = expecting(children_count=1, leave_before_birth_weeks=6)
    assert span(t, "maternity")[1] == dt.date(2027, 6, 20)
    assert span(t, "parental") == (dt.date(2027, 6, 21), dt.date(2028, 1, 30), 32 * 7)


@pytest.mark.parametrize(
    ("children", "weeks", "end"),
    [(1, 56, dt.date(2028, 8, 27)), (3, 58, dt.date(2028, 12, 10))],
)
def test_za_zyciem_lengthens_parental_leave(children: int, weeks: int, end: dt.date) -> None:
    """65 weeks for one child and 67 for more, minus the father's 9. Triplets: 33 weeks of
    maternity leave end on 31.10.2027, so 58 weeks of parental leave run 1.11.2027-10.12.2028."""
    t = expecting(children_count=children, za_zyciem=True)
    assert span(t, "parental")[1:] == (end, weeks * 7)
    relief = next(n for n in t.notes if n.id == "za-zyciem")
    assert f"najwięcej {weeks} tyg." in relief.text
    assert "za-zyciem" not in notes(expecting(children_count=children))


def test_parental_leave_must_end_with_the_year_the_child_turns_six() -> None:
    assert expecting(children_count=1).element("parental-deadline").date == dt.date(2033, 12, 31)  # type: ignore[union-attr]
    assert born(children_count=1).element("parental-deadline").date == dt.date(2032, 12, 31)  # type: ignore[union-attr]
    january = build_timeline(
        Scenario(child_born=False, due_date=dt.date(2027, 1, 5), children_count=1), PARAMS, TODAY
    )
    deadline = january.element("parental-deadline")
    assert deadline.date == dt.date(2033, 12, 31)  # type: ignore[union-attr]
    assert any("innym roku kalendarzowym" in d for d in deadline.details)  # type: ignore[union-attr]


def test_parental_leave_is_gone_after_the_deadline() -> None:
    late = build_timeline(
        Scenario(child_born=True, birth_date=dt.date(2020, 12, 1), children_count=1),
        PARAMS,
        dt.date(2027, 1, 10),
    )
    assert "parental" not in ids(late) and "parental-deadline" not in ids(late)
    assert any("Czas na urlop rodzicielski minął 31.12.2026" in w for w in late.warnings)


def test_parental_leave_is_explained() -> None:
    explained = notes(expecting(children_count=1))
    assert explained["parental"].startswith(
        "Po urlopie macierzyńskim: urlop rodzicielski | Rodzice mają razem do 41 tyg."
    )
    assert "najpóźniej do 31 grudnia 2033" in explained["parental"]
    assert "Z zaświadczeniem „Za życiem” urlop jest dłuższy: do 65 tyg." in explained["parental"]
    assert "32 tyg., od 2 sierpnia 2027 do 12 marca 2028" in explained["computed"]
    assert "parental" not in notes(expecting())  # waits for the number of children


# Phase 2: supplementary maternity leave (guide A.2 and C; art. 180²).

HOSPITAL_BIRTH = dt.date(2026, 10, 1)


def hospital(
    week: str,
    light: bool,
    *stays: tuple[str, str | None],
    birth: dt.date = HOSPITAL_BIRTH,
    children: int = 1,
) -> Timeline:
    scenario = Scenario.model_validate(
        {
            "child_born": True,
            "birth_date": birth,
            "children_count": children,
            "leave_before_birth_weeks": 0,
            "hospital_care": True,
            "birth_week": week,
            "birth_weight_up_to_1000g": light,
            "hospital_stays": [{"start": start, "end": end} for start, end in stays],
        }
    )
    return build_timeline(scenario, PARAMS, TODAY)


def supplementary_weeks(timeline: Timeline) -> int:
    segment = next((s for s in timeline.segments if s.id == "supplementary"), None)
    return segment.days // 7 if segment else 0


def test_very_premature_child_a_week_for_every_week_in_hospital() -> None:
    """Born 1.09, in hospital until 5.11: 66 days with the day of birth, so 10 weeks."""
    t = hospital("before-28", True, ("2026-09-01", "2026-11-05"), birth=dt.date(2026, 9, 1))
    assert span(t, "maternity")[1] == dt.date(2027, 1, 18)
    assert span(t, "supplementary") == (dt.date(2027, 1, 19), dt.date(2027, 3, 29), 70)
    assert span(t, "parental")[0] == dt.date(2027, 3, 30)  # moved by the supplementary leave
    assert next(s for s in t.segments if s.id == "supplementary").tone == "option"


def test_very_premature_child_at_most_fifteen_weeks() -> None:
    long_stay = ("2026-09-01", "2027-01-31")
    t = hospital("before-28", False, long_stay, birth=dt.date(2026, 9, 1))
    assert supplementary_weeks(t) == 15


def test_low_birth_weight_counts_like_a_very_premature_birth() -> None:
    """1000 g or less: the 15-week window whatever the week of pregnancy. 1.10-31.12 is 92 days,
    so 14 weeks; the 8-week window (1.10-25.11) caps the other case at 8."""
    stay = ("2026-10-01", "2026-12-31")
    assert supplementary_weeks(hospital("after-37", True, stay)) == 14
    assert supplementary_weeks(hospital("28-37", True, stay)) == 14
    assert supplementary_weeks(hospital("28-37", False, stay)) == 8


def test_premature_child_an_incomplete_week_is_rounded_up() -> None:
    assert supplementary_weeks(hospital("28-37", False, ("2026-10-01", "2026-10-07"))) == 1
    assert supplementary_weeks(hospital("28-37", False, ("2026-10-01", "2026-10-08"))) == 2
    # The day of birth counts, as the first day of maternity leave does.
    assert supplementary_weeks(hospital("28-37", False, ("2026-10-01", "2026-10-01"))) == 1


def test_hospital_stays_are_added_up() -> None:
    """1-5.10 is 5 days and 20-25.10 is 6: 11 days, so 2 weeks. Overlaps count once."""
    two = hospital("28-37", False, ("2026-10-01", "2026-10-05"), ("2026-10-20", "2026-10-25"))
    assert supplementary_weeks(two) == 2
    same = hospital("28-37", False, ("2026-10-01", "2026-10-07"), ("2026-10-03", "2026-10-07"))
    assert supplementary_weeks(same) == 1


def test_child_born_at_term_needs_two_days_starting_between_day_5_and_28() -> None:
    """Born 1.10: the 5th day is 5.10, the 28th is 28.10."""
    # 5-12.10 is 8 days: 2 weeks.
    assert supplementary_weeks(hospital("after-37", False, ("2026-10-01", "2026-10-12"))) == 2
    # In hospital on the 5th day only: no two consecutive days from the 5th day on.
    assert supplementary_weeks(hospital("after-37", False, ("2026-10-01", "2026-10-05"))) == 0
    # The 28th and 29th day: the first of the two is still inside the window.
    assert supplementary_weeks(hospital("after-37", False, ("2026-10-28", "2026-10-29"))) == 1
    # From the 29th day: too late.
    assert supplementary_weeks(hospital("after-37", False, ("2026-10-29", "2026-11-05"))) == 0


def test_child_born_at_term_counts_from_the_fifth_day_to_the_eighth_week() -> None:
    """Days 5-56 after the birth (5.10-25.11) are 52 days: at most 8 weeks."""
    t = hospital("after-37", False, ("2026-10-01", "2026-12-31"))
    assert supplementary_weeks(t) == 8
    details = next(s for s in t.segments if s.id == "supplementary").details
    assert any("52 dni" in d and "05.10.2026 a 25.11.2026" in d for d in details)


def test_child_still_in_hospital_is_counted_until_today() -> None:
    """Born 1.11, today 21.11: 21 days so far, 3 weeks. Staying until 26.12 would make 8."""
    t = hospital("28-37", False, ("2026-11-01", None), birth=dt.date(2026, 11, 1), children=2)
    assert supplementary_weeks(t) == 3
    details = next(s for s in t.segments if s.id == "supplementary").details
    assert any("jeszcze w szpitalu" in d and "najwyżej do 8 tyg." in d for d in details)
    assert any("najlżejszego dziecka" in d for d in details)  # twins


def test_a_stay_under_way_can_only_grow_by_what_is_left_of_the_window() -> None:
    """Born 1.10, still in hospital since 1.10: 52 days so far (8 weeks), the cap: it says
    nothing about growing. From 20.11 (day 51): 2 days so far, 6 more at most, so 1 week."""
    full = hospital("28-37", False, ("2026-10-01", None))
    assert supplementary_weeks(full) == 8
    assert not any("wzrosnąć" in d for s in full.segments for d in s.details)
    assert "wzrosnąć" not in notes(full)["supplementary"]
    late = hospital("28-37", False, ("2026-11-20", None))
    assert supplementary_weeks(late) == 1
    assert not any("wzrosnąć" in d for s in late.segments for d in s.details)


def test_supplementary_leave_is_explained_also_when_it_is_not_due() -> None:
    due = notes(hospital("28-37", False, ("2026-10-01", "2026-10-09")))
    assert due["supplementary"].startswith("Uzupełniający urlop macierzyński: 2 tyg. | ")
    assert "9 dni to 2 tyg., bo niepełny tydzień zaokrągla się w górę" in due["supplementary"]
    whole = notes(hospital("28-37", False, ("2026-10-01", "2026-10-07")))
    assert "7 dni to 1 tyg.. " not in whole["supplementary"]
    assert "7 dni to 1 tyg. Urlop" in whole["supplementary"]
    assert "Uzupełniający urlop macierzyński: 2 tyg., od" in due["computed"]

    not_due = hospital("after-37", False, ("2026-10-01", "2026-10-04"))
    note = next(n for n in not_due.notes if n.id == "supplementary")
    assert (note.kind, note.title) == (
        "risk",
        "Uzupełniający urlop macierzyński: warunki niespełnione",
    )
    assert "supplementary" not in ids(not_due)

    waiting = born(children_count=1, hospital_care=True)
    assert "potrzebne szczegóły" in notes(waiting)["supplementary"]
    # Week and weight known, no dates yet: still waiting, not "conditions not met".
    no_dates = born(
        children_count=1, hospital_care=True, birth_week="28-37", birth_weight_up_to_1000g=False
    )
    assert "potrzebne szczegóły" in notes(no_dates)["supplementary"]
    assert "supplementary" not in notes(born(children_count=1, hospital_care=False))


def test_a_stay_before_the_birth_or_in_the_future_is_rejected() -> None:
    with pytest.raises(ScenarioError, match="przed dniem urodzenia"):
        hospital("28-37", False, ("2026-09-28", "2026-10-05"))
    with pytest.raises(ScenarioError, match="w przyszłości"):
        hospital("28-37", False, ("2026-12-01", "2026-12-05"))


def test_no_supplementary_leave_before_the_child_is_born() -> None:
    t = expecting(children_count=1, hospital_care=True, birth_week="28-37")
    assert "supplementary" not in ids(t)
    parental = next(s for s in t.segments if s.id == "parental")
    assert any("może przysługiwać jeszcze uzupełniający urlop" in d for d in parental.details)


# Phase 3: stillbirth or death of the child (guide A.3, page 6; KP art. 180¹).

LOST_BIRTH = dt.date(2026, 11, 10)


def lost(*losses: dict[str, object], **answers: object) -> Timeline:
    scenario = Scenario.model_validate(
        {
            "role": "mother",
            "work": "employment",
            "child_born": True,
            "birth_date": LOST_BIRTH,
            "children_count": 1,
            "leave_before_birth_weeks": 0,
            "losses": list(losses),
            **answers,
        }
    )
    return build_timeline(scenario, PARAMS, TODAY)


STILLBORN = {"stillborn": True}


def test_stillbirth_gives_eight_weeks_after_the_birth() -> None:
    """10.11.2026 + 8 weeks = 4.01.2027. Nothing after it: no parental leave, no 14 weeks."""
    t = lost(STILLBORN)
    # The employed mother's request and the end of her protection (guide A.4, I).
    assert ids(t) == ["maternity", "birth", "protection-end", "maternity-request"]
    assert span(t, "maternity") == (LOST_BIRTH, dt.date(2027, 1, 4), 56)
    assert t.element("birth").title == "Poród"  # type: ignore[union-attr]
    assert [(n.id, n.kind) for n in t.notes] == [
        ("situation", "situation"),
        ("insurance", "right"),
        ("loss", "right"),
        ("computed", "computed"),
        ("protection", "right"),
        ("payer", "computed"),
        ("applications", "computed"),
    ]
    assert t.notes[0].title == "Dziecko urodziło się martwe"
    assert t.notes[0].text.startswith("Bardzo nam przykro.")
    assert t.notes[2].title == "Urlop macierzyński: 8 tygodni po porodzie"
    assert "nie krócej jednak niż przez 7 dni od dnia śmierci dziecka" in t.notes[2].text
    assert {s.article for s in t.notes[2].sources if s.doc == "kp"} >= {"art. 180¹ § 1"}


def test_stillbirth_after_leave_before_the_birth_still_gives_eight_weeks_after_it() -> None:
    """The 8 weeks are counted after the birth, whatever was used before it."""
    t = lost(STILLBORN, leave_before_birth_weeks=6)
    assert span(t, "maternity-prenatal") == (dt.date(2026, 9, 29), dt.date(2026, 11, 9), 42)
    assert span(t, "maternity") == (LOST_BIRTH, dt.date(2027, 1, 4), 56)
    maternity = next(s for s in t.segments if s.id == "maternity")
    assert not any("wliczają się" in d for d in maternity.details)


def test_early_death_eight_weeks_but_not_less_than_seven_days() -> None:
    """Born 20.09, died 13.11 (day 55 of life): 8 weeks end 14.11, 7 days from the death end
    20.11, the later of the two."""
    t = lost({"died_on": "2026-11-13"}, birth_date=dt.date(2026, 9, 20))
    assert span(t, "maternity") == (dt.date(2026, 9, 20), dt.date(2026, 11, 20), 62)
    assert t.notes[0].title == "Dziecko zmarło 13 listopada 2026"
    assert t.element("birth").title == "Narodziny dziecka"  # type: ignore[union-attr]


def test_eight_weeks_of_life_are_fifty_six_days() -> None:
    """Born 20.09: day 56 of life is 14.11 (still early), 15.11 is after 8 weeks."""
    birth = dt.date(2026, 9, 20)
    early = lost({"died_on": "2026-11-14"}, birth_date=birth)
    assert span(early, "maternity")[1] == dt.date(2026, 11, 21)
    assert early.notes[2].title == "Urlop macierzyński: 8 tygodni po porodzie"
    late = lost({"died_on": "2026-11-15"}, birth_date=birth)
    assert span(late, "maternity")[1] == dt.date(2026, 11, 22)
    assert late.notes[2].title == "Urlop zostaje jeszcze przez 7 dni"


def test_later_death_keeps_the_leave_for_seven_days() -> None:
    """Born 1.07, died 1.10: maternity leave ends 8.10 instead of 17.11."""
    t = lost({"died_on": "2026-10-01"}, birth_date=dt.date(2026, 7, 1))
    assert ids(t) == ["maternity", "birth"]
    assert span(t, "maternity")[1] == dt.date(2026, 10, 8)
    assert any(s.article == "art. 180¹ § 2" for s in t.notes[2].sources)


def test_death_during_parental_leave_keeps_it_for_seven_days() -> None:
    """Born 5.01.2026: maternity leave 5.01-24.05; died 1.08, parental leave ends 8.08."""
    t = lost({"died_on": "2026-08-01"}, birth_date=dt.date(2026, 1, 5))
    assert span(t, "maternity") == (dt.date(2026, 1, 5), dt.date(2026, 5, 24), 140)
    assert span(t, "parental") == (dt.date(2026, 5, 25), dt.date(2026, 8, 8), 76)
    assert "parental-deadline" not in ids(t)
    parental = next(s for s in t.segments if s.id == "parental")
    assert {"art. 182¹ᵍ", "art. 180² § 7"} <= {s.article for s in parental.sources}
    assert (
        "skończył się przed śmiercią dziecka"
        in next(s for s in t.segments if s.id == "maternity").summary
    )


def test_twins_one_stillborn_leave_follows_the_living_child() -> None:
    """20 weeks instead of 31 (10.11.2026-29.03.2027); parental leave as for twins (literal
    reading of art. 182¹ᵃ, flagged as an assumption)."""
    t = lost(STILLBORN, children_count=2)
    assert span(t, "maternity") == (LOST_BIRTH, dt.date(2027, 3, 29), 140)
    assert span(t, "parental") == (dt.date(2027, 3, 30), dt.date(2027, 11, 22), 34 * 7)
    assert "personal-weeks" in ids(t)
    assert t.notes[0].title == "Jedno z dzieci urodziło się martwe"
    assert t.notes[2].title == "Urlop macierzyński: 20 tyg., według liczby żyjących dzieci"
    assert "more-children" not in notes(t)
    assert any("Czy zmienia się po śmierci jednego z nich" in a for a in t.assumptions)


def test_twins_one_died_after_eight_weeks_not_less_than_seven_days() -> None:
    """Born 1.01.2026; one twin died 1.06, when 20 weeks (to 20.05) had passed: the leave runs
    to 8.06, seven days from the death, not to 5.08 (31 weeks)."""
    t = lost({"died_on": "2026-06-01"}, birth_date=dt.date(2026, 1, 1), children_count=2)
    assert span(t, "maternity")[1] == dt.date(2026, 6, 8)
    assert span(t, "parental")[0] == dt.date(2026, 6, 9)


def test_twins_both_stillborn() -> None:
    t = lost(STILLBORN, STILLBORN, children_count=2)
    assert span(t, "maternity")[1] == dt.date(2027, 1, 4)
    assert "parental" not in ids(t)
    assert t.notes[0].title == "Dzieci zmarły"


def test_loss_dates_are_checked() -> None:
    with pytest.raises(ScenarioError, match="więcej dzieci, które zmarły"):
        lost(STILLBORN, STILLBORN)
    with pytest.raises(ScenarioError, match="wcześniejsza niż data porodu"):
        lost({"died_on": "2026-11-01"})
    with pytest.raises(ScenarioError, match="w przyszłości"):
        lost({"died_on": "2026-12-01"})


def test_loss_of_an_uninsured_mother_says_only_that() -> None:
    t = lost(STILLBORN, work="none")
    assert [n.id for n in t.notes] == ["situation", "insurance"]
    assert ids(t) == ["birth"]


def test_a_loss_never_counts_before_the_birth() -> None:
    t = expecting(children_count=1, losses=[STILLBORN])
    assert "maternity" in ids(t) and "parental" in ids(t)


# Section B: the father (guide pages 7-8; KP art. 180 § 4-14, 182¹ᵃ § 4 and § 6, 182³).


def segment(timeline: Timeline, segment_id: str) -> Segment:
    return next(s for s in timeline.segments if s.id == segment_id)


def note(timeline: Timeline, note_id: str) -> CaseNote:
    return next(n for n in timeline.notes if n.id == note_id)


def lane(timeline: Timeline, name: str) -> list[str]:
    return [s.id for s in timeline.segments if s.lane == name]


# B.4: paternity leave.


def test_paternity_leave_from_the_due_date() -> None:
    """15.03.2027 + 13 days = 28.03.2027. The child completes 12 months on 15.03.2028, so the
    last day for the leave is 14.03.2028."""
    t = expecting(children_count=1)
    paternity = segment(t, "paternity")
    assert (paternity.lane, paternity.tone, paternity.title) == (
        "father",
        "option",
        "Urlop ojcowski — do wyboru",
    )
    assert span(t, "paternity") == (DUE, dt.date(2027, 3, 28), 14)
    deadline = t.element("paternity-deadline")
    assert isinstance(deadline, Marker)
    assert (deadline.lane, deadline.label, deadline.title, deadline.date) == (
        "child",
        "Ojcowski najpóźniej do",
        "Koniec czasu na urlop ojcowski",
        dt.date(2028, 3, 14),
    )
    assert any("w 2 częściach po co najmniej 7 dni" in d for d in paternity.details)
    assert {s.article for s in paternity.sources if s.doc == "kp"} == {
        "art. 182³ § 1",
        "art. 182³ § 1¹",
    }
    assert any("dzień przed pierwszymi urodzinami" in a for a in t.assumptions)


def test_paternity_leave_of_a_born_child_is_drawn_from_today() -> None:
    """Born 10.11.2026, today 21.11.2026: 21.11-4.12.2026; 12 months end with 9.11.2027."""
    t = born(children_count=1)
    assert span(t, "paternity") == (TODAY, dt.date(2026, 12, 4), 14)
    assert t.element("paternity-deadline").date == dt.date(2027, 11, 9)  # type: ignore[union-attr]
    assert "pokazujemy go od dziś" in segment(t, "paternity").summary


def test_twins_do_not_lengthen_paternity_leave() -> None:
    t = expecting(children_count=2)
    assert span(t, "paternity")[2] == 14
    assert any("nie wydłuża" in d for d in segment(t, "paternity").details)


def test_paternity_leave_ends_with_the_deadline() -> None:
    """Born 30.11.2025: the last day is 29.11.2026, so from 21.11 only 9 days are left."""
    t = born(birth_date=dt.date(2025, 11, 30), children_count=1)
    assert span(t, "paternity") == (TODAY, dt.date(2026, 11, 29), 9)
    assert "pokazujemy 9 dni" in segment(t, "paternity").summary


def test_paternity_leave_needs_at_least_seven_days() -> None:
    """Born 26.11.2025: the last day is 25.11.2026, 5 days from today, and no part may be
    shorter than a week. The deadline stays on the timeline."""
    t = born(birth_date=dt.date(2025, 11, 26), children_count=1)
    assert "paternity" not in ids(t)
    assert t.element("paternity-deadline").date == dt.date(2026, 11, 25)  # type: ignore[union-attr]
    assert any("zostało 5 dni" in w for w in t.warnings)
    assert "zostało mniej niż 7 dni" in note(t, "father").text


def test_paternity_leave_expires_after_twelve_months() -> None:
    """Born 20.11.2025: the last day was 19.11.2026, before today."""
    t = born(birth_date=dt.date(2025, 11, 20), children_count=1)
    assert "paternity" not in ids(t) and "paternity-deadline" not in ids(t)
    assert any("Czas na urlop ojcowski minął 19.11.2026" in w for w in t.warnings)
    assert "Czas na urlop ojcowski minął" in note(t, "father").text


def test_paternity_deadline_for_a_child_born_on_29_february() -> None:
    """Due 29.02.2028: 2029 has no 29 February, so 12 months end on 1.03.2029 and the last day
    is 28.02.2029."""
    t = build_timeline(
        Scenario(child_born=False, due_date=dt.date(2028, 2, 29), children_count=1), PARAMS, TODAY
    )
    assert t.element("paternity-deadline").date == dt.date(2029, 2, 28)  # type: ignore[union-attr]


def test_the_father_waits_for_the_number_of_children_and_a_living_child() -> None:
    assert lane(expecting(), "father") == []
    assert "father" not in notes(expecting())
    stillborn = lost(STILLBORN)
    assert lane(stillborn, "father") == []
    assert "paternity-deadline" not in ids(stillborn)
    assert not {"father", "takeover"} & set(notes(stillborn))


@pytest.mark.parametrize(
    ("answers", "phrase"),
    [
        ({"role": "father", "work": "none"}, "który zaczął pracę po narodzinach dziecka"),
        (
            {"role": "mother", "work": "employment", "father_work": "contract"}
            | {"father_insured": False},
            "Przy umowie zlecenia ubezpieczenie chorobowe jest dobrowolne, a tata nie jest",
        ),
    ],
)
def test_a_father_without_sickness_insurance_has_no_benefit_periods(
    answers: dict[str, object], phrase: str
) -> None:
    t = born(**answers, children_count=1)
    assert lane(t, "father") == []
    assert "paternity-deadline" not in ids(t)
    father = note(t, "father")
    assert (father.kind, father.title) == ("risk", "Tata: zasiłek wymaga ubezpieczenia chorobowego")
    assert phrase in father.text
    assert any(s.page == 10 for s in father.sources)  # no insurance, no benefit
    assert "parental" in ids(t)  # the mother's parental leave is still hers
    assert "a tata swoje" not in " ".join(t.assumptions)


@pytest.mark.parametrize("work", ["contract", "business"])
def test_a_father_who_is_not_an_employee_gets_the_benefit_not_leave(work: str) -> None:
    t = born(role="father", work=work, father_insured=True, children_count=1)
    father_lane = [s for s in t.segments if s.lane == "father"]
    assert [s.id for s in father_lane] == ["paternity", "parental-father"]
    for s in father_lane:
        assert any("Tata nie jest pracownikiem" in d for d in s.details), s.id
        assert any(src.page == 4 for src in s.sources), s.id
    assert "Tata nie jest pracownikiem" in note(t, "father").text
    # The mother's lane gets no such line: nobody said how she works.
    assert not any(
        "nie dostaje urlopu" in d for s in t.segments if s.lane == "mother" for d in s.details
    )


def test_a_father_whose_work_is_unknown_is_assumed_insured() -> None:
    t = born(children_count=1)
    assert any(
        "Na razie zakładamy, że tata mu podlega" in d for d in segment(t, "paternity").details
    )
    assert "Na razie oś zakłada, że tata mu podlega" in note(t, "father").text
    assert any("zakładamy, że tata podlega ubezpieczeniu" in a for a in t.assumptions)
    employed = born(role="father", work="employment", children_count=1)
    assert not any("zakładamy, że tata" in a for a in employed.assumptions)
    assert not any("zakładamy" in d for d in segment(employed, "paternity").details)


# B.3: the father's parental leave.


def test_the_fathers_nine_weeks_follow_the_mothers_parental_leave() -> None:
    """Her 32 weeks end on 12.03.2028; his 9 weeks run 13.03.2028 + 62 days = 14.05.2028."""
    t = expecting(children_count=1)
    parental = segment(t, "parental-father")
    assert (parental.lane, parental.tone, parental.title) == (
        "father",
        "option",
        "Urlop rodzicielski taty — do wyboru",
    )
    assert span(t, "parental-father") == (dt.date(2028, 3, 13), dt.date(2028, 5, 14), 63)
    assert "9 tyg. urlopu rodzicielskiego wyłącznie dla siebie" in parental.summary
    assert "jednocześnie albo naprzemiennie" in parental.summary
    assert {"art. 182¹ᵃ § 4", "art. 182¹ᵃ § 6"} <= {s.article for s in parental.sources}
    assert any("a tata swoje 9 tygodni zaraz po niej" in a for a in t.assumptions)


def test_the_fathers_nine_weeks_with_twins() -> None:
    """Twins: her 34 weeks end on 11.06.2028; his 9 weeks: 12.06.2028 + 62 days = 13.08.2028."""
    assert span(expecting(children_count=2), "parental-father") == (
        dt.date(2028, 6, 12),
        dt.date(2028, 8, 13),
        63,
    )


def test_an_uninsured_mother_leaves_parental_leave_to_the_father() -> None:
    """Born 10.11.2026, the mother does not work: paternity 21.11-4.12.2026, then 41 - 9 = 32
    weeks of parental leave: 5.12.2026 + 223 days = 16.07.2027."""
    t = born(role="father", work="employment", mother_work="none", children_count=1)
    assert lane(t, "mother") == []
    assert lane(t, "father") == ["paternity", "parental-father"]
    assert span(t, "parental-father") == (dt.date(2026, 12, 5), dt.date(2027, 7, 16), 224)
    parental = segment(t, "parental-father")
    assert parental.summary.startswith("Mama nie była ubezpieczona w dniu porodu")
    assert any(s.section == "B.3" and "nie była ubezpieczona" in s.quote for s in parental.sources)
    assert t.element("parental-deadline").date == dt.date(2032, 12, 31)  # type: ignore[union-attr]
    assert any("Czy w tej sytuacji tata może wykorzystać także je" in a for a in t.assumptions)
    father = note(t, "father")
    assert "także wtedy, gdy mama nie podlega ubezpieczeniu chorobowemu" in father.text
    assert note(t, "computed").text.startswith("Urlop ojcowski: 14 dni, od 21 listopada 2026")


def test_an_uninsured_mother_before_the_birth() -> None:
    """Paternity 15-28.03.2027, then 32 weeks: 29.03.2027 + 223 days = 7.11.2027."""
    t = expecting(role="mother", work="none", children_count=1)
    assert span(t, "parental-father") == (dt.date(2027, 3, 29), dt.date(2027, 11, 7), 224)
    assert segment(t, "parental-father").summary.startswith("Jeśli mama nie będzie ubezpieczona")


def test_the_fathers_parental_leave_ends_with_the_year_the_child_turns_six() -> None:
    """Born 1.06.2020, uninsured mother: no paternity leave any more, parental leave from today
    to 31.12.2026: 41 days instead of 32 weeks."""
    t = born(
        birth_date=dt.date(2020, 6, 1),
        children_count=1,
        role="father",
        work="employment",
        mother_work="none",
    )
    assert span(t, "parental-father") == (TODAY, dt.date(2026, 12, 31), 41)
    parental = segment(t, "parental-father")
    assert "Pokazujemy 41 dni" in parental.summary
    assert any("dlatego pokazujemy go krócej" in d for d in parental.details)


def test_the_fathers_parental_leave_after_the_deadline() -> None:
    t = born(
        birth_date=dt.date(2019, 6, 1),
        children_count=1,
        role="father",
        work="employment",
        mother_work="none",
    )
    assert lane(t, "father") == []
    assert "parental-deadline" not in ids(t)
    assert any("Czas na urlop rodzicielski minął 31.12.2025" in w for w in t.warnings)


# B.1: taking over maternity leave after 14 weeks.

EMPLOYED = {"role": "mother", "work": "employment", "father_work": "employment"}


def test_the_father_takes_over_after_fourteen_weeks() -> None:
    """Born 10.11.2026: 14 weeks end on 10.11.2026 + 97 days = 15.02.2027; the father has the
    rest of the 20 weeks, 16.02-29.03.2027 (42 days). Nothing else moves."""
    before = born(**EMPLOYED, children_count=1)
    t = born(**EMPLOYED, children_count=1, father_takes_over=True)
    assert span(t, "maternity") == (BORN, dt.date(2027, 2, 15), 98)
    father = segment(t, "maternity-father")
    assert (father.lane, father.tone, father.title) == (
        "father",
        "leave",
        "Urlop macierzyński taty",
    )
    assert span(t, "maternity-father") == (dt.date(2027, 2, 16), dt.date(2027, 3, 29), 42)
    assert span(t, "parental") == span(before, "parental")
    assert t.element("personal-weeks").date == dt.date(2027, 2, 15)  # type: ignore[union-attr]
    # Also: the mother's protection now ends with her part, and two requests (guide A.4, I).
    assert changed_element_ids(before, t) == [
        "maternity",
        "maternity-father",
        "protection-end",
        "maternity-resignation",
        "maternity-father-request",
    ]
    assert {"art. 180 § 4", "art. 180 § 5", "art. 180 § 14"} <= {s.article for s in father.sources}
    mother = segment(t, "maternity")
    assert "Dalszą część, od 16.02.2027 do 29.03.2027, przejmuje tata" in mother.summary
    taken = note(t, "takeover")
    assert (taken.kind, taken.title) == (
        "choice",
        "Tata przejmuje urlop macierzyński od 16 lutego 2027",
    )
    assert "Mama korzysta z urlopu macierzyńskiego do 15 lutego 2027, tata od 16 lutego 2027" in (
        note(t, "computed").text
    )
    assert "po porodzie do 29 marca 2027" in note(t, "computed").text


def test_the_mother_may_use_more_than_fourteen_weeks_first() -> None:
    """16 weeks from 15.03.2027 end on 4.07.2027; the father has 5.07-1.08.2027 (28 days)."""
    t = expecting(
        children_count=1,
        leave_before_birth_weeks=0,
        father_takes_over=True,
        mother_weeks_before_takeover=16,
    )
    assert span(t, "maternity")[1] == dt.date(2027, 7, 4)
    assert span(t, "maternity-father") == (dt.date(2027, 7, 5), dt.date(2027, 8, 1), 28)


def test_twins_leave_the_father_seventeen_weeks() -> None:
    """31 weeks from 15.03.2027 end on 17.10.2027; after 14 weeks (to 20.06.2027) the father
    has 21.06-17.10.2027, 119 days."""
    t = expecting(children_count=2, father_takes_over=True)
    assert span(t, "maternity-father") == (dt.date(2027, 6, 21), dt.date(2027, 10, 17), 119)


def test_taking_over_is_checked() -> None:
    with pytest.raises(ScenarioError, match="co najmniej 14 tygodni urlopu macierzyńskiego"):
        born(**EMPLOYED, children_count=1, father_takes_over=True, mother_weeks_before_takeover=13)
    with pytest.raises(ScenarioError, match="nie zostaje nic, co tata mógłby przejąć"):
        born(**EMPLOYED, children_count=1, father_takes_over=True, mother_weeks_before_takeover=20)
    # 6 weeks before the birth leave exactly 14 after it.
    with pytest.raises(ScenarioError, match="nie zostaje nic"):
        expecting(children_count=1, leave_before_birth_weeks=6, father_takes_over=True)


def test_the_takeover_is_offered_when_something_is_left_after_fourteen_weeks() -> None:
    offered = note(expecting(children_count=1), "takeover")
    assert (offered.kind, offered.title) == (
        "choice",
        "Tata może przejąć część urlopu macierzyńskiego",
    )
    assert "najwcześniej od 21 czerwca 2027" in offered.text
    assert "bezpośrednio po zakończeniu urlopu mamy" in offered.text
    assert "takeover" not in notes(expecting(children_count=1, leave_before_birth_weeks=6))


def test_an_uninsured_father_does_not_take_over() -> None:
    answers = {"role": "mother", "work": "employment", "father_work": "none", "children_count": 1}
    assert "takeover" not in notes(born(**answers))  # not offered
    asked = born(**answers, father_takes_over=True)
    assert "maternity-father" not in ids(asked)
    assert span(asked, "maternity")[1] == dt.date(2027, 3, 29)
    refused = note(asked, "takeover")
    assert refused.title == "Tata nie przejmie urlopu macierzyńskiego"
    assert "oś pokazuje cały urlop u mamy" in refused.text


def test_no_takeover_when_the_mother_is_not_insured() -> None:
    t = born(role="mother", work="none", children_count=1, father_takes_over=True)
    assert "maternity-father" not in ids(t)
    assert "takeover" not in notes(t)


# B.2: special situations. Born 1.10.2026: 20 weeks end on 1.10.2026 + 139 days = 17.02.2027;
# 8 weeks end on 25.11.2026, so the father can take over from 26.11.2026; 14 weeks end on
# 6.01.2027.

EVENT_BIRTH = dt.date(2026, 10, 1)
WHOLE = dt.date(2027, 2, 17)


def event(kind: str, start: str, end: str | None = None, **answers: object) -> Timeline:
    return build_timeline(
        Scenario.model_validate(
            {
                **EMPLOYED,
                "child_born": True,
                "birth_date": EVENT_BIRTH,
                "children_count": 1,
                "leave_before_birth_weeks": 0,
                "mother_event": {"kind": kind, "start": start, "end": end},
                **answers,
            }
        ),
        PARAMS,
        TODAY,
    )


def test_incapacity_the_father_takes_the_rest_after_eight_weeks() -> None:
    """From 1.12.2026: the mother 1.10-30.11.2026 (61 days), the father 1.12.2026-17.02.2027
    (79 days). Before the end of the 14 weeks, so their marker goes."""
    t = event("incapacity", "2026-12-01")
    assert span(t, "maternity") == (EVENT_BIRTH, dt.date(2026, 11, 30), 61)
    assert span(t, "maternity-father") == (dt.date(2026, 12, 1), WHOLE, 79)
    assert "personal-weeks" not in ids(t)
    assert span(t, "parental")[0] == dt.date(2027, 2, 18)  # does not move
    told = note(t, "mother-event")
    assert (told.kind, told.title) == (
        "right",
        "Tata przejmuje urlop macierzyński od 1 grudnia 2026",
    )
    assert "art. 180 § 6" in told.text
    assert any(s.article == "art. 180 § 6" for s in told.sources)
    assert any(s.section == "B.2" for s in told.sources)
    assert [n.id for n in t.notes] == [
        "situation",
        "insurance",
        "parental",
        "mother-event",
        "father",
        "computed",
        "protection",
        "payer",
        "applications",
    ]
    assert any("8 tygodni urlopu po porodzie liczymy jako 56 dni" in a for a in t.assumptions)


def test_incapacity_after_fourteen_weeks_keeps_their_marker() -> None:
    t = event("incapacity", "2027-01-10")
    assert t.element("personal-weeks").date == dt.date(2027, 1, 6)  # type: ignore[union-attr]
    assert span(t, "maternity-father") == (dt.date(2027, 1, 10), WHOLE, 39)


def test_special_situations_before_eight_weeks_start_after_them() -> None:
    """Art. 180 § 6, § 10: only after 8 weeks of leave after the birth. In hospital
    10.11-10.12.2026: the mother until 25.11.2026 (56 days), the father 26.11-10.12.2026 (5 + 10
    = 15 days), the mother back 11.12.2026-17.02.2027 (21 + 31 + 17 = 69 days). A ruling from
    10.11.2026: the father 26.11.2026-17.02.2027 (5 + 31 + 31 + 17 = 84 days)."""
    hospital = event("hospital", "2026-11-10", "2026-12-10")
    assert span(hospital, "maternity") == (EVENT_BIRTH, dt.date(2026, 11, 25), 56)
    assert span(hospital, "maternity-father") == (
        dt.date(2026, 11, 26),
        dt.date(2026, 12, 10),
        15,
    )
    assert span(hospital, "maternity-resumed") == (dt.date(2026, 12, 11), WHOLE, 69)
    waits = "dlatego urlop taty zaczyna się 26.11.2026"
    assert any(waits in d for d in segment(hospital, "maternity-father").details)
    assert any("nie wcześniej niż po 8 tygodniach" in a for a in hospital.assumptions)
    incapacity = event("incapacity", "2026-11-10")
    assert span(incapacity, "maternity")[1] == dt.date(2026, 11, 25)
    assert span(incapacity, "maternity-father") == (dt.date(2026, 11, 26), WHOLE, 84)
    assert any(waits in d for d in segment(incapacity, "maternity-father").details)


def test_a_hospital_stay_over_before_eight_weeks_changes_nothing() -> None:
    """In hospital 10.10-20.11.2026: over before 26.11.2026, the first day after 8 weeks."""
    t = event("hospital", "2026-10-10", "2026-11-20")
    assert "maternity-father" not in ids(t)
    assert span(t, "maternity")[1] == WHOLE
    told = note(t, "mother-event")
    assert told.title == "Pobyt w szpitalu przed upływem 8 tygodni"
    assert "czyli od 26 listopada 2026" in told.text
    assert "skończył się wcześniej, 20 listopada 2026" in told.text


def test_hospital_the_father_takes_the_stay_and_the_mother_comes_back() -> None:
    """In hospital 1-20.12.2026: the father 1-20.12.2026 (20 days), the mother back from
    21.12.2026 to 17.02.2027 (59 days)."""
    t = event("hospital", "2026-12-01", "2026-12-20")
    assert span(t, "maternity") == (EVENT_BIRTH, dt.date(2026, 11, 30), 61)
    assert span(t, "maternity-father") == (dt.date(2026, 12, 1), dt.date(2026, 12, 20), 20)
    resumed = segment(t, "maternity-resumed")
    assert (resumed.lane, resumed.tone, resumed.title) == (
        "mother",
        "leave",
        "Urlop macierzyński mamy — dalsza część",
    )
    assert span(t, "maternity-resumed") == (dt.date(2026, 12, 21), WHOLE, 59)
    assert lane(t, "mother")[:2] == ["maternity", "maternity-resumed"]
    assert "personal-weeks" not in ids(t)
    told = note(t, "mother-event").text
    assert "art. 180 § 10 i 11" in told
    assert "Potem mama wraca na urlop: od 21 grudnia 2026 do 17 lutego 2027" in told
    assert "a mama znów od 21 grudnia 2026 do 17 lutego 2027" in note(t, "computed").text


def test_hospital_stay_still_under_way_or_past_the_end_of_the_leave() -> None:
    ongoing = event("hospital", "2026-12-01")
    assert span(ongoing, "maternity-father") == (dt.date(2026, 12, 1), WHOLE, 79)
    assert "maternity-resumed" not in ids(ongoing)
    assert "Mama jest jeszcze w szpitalu" in note(ongoing, "mother-event").text
    longer = event("hospital", "2026-12-01", "2027-03-01")
    assert span(longer, "maternity-father")[1] == WHOLE
    assert "maternity-resumed" not in ids(longer)


def test_death_of_the_mother() -> None:
    """Died 15.11.2026 (day 46, no 8-week minimum): her leave ends that day (46 days), the
    father has 16.11.2026-17.02.2027 (94 days). He cannot be on paternity leave at the same
    time: it follows, 18.02-3.03.2027 (14 days). Her parental leave goes; his runs 41 - 9 = 32
    weeks from 4.03.2027: + 223 days = 13.10.2027."""
    t = event("death", "2026-11-15")
    assert span(t, "maternity") == (EVENT_BIRTH, dt.date(2026, 11, 15), 46)
    assert span(t, "maternity-father") == (dt.date(2026, 11, 16), WHOLE, 94)
    assert lane(t, "mother") == ["maternity"]
    assert lane(t, "father") == ["maternity-father", "paternity", "parental-father"]
    assert span(t, "paternity") == (dt.date(2027, 2, 18), dt.date(2027, 3, 3), 14)
    assert span(t, "parental-father") == (dt.date(2027, 3, 4), dt.date(2027, 10, 13), 224)
    assert "personal-weeks" not in ids(t)
    assert "parental-deadline" in ids(t)
    told = note(t, "mother-event")
    assert told.text.startswith("Bardzo nam przykro.")
    assert "art. 180 § 12" in told.text
    assert note(t, "situation").text == "Liczymy od faktycznej daty urodzenia."
    assert not any(w.startswith("Urlop macierzyński") for w in t.warnings)
    assert any("Po śmierci mamy oś nie pokazuje dalszych urlopów mamy" in a for a in t.assumptions)


def test_death_of_the_mother_moves_supplementary_leave_to_the_father() -> None:
    """Born 1.10.2026 between the 28th and 37th week, in hospital 1-20.10 (20 days, 3 weeks):
    supplementary leave 18.02-10.03.2027, now on the father's lane; his parental leave after it,
    from 11.03.2027."""
    t = event(
        "death",
        "2026-11-15",
        hospital_care=True,
        birth_week="28-37",
        birth_weight_up_to_1000g=False,
        hospital_stays=[{"start": "2026-10-01", "end": "2026-10-20"}],
    )
    supplementary = segment(t, "supplementary")
    assert supplementary.lane == "father"
    assert span(t, "supplementary") == (dt.date(2027, 2, 18), dt.date(2027, 3, 10), 21)
    assert supplementary.summary.startswith("Uzupełniający urlop macierzyński przysługuje mamie")
    assert span(t, "parental-father")[0] == dt.date(2027, 3, 11)


def test_death_of_the_mother_when_the_father_is_not_insured() -> None:
    t = event("death", "2026-11-15", father_work="none")
    assert span(t, "maternity")[1] == dt.date(2026, 11, 15)
    assert lane(t, "father") == [] and lane(t, "mother") == ["maternity"]
    assert "parental-deadline" not in ids(t)
    told = note(t, "mother-event")
    assert told.title == "Urlop macierzyński mamy"
    assert told.text.startswith("Bardzo nam przykro.")
    assert "inny członek najbliższej rodziny" in told.text
    assert note(t, "computed").text.startswith("Urlop macierzyński mamy trwał do 15 listopada")


def test_death_of_the_mother_after_her_maternity_leave() -> None:
    """Born 5.01.2026: maternity leave ended on 24.05.2026. Died 1.08.2026, during her parental
    leave: it ends that day (25.05-1.08, 7 + 30 + 31 + 1 = 69 days). The father has the rest of
    the 41 weeks: 287 - 69 = 218 days, from today (21.11.2026) after his paternity leave
    21.11-4.12.2026 (the deadline is 4.01.2027): 5.12.2026 + 217 days = 10.07.2027 (27 days of
    December, then 31 + 28 + 31 + 30 + 31 + 30 + 10)."""
    t = build_timeline(
        Scenario.model_validate(
            {
                **EMPLOYED,
                "child_born": True,
                "birth_date": "2026-01-05",
                "children_count": 1,
                "leave_before_birth_weeks": 0,
                "mother_event": {"kind": "death", "start": "2026-08-01"},
            }
        ),
        PARAMS,
        TODAY,
    )
    assert span(t, "maternity")[1] == dt.date(2026, 5, 24)
    assert "maternity-father" not in ids(t)
    assert span(t, "parental") == (dt.date(2026, 5, 25), dt.date(2026, 8, 1), 69)
    assert span(t, "paternity") == (TODAY, dt.date(2026, 12, 4), 14)
    assert span(t, "parental-father") == (dt.date(2026, 12, 5), dt.date(2027, 7, 10), 218)
    parental = segment(t, "parental-father")
    assert parental.summary.startswith("Urlop rodzicielski może wykorzystać tata. Pokazujemy 218")
    assert "jednocześnie albo naprzemiennie" not in parental.summary
    assert any("Mama wykorzystała 69 dni urlopu rodzicielskiego" in d for d in parental.details)
    assert "jednocześnie albo naprzemiennie" not in note(t, "father").text
    assert "Urlop rodzicielski może wykorzystać tata." in note(t, "father").text
    assert any("co najmniej jej 9 tygodni" in a for a in t.assumptions)
    told = note(t, "mother-event")
    assert told.title == "Urlop macierzyński już się skończył"
    assert "skończył się 24 maja 2026" in told.text
    assert "Urlop rodzicielski mamy: od 25 maja 2026 do 1 sierpnia 2026." in (
        note(t, "computed").text
    )


def test_abandonment_after_eight_weeks_at_the_earliest() -> None:
    """Abandoned on 10.11.2026, before 8 weeks were used: the mother until 25.11.2026 (56 days),
    the father 26.11.2026-17.02.2027 (84 days), then his paternity leave 18.02-3.03.2027. Her
    later leave goes; his parental leave runs from 4.03.2027."""
    t = event("abandonment", "2026-11-10")
    assert span(t, "maternity") == (EVENT_BIRTH, dt.date(2026, 11, 25), 56)
    assert span(t, "maternity-father") == (dt.date(2026, 11, 26), WHOLE, 84)
    assert any("zaczyna się 26.11.2026" in d for d in segment(t, "maternity-father").details)
    assert lane(t, "mother") == ["maternity"]
    assert span(t, "parental-father")[0] == dt.date(2027, 3, 4)
    assert "art. 180 § 13" in note(t, "mother-event").text


def test_abandonment_later_starts_the_next_day() -> None:
    """Born 1.07.2026 (20 weeks to 17.11.2026); abandoned 1.10.2026: the father from 2.10."""
    t = build_timeline(
        Scenario.model_validate(
            {
                **EMPLOYED,
                "child_born": True,
                "birth_date": "2026-07-01",
                "children_count": 1,
                "leave_before_birth_weeks": 0,
                "mother_event": {"kind": "abandonment", "start": "2026-10-01"},
            }
        ),
        PARAMS,
        TODAY,
    )
    assert span(t, "maternity-father")[:2] == (dt.date(2026, 10, 2), dt.date(2026, 11, 17))


def test_special_situation_dates_are_checked() -> None:
    with pytest.raises(ScenarioError, match="wcześniejsza niż data porodu"):
        event("death", "2026-09-30")
    with pytest.raises(ScenarioError, match="w przyszłości"):
        event("death", "2026-12-01")
    with pytest.raises(ScenarioError, match="w przyszłości"):
        event("abandonment", "2026-12-01")
    with pytest.raises(ScenarioError, match="gdy dziecko już się urodziło"):
        expecting(children_count=1, mother_event={"kind": "hospital", "start": "2027-06-01"})


def test_a_special_situation_after_the_leave_changes_nothing() -> None:
    """20 weeks from 1.10.2026 end on 17.02.2027; a stay from 1.03.2027 comes after them."""
    t = event("hospital", "2027-03-01")
    assert "maternity-father" not in ids(t)
    assert span(t, "maternity")[1] == WHOLE
    told = note(t, "mother-event")
    assert told.title == "Urlop macierzyński kończy się wcześniej"
    assert "kończy się 17 lutego 2027" in told.text


def test_an_uninsured_father_cannot_take_over_in_a_special_situation() -> None:
    t = event("incapacity", "2026-12-01", father_work="contract", father_insured=False)
    assert "maternity-father" not in ids(t)
    assert span(t, "maternity")[1] == WHOLE
    assert "personal-weeks" in ids(t)
    told = note(t, "mother-event")
    assert told.title == "Przejęcie urlopu wymaga ubezpieczenia chorobowego taty"
    assert "inny członek najbliższej rodziny" in told.text


def test_a_special_situation_overrides_taking_over() -> None:
    t = event("incapacity", "2026-12-01", father_takes_over=True)
    assert span(t, "maternity-father")[0] == dt.date(2026, 12, 1)
    assert "takeover" not in notes(t)


def test_special_situations_without_a_living_child_are_out_of_scope() -> None:
    stillborn = event("hospital", "2026-12-01", losses=[STILLBORN])
    assert ids(stillborn) == ["maternity", "birth", "protection-end", "maternity-request"]
    assert span(stillborn, "maternity")[1] == dt.date(2026, 11, 25)  # 8 weeks, untouched
    assert any("Gdy żadne dziecko nie żyje" in a for a in stillborn.assumptions)


def test_the_fathers_dates_are_explained() -> None:
    explained = notes(expecting(children_count=1))
    assert explained["father"].startswith("Tata: urlop ojcowski i urlop rodzicielski | ")
    assert "w 2 częściach po co najmniej 7 dni" in explained["father"]
    assert "do 14 marca 2028" in explained["father"]
    assert "9 tyg. należy wyłącznie do taty" in explained["father"]
    assert "Urlop ojcowski: 14 dni, od 15 marca 2027 do 28 marca 2027" in explained["computed"]
    assert (
        "Urlop rodzicielski taty: 9 tyg., od 13 marca 2028 do 14 maja 2028"
        in (explained["computed"])
    )
    assert not any("Uprawnienia taty" in a for a in expecting(children_count=1).assumptions)


# Section B after the independent check against the Labour Code (22.11.2026).


def test_abandonment_cuts_the_mothers_leave_when_the_father_is_not_insured() -> None:
    """Art. 182: abandoned on 10.11.2026, before 8 weeks were used: the mother keeps the leave
    until 25.11.2026 (56 days), not to 17.02.2027, whether or not the father can take the rest.
    Her later leave goes too."""
    t = event("abandonment", "2026-11-10", father_work="none")
    assert span(t, "maternity") == (EVENT_BIRTH, dt.date(2026, 11, 25), 56)
    assert lane(t, "mother") == ["maternity"]
    assert lane(t, "father") == []
    assert "personal-weeks" not in ids(t)
    assert t.element("protection-end").date == dt.date(2026, 11, 25)  # type: ignore[union-attr]
    assert any(s.article == "art. 182" for s in segment(t, "maternity").sources)
    told = note(t, "mother-event")
    assert told.title == "Mamie nie przysługuje dalsza część urlopu"
    assert "nie może wynosić mniej niż 8 tygodni, więc trwa do 25 listopada 2026" in told.text
    assert "nie podlega ubezpieczeniu chorobowemu" in told.text
    assert any(s.article == "art. 182" for s in told.sources)
    assert note(t, "computed").text.startswith(
        "Urlop macierzyński mamy trwa po porodzie do 25 listopada 2026"
    )
    assert any("Po porzuceniu dziecka przez mamę oś nie pokazuje" in a for a in t.assumptions)
    # Abandoned on 20.11.2026, still within the 8 weeks: the leave lasts to 25.11.2026.
    later = event("abandonment", "2026-11-20", father_work="none")
    assert span(later, "maternity")[1] == dt.date(2026, 11, 25)
    # After the 8 weeks the leave ends on the day of abandonment.
    after_eight = build_timeline(
        Scenario.model_validate(
            {
                **EMPLOYED,
                "father_work": "none",
                "child_born": True,
                "birth_date": "2026-09-01",
                "children_count": 1,
                "leave_before_birth_weeks": 0,
                "mother_event": {"kind": "abandonment", "start": "2026-11-15"},
            }
        ),
        PARAMS,
        TODAY,
    )
    # Born 1.09.2026: 30 + 31 + 15 = 76 days to 15.11.2026.
    assert span(after_eight, "maternity") == (dt.date(2026, 9, 1), dt.date(2026, 11, 15), 76)


def uninsured(kind: str, start: str, **answers: object) -> Timeline:
    """Born 1.10.2026 to a mother who does not work; the father is an employee."""
    return build_timeline(
        Scenario.model_validate(
            {
                "role": "father",
                "work": "employment",
                "mother_work": "none",
                "child_born": True,
                "birth_date": EVENT_BIRTH,
                "children_count": 1,
                "mother_event": {"kind": kind, "start": start},
                **answers,
            }
        ),
        PARAMS,
        TODAY,
    )


def test_death_of_an_uninsured_mother_gives_the_father_maternity_leave() -> None:
    """Art. 180 § 15: died 15.10.2026, 20 weeks from the birth end on 17.02.2027, so the father
    has 16.10.2026-17.02.2027 (16 + 30 + 31 + 31 + 17 = 125 days), with no 8-week minimum. Then
    his paternity leave 18.02-3.03.2027 and 32 weeks of parental leave from 4.03.2027 (+223 days
    = 13.10.2027)."""
    t = uninsured("death", "2026-10-15")
    assert lane(t, "mother") == []
    assert lane(t, "father") == ["maternity-father", "paternity", "parental-father"]
    assert span(t, "maternity-father") == (dt.date(2026, 10, 16), WHOLE, 125)
    assert span(t, "paternity") == (dt.date(2027, 2, 18), dt.date(2027, 3, 3), 14)
    assert span(t, "parental-father") == (dt.date(2027, 3, 4), dt.date(2027, 10, 13), 224)
    his = segment(t, "maternity-father")
    assert his.summary == (
        "Mama nie podlegała ubezpieczeniu chorobowemu. Tacie przysługuje część urlopu "
        "macierzyńskiego przypadająca po dniu śmierci mamy: od 16.10.2026 do 17.02.2027."
    )
    assert {s.article for s in his.sources} >= {"art. 180 § 15", "art. 180 § 1"}
    assert "art. 180 § 14" not in {s.article for s in his.sources}
    told = note(t, "mother-event")
    assert told.title == "Urlop macierzyński taty od 16 października 2026"
    assert told.text.startswith("Bardzo nam przykro. Mama nie podlegała ubezpieczeniu")
    assert "od 16 października 2026 do 17 lutego 2027 (Kodeks pracy, art. 180 § 15)" in told.text
    assert note(t, "computed").text.startswith(
        "Urlop macierzyński taty: od 16 października 2026 do 17 lutego 2027."
    )
    assert any("bez czekania 8 tygodni" in a for a in t.assumptions)
    assert not any("przepisów o innych przypadkach" in a for a in t.assumptions)
    # His request: art. 180 § 16, no deadline.
    request = t.element("maternity-father-request")
    assert request is not None and request.deadline is None  # type: ignore[union-attr]


def test_abandonment_or_incapacity_of_an_uninsured_mother() -> None:
    """The same part after the day she abandoned the child, or after the day her incapacity
    arose: 16.10.2026-17.02.2027."""
    gone = uninsured("abandonment", "2026-10-15")
    assert span(gone, "maternity-father") == (dt.date(2026, 10, 16), WHOLE, 125)
    assert "po dniu porzucenia przez nią dziecka" in segment(gone, "maternity-father").summary
    assert not note(gone, "mother-event").text.startswith("Bardzo nam przykro")
    ill = uninsured("incapacity", "2026-10-15")
    assert span(ill, "maternity-father") == (dt.date(2026, 10, 16), WHOLE, 125)
    assert "po dniu powstania jej niezdolności" in segment(ill, "maternity-father").summary
    assert any("dzień powstania niezdolności" in a for a in ill.assumptions)
    # Twins: 31 weeks = 217 days from 1.10.2026: 31 + 30 + 31 + 31 + 28 + 31 + 30 + 5, so
    # they end on 5.05.2027.
    twins = uninsured("death", "2026-10-15", children_count=2)
    assert span(twins, "maternity-father")[1] == dt.date(2027, 5, 5)


def test_a_stay_in_hospital_of_an_uninsured_mother_is_not_among_the_cases() -> None:
    t = uninsured("hospital", "2026-10-15")
    assert lane(t, "father") == ["paternity", "parental-father"]
    assert "mother-event" not in notes(t)
    assert any("a nie przy pobycie w szpitalu" in a for a in t.assumptions)


def test_nothing_left_after_an_uninsured_mother_dies_late() -> None:
    """Born 1.03.2026: 20 weeks end on 1.03.2026 + 139 days = 18.07.2026; died 1.09.2026."""
    t = uninsured("death", "2026-09-01", birth_date="2026-03-01")
    assert "maternity-father" not in ids(t)
    told = note(t, "mother-event")
    assert told.title == "Urlop macierzyński już się skończył"
    assert "liczony od dnia porodu, skończył się 18 lipca 2026" in told.text


def test_an_uninsured_father_after_an_uninsured_mother_died() -> None:
    t = uninsured("death", "2026-10-15", work="none")
    assert lane(t, "father") == []
    told = note(t, "mother-event")
    assert told.title == "Urlop macierzyński taty wymaga ubezpieczenia chorobowego"
    assert "przerwał działalność zarobkową" in told.text
    assert any(s.article == "art. 29 ust. 9" for s in told.sources)


@pytest.mark.parametrize(
    ("answers", "article"),
    [
        ({"father_takes_over": True}, "art. 29 ust. 3"),
        ({"mother_event": {"kind": "incapacity", "start": "2026-12-01"}}, "art. 29 ust. 5"),
        (
            {"mother_event": {"kind": "hospital", "start": "2026-12-01", "end": "2026-12-20"}},
            "art. 29 ust. 6",
        ),
        ({"mother_event": {"kind": "death", "start": "2026-11-15"}}, "art. 29 ust. 7"),
        ({"mother_event": {"kind": "abandonment", "start": "2026-11-10"}}, "art. 29 ust. 7"),
    ],
)
def test_a_father_who_is_not_an_employee_interrupts_his_work(
    answers: dict[str, object], article: str
) -> None:
    """Ustawa art. 29 ust. 3, 5-7: the benefit for the mother's maternity leave goes to the
    father who interrupted his work to look after the child."""
    t = build_timeline(
        Scenario.model_validate(
            {
                **EMPLOYED,
                "father_work": "contract",
                "father_insured": True,
                "child_born": True,
                "birth_date": EVENT_BIRTH,
                "children_count": 1,
                "leave_before_birth_weeks": 0,
                **answers,
            }
        ),
        PARAMS,
        TODAY,
    )
    his = segment(t, "maternity-father")
    assert any("przerwał działalność zarobkową" in d for d in his.details)
    assert article in {s.article for s in his.sources}
    # Only his part of maternity leave: not paternity leave.
    assert not any("przerwał działalność" in d for d in segment(t, "paternity").details)
    told = note(t, "takeover" if "father_takes_over" in answers else "mother-event")
    assert "przerwał działalność zarobkową w celu sprawowania osobistej opieki" in told.text
    assert article in {s.article for s in told.sources}


def test_an_uninsured_mother_and_a_father_who_is_not_an_employee() -> None:
    t = uninsured("death", "2026-10-15", work="contract", father_insured=True)
    his = segment(t, "maternity-father")
    assert any("przerwał działalność zarobkową" in d for d in his.details)
    assert "art. 29 ust. 9" in {s.article for s in his.sources}
    assert "przerwał działalność zarobkową" in note(t, "mother-event").text


def test_the_offer_to_take_over_says_what_a_father_on_a_contract_needs() -> None:
    offered = note(
        born(**EMPLOYED | {"father_work": "contract"}, father_insured=True, children_count=1),
        "takeover",
    )
    assert offered.title == "Tata może przejąć część urlopu macierzyńskiego"
    assert "przerwał działalność zarobkową" in offered.text
    assert "przerwał działalność" not in note(born(**EMPLOYED, children_count=1), "takeover").text


def test_the_wording_without_the_fathers_insurance() -> None:
    """Ustawa art. 29 ust. 7: the benefit also for an insured member of the family who
    interrupted the work; KP art. 180 § 11: the part for the time of the stay in hospital."""
    died = note(event("death", "2026-11-15", father_work="none"), "mother-event")
    assert "który jest pracownikiem" in died.text
    assert "przerwał działalność zarobkową" in died.text
    assert any(s.article == "art. 29 ust. 7" for s in died.sources)
    hospital = note(
        event("hospital", "2026-12-01", "2026-12-20", father_work="contract", father_insured=False),
        "mother-event",
    )
    assert hospital.text.startswith(
        "Mama przebywa w szpitalu. Część urlopu macierzyńskiego odpowiadającą okresowi pobytu "
        "mamy w szpitalu mógłby wtedy wykorzystać tata"
    )


def test_the_fathers_parental_option_starts_today_at_the_earliest() -> None:
    """Born 1.03.2025: maternity leave to 18.07.2025, the mother's parental leave 19.07.2025-
    27.02.2026. The father's 9 weeks from today, 21.11.2026 + 62 days = 22.01.2027."""
    t = born(**EMPLOYED, birth_date=dt.date(2025, 3, 1), children_count=1)
    assert span(t, "parental")[1] == dt.date(2026, 2, 27)
    assert span(t, "parental-father") == (TODAY, dt.date(2027, 1, 22), 63)
    # Before the birth: right after the mother's share, as before.
    assert span(expecting(children_count=1), "parental-father")[0] == dt.date(2028, 3, 13)


def test_abandonment_during_parental_leave() -> None:
    """Born 5.01.2026, abandoned 1.08.2026: as after the death, the father has 287 - 69 = 218
    days of parental leave, 5.12.2026-10.07.2027."""
    t = build_timeline(
        Scenario.model_validate(
            {
                **EMPLOYED,
                "child_born": True,
                "birth_date": "2026-01-05",
                "children_count": 1,
                "leave_before_birth_weeks": 0,
                "mother_event": {"kind": "abandonment", "start": "2026-08-01"},
            }
        ),
        PARAMS,
        TODAY,
    )
    assert span(t, "parental") == (dt.date(2026, 5, 25), dt.date(2026, 8, 1), 69)
    assert span(t, "parental-father") == (dt.date(2026, 12, 5), dt.date(2027, 7, 10), 218)
