from __future__ import annotations

from collections.abc import AsyncIterator, Mapping

import httpx

from .base import ProviderAdapter
from ..models import CanonicalRequest, CanonicalResponse, ProviderTarget, TokenCountRequest
from ..protocols import estimate_request_tokens


class VllmAdapter(ProviderAdapter):
    name = "vllm"
    supports_messages = False
    supports_stream = False
    supports_count_tokens = False

    async def stream_messages(
        self,
        client: httpx.AsyncClient,
        target: ProviderTarget,
        request: CanonicalRequest,
        extra_headers: Mapping[str, str] | None = None,
    ) -> AsyncIterator[bytes]:
        raise NotImplementedError("vLLM adapter is not implemented yet")

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
        raise NotImplementedError("vLLM transport is not implemented yet")
