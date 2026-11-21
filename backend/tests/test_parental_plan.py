"""Guide section E (page 9) and B.3 (page 7): parental leave split between the parents, in
parts, and combined with part-time work (Labour Code art. 182¹ᵃ § 6-7, 182¹ᶜ, 182¹ᵈ § 2,
182¹ᵉ, 182¹ᶠ). Expected dates were computed by hand:

One child due 15.03.2027, the mother employed: maternity leave 15.03.2027-01.08.2027, so
parental leave can start on 02.08.2027 at the earliest; the pool is 41 weeks, 32 at most for
one parent; the last day for parental leave is 31.12.2033.
"""

import datetime as dt
from typing import Any

import pytest

from app.engine import Scenario, ScenarioError, Timeline, build_timeline
from app.engine.models import Segment
from app.services.params import load_params

PARAMS = load_params()
TODAY = dt.date(2026, 11, 21)
DUE = dt.date(2027, 3, 15)
MOTHER = {"role": "mother", "work": "employment", "father_work": "employment"}


def expecting(*parts: dict[str, Any], **answers: Any) -> Timeline:
    scenario = Scenario.model_validate(
        {
            "child_born": False,
            "due_date": DUE,
            "children_count": 1,
            **MOTHER,
            **answers,
            "parental_parts": list(parts),
        }
    )
    return build_timeline(scenario, PARAMS, TODAY)


def segment(timeline: Timeline, segment_id: str) -> Segment:
    return next(s for s in timeline.segments if s.id == segment_id)


def span(timeline: Timeline, segment_id: str) -> tuple[dt.date, dt.date, int]:
    s = segment(timeline, segment_id)
    return s.start, s.end, s.days


def lane(timeline: Timeline, name: str) -> list[str]:
    return [s.id for s in timeline.segments if s.lane == name]


def notes(timeline: Timeline) -> dict[str, str]:
    return {n.id: f"{n.title} | {n.text}" for n in timeline.notes}


# Combining parental leave with work (guide E; art. 182¹ᵉ, 182¹ᶠ).


def test_working_half_time_extends_the_part_by_weeks_times_the_fraction() -> None:
    """32 weeks from 02.08.2027, the first 20 at 1/2 of full time: 20 x 1/2 = 10 weeks more,
    so 42 weeks = 294 days: 02.08.2027 + 293 days = 21.05.2028 (2028 is a leap year; without
    work the 32 weeks end on 12.03.2028, + 70 days = 21.05.2028). Work: 02.08.2027 + 139 days =
    19.12.2027. The request: 21 days before 02.08.2027 = 12.07.2027. The father's 9 weeks move
    to right after her: 22.05.2028 + 62 days = 23.07.2028."""
    t = expecting({"parent": "mother", "weeks": 32, "work_fraction": "1/2", "work_weeks": 20})
    assert lane(t, "mother") == ["prenatal-window", "maternity", "parental-mother-1"]
    part = segment(t, "parental-mother-1")
    assert (part.tone, part.title) == ("leave", "Urlop rodzicielski z pracą")
    assert span(t, "parental-mother-1") == (dt.date(2027, 8, 2), dt.date(2028, 5, 21), 294)
    assert "przez 20 tyg. pracuje na 1/2 etatu" in part.summary
    assert "Urlop wydłuża się o 10 tyg." in part.summary
    assert any(
        d.startswith("Od 02.08.2027 do 19.12.2027 mama łączy urlop z pracą") for d in part.details
    )
    assert any("20 tyg. × 1/2 = 10 tyg.; przedłuża" in d for d in part.details)
    assert any("czyli najpóźniej 12.07.2027" in d for d in part.details)
    articles = {s.article for s in part.sources}
    assert {"art. 182¹ᵉ § 1", "art. 182¹ᵉ § 2", "art. 182¹ᶠ § 2", "art. 182¹ᶠ § 5"} <= articles
    assert "art. 182¹ᶠ § 4" not in articles  # whole weeks: nothing given in days
    assert any(s.section == "E" for s in part.sources)
    assert span(t, "parental-father") == (dt.date(2028, 5, 22), dt.date(2028, 7, 23), 63)
    assert segment(t, "parental-father").tone == "option"
    assert "po zaplanowanym urlopie mamy" in segment(t, "parental-father").summary


def test_an_extension_that_is_not_whole_weeks_is_given_in_days() -> None:
    """The father's 9 weeks at 1/2: 9 x 1/2 = 4.5 weeks = 31.5 days, the incomplete day is
    dropped (art. 182¹ᶠ § 4): 31 days. He starts where his option was, after her 32 weeks:
    13.03.2028; 63 + 31 = 94 days: 13.03.2028 + 93 days = 14.06.2028."""
    t = expecting({"parent": "father", "weeks": 9, "work_fraction": "1/2"})
    assert span(t, "parental-father-1") == (dt.date(2028, 3, 13), dt.date(2028, 6, 14), 94)
    part = segment(t, "parental-father-1")
    assert part.lane == "father" and part.title == "Urlop rodzicielski taty z pracą"
    assert any(
        "9 tyg. × 1/2 = 4,5 tyg., czyli 31,5 dnia; niepełny dzień się pomija, więc 31 dni" in d
        for d in part.details
    )
    assert "art. 182¹ᶠ § 4" in {s.article for s in part.sources}
    # The mother's share stays an option: 41 - 9 = 32 weeks, as without a plan.
    assert span(t, "parental") == (dt.date(2027, 8, 2), dt.date(2028, 3, 12), 224)
    assert "parental-father" not in lane(t, "father")


@pytest.mark.parametrize(
    ("given", "fraction"), [("0.25", "1/4"), (0.4, "2/5"), ("40%", "2/5"), ("0,5", "1/2")]
)
def test_the_part_of_full_time_is_read_exactly(given: object, fraction: str) -> None:
    t = expecting({"parent": "mother", "weeks": 32, "work_fraction": given})
    assert f"pracuje na {fraction} etatu" in segment(t, "parental-mother-1").summary


def test_working_a_quarter_of_full_time_with_an_uninsured_mother() -> None:
    """Born 10.11.2026, the mother does not work: paternity leave 21.11-04.12.2026, then the
    father's 41 - 9 = 32 weeks from 05.12.2026 (without a plan until 16.07.2027). The first 16
    weeks at 1/4: 16 x 1/4 = 4 weeks = 28 days, so 252 days: 16.07.2027 + 28 = 13.08.2027."""
    scenario = Scenario(
        role="father",
        work="employment",
        mother_work="none",
        child_born=True,
        birth_date=dt.date(2026, 11, 10),
        children_count=1,
        parental_parts=[
            {"parent": "father", "weeks": 32, "work_fraction": "1/4", "work_weeks": 16}
        ],
    )
    t = build_timeline(scenario, PARAMS, TODAY)
    assert lane(t, "mother") == []
    assert span(t, "parental-father-1") == (dt.date(2026, 12, 5), dt.date(2027, 8, 13), 252)
    assert any("Czy w tej sytuacji tata może wykorzystać także je" in a for a in t.assumptions)


def test_the_case_explanation_shows_the_formula() -> None:
    t = expecting({"parent": "mother", "weeks": 32, "work_fraction": "1/2", "work_weeks": 20})
    explained = notes(t)
    ids = [n.id for n in t.notes]
    # The plan comes after the options and before what we computed for the whole timeline.
    assert ids.index("parental-plan") < ids.index("parental-work")
    assert ids.index("parental-plan-computed") == ids.index("computed") - 1
    assert next(n for n in t.notes if n.id == "parental-work").kind == "relief"
    assert (
        "W Waszym planie jest 1 część: mama 32 tyg.; razem 32 z 41 tyg."
        in explained["parental-plan"]
    )
    assert "Z puli zostaje 9 tyg." in explained["parental-plan"]
    assert "najwyżej na 1/2 etatu" in explained["parental-work"]
    assert "łącznie najwyżej do 82 tyg." in explained["parental-work"]
    assert (
        "Część 1, mama: 32 tyg., z czego 20 tyg. z pracą na 1/2 etatu. Wydłużenie: 20 tyg. × "
        "1/2 = 10 tyg., więc ta część trwa 294 dni: od 2 sierpnia 2027 do 21 maja 2028."
    ) in explained["parental-plan-computed"]
    # The father's option after her parts is not the case of a mother without parental leave.
    assert not any("Czy w tej sytuacji tata może" in a for a in t.assumptions)
    assert any("od pierwszego dnia części urlopu" in a for a in t.assumptions)


def test_twins_and_za_zyciem_raise_the_limits() -> None:
    t = expecting({"parent": "mother", "weeks": 34, "work_fraction": "1/2"}, children_count=2)
    assert "łącznie najwyżej do 86 tyg." in notes(t)["parental-work"]
    t = expecting({"parent": "mother", "weeks": 56, "work_fraction": "1/2"}, za_zyciem=True)
    assert "łącznie najwyżej do 130 tyg." in notes(t)["parental-work"]


# Splitting parental leave between the parents and into parts (guide B.3; art. 182¹ᵃ § 6, 182¹ᶜ).


def test_parents_at_the_same_time_and_one_after_the_other() -> None:
    """Mother 20 weeks from 02.08.2027: + 139 days = 19.12.2027. The father's 9 weeks at the
    same time: 02.08.2027 + 62 days = 03.10.2027. Her second part from 01.03.2028, 12 weeks:
    + 83 days = 23.05.2028. Together 32 + 9 = 41 weeks in 3 parts."""
    t = expecting(
        {"parent": "mother", "weeks": 20},
        {"parent": "father", "weeks": 9, "with_previous": True},
        {"parent": "mother", "weeks": 12, "start": "2028-03-01"},
    )
    assert lane(t, "mother") == [
        "prenatal-window",
        "maternity",
        "parental-mother-1",
        "parental-mother-2",
    ]
    assert lane(t, "father") == ["paternity", "parental-father-1"]
    assert span(t, "parental-mother-1") == (dt.date(2027, 8, 2), dt.date(2027, 12, 19), 140)
    assert span(t, "parental-father-1") == (dt.date(2027, 8, 2), dt.date(2027, 10, 3), 63)
    assert span(t, "parental-mother-2") == (dt.date(2028, 3, 1), dt.date(2028, 5, 23), 84)
    first = segment(t, "parental-mother-1")
    assert first.title == "Urlop rodzicielski — część 1"
    assert "To część 1 z 3 w planie rodziców." in first.summary
    assert any(d.startswith("W tym czasie z urlopu korzysta też tata") for d in first.details)
    assert "art. 182¹ᵃ § 6" in {s.article for s in first.sources}
    assert not any(d.startswith("W tym czasie") for d in segment(t, "parental-mother-2").details)
    plan = notes(t)["parental-plan"]
    assert "W Waszym planie jest 3 części: mama 32 tyg., tata 9 tyg.; razem 41 z 41 tyg." in plan
    assert "Z puli zostaje" not in plan
    assert "Część urlopu bierzecie jednocześnie" in plan
    assert t.element("parental-deadline").date == dt.date(2033, 12, 31)  # type: ignore[union-attr]


def test_the_fathers_parts_shrink_the_mothers_option() -> None:
    """The father plans 20 weeks: the mother has 41 - 20 = 21 left, from 02.08.2027: + 146 days
    = 26.12.2027. He starts after her share: 27.12.2027 + 139 days = 14.05.2028."""
    t = expecting({"parent": "father", "weeks": 20})
    assert span(t, "parental") == (dt.date(2027, 8, 2), dt.date(2027, 12, 26), 147)
    assert "mamie zostaje najwięcej 21 tyg." in segment(t, "parental").summary
    assert segment(t, "parental").tone == "option"
    assert span(t, "parental-father-1") == (dt.date(2027, 12, 27), dt.date(2028, 5, 14), 140)


def test_no_plan_when_no_child_lives() -> None:
    scenario = Scenario(
        **MOTHER,
        child_born=True,
        birth_date=dt.date(2026, 11, 10),
        children_count=1,
        losses=[{"stillborn": True}],
        parental_parts=[{"parent": "mother", "weeks": 32}],
    )
    t = build_timeline(scenario, PARAMS, TODAY)
    assert not any(s.id.startswith("parental") for s in t.segments)
    assert "parental-plan" not in notes(t)


# What the rules do not allow.


@pytest.mark.parametrize(
    ("parts", "answers", "message"),
    [
        (
            [{"parent": "mother", "weeks": 32, "work_fraction": "3/5"}],
            {},
            "najwyżej na 1/2 etatu",
        ),
        (
            [{"parent": "mother", "weeks": 32, "work_fraction": "0"}],
            {},
            "musi być większy od zera",
        ),
        (
            [{"parent": "mother", "weeks": 10, "work_fraction": "1/2", "work_weeks": 11}],
            {},
            "najwyżej tyle tygodni, ile ta część urlopu (10 tyg.)",
        ),
        (
            [{"parent": "mother", "weeks": 10, "work_weeks": 5}],
            {},
            "podano tygodnie pracy, ale nie wymiar pracy",
        ),
        ([{"parent": "mother", "weeks": 33}], {}, "Mama może wykorzystać najwyżej 32 tyg."),
        (
            [{"parent": "mother", "weeks": 35}],
            {"children_count": 2},
            "Mama może wykorzystać najwyżej 34 tyg.",
        ),
        (
            [{"parent": "mother", "weeks": 32}, {"parent": "father", "weeks": 10}],
            {},
            "Rodzice mają razem najwyżej 41 tyg. urlopu rodzicielskiego, także gdy korzystają "
            "z niego jednocześnie. W planie jest 42 tyg.",
        ),
        (
            [{"parent": "mother", "weeks": 5}] * 6,
            {},
            "najwyżej na 5 części (liczymy części obojga rodziców razem). W planie jest 6.",
        ),
        (
            [{"parent": "mother", "weeks": 5, "start": "2027-08-01"}],
            {},
            "najwcześniej 02.08.2027: po urlopie macierzyńskim",
        ),
        (
            # 01.12.2033 + 5 weeks - 1 day = 04.01.2034, after 31.12.2033.
            [{"parent": "mother", "weeks": 5, "start": "2033-12-01"}],
            {},
            "Część 1 urlopu rodzicielskiego (mamy) kończyłaby się 04.01.2034, a urlop trzeba "
            "wykorzystać do 31.12.2033",
        ),
        (
            # 02.08.2027 + 20 weeks - 1 day = 19.12.2027; the second part starts on 01.12.2027.
            [
                {"parent": "mother", "weeks": 20},
                {"parent": "mother", "weeks": 5, "start": "2027-12-01"},
            ],
            {},
            "Części urlopu mamy nachodzą na siebie: część 1 trwa do 19.12.2027, a część 2 zaczyna "
            "się 01.12.2027.",
        ),
        (
            [{"parent": "mother", "weeks": 32, "work_fraction": "1/2"}],
            {"work": "contract", "mother_insured": True},
            "Łączyć urlop rodzicielski z pracą może pracownik",
        ),
        (
            [{"parent": "father", "weeks": 9}],
            {"father_work": "none"},
            "Tata nie podlega ubezpieczeniu chorobowemu",
        ),
        (
            [{"parent": "mother", "weeks": 9}],
            {"work": "none"},
            "Mama nie podlega ubezpieczeniu chorobowemu w dniu porodu",
        ),
    ],
)
def test_a_plan_against_the_rules_is_refused(
    parts: list[dict[str, Any]], answers: dict[str, Any], message: str
) -> None:
    with pytest.raises(ScenarioError, match=message.replace("(", r"\(").replace(")", r"\)")):
        expecting(*parts, **answers)


def test_a_part_after_the_deadline_cannot_be_planned() -> None:
    """Born 01.06.2020: the last day was 31.12.2026, still ahead on 21.11.2026; parental leave
    from today, 4 weeks: 21.11.2026 + 27 days = 18.12.2026, but 6 weeks would end on
    01.01.2027."""
    born = {**MOTHER, "child_born": True, "birth_date": dt.date(2020, 6, 1), "children_count": 1}
    fits = Scenario(**born, parental_parts=[{"parent": "father", "weeks": 4, "start": TODAY}])
    t = build_timeline(fits, PARAMS, TODAY)
    assert span(t, "parental-father-1") == (TODAY, dt.date(2026, 12, 18), 28)
    late = Scenario(**born, parental_parts=[{"parent": "father", "weeks": 6, "start": TODAY}])
    with pytest.raises(ScenarioError, match="kończyłaby się 01.01.2027"):
        build_timeline(late, PARAMS, TODAY)
    gone = Scenario(**born, parental_parts=[{"parent": "father", "weeks": 1}])
    with pytest.raises(ScenarioError, match="Czas na urlop rodzicielski minął 31.12.2026"):
        build_timeline(gone, PARAMS, dt.date(2027, 1, 5))
