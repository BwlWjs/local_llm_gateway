from collections.abc import AsyncIterator
import json
from typing import Any

from .models import CanonicalStreamEvent, ProviderTarget, StreamEventType, UsageInfo


def encode_sse(event_type: str, data: dict[str, Any]) -> bytes:
    return f"event: {event_type}\ndata: {json.dumps(data, ensure_ascii=False, separators=(',', ':'))}\n\n".encode("utf-8")


async def passthrough_stream(chunks: AsyncIterator[bytes]) -> AsyncIterator[bytes]:
    async for chunk in chunks:
        yield chunk


def canonical_message_start(message_id: str, model: str) -> bytes:
    event = CanonicalStreamEvent(
        event_type=StreamEventType.message_start,
        delta={},
        raw_provider_event={"message_id": message_id, "model": model},
    )
    payload = {
        "type": event.event_type.value,
        "message": {
            "id": message_id,
            "type": "message",
            "role": "assistant",
            "model": model,
            "content": [],
            "stop_reason": None,
            "stop_sequence": None,
            "usage": {"input_tokens": 0, "output_tokens": 0},
        },
    }
    return encode_sse(event.event_type.value, payload)


def canonical_content_start(index: int = 0) -> bytes:
    event = CanonicalStreamEvent(event_type=StreamEventType.content_block_start, index=index)
    return encode_sse(
        event.event_type.value,
        {"type": event.event_type.value, "index": event.index, "content_block": {"type": "text", "text": ""}},
    )


def canonical_content_delta(text: str, index: int = 0) -> bytes:
    event = CanonicalStreamEvent(event_type=StreamEventType.content_block_delta, index=index, delta={"text": text})
    return encode_sse(
        event.event_type.value,
        {"type": event.event_type.value, "index": event.index, "delta": {"type": "text_delta", "text": text}},
    )


def canonical_content_stop(index: int = 0) -> bytes:
    event = CanonicalStreamEvent(event_type=StreamEventType.content_block_stop, index=index)
    return encode_sse(event.event_type.value, {"type": event.event_type.value, "index": event.index})


def canonical_message_delta(stop_reason: str, usage: UsageInfo) -> bytes:
    event = CanonicalStreamEvent(event_type=StreamEventType.message_delta, stop_reason=stop_reason, usage=usage)
    return encode_sse(
        event.event_type.value,
        {
            "type": event.event_type.value,
            "delta": {"stop_reason": event.stop_reason, "stop_sequence": None},
            "usage": {"output_tokens": event.usage.output_tokens if event.usage else 0},
        },
    )


def canonical_message_stop() -> bytes:
    event = CanonicalStreamEvent(event_type=StreamEventType.message_stop)
    return encode_sse(event.event_type.value, {"type": event.event_type.value})


def canonical_error(code: str, detail: str, extra: dict[str, Any] | None = None) -> bytes:
    event = CanonicalStreamEvent(event_type=StreamEventType.error)
    payload = {
        "type": event.event_type.value,
        "error": {
            "type": code,
            "message": detail,
            "extra": extra or {},
        },
    }
    return encode_sse(event.event_type.value, payload)


async def ollama_line_stream_to_sse(
    lines: AsyncIterator[str],
    target: ProviderTarget,
    message_id: str,
) -> AsyncIterator[bytes]:
    yield canonical_message_start(message_id, target.model)
    yield canonical_content_start(0)
    output_tokens = 0
    usage = UsageInfo()
    async for line in lines:
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        message = payload.get("message") or {}
        content = message.get("content")
        if isinstance(content, str) and content:
            output_tokens += max(1, len(content) // 4)
            yield canonical_content_delta(content, 0)
        if payload.get("done"):
            usage = UsageInfo(
                input_tokens=int(payload.get("prompt_eval_count") or 0),
                output_tokens=int(payload.get("eval_count") or output_tokens),
            )
            reason = str(payload.get("done_reason") or "end_turn")
            yield canonical_content_stop(0)
            yield canonical_message_delta(reason, usage)
            yield canonical_message_stop()
            return

    yield canonical_content_stop(0)
    yield canonical_message_delta("end_turn", usage)
    yield canonical_message_stop()
