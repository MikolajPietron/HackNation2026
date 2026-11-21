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
    assert ids(t) == ["maternity", "parental", "birth", "personal-weeks", "parental-deadline"]
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
    assert changed_element_ids(one, two) == ["maternity", "parental"]
    assert changed_element_ids(expecting(), one) == [
        "maternity",
        "parental",
        "personal-weeks",
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
    assert list(explained) == ["situation", "insurance", "before-birth", "parental", "computed"]
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
    assert list(explained) == ["situation", "insurance", "parental", "computed"]
    assert explained["situation"].startswith("Dziecko urodziło się dzisiaj | To upraszcza sprawę")
    assert "zaczyna się dziś, w dniu porodu" in explained["situation"]
    assert "po porodzie do 9 kwietnia 2027" in explained["computed"]


def test_changed_notes_name_what_an_answer_changed() -> None:
    """Twins bring parental leave onto the timeline, add a relief and change what we computed;
    the situation stays as it was."""
    before, after = expecting(), expecting(children_count=2)
    assert changed_note_ids(before, after) == ["parental", "more-children", "computed"]
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
    # her insurance is confirmed.
    for t in (asked, insured):
        leave = [s for s in t.segments if s.tone != "work"]
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
        assert ids(t) in (["due-date"], ["birth"])
        assert [n.id for n in t.notes] == ["situation", "insurance"]
        assert t.notes[1].kind == "risk"
        assert t.notes[1].title == "Zasiłek macierzyński wymaga ubezpieczenia chorobowego"
        assert "Tylko w określonych sytuacjach zasiłek przysługuje także po ustaniu" in (
            t.notes[1].text
        )
        assert "Liczy się, czy w dniu porodu podlega ubezpieczeniu" in t.markers[0].summary
        assert not t.documents


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
    assert ids(t) == ["maternity", "birth"]
    assert span(t, "maternity") == (LOST_BIRTH, dt.date(2027, 1, 4), 56)
    assert t.element("birth").title == "Poród"  # type: ignore[union-attr]
    assert [(n.id, n.kind) for n in t.notes] == [
        ("situation", "situation"),
        ("insurance", "right"),
        ("loss", "right"),
        ("computed", "computed"),
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
