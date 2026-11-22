"""F8, planning from a goal (engine/plans.py), POST /api/plans and the assistant's tool. Expected
values were computed by hand, not by the engine.

The standard family: the mother employed, 8000 zł a month; the father employed, 6000 zł; one
child born on 10.11.2026; today 21.11.2026, so the request for 81,5% can still be filed (until
10.11.2026 + 21 days = 01.12.2026).
- Bases: mother 8000 × 0,8629 = 6903,20 zł; father 6000 × 0,8629 = 5177,40 zł.
- A day: mother 100% 6903,20 / 30 = 230,1067 → 230,11; 70% 4832,24 / 30 = 161,0747 → 161,07;
  81,5% 5626,108 / 30 = 187,5369 → 187,54. Father 100% 172,58; 70% 3624,18 / 30 = 120,806 →
  120,81.
- Maternity leave 10.11.2026-29.03.2027 (140 days); paternity leave shown from today,
  21.11.2026-04.12.2026 (14 days); parental leave from 30.03.2027; the pool is 41 weeks, 32 at
  most for one parent; the last day for parental leave is 31.12.2032.
"""

import asyncio
import datetime as dt
import json
from collections.abc import AsyncIterator, Iterator
from typing import Any
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from pydantic_ai import ModelMessage, ModelRequest, ToolReturnPart
from pydantic_ai.models.function import AgentInfo, DeltaToolCall, DeltaToolCalls, FunctionModel

from app.api.deps import get_chat_model, get_param_store, get_session_store, get_today
from app.engine import Scenario, ScenarioError, build_timeline
from app.engine import plans as plans_module
from app.engine.models import ParentalPart
from app.engine.plans import Candidate, Plan, PlansResult, propose_plans
from app.main import app
from app.services.param_versions import MemoryParamStore
from app.services.params import load_params
from app.services.sessions import MemorySessionStore, Session

PARAMS = load_params()
TODAY = dt.date(2026, 11, 21)
BORN = dt.date(2026, 11, 10)
FAMILY: dict[str, Any] = {
    "role": "mother",
    "work": "employment",
    "father_work": "employment",
    "children_count": 1,
    "child_born": True,
    "birth_date": BORN,
    "leave_before_birth_weeks": 0,
    "mother_pay": 8000,
    "father_pay": 6000,
}


def plans_for(goal: str, today: dt.date = TODAY, **answers: Any) -> PlansResult:
    scenario = Scenario.model_validate({**FAMILY, **answers})
    return propose_plans(scenario, PARAMS, today, goal)  # type: ignore[arg-type]


def parts(plan: Plan) -> list[tuple[str, int, str | None]]:
    return [(p["parent"], p["weeks"], p["work_fraction"]) for p in plan.patch["parental_parts"]]


def d(text: str) -> dt.date:
    return dt.date.fromisoformat(text)


def test_most_money_compares_100_and_70_with_81_5_percent_for_the_whole_pool() -> None:
    """The whole pool: the mother 32 weeks 30.03-08.11.2027 (224 days), then the father 9 weeks
    09.11.2027-10.01.2028 (63 days).
    100% and 70%: mother 140 × 230,11 = 32 215,40 + 224 × 161,07 = 36 079,68 → 68 295,08;
    father 14 × 172,58 = 2416,12 + 63 × 120,81 = 7611,03 → 10 027,15; together 78 322,23 zł.
    81,5%: mother 364 × 187,54 = 68 264,56; the father's own 9 weeks stay at 70%: 10 027,15;
    together 78 291,71 zł, less, so it comes second. The father earns less than the mother, so
    no plan gives him the shared weeks: two plans."""
    result = plans_for("most-money")
    assert [p.id for p in result.plans] == ["whole-pool-100-70", "whole-pool-815"]
    first, second = result.plans
    assert parts(first) == [("mother", 32, None), ("father", 9, None)]
    assert (first.patch["rate_815"], second.patch["rate_815"]) == (False, True)
    assert (first.figures.mother.total, first.figures.father.total) == (68295.08, 10027.15)
    assert first.figures.total == 78322.23
    assert (second.figures.mother.total, second.figures.total) == (68264.56, 78291.71)
    assert first.figures.mother.back_to_work == d("2027-11-09")
    assert first.figures.home_until == d("2028-01-10")
    assert (first.figures.pool_used, first.figures.pool_total) == (41, 41)
    assert (first.figures.mother.leave_days, first.figures.father.leave_days) == (364, 77)
    assert "wniosek najpóźniej 01.12.2026" in second.summary
    assert "Za urlop macierzyński zasiłek wynosi 81,5% zamiast 100%." in second.given_up
    assert "parental-mother-1" in first.changed and not first.current
    assert {s.article for s in second.sources if s.doc == "ustawa"} >= {"art. 30a ust. 1"}
    # The current timeline: the parental shares are still options, so not counted.
    assert result.current is not None and result.current.total == 34631.52  # 32 215,40 + 2416,12


def test_most_money_gives_the_shared_weeks_to_the_parent_with_the_higher_base() -> None:
    """The father earns 12 000 zł: base 12 000 × 0,8629 = 10 354,80 zł, higher than the
    mother's, so a plan gives him the weeks the parents share: the mother 9 weeks, the father
    41 − 9 = 32.
    100% and 70%: mother 140 × 230,11 = 32 215,40 + 63 × 161,07 = 10 147,41 → 42 362,81; father
    paternity 14 × 345,16 (10 354,80 / 30) = 4832,24, parental 70% = 7248,36 / 30 = 241,612 →
    241,61 × 224 = 54 120,64 → 58 952,88; together 101 315,69 zł.
    81,5%: mother 203 × 187,54 = 38 070,62; father his own 63 days at 70% (63 × 241,61 =
    15 221,43), the 161 days the mother shares at 81,5% (8439,162 / 30 = 281,3054 → 281,31 ×
    161 = 45 290,91) and paternity 4832,24 → 65 344,58; together 103 415,20 zł, the most.
    The whole pool taken mostly by the mother: 100% and 70% 68 295,08 + 4832,24 + 15 221,43 =
    88 348,75; at 81,5% 68 264,56 + 4832,24 + 15 221,43 = 88 318,23, the fourth, left out."""
    result = plans_for("most-money", father_pay=12000)
    assert [p.id for p in result.plans] == [
        "father-shares-815",
        "father-shares-100-70",
        "whole-pool-100-70",
    ]
    assert [p.figures.total for p in result.plans] == [103415.2, 101315.69, 88348.75]
    best_100_70 = result.plans[1]
    assert parts(best_100_70) == [("mother", 9, None), ("father", 32, None)]
    assert best_100_70.figures.mother.total == 42362.81
    assert best_100_70.figures.father.total == 58952.88
    assert result.plans[0].figures.father.total == 65344.58


def test_longest_home_lengthens_the_leave_with_part_time_work() -> None:
    """Working 1/2 of full time through a part lengthens it by weeks × 1/2 (art. 182¹ᶠ § 2, in
    days with the incomplete day dropped, § 4).
    The mother: 32 × 7 × 1/2 = 112 days, so 224 + 112 = 336 days, 30.03.2027-28.02.2028 (2028
    is a leap year); the father: 63 × 1/2 = 31,5 → 31 days, so 94 days, 29.02-01.06.2028.
    Both working: at home with a parent until 01.06.2028; the mother alone: the father's 9 weeks
    29.02-01.05.2028; no work: until 10.01.2028.
    The mother's money while working: 70% less half = 2416,12 zł a month, a day 80,5373 → 80,54;
    224 × 80,54 = 18 040,96, then 112 × 161,07 = 18 039,84: with maternity leave 68 296,20."""
    result = plans_for("longest-home")
    assert [p.id for p in result.plans] == [
        "whole-pool-both-work",
        "whole-pool-mother-works",
        "whole-pool",
    ]
    both, mother, plain = result.plans
    assert parts(both) == [("mother", 32, "1/2"), ("father", 9, "1/2")]
    assert [p.figures.home_until for p in result.plans] == [
        d("2028-06-01"),
        d("2028-05-01"),
        d("2028-01-10"),
    ]
    assert mother.figures.mother.last_day == d("2028-02-28")
    assert (mother.figures.mother.leave_days, mother.figures.mother.work_days) == (476, 224)
    assert mother.figures.mother.total == 68296.2
    assert mother.figures.mother.back_to_work == d("2027-03-30")  # half-time from the start
    assert "urlop wydłuża się o 16 tyg." in mother.summary
    assert any("pracuje na 1/2 etatu" in g for g in mother.given_up)
    assert plain.patch["rate_815"] is None  # the goal is time: the rate stays the family's


def test_equal_split_makes_the_time_at_home_equal() -> None:
    """Equal time: the mother has 140 days of maternity leave, the father 14 of paternity
    leave, so his weeks f = (140 + 41 × 7 − 14) / 14 = 29,5 → 30 and hers 41 − 30 = 11: she 140
    + 77 = 217 days, he 14 + 210 = 224, a difference of 7.
    With the father taking over after 14 weeks: she 98 days of maternity leave, he 42 + 14 = 56,
    so f = (98 + 287 − 56) / 14 = 23,5 → 24 and hers 17: she 98 + 119 = 217, he 56 + 168 = 224.
    Parental leave halved: 20 and 21 weeks, she 140 + 140 = 280, he 14 + 147 = 161: 119 apart.
    Money of equal time: she 32 215,40 + 77 × 161,07 = 12 402,39 → 44 617,79; he 2416,12 + 210
    × 120,81 = 25 370,10 → 27 786,22."""
    result = plans_for("equal-split")
    assert [p.id for p in result.plans] == [
        "equal-time",
        "takeover-equal-time",
        "parental-halves",
    ]
    equal, takeover, halves = result.plans
    assert parts(equal) == [("mother", 11, None), ("father", 30, None)]
    assert parts(takeover) == [("mother", 17, None), ("father", 24, None)]
    assert parts(halves) == [("mother", 20, None), ("father", 21, None)]
    assert takeover.patch["father_takes_over"] is True
    assert takeover.patch["mother_weeks_before_takeover"] is None  # the minimum, 14 weeks
    days = [(p.figures.mother.leave_days, p.figures.father.leave_days) for p in result.plans]
    assert days == [(217, 224), (217, 224), (280, 161)]
    assert (equal.figures.mother.total, equal.figures.father.total) == (44617.79, 27786.22)
    assert "tata przejmuje resztę: od 16.02.2027 do 29.03.2027" in takeover.summary


def test_quick_return_puts_the_earliest_return_first() -> None:
    """The father takes over after 14 weeks: the mother back on 10.11.2026 + 98 days =
    16.02.2027; her 98 × 230,11 = 22 550,78 zł, his part 42 × 172,58 = 7248,36 + 2416,12.
    After maternity leave: back on 30.03.2027, nothing to plan (the family's current plan).
    Half-time after maternity leave: back (half-time) on 30.03.2027 too, on leave until
    28.02.2028, so it comes last."""
    result = plans_for("quick-return")
    assert [p.id for p in result.plans] == [
        "takeover",
        "after-maternity",
        "part-time-after-maternity",
    ]
    takeover, after, part_time = result.plans
    assert takeover.figures.mother.back_to_work == d("2027-02-16")
    assert takeover.figures.mother.total == 22550.78
    assert takeover.figures.father.total == 9664.48  # 7248,36 + 2416,12
    assert takeover.patch["parental_parts"] == []
    assert after.current and after.changed == []
    assert after.figures.mother.back_to_work == d("2027-03-30")
    assert any("najpóźniej do 31.12.2032" in g for g in after.given_up)
    assert part_time.figures.mother.back_to_work == d("2027-03-30")
    assert part_time.figures.mother.last_day == d("2028-02-28")


def test_amounts_unknown_compare_weeks_only() -> None:
    result = plans_for("most-money", mother_pay=None, father_pay=None)
    assert len(result.plans) == 2
    assert all(p.figures.total is None and not p.figures.amounts_known for p in result.plans)
    assert any("Kwot nie porównujemy" in n for n in result.notes)
    assert any("Bez kwot nie da się powiedzieć" in n for n in result.notes)


def test_no_81_5_percent_after_its_window() -> None:
    """Born on 01.10.2026: the request was due by 22.10.2026, before today. The plans keep 100%
    and 70% (the family said nothing about a request) and say why."""
    result = plans_for("most-money", birth_date=dt.date(2026, 10, 1))
    assert result.plans
    assert all(p.patch["rate_815"] is not True for p in result.plans)
    assert any("Termin na wniosek o 81,5% minął 22.10.2026" in n for n in result.notes)
    filed = plans_for("most-money", birth_date=dt.date(2026, 10, 1), rate_815=True)
    assert all(p.patch["rate_815"] is True for p in filed.plans)


def test_an_invalid_plan_is_never_returned(monkeypatch: pytest.MonkeyPatch) -> None:
    """The engine refuses these, so they are dropped: the mother over her 32 weeks, the pool
    over 41 weeks, six parts, work over half of full time, and parts of a parent who is not an
    employee combined with work."""

    def candidates(frame: plans_module.Frame) -> list[Candidate]:
        def make(id_: str, *made: ParentalPart) -> Candidate:
            return Candidate(id_, id_, tuple(made), None, None, None)

        return [
            make("too-long", ParentalPart(parent="mother", weeks=33)),
            make(
                "over-the-pool",
                ParentalPart(parent="mother", weeks=32),
                ParentalPart(parent="father", weeks=10),
            ),
            make("six-parts", *(ParentalPart(parent="mother", weeks=1) for _ in range(6))),
            make("too-much-work", ParentalPart(parent="mother", weeks=10, work_fraction="3/4")),
            make("valid", ParentalPart(parent="mother", weeks=10)),
        ]

    monkeypatch.setitem(plans_module.CANDIDATES, "most-money", candidates)
    result = plans_for("most-money")
    assert [p.id for p in result.plans] == ["valid"]

    contract = plans_for("longest-home", father_work="contract", father_insured=True)
    assert "whole-pool-both-work" not in [p.id for p in contract.plans]


@pytest.mark.parametrize("goal", ["most-money", "longest-home", "equal-split", "quick-return"])
@pytest.mark.parametrize(
    "answers",
    [
        {},
        {"child_born": False, "due_date": "2027-03-15", "birth_date": None},
        {"children_count": 2, "za_zyciem": True},
        {"work": "contract", "mother_insured": True, "father_work": "business"},
        {"father_work": "none", "father_pay": None},
    ],
)
def test_every_plan_fits_the_rules(goal: str, answers: dict[str, Any]) -> None:
    """Whatever the family: each plan, applied, builds without breaking a rule, stays within the
    pool, the 9 weeks of the other parent, 5 parts and half of full time."""
    scenario = Scenario.model_validate({**FAMILY, **answers})
    result = propose_plans(scenario, PARAMS, TODAY, goal)  # type: ignore[arg-type]
    for plan in result.plans:
        applied = Scenario.model_validate({**scenario.model_dump(), **plan.patch})
        build_timeline(applied, PARAMS, TODAY)
        pool = plan.figures.pool_total
        weeks = {"mother": 0, "father": 0}
        for part in applied.parental_parts:
            weeks[part.parent] += part.weeks
            assert part.work_fraction is None or part.work_fraction <= 0.5
        assert sum(weeks.values()) <= pool and max(weeks.values()) <= pool - 9
        assert len(applied.parental_parts) <= 5
    assert len(result.plans) <= 3


def test_no_plans_in_a_sensitive_situation_or_for_a_child_taken_in() -> None:
    lost = plans_for("most-money", losses=[{"died_on": "2026-11-15"}])
    assert lost.sensitive and lost.plans == [] and lost.reason
    adopted = plans_for(
        "most-money", taken_in="adoption", taken_in_on=dt.date(2026, 11, 1), birth_date=BORN
    )
    assert adopted.plans == [] and "przyjętego" in (adopted.reason or "")
    alone = plans_for("equal-split", father_work="none", father_pay=None)
    assert alone.plans == [] and alone.reason == (
        "Równy podział wymaga, żeby oboje rodzice mieli urlop rodzicielski."
    )


def test_a_broken_scenario_raises() -> None:
    with pytest.raises(ScenarioError):
        plans_for("most-money", parental_parts=[{"parent": "mother", "weeks": 40}])


# The API and the assistant.


@pytest.fixture
def client() -> Iterator[TestClient]:
    store = MemorySessionStore()
    params = MemoryParamStore()
    app.dependency_overrides[get_today] = lambda: TODAY
    app.dependency_overrides[get_session_store] = lambda: store
    app.dependency_overrides[get_param_store] = lambda: params
    yield TestClient(app)
    app.dependency_overrides.clear()


def scenario_json(**answers: Any) -> dict[str, Any]:
    return Scenario.model_validate({**FAMILY, **answers}).model_dump(mode="json")


def test_api_returns_plans_with_patches_to_apply(client: TestClient) -> None:
    response = client.post("/api/plans", json={"scenario": scenario_json(), "goal": "most-money"})
    assert response.status_code == 200, response.text
    body = response.json()
    first = body["plans"][0]
    assert first["patch"] == {
        "parental_parts": [
            {
                "parent": "mother",
                "weeks": 32,
                "start": None,
                "with_previous": False,
                "work_fraction": None,
                "work_weeks": None,
            },
            {
                "parent": "father",
                "weeks": 9,
                "start": None,
                "with_previous": False,
                "work_fraction": None,
                "work_weeks": None,
            },
        ],
        "rate_815": False,
        "father_takes_over": None,
        "mother_weeks_before_takeover": None,
    }
    assert first["figures"]["total"] == 78322.23
    bad = client.post(
        "/api/plans",
        json={
            "scenario": scenario_json(parental_parts=[{"parent": "mother", "weeks": 40}]),
            "goal": "most-money",
        },
    )
    assert bad.status_code == 422
    assert "najwyżej 32 tyg." in bad.json()["detail"]
    unknown = client.post("/api/plans", json={"scenario": scenario_json(), "goal": "fastest"})
    assert unknown.status_code == 422


SESSION = "7f1c8f0e-4d7a-4b52-9c35-0d8a4f1c2b12"


def scripted(tool: str, args: dict[str, Any], returned: list[str]) -> FunctionModel:
    """Call `tool` with `args`, keep what it returned, then answer."""

    async def stream(
        messages: list[ModelMessage], info: AgentInfo
    ) -> AsyncIterator[str | DeltaToolCalls]:
        last = messages[-1]
        answers = (
            [p for p in last.parts if isinstance(p, ToolReturnPart)]
            if isinstance(last, ModelRequest)
            else []
        )
        if answers:
            returned.extend(str(p.content) for p in answers)
            yield "Oto plany."
        else:
            yield {0: DeltaToolCall(tool, json.dumps(args), tool_call_id="call-1")}

    return FunctionModel(stream_function=stream)


def test_the_assistant_gets_the_plans_as_text_and_nothing_changes(client: TestClient) -> None:
    store = app.dependency_overrides[get_session_store]()
    scenario = scenario_json()
    asyncio.run(store.save(UUID(SESSION), Session.model_validate({"scenario": scenario})))
    returned: list[str] = []
    app.dependency_overrides[get_chat_model] = lambda: scripted(
        "propose_plans", {"goal": "quick-return"}, returned
    )
    out = client.post("/api/chat", json={"session_id": SESSION, "message": "Chcę szybko wrócić"})
    assert out.status_code == 200, out.text
    lines = [json.loads(line) for line in out.text.splitlines() if line]
    assert not any(e["type"] == "timeline" for e in lines)  # read-only: no recalculation
    text = returned[0]
    assert text.startswith("Plany dla celu „szybki powrót do pracy”")
    assert "1. Tata przejmuje urlop macierzyński po 14 tyg." in text
    assert "Mama: 14 tyg. urlopu, powrót do pracy 16.02.2027, zasiłki 22 550,78 zł." in text
    assert "set_father_takeover(takes_over=true)" in text
    assert "(to Wasz obecny plan)" in text
    saved = asyncio.run(store.load(UUID(SESSION)))
    assert saved is not None and saved.scenario == Scenario.model_validate(scenario)
