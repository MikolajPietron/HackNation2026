"""POST /api/chat — one assistant turn, streamed as NDJSON (one JSON event per line).

Events: `text` (delta), `tool-call`, `tool-result`, `timeline` (scenario + recalculated
timeline), `focus` (element the assistant explains), `done`, `error`.
The conversation (scenario and message history) is stored per session id; the client only
sends its session id and the new message.

The next interview question is never written by the model: when the turn ends, the server adds
`interview_questions`' first question as the last piece of text, word for word, and to the
model's history (so the next turn knows what was asked). The model is told not to ask it.
"""

import datetime as dt
import json
import logging
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass, field, replace
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, ValidationError, model_validator
from pydantic_ai import (
    AgentRunResult,
    AgentRunResultEvent,
    FunctionToolCallEvent,
    FunctionToolResultEvent,
    ModelAuthenticationError,
    ModelConnectionError,
    ModelMessage,
    ModelMessagesTypeAdapter,
    ModelQuotaExceededError,
    ModelRateLimitError,
    ModelResponse,
    ModelServerError,
    ModelUnavailableError,
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
from app.services.sessions import Session, SessionStore, session_lock

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
    stream = _locked_turn(request, model, params, today, store)
    return StreamingResponse(stream, media_type="application/x-ndjson")


async def _locked_turn(
    request: ChatRequest, model: Model, params: Params, today: dt.date, store: SessionStore
) -> AsyncIterator[str]:
    """The whole turn holds the session's lock, from loading the session to saving it (ZADANIA
    B.15): a change from the interface meanwhile gets 409 instead of being overwritten."""
    async with session_lock(request.session_id):
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
        async for line in _stream(prompt, load_history(session), deps, model, turn):
            yield line


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
                    messages = event.result.all_messages()
                    question = _closing_question(deps, messages)
                    if question is not None:
                        # From the answer itself: some providers send text the stream events
                        # don't mark as text (found in the Gemini eval, 22.11.2026).
                        wrote = to_payload.wrote_text or bool(_answer_text(messages).strip())
                        separator = "\n\n" if wrote else ""
                        to_payload.wrote_text = True
                        yield _line({"type": "text", "delta": separator + question})
                        messages = _with_text(messages, question)
                    await turn.save(deps.scenario, messages)
                payload = to_payload(event)
                if payload is not None:
                    yield _line(payload)
    except Exception as exc:
        logger.exception("Assistant run failed")
        yield _line({"type": "error", "message": _error_message(exc)})


@dataclass
class _Translator:
    """Maps Pydantic AI stream events to our small NDJSON protocol, and measures the turn."""

    wrote_text: bool = False
    started: float = field(default_factory=time.monotonic)
    first_text: float | None = None

    def __call__(self, event: object) -> dict[str, Any] | None:
        match event:
            case PartStartEvent(part=TextPart(content=content)):
                separator = "\n\n" if self.wrote_text else ""
                self.wrote_text = True
                self._text_started()
                return {"type": "text", "delta": separator + content} if content else None
            case PartDeltaEvent(delta=TextPartDelta(content_delta=delta)) if delta:
                self.wrote_text = True
                self._text_started()
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
            case AgentRunResultEvent(result=result):
                return {"type": "done", "usage": self._measure(result)}
        return None

    def _text_started(self) -> None:
        if self.first_text is None:
            self.first_text = time.monotonic()

    def _measure(self, result: AgentRunResult[Any]) -> dict[str, Any]:
        """ZADANIA B.17: time to the first text, the whole turn and the tokens of all its
        requests, logged as one line (no conversation content) and sent in the `done` event
        for `tools/eval`. `input_tokens` include the cached ones."""
        usage = result.usage
        metrics: dict[str, Any] = {
            "first_text_s": _seconds(self.first_text, self.started),
            "total_s": _seconds(time.monotonic(), self.started),
            "requests": usage.requests,
            "input_tokens": usage.input_tokens,
            "cache_read_tokens": usage.cache_read_tokens,
            "cache_write_tokens": usage.cache_write_tokens,
            "output_tokens": usage.output_tokens,
            "cost_usd": _cost(result.new_messages()),
        }
        turn_log.info("chat turn %s", json.dumps(metrics))
        return metrics


def _args(part: ToolCallPart) -> dict[str, Any]:
    try:
        return part.args_as_dict()
    except ValueError:
        return {}


def _line(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False) + "\n"


def _seconds(moment: float | None, start: float) -> float | None:
    return None if moment is None else round(moment - start, 2)


def _cost(messages: list[ModelMessage]) -> float | None:
    """The price of the turn's responses from genai-prices; None when a model has no price."""
    try:
        return round(
            sum(float(m.cost().total_price) for m in messages if isinstance(m, ModelResponse)),
            6,
        )
    except Exception:  # unknown model or provider, e.g. the scripted model in tests
        return None


def _turn_logger() -> logging.Logger:
    """One INFO line per chat turn, shown by `npm run dev` without configuring logging."""
    log = logging.getLogger("app.chat.turns")
    if not log.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(levelname)s:     %(message)s"))
        log.addHandler(handler)
        log.setLevel(logging.INFO)
        log.propagate = False
    return log


turn_log = _turn_logger()


def _error_message(exc: Exception) -> str:
    match exc:
        case ModelAuthenticationError():
            return "Klucz API modelu jest nieprawidłowy."
        case ModelQuotaExceededError():
            return "Asystent AI jest chwilowo niedostępny: wyczerpał się limit konta modelu."
        case ModelRateLimitError() | ModelUnavailableError() | ModelServerError():
            return "Model AI jest teraz przeciążony. Spróbuj za chwilę."
        case ModelConnectionError():
            return "Nie udało się połączyć z modelem AI. Sprawdź internet i spróbuj za chwilę."
        case UsageLimitExceeded():
            return "Asystent potrzebował zbyt wielu kroków. Spróbuj zapytać prościej."
        case _:
            return "Coś poszło nie tak po stronie asystenta. Spróbuj jeszcze raz."


def _closing_question(deps: AssistantDeps, messages: list[ModelMessage]) -> str | None:
    """The interview question the server adds under the model's answer: the first one the
    interview state gives, unless the answer already ends with it word for word."""
    questions = interview_questions(deps.scenario)
    if not questions:
        return None
    text = questions[0].text
    return None if _answer_text(messages).rstrip().endswith(text) else text


def _answer_text(messages: list[ModelMessage]) -> str:
    """The text of the model's last answer in the history."""
    last = messages[-1] if messages else None
    if not isinstance(last, ModelResponse):
        return ""
    return "".join(p.content for p in last.parts if isinstance(p, TextPart))


def _with_text(messages: list[ModelMessage], text: str) -> list[ModelMessage]:
    """The history with `text` added to the model's last answer, as if it had written it."""
    last = messages[-1] if messages else None
    if not isinstance(last, ModelResponse):
        return [*messages, ModelResponse(parts=[TextPart(content=text)])]
    return [*messages[:-1], replace(last, parts=[*last.parts, TextPart(content=text)])]


def _question(scenario: Scenario) -> dict[str, str] | None:
    question = next_question(scenario)
    return question.model_dump() if question else None
