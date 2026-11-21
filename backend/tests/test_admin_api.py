"""Admin panel: parameter versions valid from a date, and what they change on the timeline."""

import datetime as dt
from collections.abc import Iterator
from typing import Any
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_param_store, get_today
from app.main import app
from app.services.param_versions import MemoryParamStore, ParamVersion
from app.services.params import load_params

TODAY = dt.date(2026, 11, 21)
DUE = TODAY + dt.timedelta(days=120)


@pytest.fixture
def client() -> Iterator[TestClient]:
    store = MemoryParamStore()
    app.dependency_overrides[get_today] = lambda: TODAY
    app.dependency_overrides[get_param_store] = lambda: store
    yield TestClient(app)
    app.dependency_overrides.clear()


def values(first: int = 20, before: int = 6, personal: int = 14, **more: Any) -> dict[str, Any]:
    return {
        "max_weeks_before_birth": before,
        "weeks_by_children": [first, 31, 33, 35, 37],
        "mother_personal_weeks": personal,
        "rate_full": 100.0,
        "rate_parental": 70.0,
        "rate_single": 81.5,
        "rate_single_request_days": 21,
        "parental_request_days": 21,
        "paternity_request_days": 7,
        "supplementary_request_days": 21,
        **more,
    }


def maternity_days(client: TestClient) -> int:
    response = client.post("/api/timeline", json={"due_date": DUE.isoformat(), "children_count": 1})
    assert response.status_code == 200
    segment = next(s for s in response.json()["segments"] if s["id"] == "maternity")
    return segment["days"]


def test_base_file_is_in_force_without_versions(client: TestClient) -> None:
    view = client.get("/api/admin/params").json()
    assert view["in_force"] == values()
    assert view["versions"] == []
    assert view["base"]["maternity"]["weeks_by_children"]["sources"]


def test_version_valid_today_changes_the_timeline(client: TestClient) -> None:
    assert maternity_days(client) == 20 * 7
    response = client.post(
        "/api/admin/params",
        json={"effective_from": TODAY.isoformat(), "note": "Nowelizacja", "values": values(22)},
    )
    assert response.status_code == 200
    view = response.json()
    assert view["in_force"]["weeks_by_children"][0] == 22
    assert view["versions"][0]["status"] == "in_force"
    assert maternity_days(client) == 22 * 7


def test_future_version_is_scheduled_not_in_force(client: TestClient) -> None:
    later = TODAY + dt.timedelta(days=40)
    view = client.post(
        "/api/admin/params",
        json={"effective_from": later.isoformat(), "note": "Od nowego roku", "values": values(24)},
    ).json()
    assert view["versions"][0]["status"] == "scheduled"
    assert view["in_force"]["weeks_by_children"][0] == 20
    assert maternity_days(client) == 20 * 7


def test_impossible_values_are_refused(client: TestClient) -> None:
    response = client.post(
        "/api/admin/params",
        json={"effective_from": TODAY.isoformat(), "note": "Błąd", "values": values(personal=21)},
    )
    assert response.status_code == 422
    assert "więcej niż całego urlopu" in response.json()["detail"]


def test_preview_compares_the_plan_before_and_after(client: TestClient) -> None:
    result = client.post("/api/admin/preview", json={"values": values(22)}).json()
    before = next(s for s in result["before"]["segments"] if s["id"] == "maternity")
    after = next(s for s in result["after"]["segments"] if s["id"] == "maternity")
    assert (before["days"], after["days"]) == (20 * 7, 22 * 7)


# Rates of the benefit and deadlines of the requests (the brief names the rate explicitly).


def find(items: list[dict[str, Any]], item_id: str) -> dict[str, Any]:
    return next(i for i in items if i["id"] == item_id)


def test_rates_and_deadlines_are_in_the_panel(client: TestClient) -> None:
    view = client.get("/api/admin/params").json()
    assert view["in_force"] == values()
    assert view["base"]["money"]["rate_single"]["sources"]
    assert view["base"]["applications"]["paternity_days_before"]["sources"]


def test_preview_shows_a_new_rate_and_new_deadlines(client: TestClient) -> None:
    # Due 21.03.2027 (today + 120 days). The example mother earns 6000 zł: base 6000 less
    # 13,71% = 5177,40 zł; parental leave at 70% = 3624,18 zł, at 75% = 3883,05 zł a month.
    draft = values(rate_parental=75.0, paternity_request_days=14, rate_single_request_days=28)
    result = client.post("/api/admin/preview", json={"values": draft}).json()
    before, after = result["before"], result["after"]
    assert find(before["payments"], "pay-parental")["monthly"] == 3624.18
    assert find(after["payments"], "pay-parental")["monthly"] == 3883.05
    # Paternity leave from the due date: its request 7 days before, now 14.
    assert find(before["documents"], "paternity-request")["needed_by"] == "2027-03-14"
    assert find(after["documents"], "paternity-request")["needed_by"] == "2027-03-07"
    # The last day for the 81,5% request: 21 days after the birth, now 28.
    assert find(before["markers"], "rate-815-deadline")["date"] == "2027-04-11"
    assert find(after["markers"], "rate-815-deadline")["date"] == "2027-04-18"


def test_preview_with_the_request_for_the_single_rate(client: TestClient) -> None:
    body = {"values": values(rate_single=85.0), "rate_815": True}
    result = client.post("/api/admin/preview", json=body).json()
    rates = [
        find(t["payments"], "pay-maternity")["rate"] for t in (result["before"], result["after"])
    ]
    assert rates == [81.5, 85.0]


def test_a_saved_rate_changes_the_amounts(client: TestClient) -> None:
    response = client.post(
        "/api/admin/params",
        json={
            "effective_from": TODAY.isoformat(),
            "note": "Nowa stopa",
            "values": values(rate_parental=75.0),
        },
    )
    assert response.status_code == 200
    assert response.json()["in_force"]["rate_parental"] == 75.0
    timeline = client.post(
        "/api/timeline",
        json={"due_date": DUE.isoformat(), "children_count": 1, "role": "mother"}
        | {"work": "employment", "mother_pay": 6000},
    ).json()
    assert find(timeline["payments"], "pay-parental")["rate"] == 75.0


@pytest.mark.parametrize(
    ("changed", "message"),
    [
        ({"rate_full": 120.0}, "nie większa niż 100%"),
        ({"rate_parental": 0.0}, "większa od 0%"),
        ({"paternity_request_days": 0}, "między 1 a 90 dni"),
    ],
)
def test_impossible_rates_and_deadlines_are_refused(
    client: TestClient, changed: dict[str, Any], message: str
) -> None:
    response = client.post("/api/admin/preview", json={"values": values(**changed)})
    assert response.status_code == 422
    assert message in response.json()["detail"]


# A version saved before new blocks of parameters existed (Supabase keeps it as JSON).


NEW_BLOCKS = ("pregnancy", "applications", "parental_plan", "taken_in", "money")


def old_row(**params: Any) -> dict[str, Any]:
    """A stored version as the table returns it: saved when the engine knew only the mother's
    leave, with an older quote and 22 weeks for one child."""
    stored = load_params().model_dump(mode="json")
    for block in NEW_BLOCKS:
        del stored[block]
    stored["version"] = "2026.1+1"
    stored["maternity"]["weeks_by_children"]["value"][0] = 22
    stored["maternity"]["weeks_by_children"]["sources"][0]["quote"] = "Stary cytat."
    return {
        "id": str(uuid4()),
        "version": "2026.1+1",
        "effective_from": "2026-11-01",
        "note": "Wersja sprzed nowych bloków",
        "params": stored | params,
        "created_at": "2026-11-01T10:00:00+00:00",
    }


class RowStore:
    """Like the Supabase store: rows as JSON, validated when listed."""

    name = "rows"

    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self.rows = rows

    async def list(self) -> list[ParamVersion]:
        return [ParamVersion.model_validate(row) for row in self.rows]

    async def add(self, version: ParamVersion) -> None:
        self.rows.append(version.model_dump(mode="json"))


def test_an_old_version_is_read_onto_the_base_file() -> None:
    base = load_params()
    applications = base.model_dump(mode="json")["applications"]
    applications["parental_days_before"]["value"] = 28
    for key in [k for k in applications if k.startswith("sick_")]:
        del applications[key]  # saved before the sick-leave forms existed
    version = ParamVersion.model_validate(
        old_row(applications=applications, money={"rate_full": {"value": "sto"}})
    )
    params = version.params
    assert params.version == "2026.1+1"
    # Its numbers win...
    assert params.maternity.weeks_by_children.value == [22, 31, 33, 35, 37]
    assert params.applications.parental_days_before.value == 28
    # ...sources and rules come from the base file, and so do blocks it lacks...
    assert params.maternity.weeks_by_children.sources == base.maternity.weeks_by_children.sources
    assert params.applications.sick_e_zla == base.applications.sick_e_zla
    assert params.pregnancy == base.pregnancy
    assert params.taken_in == base.taken_in
    # ...and a block whose numbers no longer fit.
    assert params.money == base.money


def test_an_old_version_in_the_table_still_drives_the_calculator() -> None:
    store = RowStore([old_row()])
    app.dependency_overrides[get_today] = lambda: TODAY
    app.dependency_overrides[get_param_store] = lambda: store
    try:
        client = TestClient(app)
        view = client.get("/api/admin/params")
        assert view.status_code == 200
        assert view.json()["in_force"] == values(22)
        assert view.json()["versions"][0]["status"] == "in_force"
        assert maternity_days(client) == 22 * 7
    finally:
        app.dependency_overrides.clear()
