"""The stored model history as chat messages for the UI (to restore a conversation)."""

from typing import Any

from pydantic_ai import (
    ModelMessage,
    ModelRequest,
    TextPart,
    ToolCallPart,
    ToolReturnPart,
    UserPromptPart,
)

from app.assistant.prompts import EVENT_MARKER, HINT_MARKER


def to_chat_messages(history: list[ModelMessage]) -> list[dict[str, Any]]:
    """Same shape as the frontend's `ChatMessage`: user texts, assistant texts and tool steps."""
    messages: list[dict[str, Any]] = []
    assistant: dict[str, Any] | None = None
    tools: dict[str, dict[str, Any]] = {}

    def add(role: str) -> dict[str, Any]:
        message = {"id": f"h{len(messages)}", "role": role, "status": "done", "parts": []}
        messages.append(message)
        return message

    for message in history:
        if isinstance(message, ModelRequest):
            for part in message.parts:
                if isinstance(part, UserPromptPart):
                    # App events and hints are not the user's words: hidden, the reply starts
                    # fresh. A message with a hint is [the user's text, hint].
                    texts = [part.content] if isinstance(part.content, str) else part.content
                    hidden = (EVENT_MARKER, HINT_MARKER)
                    said = [t for t in texts if isinstance(t, str) and not t.startswith(hidden)]
                    if said:
                        add("user")["parts"].append({"kind": "text", "text": "\n\n".join(said)})
                    assistant = None
                elif isinstance(part, ToolReturnPart) and part.tool_call_id in tools:
                    ok = part.outcome == "success"
                    tools[part.tool_call_id]["status"] = "done" if ok else "failed"
            continue
        if assistant is None:
            assistant = add("assistant")
        parts = assistant["parts"]
        for part in message.parts:
            if isinstance(part, TextPart) and part.content:
                if parts and parts[-1]["kind"] == "text":
                    parts[-1]["text"] += "\n\n" + part.content
                else:
                    parts.append({"kind": "text", "text": part.content})
            elif isinstance(part, ToolCallPart):
                try:
                    args = part.args_as_dict()
                except ValueError:
                    args = {}
                tool = {
                    "kind": "tool",
                    "id": part.tool_call_id,
                    "name": part.tool_name,
                    "args": args,
                    "status": "done",
                }
                tools[part.tool_call_id] = tool
                parts.append(tool)
    return messages
