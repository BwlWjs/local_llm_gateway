from __future__ import annotations

import json
from collections.abc import Iterable
from typing import Any
from uuid import uuid4

from .models import CanonicalRequest, TokenCountRequest


def content_to_text(content: Any) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if not isinstance(item, dict):
                continue
            if (
                item.get("type") == "text"
                and isinstance(item.get("text"), str)
                or item.get("type") == "input_text"
                and isinstance(item.get("text"), str)
            ):
                parts.append(item["text"])
            elif item.get("type") == "tool_result":
                parts.append(content_to_text(item.get("content")))
        return "".join(parts)
    return str(content)


def messages_to_prompt(
    messages: Iterable[dict[str, Any]], system: str | list[dict[str, Any]] | None = None
) -> str:
    parts: list[str] = []
    if system:
        parts.append(f"System: {content_to_text(system)}")
    for msg in messages:
        role = str(msg.get("role", "user"))
        parts.append(f"{role.title()}: {content_to_text(msg.get('content'))}")
    return "\n".join(parts).strip()


def estimate_tokens(text: str) -> int:
    if not text:
        return 0
    return max(1, len(text) // 4)


def estimate_request_tokens(request: CanonicalRequest | TokenCountRequest) -> int:
    prompt = messages_to_prompt(request.messages, getattr(request, "system", None))
    extra = 0
    if getattr(request, "tools", None):
        extra += estimate_tokens(str(request.tools))
    if getattr(request, "metadata", None):
        extra += estimate_tokens(str(request.metadata))
    return estimate_tokens(prompt) + extra


def _tool_call_id(call_id: Any) -> str:
    if isinstance(call_id, str) and call_id:
        return call_id
    return f"toolu_{uuid4().hex}"


def anthropic_tools_to_provider(
    tools: list[dict[str, Any]] | None,
) -> list[dict[str, Any]]:
    """Convert Anthropic tool schema ({name, description, input_schema}) to OpenAI function tools."""
    if not tools:
        return []
    converted: list[dict[str, Any]] = []
    for tool in tools:
        if not isinstance(tool, dict):
            continue
        if tool.get("type") == "function":
            converted.append(tool)
            continue
        converted.append(
            {
                "type": "function",
                "function": {
                    "name": tool.get("name"),
                    "description": tool.get("description") or "",
                    "parameters": tool.get("input_schema")
                    or {"type": "object", "properties": {}},
                },
            }
        )
    return converted


def anthropic_tool_choice_to_provider(tool_choice: Any) -> Any:
    """Convert Anthropic tool_choice to the OpenAI/Ollama vocabulary."""
    if tool_choice is None:
        return None
    if isinstance(tool_choice, str):
        return {"auto": "auto", "any": "required", "none": "none"}.get(
            tool_choice, "auto"
        )
    if isinstance(tool_choice, dict):
        kind = tool_choice.get("type")
        if kind == "any":
            return "required"
        if kind == "tool" and tool_choice.get("name"):
            return {"type": "function", "function": {"name": tool_choice["name"]}}
        if kind in ("auto", "none"):
            return kind
    return "auto"


def canonical_messages_to_provider(
    messages: list[dict[str, Any]],
    *,
    style: str = "openai",
) -> list[dict[str, Any]]:
    """Convert canonical (Anthropic-shaped) messages to provider chat messages.

    Assistant ``tool_use`` blocks become provider ``tool_calls``; user ``tool_result``
    blocks become ``role: "tool"`` messages. ``style="ollama"`` keeps tool call
    arguments as objects (Ollama convention), ``style="openai"`` serializes them to
    JSON strings and tags tool messages with ``tool_call_id``.
    """
    out: list[dict[str, Any]] = []
    for msg in messages:
        if not isinstance(msg, dict):
            continue
        role = str(msg.get("role", "user"))
        content = msg.get("content")
        if not isinstance(content, list):
            out.append({"role": role, "content": content_to_text(content)})
            continue

        text_parts: list[str] = []
        tool_calls: list[dict[str, Any]] = []
        tool_results: list[dict[str, str]] = []
        for block in content:
            if not isinstance(block, dict):
                continue
            btype = block.get("type")
            if btype == "text" and isinstance(block.get("text"), str):
                text_parts.append(block["text"])
            elif btype == "tool_use":
                arguments = block.get("input")
                if not isinstance(arguments, dict):
                    arguments = {}
                function: dict[str, Any] = {
                    "name": block.get("name"),
                    "arguments": arguments
                    if style == "ollama"
                    else json.dumps(arguments, ensure_ascii=False),
                }
                tool_calls.append(
                    {
                        "id": _tool_call_id(block.get("id")),
                        "type": "function",
                        "function": function,
                    }
                )
            elif btype == "tool_result":
                tool_results.append(
                    {
                        "tool_call_id": str(block.get("tool_use_id") or ""),
                        "content": content_to_text(block.get("content")),
                    }
                )

        entry: dict[str, Any] = {"role": role, "content": "".join(text_parts)}
        if tool_calls:
            entry["tool_calls"] = tool_calls
        # a message that only carries tool results collapses into the tool messages below
        if text_parts or not tool_results:
            out.append(entry)

        for result in tool_results:
            if style == "ollama":
                out.append({"role": "tool", "content": result["content"]})
            else:
                out.append(
                    {
                        "role": "tool",
                        "tool_call_id": result["tool_call_id"],
                        "content": result["content"],
                    }
                )
    return out


def provider_tool_calls_to_content(
    tool_calls: Any, *, style: str = "openai"
) -> list[dict[str, Any]]:
    """Convert provider tool_calls (response side) to Anthropic tool_use content blocks."""
    if not tool_calls or not isinstance(tool_calls, list):
        return []
    blocks: list[dict[str, Any]] = []
    for call in tool_calls:
        if not isinstance(call, dict):
            continue
        function = call.get("function") or {}
        name = function.get("name")
        if not name:
            continue
        arguments = function.get("arguments")
        if style == "ollama":
            input_data = arguments if isinstance(arguments, dict) else {}
        elif isinstance(arguments, str):
            try:
                input_data = json.loads(arguments) if arguments.strip() else {}
            except json.JSONDecodeError:
                input_data = {"_raw": arguments}
        elif isinstance(arguments, dict):
            input_data = arguments
        else:
            input_data = {}
        blocks.append(
            {
                "type": "tool_use",
                "id": _tool_call_id(call.get("id")),
                "name": name,
                "input": input_data,
            }
        )
    return blocks
