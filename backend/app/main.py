"""FastAPI entry point. Run from the repo root: `npm run dev:api`."""

from typing import Annotated

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import chat, session, timeline
from app.api.deps import get_session_store
from app.config import get_settings
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


@app.get("/api/health")
async def health(store: Annotated[SessionStore, Depends(get_session_store)]) -> dict[str, str]:
    """`sessions` says where conversations are stored: "supabase" or "memory"."""
    return {"status": "ok", "sessions": store.name}
