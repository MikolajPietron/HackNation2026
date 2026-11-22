"""The built frontend served by the API process (app/static.py)."""

from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.static import mount_frontend


def served(tmp_path: Path) -> TestClient:
    (tmp_path / "assets").mkdir()
    (tmp_path / "index.html").write_text("<!doctype html><title>plan</title>")
    (tmp_path / "assets" / "app-abc.js").write_text("console.log(1)")
    (tmp_path.parent / "secret.txt").write_text("no")
    app = FastAPI()

    @app.get("/api/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    assert mount_frontend(app, tmp_path)
    return TestClient(app)


def test_the_app_routes_get_the_page_and_files_get_themselves(tmp_path: Path) -> None:
    client = served(tmp_path)
    for route in ("/", "/admin", "/raport", "/plan/some-token"):
        page = client.get(route)
        assert page.status_code == 200 and "<title>plan</title>" in page.text
        assert page.headers["cache-control"] == "no-cache"
    script = client.get("/assets/app-abc.js")
    assert script.text == "console.log(1)"
    assert "immutable" in script.headers["cache-control"]


def test_the_api_stays_the_api_and_nothing_outside_the_build_is_served(tmp_path: Path) -> None:
    client = served(tmp_path)
    assert client.get("/api/health").json() == {"status": "ok"}
    assert client.get("/api/nothing-here").status_code == 404
    assert client.get("/%2e%2e/secret.txt").text != "no"


def test_without_a_build_nothing_is_mounted(tmp_path: Path) -> None:
    assert not mount_frontend(FastAPI(), tmp_path / "missing")
