"""F24 "Przetłumacz pismo z ZUS": a made-up letter (drawn with Pillow) read by a scripted model
(no key, no network). The model's answer carries personal data on purpose: none of it may reach
the parent's answer or the log. Dates the letter does not state are dropped."""

import datetime as dt
import io
import json
import logging
from collections.abc import Iterator
from typing import Any

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from PIL import Image, ImageDraw
from pydantic_ai import BinaryContent
from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    ModelResponse,
    ToolCallPart,
    UserPromptPart,
)
from pydantic_ai.models.function import AgentInfo, FunctionModel

from app.api.deps import get_param_store, get_session_store, get_today
from app.api.document_model import allowed, get_document_model_factory
from app.config import Settings
from app.engine import Scenario
from app.letters.explain import explain, timeline_elements
from app.letters.models import LetterReading
from app.letters.privacy import Scrubber
from app.main import app
from app.services.param_versions import MemoryParamStore
from app.services.params import load_params
from app.services.sessions import MemorySessionStore, Session

TODAY = dt.date(2026, 11, 22)
SESSION = "5f0c7f1e-3c2a-4f6b-9d7e-2a1b3c4d5e60"

NAME, PESEL, STREET = "Anna Kowalska", "85010112345", "ul. Długa 5/3, 00-950 Warszawa"
SECRETS = ("Kowalsk", "Anna", "Anny", PESEL, "Długa 5", "00-950", "600 700 800")


def letter_image(lines: int = 30) -> bytes:
    image = Image.new("RGB", (900, 1250), "white")
    draw = ImageDraw.Draw(image)
    for row in range(lines):
        draw.rectangle((70, 90 + row * 32, 830, 104 + row * 32), fill="black")
    out = io.BytesIO()
    image.save(out, format="PNG")
    return out.getvalue()


def quote(text: str, page: int = 1) -> dict[str, Any]:
    return {"text": text, "page": page}


def reading(**changes: Any) -> dict[str, Any]:
    """A summons to complete documents for the maternity benefit, as the model would fill it."""
    base: dict[str, Any] = {
        "is_zus_letter": True,
        "kind": "summons",
        "heading": "WEZWANIE",
        "subject": f"ZUS prosi {NAME} o dokumenty do zasiłku macierzyńskiego.",
        "benefits": ["maternity"],
        "outcome": "none",
        "summary": (
            f"Pani {NAME} (PESEL {PESEL}, {STREET}) musi dostarczyć zaświadczenie Z-3 "
            "i wniosek ZUR. Telefon do Anny Kowalskiej: 600 700 800."
        ),
        "reason": None,
        "actions": [
            {
                "what": "Dostarcz do ZUS zaświadczenie płatnika składek Z-3.",
                "deadline_text": "do 15 grudnia 2026 r.",
                "deadline_date": "2026-12-15",
                "quote": quote(f"Wzywamy Panią {NAME} do dostarczenia Z-3 do 15 grudnia 2026 r."),
            },
            {
                "what": "Złóż wniosek o zasiłek.",
                "deadline_text": "w terminie 7 dni od dnia doręczenia pisma",
                # Computed by the model from "7 dni": not written in the letter.
                "deadline_date": "2026-11-29",
                "quote": quote("w terminie 7 dni od dnia doręczenia pisma", page=2),
            },
        ],
        "prepare": [
            {
                "text": "Zaświadczenie płatnika składek Z-3 od pracodawcy.",
                "quote": quote("zaświadczenie płatnika składek Z-3"),
            }
        ],
        "periods": [
            {
                "benefit": "maternity",
                "start": "2026-10-01",
                "end": "2027-02-17",
                "quote": quote("za okres od 01.10.2026 r. do 17.02.2027 r."),
            }
        ],
        "appeal": None,
        "forms": ["Z-3", "ZUR", "ZUS-X1"],
        "personal_data": [NAME, PESEL, STREET],
        "unreadable": [],
    }
    return base | changes


def scripted(answer: dict[str, Any], seen: list[list[ModelMessage]] | None = None) -> FunctionModel:
    def function(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        if seen is not None:
            seen.append(messages)
        tool = info.output_tools[0].name
        return ModelResponse(parts=[ToolCallPart(tool_name=tool, args=json.dumps(answer))])

    return FunctionModel(function, model_name="claude-test")


@pytest.fixture
def store() -> MemorySessionStore:
    return MemorySessionStore()


@pytest.fixture
def client(store: MemorySessionStore) -> Iterator[TestClient]:
    app.dependency_overrides[get_today] = lambda: TODAY
    app.dependency_overrides[get_session_store] = lambda: store
    params = MemoryParamStore()
    app.dependency_overrides[get_param_store] = lambda: params
    yield TestClient(app)
    app.dependency_overrides.clear()


def use_model(model: FunctionModel) -> None:
    app.dependency_overrides[get_document_model_factory] = lambda: lambda: model


def upload(client: TestClient, data: bytes, **form: str) -> Any:
    return client.post(
        "/api/letters/explain", files={"file": ("pismo.png", data, "image/png")}, data=form
    )


def test_a_letter_is_explained_without_personal_data(
    client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    seen: list[list[ModelMessage]] = []
    use_model(scripted(reading(), seen))
    with caplog.at_level(logging.DEBUG):
        response = upload(client, letter_image())
    assert response.status_code == 200, response.text
    body = response.json()

    # Marked as AI, with the model that read it.
    assert body["ai"] is True
    assert body["model"] == "claude-test"
    assert "AI" in body["ai_label"]
    assert (body["kind"], body["kind_label"]) == ("summons", "Wezwanie")
    assert body["action_needed"] is True
    assert (body["pages"], body["pages_read"]) == (1, 1)

    # Personal data never leaves: not in the answer, not in the log.
    text = json.dumps(body, ensure_ascii=False)
    for secret in SECRETS:
        assert secret not in text, secret
        assert secret not in caplog.text, secret
    assert "personal_data" not in body
    assert body["personal_data_removed"] is True
    assert "zaświadczenie Z-3" in body["summary"]

    # The model got the page as images, in two halves.
    request = seen[0][0]
    assert isinstance(request, ModelRequest)
    parts = [p for p in request.parts if isinstance(p, UserPromptPart)]
    images = [c for p in parts for c in p.content if isinstance(c, BinaryContent)]
    assert len(images) == 2


def test_dates_come_from_the_letter_never_from_the_model(client: TestClient) -> None:
    use_model(scripted(reading()))
    body = upload(client, letter_image()).json()
    written, computed = body["actions"]
    assert written["deadline_date"] == "2026-12-15"
    assert computed["deadline_date"] is None, "7 days from delivery is not a date in the letter"
    assert computed["deadline_text"] == "w terminie 7 dni od dnia doręczenia pisma"
    assert any("29.11.2026 nie jest zapisana" in w for w in body["warnings"])
    assert any("od dnia doręczenia" in w for w in body["warnings"])
    period = body["periods"][0]
    assert (period["start"], period["end"]) == ("2026-10-01", "2027-02-17")
    assert [q["page"] for q in body["quotes"]] == sorted(q["page"] for q in body["quotes"])


def test_forms_are_named_from_the_guide_and_abolished_ones_flagged(client: TestClient) -> None:
    use_model(scripted(reading()))
    body = upload(client, letter_image()).json()
    forms = {f["code"]: f for f in body["forms"]}
    assert set(forms) == {"Z-3", "ZUR"}
    assert forms["ZUR"]["abolished"] is True
    assert forms["ZUR"]["merged_into"] == "ZAM"
    assert any(s["page"] == 12 for s in forms["ZUR"]["sources"])
    assert forms["Z-3"]["abolished"] is False
    assert body["other_forms"] == ["ZUS-X1"]
    assert any("Pismo wymienia formularz ZUR" in w and "złóż ZAM" in w for w in body["warnings"])


def test_timeline_elements_follow_the_session(
    client: TestClient, store: MemorySessionStore
) -> None:
    use_model(scripted(reading()))
    alone = upload(client, letter_image()).json()["timeline_elements"]
    assert "maternity" in alone and "maternity-request" in alone

    scenario = Scenario(
        role="mother",
        work="employment",
        child_born=True,
        birth_date=dt.date(2026, 10, 1),
        children_count=1,
        leave_before_birth_weeks=0,
    )
    import asyncio
    from uuid import UUID

    asyncio.run(store.save(UUID(SESSION), Session(scenario=scenario)))
    on_timeline = upload(client, letter_image(), session_id=SESSION).json()["timeline_elements"]
    assert on_timeline == ["maternity", "maternity-request"]


def test_a_failing_model_does_not_repeat_the_letter(client: TestClient) -> None:
    def broken(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        raise RuntimeError(f"cannot read {NAME} {PESEL}")

    use_model(FunctionModel(broken))
    response = upload(client, letter_image())
    assert response.status_code == 502
    assert NAME not in response.text and PESEL not in response.text


def test_files_that_are_no_letter_are_refused(client: TestClient) -> None:
    use_model(scripted(reading()))
    assert upload(client, b"hello").status_code == 415
    assert upload(client, letter_image(lines=0)).status_code == 422, "a blank photo"
    images = [Image.new("RGB", (200, 280), "white") for _ in range(11)]
    out = io.BytesIO()
    images[0].save(out, format="PDF", save_all=True, append_images=images[1:])
    response = client.post(
        "/api/letters/explain", files={"file": ("pismo.pdf", out.getvalue(), "application/pdf")}
    )
    assert response.status_code == 413


# ---------------------------------------------------------------------------------------------
# Deterministic parts


def test_personal_data_is_removed_but_dates_and_amounts_stay() -> None:
    scrub = Scrubber(["MAJA KOWALSKA", "Jan", STREET])
    text = (
        "Pani Maja Kowalska (Majki Kowalskiej, MAJA KOWALSKA), mąż Jan (Jana), PESEL 85010112345, "
        "ul. Długa 5/3, 00-950 Warszawa, tel. +48 600 700 800, konto PL61 1090 1014 0000 0712 "
        "1981 2874, e-mail maja@example.pl. Decyzja z 1 maja 2027 r.: zasiłek od 01.10.2026 do "
        "2027-02-17 w kwocie 6 000,00 zł. Długo czekasz?"
    )
    clean = scrub(text)
    for secret in ("Kowalsk", "KOWALSK", "Maj", "Jan", "85010112345", "Długa 5", "600"):
        assert secret not in clean, secret
    assert "PL61" not in clean and "example.pl" not in clean and "00-950" not in clean
    for kept in ("1 maja 2027", "01.10.2026", "2027-02-17", "6 000,00 zł", "Długo czekasz?"):
        assert kept in clean, kept
    assert scrub.removed is True
    assert Scrubber([])("Nic osobowego.") == "Nic osobowego."


def test_free_text_dates_not_in_the_quotes_are_flagged() -> None:
    letter = LetterReading.model_validate(
        reading(summary="Masz czas do 1 grudnia 2026.", personal_data=[])
    )
    result = explain(letter, model="m", pages=1, pages_read=1, params=load_params())
    assert any("1.12.2026" in w or "01.12.2026" in w for w in result.warnings)


def test_a_quote_from_a_page_the_letter_lacks_is_flagged() -> None:
    letter = LetterReading.model_validate(reading(personal_data=[]))
    result = explain(letter, model="m", pages=1, pages_read=1, params=load_params())
    assert any("ma numer strony 2, a pismo ma 1 str." in w for w in result.warnings)
    two_pages = explain(letter, model="m", pages=2, pages_read=2, params=load_params())
    assert not any("numer strony" in w for w in two_pages.warnings)


def test_a_letter_that_is_not_from_zus_says_so() -> None:
    letter = LetterReading.model_validate(
        reading(is_zus_letter=False, kind="other", actions=[], forms=[], personal_data=[])
    )
    result = explain(letter, model="m", pages=1, pages_read=1, params=load_params())
    assert result.action_needed is False
    assert result.warnings[0].startswith("To nie wygląda na pismo z ZUS")


def test_benefits_map_to_timeline_elements() -> None:
    assert timeline_elements(["paternity"], None) == [
        "paternity",
        "paternity-request",
        "paternity-deadline",
    ]
    assert "sick-benefit" in timeline_elements(["sickness"], None)
    assert timeline_elements(["other"], None) == []


# ---------------------------------------------------------------------------------------------
# Only Claude or Gemini reads documents


def test_only_claude_or_gemini_may_read_documents() -> None:
    assert allowed("claude-opus-5-5") and allowed("anthropic/claude-opus-5.5")
    assert allowed("gemini-pro-latest")
    assert not allowed("openai/gpt-5.4-mini")

    def make(**settings: Any) -> object:
        return get_document_model_factory(Settings(_env_file=None, **settings))()

    with pytest.raises(HTTPException) as other:
        make(llm_provider="openrouter", openrouter_api_key="k", cases_model="openai/gpt-5")
    assert other.value.status_code == 503
    with pytest.raises(HTTPException):
        make(llm_provider="google", cases_model="gemini-pro-latest")  # no key
    with pytest.raises(HTTPException):
        make(llm_provider="google", gemini_api_key="g", cases_model="claude-opus-5-5")
    model = make(llm_provider="openrouter", openrouter_api_key="k")
    assert "claude" in model.model_name  # type: ignore[attr-defined]
