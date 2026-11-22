"""Share the plan with the other parent: a read-only link ("udostępnij plan partnerowi").

POST /api/session/{id}/share   → {token}: a new random link to a copy of the plan as it is now
GET  /api/shared/{token}       → {scenario, timeline, shared: true}

The copy holds the session's scenario only, with an empty history: the conversation is not
shared. The scenario has no personal data (no names, PESEL or addresses: those stay in the
parent's browser); the only things a parent typed into it are amounts (pay, the months of pay
for the benefit base) and dates. Whoever has the link sees the plan and nothing else.

The copy lives in the same session store, but under an id derived from the token
(`shared_id`), not under the token itself: the token is never a session id, so the session
endpoints (`PATCH /api/session/{id}/scenario`, the chat) cannot change the shared copy through
it, and there is no endpoint here that writes to it. The original session is never touched:
sharing again makes a new copy with a new token; old links keep the plan they were made with.
"""

import datetime as dt
from typing import Annotated, Literal
from uuid import UUID, uuid4, uuid5

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.api.deps import get_params, get_session_store, get_today
from app.engine import Params, Scenario, ScenarioError, Timeline, build_timeline
from app.services.sessions import Session, SessionStore

router = APIRouter(prefix="/api", tags=["share"])

SHARED = UUID("6f1c2a7e-0d4b-4e51-9a3c-5b8e2f7d1c90")
"""The namespace of the ids the shared copies are stored under."""
NOTHING_TO_SHARE = (
    "Nie ma jeszcze planu do udostępnienia: najpierw potrzebna jest przewidywana data porodu "
    "albo data urodzenia."
)
UNKNOWN_LINK = "Nie znaleźliśmy tego planu. Sprawdź link albo poproś o nowy."


def shared_id(token: UUID) -> UUID:
    """Where the copy for this token is stored: a fixed function of the token, never the token."""
    return uuid5(SHARED, str(token))


class ShareLink(BaseModel):
    token: UUID


class SharedPlan(BaseModel):
    """The plan as the other parent sees it: read-only, recalculated from the shared answers."""

    scenario: Scenario
    timeline: Timeline | None
    """None when the shared answers no longer give a timeline under the current rules."""
    shared: Literal[True] = True


@router.post("/session/{session_id}/share")
async def share_session(
    session_id: UUID, store: Annotated[SessionStore, Depends(get_session_store)]
) -> ShareLink:
    """A read-only copy of the session's plan under a new random token."""
    session = await store.load(session_id)
    if session.scenario.anchor_date is None:
        raise HTTPException(status_code=422, detail=NOTHING_TO_SHARE)
    token = uuid4()
    await store.save(shared_id(token), Session(scenario=session.scenario))
    return ShareLink(token=token)


@router.get("/shared/{token}")
async def get_shared(
    token: str,
    store: Annotated[SessionStore, Depends(get_session_store)],
    params: Annotated[Params, Depends(get_params)],
    today: Annotated[dt.date, Depends(get_today)],
) -> SharedPlan:
    """The shared plan, rebuilt with today's rules like `GET /api/session/{id}`."""
    try:
        key = shared_id(UUID(token))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=UNKNOWN_LINK) from exc
    scenario = (await store.load(key)).scenario
    if scenario.anchor_date is None:
        raise HTTPException(status_code=404, detail=UNKNOWN_LINK)
    try:
        timeline = build_timeline(scenario, params, today)
    except ScenarioError:
        timeline = None
    return SharedPlan(scenario=scenario, timeline=timeline)
