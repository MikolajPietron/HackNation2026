"""Session endpoints: start one from the onboarding, restore it after a reload, forget it."""

import datetime as dt
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field

from app.api.chat import load_history
from app.api.deps import get_params, get_session_store, get_today
from app.assistant.describe import InterviewQuestion, next_question
from app.assistant.transcript import to_chat_messages
from app.engine import Params, Scenario, ScenarioError, Timeline, build_timeline
from app.engine.models import Earnings, Role, TakenIn, Work
from app.engine.plausibility import (
    birth_date_problem,
    child_birth_problem,
    due_date_problem,
    taken_in_problem,
)
from app.services.sessions import Session, SessionStore

router = APIRouter(prefix="/api", tags=["session"])


class SessionView(BaseModel):
    """What the UI needs to pick up where the parent left off."""

    messages: list[dict[str, Any]]
    scenario: Scenario
    timeline: Timeline | None
    question: InterviewQuestion | None = None
    """The next interview question, for the answer cards (the assistant asks the same)."""


class TakenInAnswer(BaseModel):
    """Guide section D: the child was taken in for upbringing, not born to the family."""

    kind: TakenIn
    date: dt.date
    """The day of taking in (adoption: and of the court application, the later of the two)."""


class OnboardingAnswers(BaseModel):
    """Everything the onboarding asks. Work and earnings are the respondent's own."""

    role: Role
    child_born: bool
    date: dt.date
    """Date of birth when `child_born`, otherwise the expected due date."""
    children_count: int = Field(ge=1, le=10)
    work: Work
    earnings: Earnings | None = None
    """Not asked when the respondent does not work."""
    taken_in: TakenInAnswer | None = None
    """Set for a child taken in for upbringing: then `child_born` is true, `date` is the child's
    date of birth and `children_count` the children taken in at once."""


class SessionStart(BaseModel):
    scenario: Scenario
    timeline: Timeline
    question: InterviewQuestion | None = None


@router.put("/session/{session_id}/onboarding")
async def start_from_onboarding(
    session_id: UUID,
    answers: OnboardingAnswers,
    store: Annotated[SessionStore, Depends(get_session_store)],
    params: Annotated[Params, Depends(get_params)],
    today: Annotated[dt.date, Depends(get_today)],
) -> SessionStart:
    """Saves the onboarding answers as the start of the interview; the chat continues from them."""
    taken_in = answers.taken_in
    if taken_in is not None:
        problem = taken_in_problem(taken_in.date, today) or child_birth_problem(answers.date, today)
    else:
        check = birth_date_problem if answers.child_born else due_date_problem
        problem = check(answers.date, today)
    if problem:
        raise HTTPException(status_code=422, detail=problem)
    scenario = Scenario(
        role=answers.role,
        work=answers.work,
        earnings=answers.earnings,
        child_born=answers.child_born or taken_in is not None,
        due_date=None if answers.child_born or taken_in else answers.date,
        birth_date=answers.date if answers.child_born or taken_in else None,
        children_count=answers.children_count,
        taken_in=taken_in.kind if taken_in else None,
        taken_in_on=taken_in.date if taken_in else None,
    )
    try:
        timeline = build_timeline(scenario, params, today)
    except ScenarioError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    await store.save(session_id, Session(scenario=scenario))
    return SessionStart(scenario=scenario, timeline=timeline, question=next_question(scenario))


@router.get("/session/{session_id}")
async def get_session(
    session_id: UUID,
    store: Annotated[SessionStore, Depends(get_session_store)],
    params: Annotated[Params, Depends(get_params)],
    today: Annotated[dt.date, Depends(get_today)],
) -> SessionView:
    session = await store.load(session_id)
    timeline = None
    if session.scenario.anchor_date is not None:
        try:
            # Recalculated from the saved answers, so it always follows the current rules.
            timeline = build_timeline(session.scenario, params, today)
        except ScenarioError:
            timeline = None
    return SessionView(
        messages=to_chat_messages(load_history(session)),
        scenario=session.scenario,
        timeline=timeline,
        question=next_question(session.scenario),
    )


@router.delete("/session/{session_id}", status_code=204)
async def delete_session(
    session_id: UUID, store: Annotated[SessionStore, Depends(get_session_store)]
) -> Response:
    await store.delete(session_id)
    return Response(status_code=204)
