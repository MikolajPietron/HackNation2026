"""F24 "Przetłumacz pismo z ZUS" (an AI feature, marked as such in the answer).

POST /api/letters/explain   a photo or PDF of a letter from ZUS → `LetterExplanation`

The letter goes only to the document model (Claude or Gemini, `document_model.py`). Nothing is
stored: no cache, no session, no log of its content; errors never repeat it. With `session_id`
the answer points only to the elements on that session's timeline.
"""

import datetime as dt
from collections.abc import Callable
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from starlette.concurrency import run_in_threadpool

from app.api.deps import get_params, get_session_store, get_today
from app.api.document_model import ModelFactory, get_document_model_factory
from app.cases.pages import page_count, render_pages
from app.engine import Params, ScenarioError, Timeline, build_timeline
from app.letters.explain import explain
from app.letters.models import LetterExplanation
from app.letters.reader import LetterReader, ModelLetterReader
from app.services.sessions import SessionStore

router = APIRouter(prefix="/api/letters", tags=["letters"])

MAX_UPLOAD = 20 * 1024 * 1024
MAX_PAGES = 10
ALLOWED = (b"%PDF", b"\xff\xd8\xff", b"\x89PNG")

ReaderFactory = Callable[[], LetterReader]


def get_letter_reader_factory(
    models: Annotated[ModelFactory, Depends(get_document_model_factory)],
) -> ReaderFactory:
    """The reader (and its model) is made only once the file is fine."""
    return lambda: ModelLetterReader(models())


async def _timeline(
    session_id: UUID | None, store: SessionStore, params: Params, today: dt.date
) -> Timeline | None:
    if session_id is None:
        return None
    scenario = (await store.load(session_id)).scenario
    if scenario.anchor_date is None:
        return None
    try:
        return build_timeline(scenario, params, today)
    except ScenarioError:
        return None


@router.post("/explain")
async def explain_letter(
    make_reader: Annotated[ReaderFactory, Depends(get_letter_reader_factory)],
    store: Annotated[SessionStore, Depends(get_session_store)],
    params: Annotated[Params, Depends(get_params)],
    today: Annotated[dt.date, Depends(get_today)],
    file: Annotated[UploadFile, File(description="Zdjęcie albo PDF pisma z ZUS")],
    session_id: Annotated[UUID | None, Form()] = None,
) -> LetterExplanation:
    data = await file.read(MAX_UPLOAD + 1)
    if len(data) > MAX_UPLOAD:
        raise HTTPException(413, "Plik jest za duży (najwyżej 20 MB).")
    if not data.startswith(ALLOWED):
        raise HTTPException(415, "Wgraj zdjęcie (JPG, PNG) albo PDF pisma.")
    try:
        if await run_in_threadpool(page_count, data) > MAX_PAGES:
            raise HTTPException(413, f"Pismo ma za dużo stron (najwyżej {MAX_PAGES}).")
        pages = await run_in_threadpool(render_pages, data)
    except HTTPException:
        raise
    except Exception:  # noqa: BLE001 — a broken file; its content is not repeated
        raise HTTPException(
            422, "Nie udało się otworzyć pliku. Wgraj zdjęcie (JPG, PNG) albo PDF."
        ) from None
    to_read = [page for page in pages if not page.blank]
    if not to_read:
        raise HTTPException(422, "Na zdjęciu nie widać tekstu. Zrób wyraźniejsze zdjęcie pisma.")
    reader = make_reader()
    try:
        reading = await reader.read(to_read)
    except HTTPException:
        raise
    except Exception:  # noqa: BLE001 — the model or the network failed; no letter content here
        raise HTTPException(
            502, "Nie udało się odczytać pisma. Spróbuj ponownie albo wgraj wyraźniejsze zdjęcie."
        ) from None
    return explain(
        reading,
        model=reader.model_name,
        pages=len(pages),
        pages_read=len(to_read),
        params=params,
        timeline=await _timeline(session_id, store, params, today),
    )
