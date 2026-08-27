from __future__ import annotations

import asyncio

import pytest

from local_llm_gateway.core.errors import GatewayError
from local_llm_gateway.core.runtime import RuntimeSnapshot
from local_llm_gateway.core.service import GatewayService
from local_llm_gateway.facades.anthropic import AnthropicFacade
from local_llm_gateway.facades.openai import OpenAIFacade
from local_llm_gateway.models import (
    CanonicalResponse,
    MessageRequest,
    OpenAIChatCompletionRequest,
    ProtocolName,
    UsageInfo,
)
from local_llm_gateway.providers.registry import get_provider_adapter
from local_llm_gateway.router import ModelRegistry
from local_llm_gateway.streaming import ollama_line_stream_to_sse
from local_llm_gateway.translator import (
    canonical_response_to_anthropic,
    canonical_response_to_openai,
)


def _test_registry() -> ModelRegistry:
    return ModelRegistry(
        raw="{}",
        defaults={
            "local-coder": {
                "provider": "ollama",
                "model": "qwen2.5-coder:7b",
                "display_name": "Local Coder",
            }
        },
        provider_caps={
            "ollama": {
                "supports_messages": True,
                "supports_stream": True,
                "supports_count_tokens": False,
                "supports_tools": True,
                "supports_system": True,
                "max_context_tokens": 8192,
            }
        },
    )


def test_default_route_resolves_to_ollama_qwen():
    target = _test_registry().resolve("local-coder")

    assert target.provider == "ollama"
    assert target.model == "qwen2.5-coder:7b"
    assert target.supports_stream is True


def test_unknown_model_raises_route_not_found():
    with pytest.raises(GatewayError) as exc_info:
        _test_registry().resolve("missing-model")

    assert exc_info.value.status_code == 404
    assert exc_info.value.code == "route_not_found"


def test_unknown_provider_raises_gateway_error():
    with pytest.raises(GatewayError) as exc_info:
        get_provider_adapter("unknown")

    assert exc_info.value.status_code == 501
    assert exc_info.value.code == "provider_unsupported"


def test_anthropic_facade_builds_canonical_request():
    request = MessageRequest(
        model="local-coder",
        messages=[{"role": "user", "content": "hello"}],
        system="system prompt",
        temperature=0.2,
        top_p=0.9,
        top_k=40,
        stop_sequences=["END"],
        metadata={"trace": "x"},
    )

    canonical = AnthropicFacade().to_canonical(request, "req_test")

    assert canonical.protocol == ProtocolName.anthropic
    assert canonical.request_id == "req_test"
    assert canonical.sampling.top_k == 40
    assert canonical.sampling.stop_sequences == ["END"]
    assert canonical.metadata == {"trace": "x"}


def test_openai_facade_builds_canonical_request():
    request = OpenAIChatCompletionRequest(
        model="local-coder",
        messages=[{"role": "user", "content": "hello"}],
        stream=True,
        temperature=0.2,
        top_p=0.8,
        top_k=32,
        stop="END",
        stream_options={"include_usage": True},
    )

    canonical = OpenAIFacade().to_canonical(request, "req_test")

    assert canonical.protocol == ProtocolName.openai
    assert canonical.stream is True
    assert canonical.sampling.top_k == 32
    assert canonical.sampling.stop_sequences == ["END"]
    assert canonical.stream_options == {"include_usage": True}


def test_service_lists_default_model():
    service = GatewayService(runtime=RuntimeSnapshot(registry=_test_registry()))

    response = service.list_models()

    assert response.data
    assert response.data[0].id == "local-coder"


def test_response_translators_return_protocol_shapes():
    response = CanonicalResponse(
        id="msg_test",
        model="qwen2.5-coder:7b",
        content=[{"type": "text", "text": "hello"}],
        stop_reason="end_turn",
        usage=UsageInfo(input_tokens=3, output_tokens=2),
    )

    anthropic = canonical_response_to_anthropic(response)
    openai = canonical_response_to_openai(response)

    assert anthropic["id"] == "msg_test"
    assert anthropic["usage"] == {"input_tokens": 3, "output_tokens": 2}
    assert openai["object"] == "chat.completion"
    assert openai["choices"][0]["message"]["content"] == "hello"
    assert openai["usage"]["total_tokens"] == 5


def test_ollama_line_stream_to_sse_emits_expected_events():
    async def _collect() -> list[bytes]:
        async def _lines():
            yield '{"message":{"content":"hel"},"done":false}'
            yield '{"message":{"content":"lo"},"done":true,"done_reason":"stop","prompt_eval_count":10,"eval_count":2}'

        target = _test_registry().resolve("local-coder")
        chunks = []
        async for chunk in ollama_line_stream_to_sse(_lines(), target, "msg_test"):
            chunks.append(chunk)
        return chunks

    chunks = asyncio.run(_collect())

    assert chunks[0].startswith(b"event: message_start")
    assert chunks[1].startswith(b"event: content_block_start")
    assert any(chunk.startswith(b"event: content_block_delta") for chunk in chunks)
    assert any(chunk.startswith(b"event: message_delta") for chunk in chunks)
    assert chunks[-1].startswith(b"event: message_stop")


def test_anthropic_stop_reason_mapping():
    from local_llm_gateway.streaming import to_anthropic_stop_reason

    assert to_anthropic_stop_reason("stop") == "end_turn"
    assert to_anthropic_stop_reason("length") == "max_tokens"
    assert to_anthropic_stop_reason("tool_calls") == "tool_use"
    assert to_anthropic_stop_reason("end_turn") == "end_turn"
    assert to_anthropic_stop_reason(None) is None
    assert to_anthropic_stop_reason("unexpected") == "end_turn"


def test_anthropic_translator_maps_openai_stop_reason():
    response = CanonicalResponse(
        id="msg_test",
        model="qwen2.5-coder:7b",
        content=[{"type": "text", "text": "hello"}],
        stop_reason="stop",
        usage=UsageInfo(input_tokens=3, output_tokens=2),
    )

    anthropic = canonical_response_to_anthropic(response)

    assert anthropic["stop_reason"] == "end_turn"


def test_ollama_stream_maps_stop_to_end_turn():
    async def _collect() -> list[bytes]:
        async def _lines():
            yield '{"message":{"content":"hi"},"done":true,"done_reason":"stop","prompt_eval_count":1,"eval_count":1}'

        target = _test_registry().resolve("local-coder")
        chunks = []
        async for chunk in ollama_line_stream_to_sse(_lines(), target, "msg_test"):
            chunks.append(chunk)
        return chunks

    chunks = asyncio.run(_collect())

    delta = next(c for c in chunks if c.startswith(b"event: message_delta"))
    assert b'"stop_reason":"end_turn"' in delta
