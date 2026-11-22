"""Session endpoints: start one from the onboarding, change the scenario from the interface,
restore it after a reload, forget it."""

import datetime as dt
import json
from typing import Annotated, Any, Literal, Self
from uuid import UUID

from fastapi import APIRouter, Body, Depends, HTTPException, Response
from pydantic import BaseModel, Field, ValidationError, model_validator
from pydantic_ai import ModelMessagesTypeAdapter, ModelRequest, UserPromptPart

from app.api.chat import load_history
from app.api.deps import get_params, get_session_store, get_today
from app.assistant.agent import MIN_MONTHLY_PAY
from app.assistant.describe import InterviewQuestion, next_question
from app.assistant.prompts import EVENT_MARKER
from app.assistant.transcript import to_chat_messages
from app.engine import Params, Scenario, ScenarioError, Timeline, build_timeline
from app.engine.models import Earnings, Pay, PayerSize, Role, TakenIn, Work
from app.engine.plausibility import (
    birth_date_problem,
    child_birth_problem,
    due_date_problem,
    taken_in_problem,
)
from app.services.sessions import BUSY, Session, SessionStore, session_lock

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


PAID_WORK = ("employment", "contract", "business")


class WorkFacts(BaseModel):
    """What the onboarding learned about one parent's work. None = not asked, or "nie wiem":
    the interview in the chat asks it later. The same checks as the assistant's tools."""

    work: Work | None = None
    insured: bool | None = None
    """Contract or business only: registered for the voluntary sickness insurance."""
    payer_size: PayerSize | None = None
    """Employment or contract only: does the payer report more than 20 people?"""
    pay: Pay | Literal["unknown"] | None = None
    """The monthly amount the benefit base comes from: gross salary for an employee, the base of
    the sickness contribution on a contract or with a business. "unknown" = did not give it."""

    @model_validator(mode="after")
    def fits_the_work(self) -> Self:
        if problem := work_facts_problem(self):
            raise ValueError(problem)
        return self


def work_facts_problem(facts: WorkFacts) -> str | None:
    """Why these answers about one parent's work do not go together, or None."""
    if facts.insured is not None and facts.work not in ("contract", "business"):
        return "Dobrowolne ubezpieczenie chorobowe dotyczy umowy zlecenia i własnej firmy."
    if facts.payer_size is not None and facts.work not in ("employment", "contract"):
        return "Liczba osób u płatnika dotyczy etatu i umowy zlecenia."
    if facts.pay is not None and (facts.work not in PAID_WORK or facts.insured is False):
        return "Kwotę podaje tylko ktoś, kto pracuje i ma ubezpieczenie chorobowe."
    if isinstance(facts.pay, float) and facts.pay < MIN_MONTHLY_PAY:
        return "To bardzo mała kwota miesięczna. Podaj ją w złotych, np. 8000."
    return None


class OnboardingAnswers(BaseModel):
    """Everything the onboarding asks. `work`, `insured`, `payer_size` and `pay` are the
    respondent's own; `partner` is what they said about the other parent. Every fact the
    onboarding gives is one question fewer in the chat (`interview_questions` skips it)."""

    role: Role
    child_born: bool
    date: dt.date
    """Date of birth when `child_born`, otherwise the expected due date."""
    children_count: int = Field(ge=1, le=10)
    work: Work
    insured: bool | None = None
    payer_size: PayerSize | None = None
    pay: Pay | Literal["unknown"] | None = None
    partner: WorkFacts = WorkFacts()
    earnings: Earnings | None = None
    """No longer asked: the range gave no amounts (`pay` does). Kept for older clients."""
    taken_in: TakenInAnswer | None = None
    """Set for a child taken in for upbringing: then `child_born` is true, `date` is the child's
    date of birth and `children_count` the children taken in at once."""
    # About the mother and the birth; asked only where the interview would ask them.
    hospital_care: bool | None = None
    """Born child: premature, or in hospital after the birth. The chat asks the details."""
    leave_before_birth_weeks: int | None = Field(default=None, ge=0)
    """Born child: weeks of maternity leave the mother took before the birth (0 = none)."""
    sick_leave: bool | None = None
    """Child on the way: the mother is (or was) on sick leave in this pregnancy."""
    sick_leave_start: dt.date | None = None
    sick_leave_end: dt.date | None = None
    """None = until the birth."""
    insured_since: dt.date | None = None
    """The mother's uninterrupted sickness insurance since; from the (simulated) ZUS data."""

    @property
    def own(self) -> WorkFacts:
        """The respondent's own answers, in the shape of `partner` (checked by the validator)."""
        return WorkFacts.model_construct(
            work=self.work, insured=self.insured, payer_size=self.payer_size, pay=self.pay
        )

    @model_validator(mode="after")
    def facts_fit_the_case(self) -> Self:
        if problem := work_facts_problem(self.own):
            raise ValueError(problem)
        born = self.child_born and self.taken_in is None
        expected = not self.child_born and self.taken_in is None
        about_birth = (self.hospital_care, self.leave_before_birth_weeks)
        if not born and any(answer is not None for answer in about_birth):
            raise ValueError(
                "O szpital i urlop przed porodem pytamy, gdy dziecko już się urodziło."
            )
        if not expected and self.sick_leave is not None:
            raise ValueError("O zwolnienie lekarskie w ciąży pytamy, gdy dziecko jest w drodze.")
        if self.sick_leave and self.sick_leave_start is None:
            raise ValueError("Potrzebna jest data początku zwolnienia lekarskiego.")
        if not self.sick_leave and (self.sick_leave_start or self.sick_leave_end):
            raise ValueError("Daty zwolnienia podaje się tylko razem ze zwolnieniem.")
        return self


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
    if answers.sick_leave_start is not None and answers.sick_leave_start > today:
        problem = "Zwolnienie lekarskie nie może zaczynać się w przyszłości. Sprawdź datę."
    if answers.insured_since is not None and answers.insured_since > today:
        problem = "Ubezpieczenie nie może zaczynać się w przyszłości. Sprawdź datę."
    if problem:
        raise HTTPException(status_code=422, detail=problem)
    # The respondent's own facts go to their parent, the partner's to the other one. The own work
    # stays in `work` (see Scenario.mothers_work).
    own, partner = answers.own, answers.partner
    mother, father = (own, partner) if answers.role == "mother" else (partner, own)
    if answers.sick_leave and mother.work is None:
        raise HTTPException(
            status_code=422, detail="Zwolnienie lekarskie: najpierw potrzebna jest praca mamy."
        )
    scenario = Scenario(
        role=answers.role,
        work=answers.work,
        earnings=answers.earnings,
        mother_work=mother.work if answers.role == "father" else None,
        father_work=father.work if answers.role == "mother" else None,
        mother_insured=mother.insured,
        father_insured=father.insured,
        mother_payer_size=mother.payer_size,
        father_payer_size=father.payer_size,
        mother_pay=mother.pay,
        father_pay=father.pay,
        child_born=answers.child_born or taken_in is not None,
        due_date=None if answers.child_born or taken_in else answers.date,
        birth_date=answers.date if answers.child_born or taken_in else None,
        children_count=answers.children_count,
        taken_in=taken_in.kind if taken_in else None,
        taken_in_on=taken_in.date if taken_in else None,
        hospital_care=answers.hospital_care,
        leave_before_birth_weeks=answers.leave_before_birth_weeks,
        sick_leave=answers.sick_leave,
        sick_leave_start=answers.sick_leave_start,
        sick_leave_end=answers.sick_leave_end,
        insured_since=answers.insured_since,
    )
    try:
        timeline = build_timeline(scenario, params, today)
    except ScenarioError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    await store.save(session_id, Session(scenario=scenario))
    return SessionStart(scenario=scenario, timeline=timeline, question=next_question(scenario))


@router.patch("/session/{session_id}/scenario")
async def change_scenario(
    session_id: UUID,
    changes: Annotated[dict[str, Any], Body()],
    store: Annotated[SessionStore, Depends(get_session_store)],
    params: Annotated[Params, Depends(get_params)],
    today: Annotated[dt.date, Depends(get_today)],
) -> SessionStart:
    """The interface changes the scenario without the chat (FUNKCJE: "Te same narzędzia wywołuje
    interfejs"): e.g. the parental plan (`parental_parts`), the 81,5% choice (`rate_815`), a job
    loss (`job_loss`) or the months of pay (`mother_pay_history`). The fields given replace the
    saved ones (null clears one); the engine validates the result the same way as after a chat
    tool. The chat history gets a hidden note of what changed, so the assistant knows."""
    lock = session_lock(session_id)
    if lock.locked():
        raise HTTPException(status_code=409, detail=BUSY)
    async with lock:
        unknown = sorted(set(changes) - set(Scenario.model_fields))
        if unknown:
            raise HTTPException(
                status_code=422, detail=f"Nieznane pola scenariusza: {', '.join(unknown)}."
            )
        session = await store.load(session_id)
        before = session.scenario.model_dump(mode="json")
        try:
            scenario = Scenario.model_validate({**before, **changes})
        except ValidationError as exc:
            field = ".".join(str(part) for part in exc.errors()[0]["loc"]) or "scenariusz"
            raise HTTPException(
                status_code=422, detail=f"Nieprawidłowa wartość pola „{field}”. Sprawdź dane."
            ) from exc
        if scenario.anchor_date is None:
            raise HTTPException(
                status_code=422,
                detail="Najpierw potrzebna jest data: przewidywana data porodu albo data "
                "urodzenia.",
            )
        try:
            timeline = build_timeline(scenario, params, today)
        except ScenarioError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        after = scenario.model_dump(mode="json")
        changed = {k: after[k] for k in changes if after.get(k) != before.get(k)}
        if changed:
            listed = "; ".join(
                f"{k} = {json.dumps(v, ensure_ascii=False)}" for k, v in sorted(changed.items())
            )
            note = (
                f"{EVENT_MARKER} Rodzic zmienił w aplikacji, bez czatu: {listed}. Oś czasu jest "
                "już przeliczona; tych odpowiedzi nie zapisuj drugi raz."
            )
            history = [*load_history(session), ModelRequest(parts=[UserPromptPart(content=note)])]
            session.history = ModelMessagesTypeAdapter.dump_python(history, mode="json")
        session.scenario = scenario
        await store.save(session_id, session)
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
