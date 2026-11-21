"""Admin panel: parameter versions valid from a date, and what they change on the timeline."""

import datetime as dt
from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_param_store, get_today
from app.main import app
from app.services.param_versions import MemoryParamStore

TODAY = dt.date(2026, 11, 21)
DUE = TODAY + dt.timedelta(days=120)


@pytest.fixture
def client() -> Iterator[TestClient]:
    store = MemoryParamStore()
    app.dependency_overrides[get_today] = lambda: TODAY
    app.dependency_overrides[get_param_store] = lambda: store
    yield TestClient(app)
    app.dependency_overrides.clear()


def values(first: int = 20, before: int = 6, personal: int = 14) -> dict[str, Any]:
    return {
        "max_weeks_before_birth": before,
        "weeks_by_children": [first, 31, 33, 35, 37],
        "mother_personal_weeks": personal,
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
