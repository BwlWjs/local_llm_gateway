from __future__ import annotations

from collections.abc import AsyncIterator, Mapping
from typing import Any

import httpx

from .base import ProviderAdapter
from ..core.errors import GatewayError
from ..models import CanonicalRequest, CanonicalResponse, ProviderTarget, TokenCountRequest, UsageInfo
from ..protocols import content_to_text, estimate_request_tokens
from ..streaming import openai_stream_to_sse


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
            async with client.stream("POST", url, json=payload, headers=extra_headers) as response:
                response.raise_for_status()
                async for chunk in openai_stream_to_sse(response.aiter_lines(), target, self._message_id()):
                    yield chunk
        except httpx.TimeoutException as exc:
            raise GatewayError(504, "upstream_timeout", f"vllm timeout: {exc}") from exc
        except httpx.HTTPStatusError as exc:
            raise GatewayError(502, "upstream_protocol_error", f"vllm status error: {exc.response.status_code}") from exc
        except httpx.HTTPError as exc:
            raise GatewayError(502, "upstream_network_error", f"vllm network error: {exc}") from exc

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
            raise GatewayError(502, "upstream_protocol_error", f"vllm status error: {exc.response.status_code}") from exc
        except httpx.HTTPError as exc:
            raise GatewayError(502, "upstream_network_error", f"vllm network error: {exc}") from exc

        choices = data.get("choices") or []
        content = ""
        stop_reason = None
        if choices and isinstance(choices[0], dict):
            message = choices[0].get("message") or {}
            content = content_to_text(message.get("content"))
            stop_reason = choices[0].get("finish_reason")
        usage = data.get("usage") or {}
        return CanonicalResponse(
            id=self._message_id(),
            model=target.model,
            content=[{"type": "text", "text": content}] if content else [],
            stop_reason=str(stop_reason or "stop"),
            usage=UsageInfo(
                input_tokens=int(usage.get("prompt_tokens") or estimate_request_tokens(request)),
                output_tokens=int(usage.get("completion_tokens") or 0),
            ),
        )

    def _build_payload(self, target: ProviderTarget, request: CanonicalRequest, *, stream: bool) -> dict[str, Any]:
        messages: list[dict[str, Any]] = []
        if request.system:
            messages.append({"role": "system", "content": content_to_text(request.system)})
        for item in request.messages:
            if not isinstance(item, dict):
                continue
            messages.append({"role": str(item.get("role", "user")), "content": content_to_text(item.get("content"))})

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
        return payload

    @staticmethod
    def _message_id() -> str:
        from uuid import uuid4

        return f"msg_{uuid4().hex}"
