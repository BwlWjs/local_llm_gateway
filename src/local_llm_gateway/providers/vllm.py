from __future__ import annotations

from collections.abc import AsyncIterator, Mapping
from typing import Any

import httpx

from ..core.errors import GatewayError
from ..models import (
    CanonicalRequest,
    CanonicalResponse,
    ProviderTarget,
    TokenCountRequest,
    UsageInfo,
)
from ..protocols import (
    anthropic_tool_choice_to_provider,
    anthropic_tools_to_provider,
    canonical_messages_to_provider,
    content_to_text,
    estimate_request_tokens,
    provider_tool_calls_to_content,
)
from ..streaming import openai_stream_to_sse
from .base import ProviderAdapter


class VllmAdapter(ProviderAdapter):
    name = "vllm"
    supports_messages = True
    supports_stream = True
    supports_count_tokens = False
    supports_tools = True
    supports_system = True

    async def stream_messages(
        self,
        client: httpx.AsyncClient,
        target: ProviderTarget,
        request: CanonicalRequest,
        extra_headers: Mapping[str, str] | None = None,
    ) -> AsyncIterator[bytes]:
        payload = self._build_payload(target, request, stream=True)
        url = f"{target.base_url.rstrip('/')}/v1/chat/completions"
        try:
            async with client.stream(
                "POST", url, json=payload, headers=extra_headers
            ) as response:
                response.raise_for_status()
                async for chunk in openai_stream_to_sse(
                    response.aiter_lines(),
                    target,
                    self._message_id(),
                    input_tokens_estimate=estimate_request_tokens(request),
                ):
                    yield chunk
        except httpx.TimeoutException as exc:
            raise GatewayError(504, "upstream_timeout", f"vllm timeout: {exc}") from exc
        except httpx.HTTPStatusError as exc:
            raise GatewayError(
                502,
                "upstream_protocol_error",
                f"vllm status error: {exc.response.status_code}",
            ) from exc
        except httpx.HTTPError as exc:
            raise GatewayError(
                502, "upstream_network_error", f"vllm network error: {exc}"
            ) from exc

    async def count_tokens(
        self,
        client: httpx.AsyncClient,
        target: ProviderTarget,
        request: TokenCountRequest,
        extra_headers: Mapping[str, str] | None = None,
    ) -> int:
        return estimate_request_tokens(request)

    async def create_message(
        self,
        client: httpx.AsyncClient,
        target: ProviderTarget,
        request: CanonicalRequest,
        extra_headers: Mapping[str, str] | None = None,
    ) -> CanonicalResponse:
        payload = self._build_payload(target, request, stream=False)
        url = f"{target.base_url.rstrip('/')}/v1/chat/completions"
        try:
            response = await client.post(url, json=payload, headers=extra_headers)
            response.raise_for_status()
            data = response.json()
        except httpx.TimeoutException as exc:
            raise GatewayError(504, "upstream_timeout", f"vllm timeout: {exc}") from exc
        except httpx.HTTPStatusError as exc:
            raise GatewayError(
                502,
                "upstream_protocol_error",
                f"vllm status error: {exc.response.status_code}",
            ) from exc
        except httpx.HTTPError as exc:
            raise GatewayError(
                502, "upstream_network_error", f"vllm network error: {exc}"
            ) from exc

        choices = data.get("choices") or []
        content = ""
        stop_reason = None
        tool_calls: list[dict[str, Any]] = []
        if choices and isinstance(choices[0], dict):
            message = choices[0].get("message") or {}
            content = content_to_text(message.get("content"))
            stop_reason = choices[0].get("finish_reason")
            tool_calls = message.get("tool_calls") or []
        tool_blocks = provider_tool_calls_to_content(tool_calls, style="openai")
        blocks: list[dict[str, Any]] = []
        if content:
            blocks.append({"type": "text", "text": content})
        blocks.extend(tool_blocks)
        if tool_blocks:
            stop_reason = "tool_calls"
        usage = data.get("usage") or {}
        return CanonicalResponse(
            id=self._message_id(),
            model=target.model,
            content=blocks,
            stop_reason=str(stop_reason or "stop"),
            usage=UsageInfo(
                input_tokens=int(
                    usage.get("prompt_tokens") or estimate_request_tokens(request)
                ),
                output_tokens=int(usage.get("completion_tokens") or 0),
            ),
        )

    def _build_payload(
        self, target: ProviderTarget, request: CanonicalRequest, *, stream: bool
    ) -> dict[str, Any]:
        messages: list[dict[str, Any]] = []
        if request.system:
            messages.append(
                {"role": "system", "content": content_to_text(request.system)}
            )
        messages.extend(
            canonical_messages_to_provider(request.messages, style="openai")
        )

        payload: dict[str, Any] = {
            "model": target.model,
            "messages": messages,
            "stream": stream,
            "max_tokens": request.max_tokens,
        }
        sampling = request.sampling
        if sampling.temperature is not None:
            payload["temperature"] = sampling.temperature
        if sampling.top_p is not None:
            payload["top_p"] = sampling.top_p
        if sampling.top_k is not None:
            payload["top_k"] = sampling.top_k
        if sampling.stop_sequences:
            payload["stop"] = sampling.stop_sequences
        if request.tools:
            payload["tools"] = anthropic_tools_to_provider(request.tools)
            payload["tool_choice"] = (
                anthropic_tool_choice_to_provider(request.tool_choice) or "auto"
            )
        if stream and request.stream_options:
            payload["stream_options"] = request.stream_options
        return payload

    @staticmethod
    def _message_id() -> str:
        from uuid import uuid4

        return f"msg_{uuid4().hex}"
