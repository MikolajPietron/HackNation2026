"""Example cases from ZUS (the brief: "Strona powinna mieć możliwość uploadu/wyboru wybranych
wniosków"; the jury checks the insurance and the calculation on them).

GET  /api/cases                      the catalogue S01–S86 (ids and categories, no file names)
GET  /api/cases/agreement            agreement with the decisions of ZUS, from the cache only
POST /api/cases/{id}/read            read a catalogue case with Claude (once; then from cache)
POST /api/cases/upload               read an uploaded PDF or photo the same way
POST /api/cases/assess               recalculate after the facts were corrected by hand (no AI)
PUT  /api/cases/session/{session_id} load the case into the plan (a new conversation)
"""

import datetime as dt
from collections.abc import Callable
from functools import lru_cache
from pathlib import Path
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic_ai.models import Model
from pydantic_ai.models.google import GoogleModel
from pydantic_ai.providers.google import GoogleProvider
from starlette.concurrency import run_in_threadpool

from app.api.deps import KEY_NAMES, _chat_model, get_params, get_session_store, get_today
from app.api.session import SessionStart
from app.assistant.describe import next_question
from app.cases.agreement import agreement
from app.cases.assess import assess
from app.cases.cache import CachedRead, CaseCache, digest, file_digest
from app.cases.catalog import find_case, list_case_files
from app.cases.models import (
    AgreementReport,
    ApplyRequest,
    AssessRequest,
    CaseList,
    CaseListItem,
    CaseResult,
)
from app.cases.pages import page_count, render_pages
from app.cases.reader import CaseReader, ModelCaseReader
from app.config import Settings, get_settings
from app.engine import Params, ScenarioError, build_timeline
from app.services.sessions import Session, SessionStore


def _reading_failed(error: Exception) -> str:
    """What the parent sees when the model could not read the file: no provider's raw answer."""
    text = str(error).lower()
    if any(word in text for word in ("spend cap", "spending cap", "quota", "credits", "limit")):
        return (
            "Odczyt dokumentów przez AI jest chwilowo niedostępny: wyczerpał się limit konta "
            "albo klucza modelu. Przykładowe rodziny i kalkulator działają bez AI."
        )
    return "Nie udało się odczytać sprawy. Spróbuj ponownie za chwilę."


router = APIRouter(prefix="/api/cases", tags=["cases"])

ROOT = Path(__file__).resolve().parents[3]
MAX_UPLOAD = 40 * 1024 * 1024
ALLOWED = (b"%PDF", b"\xff\xd8\xff", b"\x89PNG")


def get_cases_folder(settings: Annotated[Settings, Depends(get_settings)]) -> Path:
    return Path(settings.cases_dir) if settings.cases_dir else ROOT / "docs/dokumentyZUS/sprawy"


def get_case_cache(settings: Annotated[Settings, Depends(get_settings)]) -> CaseCache:
    folder = Path(settings.cases_cache_dir)
    return CaseCache(folder if folder.is_absolute() else ROOT / "backend" / folder)


ReaderFactory = Callable[[], CaseReader]


def get_reader_factory(settings: Annotated[Settings, Depends(get_settings)]) -> ReaderFactory:
    """The reader is made only when a case has not been read yet, so a case from the cache needs
    no key and sends nothing anywhere. Tests replace this with a fake reader."""

    def make() -> CaseReader:
        name = settings.cases_model_name
        # Claude or Gemini, never the chat's model of another vendor: see Settings.cases_model.
        if name.startswith("gemini"):
            if not settings.gemini_api_key:
                raise HTTPException(
                    status_code=503,
                    detail="Odczyt spraw przez Gemini wymaga klucza GEMINI_API_KEY w backend/.env.",
                )
            return ModelCaseReader(_gemini_model(name, settings.gemini_api_key))
        if not settings.llm_api_key:
            raise HTTPException(
                status_code=503,
                detail=(
                    "Odczyt spraw przez AI jest wyłączony: brak klucza "
                    f"{KEY_NAMES[settings.llm_provider]} w backend/.env."
                ),
            )
        return ModelCaseReader(_chat_model(settings.llm_provider, name, settings.llm_api_key, None))

    return make


@lru_cache(maxsize=2)
def _gemini_model(name: str, api_key: str) -> Model:
    return GoogleModel(name, provider=GoogleProvider(api_key=api_key))


Folder = Annotated[Path, Depends(get_cases_folder)]
Cache = Annotated[CaseCache, Depends(get_case_cache)]
Readers = Annotated[ReaderFactory, Depends(get_reader_factory)]


@router.get("")
async def list_cases(folder: Folder, cache: Cache) -> CaseList:
    def items() -> list[CaseListItem]:
        out = []
        for case in list_case_files(folder):
            key = file_digest(case.path)
            cached = cache.get(key)
            pages = cached.pages if cached else page_count(case.path.read_bytes())
            out.append(
                CaseListItem(
                    id=case.id,
                    category=case.category,
                    title=cached.facts.title if cached else "",
                    pages=pages,
                    read=cached is not None,
                )
            )
        return out

    return CaseList(configured=folder.is_dir(), cases=await run_in_threadpool(items))


@router.get("/agreement")
async def agreement_report(
    folder: Folder,
    cache: Cache,
    params: Annotated[Params, Depends(get_params)],
    today: Annotated[dt.date, Depends(get_today)],
) -> AgreementReport:
    """How often the calculator agrees with ZUS, from the cases already read (like
    `batch --only-cached`): nothing is read, no key is needed."""
    return await run_in_threadpool(
        lambda: agreement(list_case_files(folder), cache, params, today, configured=folder.is_dir())
    )


async def _read(
    data: bytes,
    case_id: str | None,
    cache: CaseCache,
    make_reader: ReaderFactory,
    params: Params,
    today: dt.date,
) -> CaseResult:
    key = digest(data)
    stored = cache.get(key)
    cached = stored is not None
    if stored is None:
        try:
            pages = await run_in_threadpool(render_pages, data)
        except Exception as error:  # noqa: BLE001 — any broken file is the parent's problem to see
            raise HTTPException(
                422, "Nie udało się otworzyć pliku. Wgraj PDF albo zdjęcie (JPG, PNG)."
            ) from error
        to_read = [page for page in pages if not page.blank]
        try:
            facts = await make_reader().read(to_read)
        except HTTPException:
            raise
        except Exception as error:  # noqa: BLE001 — the model or the network failed
            raise HTTPException(502, _reading_failed(error)) from error
        stored = CachedRead(facts=facts, pages=len(pages), pages_read=len(to_read))
        cache.put(key, stored)
    return assess(
        stored.facts,
        case_id=case_id,
        pages=stored.pages,
        pages_read=stored.pages_read,
        cached=cached,
        params=params,
        today=today,
    )


@router.post("/{case_id}/read")
async def read_case(
    case_id: str,
    folder: Folder,
    cache: Cache,
    params: Annotated[Params, Depends(get_params)],
    today: Annotated[dt.date, Depends(get_today)],
    make_reader: Readers,
) -> CaseResult:
    case = find_case(folder, case_id)
    if case is None:
        raise HTTPException(404, f"Nie ma sprawy {case_id} w katalogu.")
    data = await run_in_threadpool(case.path.read_bytes)
    return await _read(data, case_id, cache, make_reader, params, today)


@router.post("/upload")
async def upload_case(
    folder: Folder,
    cache: Cache,
    params: Annotated[Params, Depends(get_params)],
    today: Annotated[dt.date, Depends(get_today)],
    make_reader: Readers,
    file: Annotated[UploadFile, File(description="PDF albo zdjęcie sprawy")],
) -> CaseResult:
    data = await file.read(MAX_UPLOAD + 1)
    if len(data) > MAX_UPLOAD:
        raise HTTPException(413, "Plik jest za duży (najwyżej 40 MB).")
    if not data.startswith(ALLOWED):
        raise HTTPException(415, "Wgraj PDF albo zdjęcie (JPG, PNG).")
    key = digest(data)
    # An uploaded file of the catalogue keeps its id (and its earlier reading).
    known = await run_in_threadpool(
        lambda: next((c.id for c in list_case_files(folder) if file_digest(c.path) == key), None)
    )
    return await _read(data, known, cache, make_reader, params, today)


@router.post("/assess")
async def assess_case(
    request: AssessRequest,
    params: Annotated[Params, Depends(get_params)],
    today: Annotated[dt.date, Depends(get_today)],
) -> CaseResult:
    return assess(
        request.facts,
        case_id=request.id,
        pages=request.pages,
        pages_read=request.pages_read,
        cached=True,
        params=params,
        today=today,
    )


@router.put("/session/{session_id}")
async def load_into_plan(
    session_id: UUID,
    request: ApplyRequest,
    store: Annotated[SessionStore, Depends(get_session_store)],
    params: Annotated[Params, Depends(get_params)],
    today: Annotated[dt.date, Depends(get_today)],
) -> SessionStart:
    """The case becomes the plan: a new conversation that starts from the case's facts."""
    try:
        timeline = build_timeline(request.scenario, params, today)
    except ScenarioError as error:
        raise HTTPException(422, str(error)) from error
    await store.save(session_id, Session(scenario=request.scenario))
    return SessionStart(
        scenario=request.scenario, timeline=timeline, question=next_question(request.scenario)
    )
