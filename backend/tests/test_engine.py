"""Base timeline rules. Expected dates were computed by hand from the rules in params/2026.json."""

import datetime as dt

import pytest

from app.engine import Scenario, ScenarioError, Timeline, build_timeline, changed_element_ids
from app.engine.models import Segment
from app.services.params import load_params

PARAMS = load_params()
TODAY = dt.date(2026, 11, 21)
DUE = dt.date(2027, 3, 15)


def build(**changes: object) -> Timeline:
    return build_timeline(Scenario.model_validate({"birth_date": DUE, **changes}), PARAMS, TODAY)


def segment(timeline: Timeline, segment_id: str) -> Segment:
    return next(s for s in timeline.segments if s.id == segment_id)


def test_single_child_default_plan() -> None:
    t = build()
    m = segment(t, "maternity")
    assert (m.start, m.end, m.days, m.rate_percent) == (DUE, dt.date(2027, 8, 1), 140, 100)
    pm = segment(t, "parental-mother")
    assert (pm.start, pm.end, pm.days, pm.rate_percent) == (
        dt.date(2027, 8, 2),
        dt.date(2028, 3, 12),
        32 * 7,
        70,
    )
    pf = segment(t, "parental-father")
    assert (pf.start, pf.end, pf.days, pf.rate_percent) == (
        dt.date(2028, 3, 13),
        dt.date(2028, 5, 14),
        9 * 7,
        70,
    )
    p = segment(t, "paternity")
    assert (p.start, p.end, p.rate_percent, p.is_example) == (DUE, dt.date(2027, 3, 28), 100, True)


def test_markers() -> None:
    assert {m.id: m.date for m in build().markers} == {
        "birth": DUE,
        "flat-rate-deadline": dt.date(2027, 4, 5),
        "paternity-window-end": dt.date(2028, 3, 15),
        "parental-limit": dt.date(2033, 12, 31),
    }


def test_application_deadlines() -> None:
    apps = {a.id: a for a in build().applications}
    assert (apps["app-maternity"].due, apps["app-maternity"].is_deadline) == (DUE, False)
    assert apps["app-parental-mother"].due == dt.date(2027, 7, 12)  # 21 days before 02.08.2027
    assert apps["app-paternity"].due == dt.date(2027, 3, 8)  # 7 days before 15.03.2027
    assert apps["app-parental-father"].due == dt.date(2028, 2, 21)  # leap year 2028
    assert not any(a.passed for a in apps.values())


@pytest.mark.parametrize(
    ("children", "weeks"), [(1, 20), (2, 31), (3, 33), (4, 35), (5, 37), (7, 37)]
)
def test_maternity_weeks_by_children(children: int, weeks: int) -> None:
    assert segment(build(children_count=children), "maternity").days == weeks * 7


def test_twins_get_longer_parental_but_same_paternity() -> None:
    t = build(children_count=2)
    assert segment(t, "parental-mother").days == (43 - 9) * 7
    assert segment(t, "parental-father").days == 9 * 7
    assert segment(t, "paternity").days == 14


def test_leave_before_birth_is_part_of_maternity() -> None:
    t = build(maternity_weeks_before_birth=6)
    before, after = segment(t, "maternity-prenatal"), segment(t, "maternity")
    assert (before.start, before.end, before.days) == (
        dt.date(2027, 2, 1),
        dt.date(2027, 3, 14),
        42,
    )
    assert (after.start, after.end) == (DUE, dt.date(2027, 6, 20))
    assert before.days + after.days == 20 * 7
    assert next(a for a in t.applications if a.id == "app-maternity").due == dt.date(2027, 2, 1)


def test_more_than_six_weeks_before_birth_is_rejected() -> None:
    with pytest.raises(ScenarioError, match="najwyżej 6 tyg"):
        build(maternity_weeks_before_birth=7)


def test_flat_rate_variant() -> None:
    t = build(flat_rate=True)
    assert segment(t, "maternity").rate_percent == 81.5
    assert segment(t, "parental-mother").rate_percent == 81.5
    assert segment(t, "parental-father").rate_percent == 70  # the other parent's 9 weeks
    app = next(a for a in t.applications if a.id == "app-parental-mother")
    assert (app.due, app.is_deadline) == (dt.date(2027, 4, 5), True)


def test_paternity_must_end_before_child_turns_12_months() -> None:
    assert segment(build(paternity_start=dt.date(2028, 3, 1)), "paternity").end == dt.date(
        2028, 3, 14
    )
    with pytest.raises(ScenarioError, match="12 miesięcy"):
        build(paternity_start=dt.date(2028, 3, 2))
    with pytest.raises(ScenarioError, match="w dniu porodu"):
        build(paternity_start=DUE - dt.timedelta(days=1))


def test_expected_date_in_the_past_is_flagged() -> None:
    t = build_timeline(Scenario(birth_date=dt.date(2026, 11, 1)), PARAMS, TODAY)
    assert any("już minęła" in w for w in t.warnings)


def test_passed_application_deadlines_are_flagged() -> None:
    born = Scenario(birth_date=dt.date(2026, 11, 10), child_born=True)
    apps = {a.id: a for a in build_timeline(born, PARAMS, TODAY).applications}
    assert apps["app-paternity"].passed  # due 03.11.2026
    assert not apps["app-parental-mother"].passed


def test_every_element_has_a_source() -> None:
    for element in build(maternity_weeks_before_birth=2, flat_rate=True).elements():
        assert element.sources, element.id
        assert all(s.page or s.article for s in element.sources), element.id


def test_changed_elements_after_twins() -> None:
    single, twins = build(), build(children_count=2)
    changed = set(changed_element_ids(single, twins))
    assert {"maternity", "parental-mother", "parental-father", "app-parental-father"} <= changed
    assert not {"paternity", "birth", "app-paternity"} & changed
    assert changed_element_ids(None, single) == []


def test_missing_birth_date() -> None:
    with pytest.raises(ScenarioError):
        build_timeline(Scenario(), PARAMS, TODAY)


def test_summary_tiles() -> None:
    assert [(s.id, s.value, s.unit) for s in build(maternity_weeks_before_birth=2).summary] == [
        ("maternity", 20, "tyg."),
        ("parental", 41, "tyg."),
        ("paternity", 14, "dni"),
    ]
    assert [s.value for s in build(children_count=2).summary] == [31, 43, 14]
