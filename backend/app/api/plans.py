"""POST /api/plans and POST /api/stress: plans for a goal (F8) and the stress test of the plan
(F11). Deterministic, no AI. The front applies a chosen plan with its `patch` through
`PATCH /api/session/{id}/scenario`."""

import datetime as dt
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.api.deps import get_params, get_today
from app.engine import Params, Scenario, ScenarioError
from app.engine.plans import Goal, PlansResult, propose_plans
from app.engine.stress import StressReport, stress_test

router = APIRouter(prefix="/api", tags=["plans"])


class PlansRequest(BaseModel):
    scenario: Scenario
    goal: Goal


class StressRequest(BaseModel):
    scenario: Scenario
    timelines: bool = False
    """Also return both timelines of every event (for "Pokaż na osi")."""


@router.post("/plans")
def plans(
    request: PlansRequest,
    params: Annotated[Params, Depends(get_params)],
    today: Annotated[dt.date, Depends(get_today)],
) -> PlansResult:
    try:
        return propose_plans(request.scenario, params, today, request.goal)
    except ScenarioError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/stress")
def stress(
    request: StressRequest,
    params: Annotated[Params, Depends(get_params)],
    today: Annotated[dt.date, Depends(get_today)],
) -> StressReport:
    try:
        return stress_test(request.scenario, params, today, timelines=request.timelines)
    except ScenarioError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
