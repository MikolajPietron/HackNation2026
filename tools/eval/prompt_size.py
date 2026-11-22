"""What the chat model gets per turn, measured offline: no LLM calls, no network.

The chat runs through the real endpoint (`POST /api/chat`) on a scripted model that records
what every request sent: instructions, tool definitions and messages. For representative
interview states it prints the size of one turn in characters and an approximate token count
(characters / 3, about what Claude's tokenizer gives for Polish text). Each state's turn is
the parent's message, one tool call that fits the state and the answer after it: two requests,
as most turns of the interview. Run it before and after changing prompts, tools or describe.py:

    cd backend && uv run python ../tools/eval/prompt_size.py
    cd backend && uv run python ../tools/eval/prompt_size.py --json /tmp/sizes.json
    cd backend && uv run python ../tools/eval/prompt_size.py --backend /path/to/old/backend

`--backend` measures another checkout of the backend (e.g. an older commit exported with
`git archive`), with this checkout's virtual environment.

Columns of the first request: "static" is the literal instructions (the cacheable prefix with
the tools), "state" the instructions rebuilt before every request (`current_state`), "messages"
the user prompt and history. "turn" adds up every request of the turn: what the provider bills
as input tokens, cached or not.
"""

import argparse
import asyncio
import datetime as dt
import json
import logging
import os
import sys
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

DEFAULT_BACKEND = Path(__file__).resolve().parents[2] / "backend"
_backend = DEFAULT_BACKEND
if "--backend" in sys.argv:
    _backend = Path(sys.argv[sys.argv.index("--backend") + 1]).resolve()
sys.path.insert(0, str(_backend))
os.environ.setdefault("PYDANTIC_AI_NO_BANNER", "1")

from fastapi.testclient import TestClient  # noqa: E402
from pydantic_ai import (  # noqa: E402
    ModelMessage,
    ModelRequest,
    TextPart,
    ToolCallPart,
    ToolReturnPart,
    UserPromptPart,
)
from pydantic_ai.models.function import AgentInfo, DeltaToolCall, FunctionModel  # noqa: E402

from app.api.deps import (  # noqa: E402
    get_chat_model,
    get_param_store,
    get_session_store,
    get_today,
)
from app.engine import Scenario  # noqa: E402
from app.main import app  # noqa: E402
from app.services.param_versions import MemoryParamStore  # noqa: E402
from app.services.sessions import MemorySessionStore  # noqa: E402

TODAY = dt.date(2026, 11, 21)  # the day tools/eval/scenarios.py assumes
CHARS_PER_TOKEN = 3.0

EXPECTING = {
    "role": "mother",
    "child_born": False,
    "date": "2027-03-15",
    "children_count": 1,
    "work": "employment",
}
BORN = {**EXPECTING, "child_born": True, "date": "2026-10-01"}
ADOPTION = {
    "role": "mother",
    "child_born": True,
    "date": "2024-05-10",
    "children_count": 1,
    "work": "none",
    "taken_in": {"kind": "adoption", "date": "2026-11-02"},
}
MONEY = {
    **EXPECTING,
    "payer_size": "over-20",
    "pay": 8000,
    "partner": {"work": "employment", "payer_size": "over-20", "pay": 6000},
}
Call = tuple[str, dict[str, Any]]


@dataclass(frozen=True)
class State:
    name: str
    onboarding: dict[str, Any]
    changes: dict[str, Any]
    """Scenario fields stored before the turn (answers given earlier)."""
    body: dict[str, str]
    """The turn: {"message": …} or {"event": …}."""
    call: Call
    """The tool the scripted model calls before it answers."""


STATES = [
    State(
        "expecting-event",
        EXPECTING,
        {},
        {"event": "timeline_ready"},
        ("explain_timeline_element", {"element_id": "maternity"}),
    ),
    State(
        "expecting-early",
        EXPECTING,
        {},
        {"message": "Będę pracować do porodu."},
        ("set_leave_before_birth", {"weeks": 0}),
    ),
    State(
        "born",
        BORN,
        {"leave_before_birth_weeks": 0},
        {"message": "Urodziła się o czasie i nie była w szpitalu."},
        ("set_hospital_care", {"applies": False}),
    ),
    State(
        "after-loss",
        BORN,
        {"leave_before_birth_weeks": 0, "losses": [{"died_on": "2026-11-20"}]},
        {"message": "Co mi teraz przysługuje?"},
        ("explain_timeline_element", {"element_id": "maternity"}),
    ),
    State(
        "adoption",
        ADOPTION,
        {},
        {"message": "Mąż pracuje na etacie."},
        ("set_father_work", {"work": "employment"}),
    ),
    State(
        "money",
        MONEY,
        {"leave_before_birth_weeks": 0},
        {"message": "Złożę wniosek o 81,5%."},
        ("set_rate_choice", {"rate_815": True}),
    ),
]

# A short conversation with tool calls: the history and the tool results grow turn by turn.
CONVERSATION: list[tuple[dict[str, str], Call]] = [
    ({"event": "timeline_ready"}, ("explain_timeline_element", {"element_id": "maternity"})),
    ({"message": "Będą bliźnięta."}, ("set_children_count", {"count": 2})),
    ({"message": "Będę pracować do porodu."}, ("set_leave_before_birth", {"weeks": 0})),
    ({"message": "Mąż pracuje na etacie."}, ("set_father_work", {"work": "employment"})),
    (
        {"message": "Ile trwa urlop ojcowski?"},
        ("explain_timeline_element", {"element_id": "paternity"}),
    ),
]


@dataclass
class Request:
    """One model request: sizes in characters."""

    static: int
    state: int
    tools: int
    messages: int
    tool_names: list[str] = field(default_factory=list)

    @property
    def total(self) -> int:
        return self.static + self.state + self.tools + self.messages


def _tools_chars(info: AgentInfo) -> int:
    return len(
        json.dumps(
            [
                {
                    "name": t.name,
                    "description": t.description,
                    "input_schema": t.parameters_json_schema,
                }
                for t in info.function_tools
            ],
            ensure_ascii=False,
        )
    )


def _messages_chars(messages: list[ModelMessage]) -> int:
    total = 0
    for message in messages:
        for part in message.parts:
            match part:
                case UserPromptPart(content=str() as text) | TextPart(content=text):
                    total += len(text)
                case ToolReturnPart():
                    total += len(part.model_response_str())
                case ToolCallPart():
                    total += len(part.tool_name) + len(part.args_as_json_str())
    return total


def _split_instructions(info: AgentInfo) -> tuple[int, int]:
    """(static, dynamic) characters of the instructions the model got."""
    parts = info.model_request_parameters.instruction_parts or []
    if not parts:
        return len(info.instructions or ""), 0
    static = sum(len(p.content) + 2 for p in parts if not p.dynamic)
    dynamic = sum(len(p.content) + 2 for p in parts if p.dynamic)
    return static, dynamic


def recording_model(requests: list[Request], call: Call) -> FunctionModel:
    """Records every request; calls `call` once, then answers with a short text."""

    async def stream(messages: list[ModelMessage], info: AgentInfo) -> AsyncIterator[Any]:
        static, dynamic = _split_instructions(info)
        requests.append(
            Request(
                static=static,
                state=dynamic,
                tools=_tools_chars(info),
                messages=_messages_chars(messages),
                tool_names=sorted(t.name for t in info.function_tools),
            )
        )
        last = messages[-1]
        answered = isinstance(last, ModelRequest) and any(
            isinstance(p, ToolReturnPart) for p in last.parts
        )
        if not answered:
            name, args = call
            yield {0: DeltaToolCall(name, json.dumps(args), tool_call_id=f"c-{uuid4().hex[:8]}")}
        else:
            yield "Odpowiedź asystenta w dwóch krótkich zdaniach. Tak wygląda zwykła długość."

    return FunctionModel(stream_function=stream)


def _client(store: MemorySessionStore) -> TestClient:
    app.dependency_overrides[get_today] = lambda: TODAY
    app.dependency_overrides[get_session_store] = lambda: store
    params = MemoryParamStore()
    app.dependency_overrides[get_param_store] = lambda: params
    return TestClient(app)


def _turn(client: TestClient, sid: UUID, call: Call, body: dict[str, str]) -> list[Request]:
    requests: list[Request] = []
    model = recording_model(requests, call)
    app.dependency_overrides[get_chat_model] = lambda: model
    response = client.post("/api/chat", json={"session_id": str(sid), **body})
    response.raise_for_status()
    lines = [json.loads(x) for x in response.text.splitlines() if x]
    errors = [e["message"] for e in lines if e["type"] == "error"]
    failed = [e["name"] for e in lines if e["type"] == "tool-result" and not e["ok"]]
    if errors or failed:
        raise RuntimeError(f"turn failed: {errors or failed}")
    return requests


def measure_state(state: State) -> list[Request]:
    store = MemorySessionStore()
    client = _client(store)
    sid = uuid4()
    client.put(f"/api/session/{sid}/onboarding", json=state.onboarding).raise_for_status()
    if state.changes:
        session = asyncio.run(store.load(sid))
        session.scenario = Scenario.model_validate(
            {**session.scenario.model_dump(), **state.changes}
        )
        asyncio.run(store.save(sid, session))
    return _turn(client, sid, state.call, state.body)


def measure_conversation() -> list[list[Request]]:
    store = MemorySessionStore()
    client = _client(store)
    sid = uuid4()
    client.put(f"/api/session/{sid}/onboarding", json=EXPECTING).raise_for_status()
    return [_turn(client, sid, call, body) for body, call in CONVERSATION]


logging.getLogger("app.chat.turns").setLevel(logging.WARNING)  # the scripted turns' log lines


def tokens(chars: int) -> int:
    return round(chars / CHARS_PER_TOKEN)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("--json", type=Path, help="write the numbers as JSON here")
    parser.add_argument(
        "--backend", type=Path, default=DEFAULT_BACKEND, help="the backend checkout to measure"
    )
    args = parser.parse_args()

    out: dict[str, Any] = {"backend": str(args.backend), "states": {}, "conversation": []}
    print(f"backend: {args.backend}")
    print(f"One turn per state (chars; ~tokens = chars / {CHARS_PER_TOKEN:g})")
    head = f"{'state':16} {'static':>7} {'tools':>7} {'state':>7} {'msgs':>6} {'1st req':>8}"
    print(f"{head} {'turn':>8} {'~tokens':>8}  tools")
    print("-" * 92)
    for state in STATES:
        requests = measure_state(state)
        first = requests[0]
        turn = sum(r.total for r in requests)
        out["states"][state.name] = {
            "first_request": {**first.__dict__, "total": first.total},
            "requests": len(requests),
            "turn_chars": turn,
            "turn_tokens": tokens(turn),
        }
        print(
            f"{state.name:16} {first.static:>7} {first.tools:>7} {first.state:>7} "
            f"{first.messages:>6} {first.total:>8} {turn:>8} {tokens(turn):>8}  "
            f"{len(first.tool_names)}"
        )

    print("\nConversation (expecting mother, 5 turns with tool calls): all requests of a turn")
    print(f"{'turn':4} {'requests':>8} {'input chars':>12} {'~tokens':>8}  input")
    print("-" * 92)
    grand = 0
    for index, ((body, _call), requests) in enumerate(
        zip(CONVERSATION, measure_conversation(), strict=True), 1
    ):
        chars = sum(r.total for r in requests)
        grand += chars
        said = body.get("message") or f"<{body.get('event')}>"
        out["conversation"].append({"turn": index, "requests": len(requests), "chars": chars})
        print(f"{index:<4} {len(requests):>8} {chars:>12} {tokens(chars):>8}  {said}")
    print(f"{'all':4} {'':>8} {grand:>12} {tokens(grand):>8}")
    out["conversation_total"] = {"chars": grand, "tokens": tokens(grand)}
    if args.json:
        args.json.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"\ndetails: {args.json}")
    app.dependency_overrides.clear()
    return 0


if __name__ == "__main__":
    sys.exit(main())
