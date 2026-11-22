"""FastAPI entry point. Run from the repo root: `npm run dev:api`."""

from typing import Annotated

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import (
    admin,
    cases,
    chat,
    letters,
    plans,
    request_check,
    session,
    share,
    timeline,
)
from app.api.deps import get_param_store, get_session_store
from app.config import get_settings
from app.services.param_versions import ParamStore
from app.services.sessions import SessionStore

app = FastAPI(title="Zasiłkowy Przewodnik API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(timeline.router)
app.include_router(chat.router)
app.include_router(session.router)
app.include_router(admin.router)
app.include_router(cases.router)
app.include_router(plans.router)  # F8 plans for a goal, F11 stress test
app.include_router(letters.router)
app.include_router(request_check.router)
app.include_router(share.router)  # a read-only link to the plan for the other parent


@app.get("/api/health")
async def health(
    store: Annotated[SessionStore, Depends(get_session_store)],
    params: Annotated[ParamStore, Depends(get_param_store)],
) -> dict[str, str]:
    """Where conversations are stored ("supabase" or "file") and parameter versions ("supabase" or
    "memory")."""
    return {"status": "ok", "sessions": store.name, "params": params.name}
