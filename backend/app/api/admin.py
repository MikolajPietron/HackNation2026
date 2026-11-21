"""Admin panel: the legal parameters, their versions and a preview of what a change does.

A change is saved as a new version valid from a date (a law changes from a day, not "now").
The sources of the base file stay attached; the note says what the change is based on.
Demo: no login. In production these endpoints sit behind the administrators' sign-in.
"""

import datetime as dt
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.api.deps import get_param_store, get_params, get_today
from app.engine import Params, Scenario, ScenarioError, Timeline, build_timeline
from app.services.param_versions import ParamStore, ParamVersion, active_version
from app.services.params import load_params

router = APIRouter(prefix="/api/admin", tags=["admin"])

PREVIEW_DAYS_TO_BIRTH = 120
"""The preview's example family expects the baby about four months from today."""


class ParamValues(BaseModel):
    """The numbers the panel can change (phase 1 and 2a of the engine)."""

    max_weeks_before_birth: int = Field(ge=0, le=20)
    weeks_by_children: list[int] = Field(min_length=5, max_length=5)
    mother_personal_weeks: int = Field(ge=1, le=52)


def values_of(params: Params) -> ParamValues:
    m = params.maternity
    return ParamValues(
        max_weeks_before_birth=m.max_weeks_before_birth.value,
        weeks_by_children=list(m.weeks_by_children.value),
        mother_personal_weeks=m.mother_personal_weeks.value,
    )


def check(values: ParamValues) -> None:
    """Numbers that would make the plan impossible. Polish messages, shown in the panel."""
    weeks = values.weeks_by_children
    if any(w < 1 or w > 60 for w in weeks):
        raise HTTPException(422, "Wymiar urlopu musi mieścić się między 1 a 60 tygodni.")
    if any(later < earlier for earlier, later in zip(weeks, weeks[1:], strict=False)):
        raise HTTPException(422, "Przy większej liczbie dzieci urlop nie może być krótszy.")
    if values.mother_personal_weeks > weeks[0]:
        raise HTTPException(422, "Tygodni tylko dla mamy nie może być więcej niż całego urlopu.")
    if values.max_weeks_before_birth >= weeks[0]:
        raise HTTPException(422, "Część przed porodem musi być krótsza niż cały urlop.")


def with_values(params: Params, values: ParamValues, version: str) -> Params:
    """A copy of the parameters with new numbers; the sources stay attached."""
    copy = params.model_copy(deep=True, update={"version": version})
    m = copy.maternity
    m.max_weeks_before_birth.value = values.max_weeks_before_birth
    m.weeks_by_children.value = list(values.weeks_by_children)
    m.mother_personal_weeks.value = values.mother_personal_weeks
    return copy


class VersionView(BaseModel):
    id: UUID
    version: str
    effective_from: dt.date
    note: str
    created_at: dt.datetime
    values: ParamValues
    status: Literal["in_force", "scheduled", "past"]


class AdminView(BaseModel):
    today: dt.date
    base: Params
    """The base file, with every source."""
    in_force: ParamValues
    versions: list[VersionView]
    """Newest first."""


async def admin_view(store: ParamStore, today: dt.date) -> AdminView:
    versions = await store.list()
    current = active_version(versions, today)
    base = load_params()
    views = [
        VersionView(
            id=v.id,
            version=v.version,
            effective_from=v.effective_from,
            note=v.note,
            created_at=v.created_at,
            values=values_of(v.params),
            status="scheduled"
            if v.effective_from > today
            else "in_force"
            if current is not None and v.id == current.id
            else "past",
        )
        for v in versions
    ]
    views.sort(key=lambda v: (v.effective_from, v.created_at), reverse=True)
    return AdminView(
        today=today,
        base=base,
        in_force=values_of(current.params if current else base),
        versions=views,
    )


@router.get("/params")
async def list_params(
    store: Annotated[ParamStore, Depends(get_param_store)],
    today: Annotated[dt.date, Depends(get_today)],
) -> AdminView:
    return await admin_view(store, today)


class NewVersion(BaseModel):
    effective_from: dt.date
    note: str = Field(min_length=3, max_length=500)
    """What the change is based on, e.g. the act and the article."""
    values: ParamValues


@router.post("/params")
async def save_version(
    body: NewVersion,
    store: Annotated[ParamStore, Depends(get_param_store)],
    today: Annotated[dt.date, Depends(get_today)],
) -> AdminView:
    check(body.values)
    base = load_params()
    number = len(await store.list()) + 1
    version = f"{base.version}+{number}"
    await store.add(
        ParamVersion(
            version=version,
            effective_from=body.effective_from,
            note=body.note.strip(),
            params=with_values(base, body.values, version),
        )
    )
    return await admin_view(store, today)


class Preview(BaseModel):
    values: ParamValues
    children_count: int = Field(default=1, ge=1, le=5)


class PreviewResult(BaseModel):
    """The example family's plan with the parameters in force and with the draft."""

    before: Timeline
    after: Timeline


@router.post("/preview")
async def preview(
    body: Preview,
    params: Annotated[Params, Depends(get_params)],
    today: Annotated[dt.date, Depends(get_today)],
) -> PreviewResult:
    check(body.values)
    scenario = Scenario(
        role="mother",
        work="employment",
        child_born=False,
        due_date=today + dt.timedelta(days=PREVIEW_DAYS_TO_BIRTH),
        children_count=body.children_count,
    )
    try:
        return PreviewResult(
            before=build_timeline(scenario, params, today),
            after=build_timeline(scenario, with_values(params, body.values, "podgląd"), today),
        )
    except ScenarioError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
