"""POST /api/chat — one assistant turn, streamed as NDJSON (one JSON event per line).

Events: `text` (delta), `tool-call`, `tool-result`, `timeline` (scenario + recalculated
timeline), `focus` (element the assistant explains), `done`, `error`.
The conversation (scenario and message history) is stored per session id; the client only
sends its session id and the new message.
"""

import datetime as dt
import json
import logging
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, ValidationError, model_validator
from pydantic_ai import (
    AgentRunResultEvent,
    FunctionToolCallEvent,
    FunctionToolResultEvent,
    ModelAuthenticationError,
    ModelMessage,
    ModelMessagesTypeAdapter,
    ModelOverloadedError,
    ModelRateLimitError,
    PartDeltaEvent,
    PartStartEvent,
    TextPart,
    TextPartDelta,
    ToolCallPart,
    UsageLimitExceeded,
)
from pydantic_ai.models import Model

from app.api.deps import get_chat_model, get_params, get_session_store, get_today
from app.assistant.agent import (
    USAGE_LIMITS,
    AssistantDeps,
    ElementFocused,
    TimelineUpdated,
    assistant,
)
from app.assistant.describe import interview_questions, next_question, opening_notes
from app.assistant.prompts import timeline_ready_prompt
from app.engine import Params, Scenario, ScenarioError, build_timeline
from app.services.sessions import Session, SessionStore

router = APIRouter(prefix="/api", tags=["assistant"])
logger = logging.getLogger(__name__)


class ChatRequest(BaseModel):
    """A user message, or an app event the assistant reacts to (the user does not see it)."""

    session_id: UUID
    message: str | None = Field(default=None, min_length=1, max_length=4000)
    event: Literal["timeline_ready"] | None = None

    @model_validator(mode="after")
    def message_or_event(self) -> "ChatRequest":
        if (self.message is None) == (self.event is None):
            raise ValueError("Podaj wiadomość albo zdarzenie, jedno z dwóch.")
        return self


def load_history(session: Session) -> list[ModelMessage]:
    """The stored history, or an empty one if it can no longer be read."""
    try:
        return ModelMessagesTypeAdapter.validate_python(session.history)
    except ValidationError:
        logger.warning("Stored history is unreadable; starting the conversation again.")
        return []


@router.post("/chat")
async def chat(
    request: ChatRequest,
    model: Annotated[Model, Depends(get_chat_model)],
    params: Annotated[Params, Depends(get_params)],
    today: Annotated[dt.date, Depends(get_today)],
    store: Annotated[SessionStore, Depends(get_session_store)],
) -> StreamingResponse:
    session = await store.load(request.session_id)
    deps = AssistantDeps(scenario=session.scenario, params=params, today=today)
    if session.scenario.anchor_date is not None:
        try:
            deps.timeline = build_timeline(session.scenario, params, today)
        except ScenarioError:
            # Saved under older rules: keep the conversation, ask for the facts again.
            deps.scenario = Scenario()
    turn = _Turn(request.session_id, session, store)
    if request.message is not None:
        prompt = request.message
    else:  # the only event: "timeline_ready"
        deps.answers_allowed = False
        questions = interview_questions(deps.scenario)
        notes = opening_notes(deps.timeline.notes) if deps.timeline else []
        points = [note.title for note in notes]
        prompt = timeline_ready_prompt(questions[0].text if questions else None, points)
    stream = _stream(prompt, load_history(session), deps, model, turn)
    return StreamingResponse(stream, media_type="application/x-ndjson")


@dataclass
class _Turn:
    """Saves the session as the turn goes: the scenario after every tool, the history at the end."""

    session_id: UUID
    session: Session
    store: SessionStore

    async def save(self, scenario: Scenario, history: list[ModelMessage] | None = None) -> None:
        self.session.scenario = scenario
        if history is not None:
            self.session.history = ModelMessagesTypeAdapter.dump_python(history, mode="json")
        await self.store.save(self.session_id, self.session)


async def _stream(
    message: str, history: list[ModelMessage], deps: AssistantDeps, model: Model, turn: _Turn
) -> AsyncIterator[str]:
    to_payload = _Translator()
    try:
        async with assistant.run_stream_events(
            message,
            message_history=history or None,
            deps=deps,
            model=model,
            usage_limits=USAGE_LIMITS,
        ) as events:
            async for event in events:
                if isinstance(event, TimelineUpdated):
                    await turn.save(event.scenario)
                elif isinstance(event, AgentRunResultEvent):
                    await turn.save(deps.scenario, event.result.all_messages())
                payload = to_payload(event)
                if payload is not None:
                    yield _line(payload)
    except Exception as exc:
        logger.exception("Assistant run failed")
        yield _line({"type": "error", "message": _error_message(exc)})


@dataclass
class _Translator:
    """Maps Pydantic AI stream events to our small NDJSON protocol."""

    wrote_text: bool = False

    def __call__(self, event: object) -> dict[str, Any] | None:
        match event:
            case PartStartEvent(part=TextPart(content=content)):
                separator = "\n\n" if self.wrote_text else ""
                self.wrote_text = True
                return {"type": "text", "delta": separator + content} if content else None
            case PartDeltaEvent(delta=TextPartDelta(content_delta=delta)) if delta:
                self.wrote_text = True
                return {"type": "text", "delta": delta}
            case FunctionToolCallEvent(part=part):
                return {
                    "type": "tool-call",
                    "id": part.tool_call_id,
                    "name": part.tool_name,
                    "args": _args(part),
                }
            case FunctionToolResultEvent(part=part):
                return {
                    "type": "tool-result",
                    "id": part.tool_call_id,
                    "name": part.tool_name,
                    "ok": part.outcome == "success",
                }
            case TimelineUpdated(scenario=scenario, timeline=timeline):
                return {
                    "type": "timeline",
                    "scenario": scenario.model_dump(mode="json"),
                    "timeline": timeline.model_dump(mode="json") if timeline else None,
                    "changed": event.changed,
                    "changed_notes": event.changed_notes,
                    "focus": event.focus,
                    "question": _question(scenario),
                }
            case ElementFocused(element_id=element_id):
                return {"type": "focus", "element_id": element_id}
            case AgentRunResultEvent():
                return {"type": "done"}
        return None


def _args(part: ToolCallPart) -> dict[str, Any]:
    try:
        return part.args_as_dict()
    except ValueError:
        return {}


def _line(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False) + "\n"


def _error_message(exc: Exception) -> str:
    match exc:
        case ModelAuthenticationError():
            return "Klucz API modelu jest nieprawidłowy."
        case ModelRateLimitError() | ModelOverloadedError():
            return "Model AI jest teraz przeciążony. Spróbuj za chwilę."
        case UsageLimitExceeded():
            return "Asystent potrzebował zbyt wielu kroków. Spróbuj zapytać prościej."
        case _:
            return "Coś poszło nie tak po stronie asystenta. Spróbuj jeszcze raz."


def _question(scenario: Scenario) -> dict[str, str] | None:
    question = next_question(scenario)
    return question.model_dump() if question else None
