from __future__ import annotations

import asyncio

from local_llm_gateway.models import (
    CanonicalRequest,
    ProtocolName,
    ProviderTarget,
    SamplingParams,
)
from local_llm_gateway.providers.registry import get_provider_adapter
from local_llm_gateway.streaming import openai_stream_to_sse


def _target() -> ProviderTarget:
    return ProviderTarget(provider="vllm", model="qwen2.5-coder:7b", base_url="http://127.0.0.1:8000")


def _request() -> CanonicalRequest:
    return CanonicalRequest(
        request_id="r1",
        protocol=ProtocolName.openai,
        model="qwen2.5-coder:7b",
        messages=[{"role": "user", "content": "hi"}],
        system="you are helpful",
        max_tokens=50,
        stream=True,
        sampling=SamplingParams(temperature=0.5, top_p=0.9),
    )


def test_vllm_adapter_capabilities():
    adapter = get_provider_adapter("vllm")
    assert adapter.supports_messages is True
    assert adapter.supports_stream is True
    assert adapter.supports_count_tokens is False


def test_vllm_payload_builds_openai_format():
    adapter = get_provider_adapter("vllm")
    payload = adapter._build_payload(_target(), _request(), stream=True)
    assert payload["model"] == "qwen2.5-coder:7b"
    assert payload["stream"] is True
    assert payload["max_tokens"] == 50
    assert payload["temperature"] == 0.5
    assert payload["top_p"] == 0.9
    assert payload["messages"][0] == {"role": "system", "content": "you are helpful"}
    assert payload["messages"][1] == {"role": "user", "content": "hi"}


def test_openai_stream_to_sse():
    target = _target()

    async def lines():
        yield 'data: {"choices":[{"delta":{"content":"Hello"},"finish_reason":null}]}'
        yield 'data: {"choices":[{"delta":{"content":" world"},"finish_reason":null}]}'
        yield 'data: {"choices":[{"delta":{},"finish_reason":"stop"}]}'
        yield "data: [DONE]"

    async def collect():
        return [c async for c in openai_stream_to_sse(lines(), target, "msg_1")]

    joined = b"".join(asyncio.run(collect())).decode()
    assert "Hello" in joined
    assert "world" in joined
    assert "message_stop" in joined
