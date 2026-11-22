"""The onboarding gives the facts the first timeline needs: both parents' work and insurance, who
pays, the amounts, and the mother's sick leave or the birth. Each one is a question fewer in the
chat. Expected values are written out by hand."""

import datetime as dt
from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_param_store, get_session_store, get_today
from app.assistant.describe import interview_questions
from app.engine import Scenario
from app.main import app
from app.services.param_versions import MemoryParamStore
from app.services.sessions import MemorySessionStore

TODAY = dt.date(2026, 11, 21)
SESSION = "5b0a7c52-9f3e-4c1d-8e2a-6d4b3f1a9c07"
URL = f"/api/session/{SESSION}/onboarding"


@pytest.fixture
def client() -> Iterator[TestClient]:
    store = MemorySessionStore()
    params = MemoryParamStore()
    app.dependency_overrides[get_today] = lambda: TODAY
    app.dependency_overrides[get_session_store] = lambda: store
    app.dependency_overrides[get_param_store] = lambda: params
    yield TestClient(app)
    app.dependency_overrides.clear()


def remaining(started: dict[str, Any]) -> list[str]:
    """The interview questions the chat still has to ask, by key."""
    return [q.key for q in interview_questions(Scenario.model_validate(started["scenario"]))]


EXPECTING_MOTHER = {
    "role": "mother",
    "child_born": False,
    "date": "2027-03-15",
    "children_count": 1,
    "work": "employment",
    "payer_size": "over-20",
    "pay": 7000,
    "partner": {"work": "employment", "payer_size": "up-to-20", "pay": 8000},
    "sick_leave": True,
    "sick_leave_start": "2026-10-01",
}


def test_a_mother_on_the_way_gives_both_parents_and_her_sick_leave(client: TestClient) -> None:
    started = client.put(URL, json=EXPECTING_MOTHER)
    assert started.status_code == 200, started.text
    scenario = started.json()["scenario"]
    assert {
        k: scenario[k]
        for k in (
            "work",
            "mother_work",
            "father_work",
            "mother_payer_size",
            "father_payer_size",
            "mother_pay",
            "father_pay",
            "sick_leave",
            "sick_leave_start",
            "sick_leave_end",
        )
    } == {
        "work": "employment",
        "mother_work": None,  # her own work stays in `work`
        "father_work": "employment",
        "mother_payer_size": "over-20",
        "father_payer_size": "up-to-20",
        "mother_pay": 7000.0,
        "father_pay": 8000.0,
        "sick_leave": True,
        "sick_leave_start": "2026-10-01",
        "sick_leave_end": None,
    }
    timeline = started.json()["timeline"]
    # The money lane is there from the start, for both parents.
    assert {p["lane"] for p in timeline["payments"]} == {"mother", "father"}
    assert "sick-pay" in [s["id"] for s in timeline["segments"]]
    # What is left for the chat: her decision before the birth, since when she is insured (the
    # sickness benefit), and the 81,5% choice. Nothing about the father, payers or amounts.
    assert started.json()["question"]["key"] == "leave-before-birth"
    assert remaining(started.json()) == ["leave-before-birth", "insured-since", "rate-815"]


def test_a_father_with_a_born_child_gives_the_mothers_facts(client: TestClient) -> None:
    started = client.put(
        URL,
        json={
            "role": "father",
            "child_born": True,
            "date": "2026-11-02",
            "children_count": 1,
            "work": "employment",
            "payer_size": "up-to-20",
            "pay": "unknown",
            "partner": {"work": "business", "insured": True, "pay": 5000},
            "hospital_care": False,
            "leave_before_birth_weeks": 2,
        },
    )
    assert started.status_code == 200, started.text
    scenario = started.json()["scenario"]
    assert (scenario["work"], scenario["mother_work"], scenario["father_work"]) == (
        "employment",
        "business",
        None,
    )
    assert (scenario["mother_insured"], scenario["mother_pay"], scenario["father_pay"]) == (
        True,
        5000.0,
        "unknown",
    )
    assert scenario["father_payer_size"] == "up-to-20"
    assert scenario["mother_payer_size"] is None  # a business files straight with ZUS
    assert (scenario["hospital_care"], scenario["leave_before_birth_weeks"]) == (False, 2)
    segments = {s["id"]: s for s in started.json()["timeline"]["segments"]}
    # 2 weeks before 2 November 2026: from 19 October to 1 November.
    assert (segments["maternity-prenatal"]["start"], segments["maternity-prenatal"]["end"]) == (
        "2026-10-19",
        "2026-11-01",
    )
    assert remaining(started.json()) == ["rate-815"]


def test_a_mother_without_the_voluntary_insurance_sees_it_at_once(client: TestClient) -> None:
    started = client.put(
        URL,
        json={
            "role": "mother",
            "child_born": False,
            "date": "2027-03-15",
            "children_count": 1,
            "work": "contract",
            "insured": False,
        },
    )
    assert started.status_code == 200, started.text
    assert started.json()["scenario"]["mother_insured"] is False
    # Not insured: no maternity leave to draw, and no question about it.
    assert not [s for s in started.json()["timeline"]["segments"] if s["lane"] == "mother"]
    assert started.json()["question"]["key"] == "father-work"


def test_not_knowing_leaves_the_question_to_the_chat(client: TestClient) -> None:
    started = client.put(
        URL,
        json={
            "role": "father",
            "child_born": False,
            "date": "2027-03-15",
            "children_count": 1,
            "work": "contract",
            "payer_size": "unknown",
            "partner": {"work": "contract"},
        },
    )
    assert started.status_code == 200, started.text
    keys = remaining(started.json())
    # His insurance and both amounts were not given; the mother's insurance comes first.
    assert keys[0] == "mother-insurance"
    assert "father-insurance" in keys
    assert "father-payer" not in keys  # "nie wiem" is an answer: not asked again


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"work": "employment", "insured": True}, "Dobrowolne ubezpieczenie"),
        ({"work": "business", "payer_size": "over-20"}, "Liczba osób u płatnika"),
        ({"work": "contract", "insured": False, "pay": 4000}, "Kwotę podaje tylko"),
        ({"work": "none", "payer_size": None, "pay": 4000}, "Kwotę podaje tylko"),
        ({"pay": 8}, "bardzo mała kwota"),
        ({"partner": {"work": "employment", "insured": False}}, "Dobrowolne ubezpieczenie"),
        ({"hospital_care": True}, "gdy dziecko już się urodziło"),
        (
            {"child_born": True, "date": "2026-11-02", "sick_leave": None}
            | {"sick_leave_start": None, "leave_before_birth_weeks": 2}
            | {"taken_in": {"kind": "adoption", "date": "2026-11-02"}},
            "przy przyjęciu dziecka",
        ),
        ({"child_born": True, "date": "2026-11-02"}, "gdy dziecko jest w drodze"),
        ({"sick_leave_start": None}, "data początku zwolnienia"),
        ({"sick_leave": False}, "tylko razem ze zwolnieniem"),
    ],
)
def test_answers_that_do_not_go_together_are_rejected(
    client: TestClient, change: dict[str, Any], message: str
) -> None:
    response = client.put(URL, json={**EXPECTING_MOTHER, **change})
    assert response.status_code == 422
    assert message in response.text


@pytest.mark.parametrize(
    ("weeks", "left"),
    [
        # 2 weeks before 15.03.2027: from 01.03.2027; the chat then asks for the doctor's note.
        (2, ["certificate", "insured-since", "rate-815"]),
        # Work until the birth: nothing more about the leave.
        (0, ["insured-since", "rate-815"]),
    ],
)
def test_a_mother_on_the_way_can_decide_her_leave_before_the_birth(
    client: TestClient, weeks: int, left: list[str]
) -> None:
    """Decision of 22.11.2026: the onboarding also asks when the leave starts, so the plan does
    not open with that choice; "not yet" (no answer) leaves it to the plan, as before."""
    started = client.put(URL, json={**EXPECTING_MOTHER, "leave_before_birth_weeks": weeks})
    assert started.status_code == 200, started.text
    assert started.json()["scenario"]["leave_before_birth_weeks"] == weeks
    assert remaining(started.json()) == left
    if weeks:
        segments = started.json()["timeline"]["segments"]
        leave = next(s for s in segments if s["id"] == "maternity-prenatal")
        assert leave["start"] == "2027-03-01"


def test_data_from_zus_leaves_only_the_decisions(client: TestClient) -> None:
    """The simulated download from ZUS also gives since when she is insured: with her sick leave
    known, the chat no longer asks it."""
    started = client.put(
        URL,
        json={
            **EXPECTING_MOTHER,
            "sick_leave_start": "2026-09-02",
            "sick_leave_end": "2026-09-15",
            "insured_since": "2023-03-01",
        },
    )
    assert started.status_code == 200, started.text
    assert started.json()["scenario"]["insured_since"] == "2023-03-01"
    assert remaining(started.json()) == ["leave-before-birth", "rate-815"]
    future = client.put(URL, json={**EXPECTING_MOTHER, "insured_since": "2026-12-01"})
    assert future.status_code == 422


def test_the_sick_leave_dates_are_checked(client: TestClient) -> None:
    future = client.put(URL, json={**EXPECTING_MOTHER, "sick_leave_start": "2026-12-01"})
    assert future.status_code == 422
    assert future.json()["detail"] == (
        "Zwolnienie lekarskie nie może zaczynać się w przyszłości. Sprawdź datę."
    )
    backwards = {**EXPECTING_MOTHER, "sick_leave_end": "2026-09-01"}
    assert client.put(URL, json=backwards).status_code == 422
    ended = client.put(URL, json={**EXPECTING_MOTHER, "sick_leave_end": "2026-10-14"})
    assert ended.json()["scenario"]["sick_leave_end"] == "2026-10-14"
