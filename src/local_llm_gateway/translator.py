from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from .models import CanonicalResponse
from .protocols import content_to_text
from .streaming import passthrough_stream, to_anthropic_stop_reason


def canonical_response_to_anthropic(response: CanonicalResponse) -> dict[str, Any]:
    return {
        "type": response.type,
        "id": response.id,
        "model": response.model,
        "role": response.role,
        "content": response.content,
        "stop_reason": to_anthropic_stop_reason(response.stop_reason),
        "stop_sequence": response.stop_sequence,
        "usage": response.usage.model_dump(),
    }


def canonical_response_to_openai(response: CanonicalResponse) -> dict[str, Any]:
    text = ""
    if response.content:
        text = content_to_text(response.content)
    return {
        "id": response.id,
        "object": "chat.completion",
        "model": response.model,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": text},
                "finish_reason": response.stop_reason,
            }
        ],
        "usage": {
            "prompt_tokens": response.usage.input_tokens,
            "completion_tokens": response.usage.output_tokens,
            "total_tokens": response.usage.input_tokens + response.usage.output_tokens,
        },
    }


class StreamTranslator:
    async def forward(self, chunks: AsyncIterator[bytes]) -> AsyncIterator[bytes]:
        async for chunk in passthrough_stream(chunks):
            yield chunk
