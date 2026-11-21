"""POST /api/timeline — the deterministic calculator, no AI (for 'what if' toggles and tests)."""

import datetime as dt
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_params, get_today
from app.engine import Params, Scenario, ScenarioError, Timeline, build_timeline

router = APIRouter(prefix="/api", tags=["timeline"])


@router.post("/timeline")
def timeline(
    scenario: Scenario,
    params: Annotated[Params, Depends(get_params)],
    today: Annotated[dt.date, Depends(get_today)],
) -> Timeline:
    try:
        return build_timeline(scenario, params, today)
    except ScenarioError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
