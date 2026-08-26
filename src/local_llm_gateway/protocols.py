from __future__ import annotations

from collections.abc import Iterable
from typing import Any

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
            if item.get("type") == "text" and isinstance(item.get("text"), str):
                parts.append(item["text"])
            elif item.get("type") == "input_text" and isinstance(item.get("text"), str):
                parts.append(item["text"])
        return "".join(parts)
    return str(content)


def messages_to_prompt(messages: Iterable[dict[str, Any]], system: str | list[dict[str, Any]] | None = None) -> str:
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
