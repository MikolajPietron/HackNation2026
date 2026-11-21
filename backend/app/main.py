"""FastAPI entry point. Run from the repo root: `npm run dev:api`."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import chat, timeline
from app.config import get_settings

app = FastAPI(title="Zasiłkowy Przewodnik API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(timeline.router)
app.include_router(chat.router)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
