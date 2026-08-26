from __future__ import annotations

import asyncio

import httpx

from local_llm_gateway.models import (
    CanonicalRequest,
    ProtocolName,
    ProviderTarget,
)
from local_llm_gateway.providers.registry import get_provider_adapter


def _target() -> ProviderTarget:
    return ProviderTarget(provider="ollama", model="m", base_url="http://mock")


def _request() -> CanonicalRequest:
    return CanonicalRequest(
        request_id="r1",
        protocol=ProtocolName.anthropic,
        model="m",
        messages=[{"role": "user", "content": "hello"}],
    )


def test_ollama_create_message_mock():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "message": {"role": "assistant", "content": "hi there"},
                "done": True,
                "prompt_eval_count": 10,
                "eval_count": 2,
            },
        )

    adapter = get_provider_adapter("ollama")

    async def go() -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            resp = await adapter.create_message(client, _target(), _request())
            assert resp.content == [{"type": "text", "text": "hi there"}]
            assert resp.usage.input_tokens == 10
            assert resp.usage.output_tokens == 2

    asyncio.run(go())


def test_ollama_stream_mock_orders_sse():
    async def handler(request: httpx.Request) -> httpx.Response:
        async def body():
            yield b'{"message":{"content":"Hello"},"done":false}\n'
            yield b'{"message":{"content":" world"},"done":true,"prompt_eval_count":5,"eval_count":3}\n'

        return httpx.Response(200, content=body())

    adapter = get_provider_adapter("ollama")

    async def go() -> str:
        chunks: list[bytes] = []
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            async for chunk in adapter.stream_messages(client, _target(), _request()):
                chunks.append(chunk)
        return b"".join(chunks).decode()

    out = asyncio.run(go())
    # events arrive in order
    assert out.index("message_start") < out.index("content_block_delta") < out.index("message_stop")
    assert "Hello" in out
    assert "world" in out
