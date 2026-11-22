"""Example cases: the catalogue numbering, page rendering, facts -> scenario, the insurance check
and the comparison with ZUS, and the API with a fake reader (no key, no network). Real cases are
confidential and never in the repo: files here are made up and drawn with Pillow."""

import datetime as dt
import io
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image, ImageDraw

from app.api.cases import get_case_cache, get_cases_folder, get_reader_factory
from app.api.deps import get_today
from app.cases.assess import assess, check_insurance, compare, to_scenario
from app.cases.cache import CaseCache
from app.cases.catalog import list_case_files
from app.cases.models import CaseFacts, Decision, InsurancePeriod, LeavePeriod, PayMonth
from app.cases.pages import render_pages
from app.main import app
from app.services.params import load_params

TODAY = dt.date(2026, 11, 22)


def fake_pdf(pages: int = 3, blank: tuple[int, ...] = ()) -> bytes:
    images = []
    for number in range(1, pages + 1):
        image = Image.new("RGB", (850, 1100), "white")
        if number not in blank:
            draw = ImageDraw.Draw(image)
            for row in range(40):
                draw.rectangle((60, 80 + row * 24, 790, 92 + row * 24), fill="black")
        images.append(image)
    out = io.BytesIO()
    images[0].save(out, format="PDF", save_all=True, append_images=images[1:])
    return out.getvalue()


def facts(**changes: object) -> CaseFacts:
    base = CaseFacts(
        summary="Mama wnioskuje o zasiłek macierzyński po porodzie.",
        applicant="mother",
        benefit_requested="zasiłek macierzyński",
        child_born=True,
        birth_date=dt.date(2026, 3, 10),
        due_date=None,
        children_count=1,
        documents=[],
        insurance=[
            InsurancePeriod(
                person="mother",
                title="employment",
                label="umowa o pracę",
                start=dt.date(2024, 1, 1),
                end=None,
                sickness="mandatory",
                pages=[3],
            )
        ],
        leaves=[
            LeavePeriod(person="mother", kind="maternity", start=dt.date(2026, 3, 10), pages=[1])
        ],
        pay=[
            PayMonth(month=f"2025-{m:02d}", amount=6000, kind="salary", person="mother", pages=[4])
            for m in range(1, 13)
        ],
        decision=Decision(outcome="granted", benefit="zasiłek macierzyński", reason="", pages=[9]),
    )
    return base.model_copy(update=changes)


# ---------------------------------------------------------------------------------------------
# Catalogue


def test_catalogue_numbers_cases_like_the_data_pipeline(tmp_path: Path) -> None:
    # Categories come from the names, in the order of tools/zus-data/build_catalog.py.
    for name in [
        "Kowalska macierzyński.pdf",
        "Nowak odmowa.pdf",
        "Lis urlop ojcowski.pdf",
        "Nowak odmowa (1).pdf",  # the duplicate is skipped
        "notatka.txt",
    ]:
        (tmp_path / name).write_bytes(b"%PDF-1.4")
    cases = list_case_files(tmp_path)
    assert [(c.id, c.category) for c in cases] == [
        ("S01", "Odmowa"),
        ("S02", "Urlop ojcowski"),
        ("S03", "Macierzyński"),
    ]


def test_blank_pages_are_found() -> None:
    pages = render_pages(fake_pdf(3, blank=(2,)))
    assert [p.blank for p in pages] == [False, True, False]
    assert all(len(p.tiles) == 2 for p in pages), "every page goes as two halves"
    assert all(tile.startswith(b"\xff\xd8") for p in pages for tile in p.tiles)


# ---------------------------------------------------------------------------------------------
# Facts -> answers


def test_employee_case_becomes_a_scenario_with_her_pay() -> None:
    scenario, notes = to_scenario(facts())
    assert scenario.role == "mother"
    assert scenario.work == "employment"
    assert scenario.child_born is True
    assert scenario.birth_date == dt.date(2026, 3, 10)
    assert scenario.leave_before_birth_weeks == 0
    assert scenario.mother_pay == 6000
    assert any("średniej przychodu z Z-3 z 12 mies." in note for note in notes)


def test_leave_before_the_birth_is_its_first_day() -> None:
    early = [LeavePeriod(person="mother", kind="maternity", start=dt.date(2026, 2, 20), pages=[1])]
    scenario, _ = to_scenario(facts(leaves=early))
    assert scenario.leave_start == dt.date(2026, 2, 20)


def test_sick_leave_earlier_in_pregnancy_does_not_move_the_day_of_the_right() -> None:
    leaves = [
        LeavePeriod(person="mother", kind="sick", start=dt.date(2026, 1, 5), pages=[4]),
        LeavePeriod(person="mother", kind="maternity", start=dt.date(2026, 3, 10), pages=[1]),
    ]
    assert check_insurance(facts(leaves=leaves)).on == dt.date(2026, 3, 10)


def test_parental_leave_asked_for_becomes_the_plan() -> None:
    parental = LeavePeriod(
        person="mother",
        kind="parental",
        start=dt.date(2026, 7, 28),
        end=dt.date(2027, 3, 8),
        pages=[3],
    )
    case = facts(leaves=[*facts().leaves, parental, parental.model_copy(update={"pages": [9]})])
    scenario, _ = to_scenario(case)
    assert [(p.parent, p.weeks) for p in scenario.parental_parts] == [("mother", 32)]


def test_insured_on_the_day_the_right_arises() -> None:
    check = check_insurance(facts())
    assert check.covered is True
    assert check.on == dt.date(2026, 3, 10)
    assert check.text.startswith("Mama podlega ubezpieczeniu chorobowemu")


def test_contract_ended_before_the_birth_means_no_insurance() -> None:
    ended = [
        InsurancePeriod(
            person="mother",
            title="employment",
            label="umowa o pracę na czas określony",
            start=dt.date(2025, 1, 1),
            end=dt.date(2026, 2, 28),
            sickness="mandatory",
            pages=[2],
        )
    ]
    case = facts(
        insurance=ended, decision=Decision(outcome="refused", benefit="", reason="", pages=[])
    )
    check = check_insurance(case)
    assert check.covered is False
    assert "28 lutego 2026" in check.text
    result = compare(case, check)
    assert (result.ours, result.zus, result.match) == ("refused", "refused", True)


def test_refusal_for_another_reason_is_shown_as_a_difference() -> None:
    case = facts(
        decision=Decision(
            outcome="refused", benefit="", reason="Umowa zawarta dla pozoru.", pages=[7]
        )
    )
    result = compare(case, check_insurance(case))
    assert result.match is False
    assert "z innego powodu" in result.text


def test_a_premature_child_in_hospital_gets_what_supplementary_leave_needs() -> None:
    from app.cases.models import HospitalPeriod

    case = facts(
        birth_week=29,
        birth_weight_grams=650,
        hospital_stays=[HospitalPeriod(start=dt.date(2026, 3, 10), end=dt.date(2026, 5, 20))],
    )
    scenario, _ = to_scenario(case)
    assert scenario.birth_week == "28-37"
    assert scenario.birth_weight_up_to_1000g is True
    assert scenario.hospital_care is True
    assert scenario.hospital_stays[0].end == dt.date(2026, 5, 20)
    result = assess(
        case, case_id="S99", pages=1, pages_read=1, cached=False, params=load_params(), today=TODAY
    )
    assert result.timeline is not None
    assert any(s.id == "supplementary" for s in result.timeline.segments)


def test_assess_builds_the_timeline_with_amounts() -> None:
    result = assess(
        facts(),
        case_id="S99",
        pages=10,
        pages_read=9,
        cached=False,
        params=load_params(),
        today=TODAY,
    )
    assert result.problem is None
    assert result.timeline is not None
    assert result.timeline.payments, "the pay from Z-3 gives amounts"
    assert result.comparison.match is True


def test_no_date_means_no_timeline_but_still_an_answer() -> None:
    result = assess(
        facts(birth_date=None, child_born=None, leaves=[]),
        case_id=None,
        pages=1,
        pages_read=1,
        cached=False,
        params=load_params(),
        today=TODAY,
    )
    assert result.timeline is None
    assert result.problem


# ---------------------------------------------------------------------------------------------
# API


class FakeReader:
    def __init__(self) -> None:
        self.calls = 0

    async def read(self, pages: list) -> CaseFacts:  # noqa: ANN001
        self.calls += 1
        assert pages, "blank pages are skipped, the rest is sent"
        return facts()


@pytest.fixture
def client(tmp_path: Path):
    folder = tmp_path / "sprawy"
    folder.mkdir()
    (folder / "Kowalska macierzyński.pdf").write_bytes(fake_pdf(3, blank=(3,)))
    reader = FakeReader()
    app.dependency_overrides[get_cases_folder] = lambda: folder
    app.dependency_overrides[get_case_cache] = lambda: CaseCache(tmp_path / "cache")
    app.dependency_overrides[get_reader_factory] = lambda: lambda: reader
    app.dependency_overrides[get_today] = lambda: TODAY
    with TestClient(app) as test_client:
        test_client.reader = reader  # type: ignore[attr-defined]
        yield test_client
    app.dependency_overrides.clear()


def test_list_shows_ids_and_categories_but_no_file_names(client: TestClient) -> None:
    body = client.get("/api/cases").json()
    assert body["configured"] is True
    assert body["cases"] == [
        {"id": "S01", "category": "Macierzyński", "title": "", "pages": 3, "read": False}
    ]
    assert "Kowalska" not in str(body)


def test_a_case_is_read_once_then_comes_from_the_cache(client: TestClient) -> None:
    first = client.post("/api/cases/S01/read").json()
    assert first["id"] == "S01"
    assert (first["pages"], first["pages_read"], first["cached"]) == (3, 2, False)
    assert first["insurance"]["covered"] is True
    again = client.post("/api/cases/S01/read").json()
    assert again["cached"] is True
    assert client.reader.calls == 1  # type: ignore[attr-defined]
    assert client.get("/api/cases").json()["cases"][0]["read"] is True


def test_an_uploaded_catalogue_file_keeps_its_id(client: TestClient, tmp_path: Path) -> None:
    data = (tmp_path / "sprawy" / "Kowalska macierzyński.pdf").read_bytes()
    result = client.post(
        "/api/cases/upload", files={"file": ("sprawa.pdf", data, "application/pdf")}
    )
    assert result.status_code == 200
    assert result.json()["id"] == "S01"


def test_upload_rejects_other_files(client: TestClient) -> None:
    result = client.post("/api/cases/upload", files={"file": ("a.txt", b"hello", "text/plain")})
    assert result.status_code == 415


def test_corrected_facts_are_recalculated_without_ai(client: TestClient) -> None:
    corrected = facts(children_count=2).model_dump(mode="json")
    result = client.post("/api/cases/assess", json={"id": "S01", "facts": corrected}).json()
    assert result["scenario"]["children_count"] == 2
    assert client.reader.calls == 0  # type: ignore[attr-defined]


def test_a_case_loads_into_the_plan(client: TestClient) -> None:
    scenario = to_scenario(facts())[0].model_dump(mode="json")
    session = "8b0c7f1e-3c2a-4f6b-9d7e-2a1b3c4d5e6f"
    start = client.put(f"/api/cases/session/{session}", json={"scenario": scenario}).json()
    assert start["scenario"]["birth_date"] == "2026-03-10"
    restored = client.get(f"/api/session/{session}").json()
    assert restored["scenario"]["mother_pay"] == 6000


def test_the_report_sets_read_cases_against_zus(client: TestClient) -> None:
    empty = client.get("/api/cases/report").json()
    assert (empty["read"], empty["decided"], empty["agree"]) == (0, 0, 0)
    assert empty["rows"][0] == {**empty["rows"][0], "id": "S01", "read": False}
    client.post("/api/cases/S01/read")
    report = client.get("/api/cases/report").json()
    assert (report["read"], report["decided"], report["agree"]) == (1, 1, 1)
    row = report["rows"][0]
    assert (row["zus"], row["ours"], row["match"]) == ("granted", "granted", True)
    assert row["insurance"].startswith("Mama podlega")
