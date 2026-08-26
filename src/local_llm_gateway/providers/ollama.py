from __future__ import annotations

from collections.abc import AsyncIterator, Mapping
from typing import Any

import httpx

from .base import ProviderAdapter
from ..core.errors import GatewayError
from ..models import CanonicalRequest, CanonicalResponse, ProviderTarget, TokenCountRequest, UsageInfo
from ..protocols import estimate_request_tokens
from ..protocols import content_to_text
from ..streaming import ollama_line_stream_to_sse


class OllamaAdapter(ProviderAdapter):
    name = "ollama"

    async def stream_messages(
        self,
        client: httpx.AsyncClient,
        target: ProviderTarget,
        request: CanonicalRequest,
        extra_headers: Mapping[str, str] | None = None,
    ) -> AsyncIterator[bytes]:
        payload = self._build_payload(target, request, stream=True)
        url = f"{target.base_url.rstrip('/')}/api/chat"
        try:
            async with client.stream("POST", url, json=payload, headers=extra_headers) as response:
                response.raise_for_status()
                async for chunk in ollama_line_stream_to_sse(response.aiter_lines(), target, self._message_id()):
                    yield chunk
        except httpx.TimeoutException as exc:
            raise GatewayError(504, "upstream_timeout", f"ollama timeout: {exc}") from exc
        except httpx.HTTPStatusError as exc:
            raise GatewayError(502, "upstream_protocol_error", f"ollama status error: {exc.response.status_code}") from exc
        except httpx.HTTPError as exc:
            raise GatewayError(502, "upstream_network_error", f"ollama network error: {exc}") from exc

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
        url = f"{target.base_url.rstrip('/')}/api/chat"
        try:
            response = await client.post(url, json=payload, headers=extra_headers)
            response.raise_for_status()
            data = response.json()
        except httpx.TimeoutException as exc:
            raise GatewayError(504, "upstream_timeout", f"ollama timeout: {exc}") from exc
        except httpx.HTTPStatusError as exc:
            raise GatewayError(502, "upstream_protocol_error", f"ollama status error: {exc.response.status_code}") from exc
        except httpx.HTTPError as exc:
            raise GatewayError(502, "upstream_network_error", f"ollama network error: {exc}") from exc

        content = ""
        message = data.get("message") or {}
        if isinstance(message.get("content"), str):
            content = message["content"]
        return CanonicalResponse(
            id=self._message_id(),
            model=target.model,
            content=[{"type": "text", "text": content}] if content else [],
            stop_reason=str(data.get("done_reason") or "end_turn"),
            usage=UsageInfo(
                input_tokens=int(data.get("prompt_eval_count") or estimate_request_tokens(request)),
                output_tokens=int(data.get("eval_count") or 0),
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

        sampling = request.sampling
        options: dict[str, Any] = {"num_predict": request.max_tokens}
        if sampling.temperature is not None:
            options["temperature"] = sampling.temperature
        if sampling.top_p is not None:
            options["top_p"] = sampling.top_p
        if sampling.top_k is not None:
            options["top_k"] = sampling.top_k
        if sampling.stop_sequences:
            options["stop"] = sampling.stop_sequences

        payload: dict[str, Any] = {
            "model": target.model,
            "messages": messages,
            "stream": stream,
            "options": options,
        }
        if request.tools:
            payload["tools"] = request.tools
        if request.tool_choice is not None:
            payload["tool_choice"] = request.tool_choice
        return payload

    @staticmethod
    def _message_id() -> str:
        from uuid import uuid4

        return f"msg_{uuid4().hex}"
