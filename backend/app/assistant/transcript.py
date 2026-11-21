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
                if isinstance(part, UserPromptPart) and isinstance(part.content, str):
                    add("user")["parts"].append({"kind": "text", "text": part.content})
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
