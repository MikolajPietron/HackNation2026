"""Dev only: the chat through the local Claude Code CLI, on the developer's claude.ai subscription.

`CLAUDE_CODE_MODEL=opus` (or `sonnet`, or a full model id) in backend/.env makes `get_chat_model`
return this model instead of a provider's API: every request of the agent becomes one
`claude -p` run, which counts against the subscription's limits instead of costing API tokens.
Meant for `tools/eval` on the developer's own machine, never on a server: one person's
subscription is not a backend for an app other people use.

Claude Code cannot take our tools natively, so each request is rendered as text: the agent's
instructions are the system prompt, the tools available for this request and the conversation
so far are the prompt, and the answer comes back as structured output `{text, tool_calls}`
(`--json-schema`). The agent loop, the tools, the events and everything `tools/eval` checks stay
ours. What differs from production: tool calls are emulated (not native tool use), nothing
streams (the whole answer arrives at once, so the time to the first text is the time of the
request), and the tokens and cost in `done.usage` are Pydantic AI's estimates, not the bill.
"""

import asyncio
import json
import os
import tempfile
import uuid
from collections.abc import AsyncIterator, Iterable
from functools import cache
from pathlib import Path
from typing import Any

from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    ModelResponse,
    TextPart,
    ToolCallPart,
    ToolReturnPart,
    UserPromptPart,
)
from pydantic_ai.models.function import AgentInfo, DeltaToolCall, DeltaToolCalls, FunctionModel
from pydantic_ai.tools import ToolDefinition

TIMEOUT_S = 300
"""One request: the CLI starts, the model may think, structured output takes a second round."""

EFFORT = {"minimal": "low", "low": "low", "medium": "medium", "high": "high", "xhigh": "xhigh"}
EFFORT |= {"max": "max"}
"""`ModelSettings.thinking` → `claude --effort` (the CLI has no "minimal")."""

API_ENV = ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_BASE_URL", "CLAUDECODE")
"""Removed from the CLI's environment: with an API key set, Claude Code bills the key instead of
the subscription, which is the whole point of this model."""

INVISIBLE = "\u200b\u200c\u200d\u2060\ufeff"

ANSWER_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "text": {"type": "string"},
        "tool_calls": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"name": {"type": "string"}, "args": {"type": "object"}},
                "required": ["name", "args"],
            },
        },
    },
    "required": ["text", "tool_calls"],
}

PROTOCOL = """

# How to answer in this environment

You are the assistant described above, running inside the application. Here you cannot call
tools directly: you answer with one JSON object (the structured output) and the application runs
the tools for you.

- `tool_calls`: the tools to call now, each `{"name": ..., "args": {...}}` with arguments that
  match the tool's JSON schema. An empty list when you need no more tools.
- `text`: your whole answer to the parent, written as the instructions above say. Leave it empty
  while you call tools; write it in the message where `tool_calls` is empty (your last one), so
  it can use the tools' results. That last message must have text.

After your tool calls the application runs them and asks you again, with their results at the end
of the conversation; then continue. Call only the tools listed below for this request. Never put
tool calls, JSON or these technical rules into `text`.

## Tools available for this request
"""


def claude_code_model(model: str) -> FunctionModel:
    """The chat model backed by `claude -p --model <model>`."""

    async def stream(
        messages: list[ModelMessage], info: AgentInfo
    ) -> AsyncIterator[str | DeltaToolCalls]:
        answer = await _ask(model, messages, info)
        # Zero-width characters too: an "empty" text came back as a lone U+200B in the eval.
        text = str(answer.get("text") or "").strip().strip(INVISIBLE).strip()
        calls = [c for c in answer.get("tool_calls") or [] if isinstance(c, dict) and c.get("name")]
        if text or not calls:
            # Nothing at all: an empty text, so Pydantic AI asks again, as after an empty API
            # answer (the stream must yield something).
            yield text
        if calls:
            yield {
                i: DeltaToolCall(
                    name=str(call["name"]),
                    json_args=json.dumps(call.get("args") or {}, ensure_ascii=False),
                    tool_call_id=f"cc_{uuid.uuid4().hex[:12]}",
                )
                for i, call in enumerate(calls)
            }

    return FunctionModel(stream_function=stream, model_name=f"claude-code:{model}")


async def _ask(model: str, messages: list[ModelMessage], info: AgentInfo) -> dict[str, Any]:
    tools = [*info.function_tools, *info.output_tools]
    thinking = (info.model_settings or {}).get("thinking")
    result = await run_claude(
        model,
        system=(info.instructions or "") + PROTOCOL + _tools_text(tools),
        prompt=_conversation_text(messages),
        schema=ANSWER_SCHEMA,
        effort=EFFORT.get(thinking) if isinstance(thinking, str) else None,
    )
    answer = result.get("structured_output")
    if not isinstance(answer, dict):
        try:
            answer = json.loads(result.get("result") or "")
        except json.JSONDecodeError:
            # No JSON at all: take what it wrote as the text of the answer.
            answer = {"text": str(result.get("result") or ""), "tool_calls": []}
    return answer if isinstance(answer, dict) else {"text": str(answer), "tool_calls": []}


async def run_claude(
    model: str,
    *,
    system: str,
    prompt: str | list[dict[str, Any]],
    schema: dict[str, Any],
    effort: str | None = None,
    timeout: float = TIMEOUT_S,
) -> dict[str, Any]:
    """One `claude -p` run with no tools, no settings, no MCP and no saved session, on the
    subscription; returns Claude Code's result (`structured_output`, `usage`). `prompt` is text,
    or content blocks (text and base64 images, as in the Messages API) sent as one stream-json
    user message."""
    blocks = not isinstance(prompt, str)
    with tempfile.NamedTemporaryFile("w", suffix=".txt", dir=_workdir(), delete=False) as f:
        f.write(system)
        system_file = f.name
    command = ["claude", "-p", "--model", model, "--tools", "", "--setting-sources", ""]
    command += ["--strict-mcp-config", "--no-session-persistence"]
    command += ["--system-prompt-file", system_file, "--json-schema", json.dumps(schema)]
    if blocks:
        command += ["--input-format", "stream-json", "--output-format", "stream-json", "--verbose"]
        message = {"type": "user", "message": {"role": "user", "content": prompt}}
        stdin = json.dumps(message, ensure_ascii=False) + "\n"
    else:
        command += ["--output-format", "json"]
        stdin = str(prompt)
    if effort:
        command += ["--effort", effort]
    try:
        process = await asyncio.create_subprocess_exec(
            *command,
            cwd=_workdir(),
            env={k: v for k, v in os.environ.items() if k not in API_ENV},
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            out, err = await asyncio.wait_for(process.communicate(stdin.encode()), timeout)
        except TimeoutError:
            process.kill()
            raise RuntimeError(f"claude -p: no answer in {timeout:.0f} s") from None
    finally:
        Path(system_file).unlink(missing_ok=True)
    return _result(out.decode(), err.decode(), process.returncode)


def _result(out: str, err: str, code: int | None) -> dict[str, Any]:
    """The result object: the whole output (json) or its last `result` line (stream-json)."""
    result: dict[str, Any] | None = None
    for line in reversed(out.strip().splitlines()):
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(item, dict) and item.get("type") == "result":
            result = item
            break
    if result is None:
        raise RuntimeError(f"claude -p exited {code}: {(err or out).strip()[-500:]}")
    if result.get("is_error"):
        raise RuntimeError(f"claude -p: {result.get('subtype')}: {str(result.get('result'))[:500]}")
    return result


@cache
def _workdir() -> str:
    """An empty folder: no CLAUDE.md, memory or project settings reach the CLI."""
    return tempfile.mkdtemp(prefix="claude-code-")


def _tools_text(tools: Iterable[ToolDefinition]) -> str:
    blocks = [
        f"### {t.name}\n{(t.description or '').strip()}\n"
        f"Arguments (JSON Schema): {json.dumps(t.parameters_json_schema, ensure_ascii=False)}"
        for t in tools
    ]
    return "\n\n".join(blocks) if blocks else "(none: answer with text only)"


def _conversation_text(messages: list[ModelMessage]) -> str:
    """The history as a transcript the model continues with its next message."""
    lines = ["# The conversation so far", ""]
    for message in messages:
        if isinstance(message, ModelRequest):
            for part in message.parts:
                lines += _request_part(part)
        elif isinstance(message, ModelResponse):
            for part in message.parts:
                if isinstance(part, TextPart) and part.content.strip():
                    lines += ["[assistant]", part.content, ""]
                elif isinstance(part, ToolCallPart):
                    lines += [
                        f"[assistant calls {part.tool_name}, id {part.tool_call_id}]",
                        part.args_as_json_str(),
                        "",
                    ]
    lines += ["Write your next message as the assistant: the JSON object."]
    return "\n".join(lines)


def _request_part(part: Any) -> list[str]:
    if isinstance(part, UserPromptPart):
        content = part.content
        if not isinstance(content, str):
            content = "\n".join(
                c if isinstance(c, str) else f"[{type(c).__name__}]" for c in content
            )
        return ["[user]", content, ""]
    if isinstance(part, ToolReturnPart):
        return [
            f"[result of {part.tool_name}, id {part.tool_call_id}]",
            part.model_response_str(),
            "",
        ]
    if hasattr(part, "model_response"):  # a retry: a tool's error or invalid arguments
        name = getattr(part, "tool_name", None)
        head = f"[error of {name}, id {getattr(part, 'tool_call_id', '')}]" if name else "[error]"
        return [head, str(part.model_response()), ""]
    content = getattr(part, "content", None)
    if isinstance(content, str) and content.strip():
        # A system prompt or an instruction that arrives during the run.
        return [f"[application: {getattr(part, 'part_kind', 'note')}]", content, ""]
    return []
