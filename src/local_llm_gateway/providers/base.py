from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator, Mapping

import httpx

from ..models import CanonicalRequest, CanonicalResponse, ProviderTarget, TokenCountRequest


class ProviderError(Exception):
    def __init__(self, status_code: int, detail: str) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


class ProviderAdapter(ABC):
    name: str
    supports_messages: bool = True
    supports_stream: bool = True
    supports_count_tokens: bool = True
    supports_tools: bool = True
    supports_system: bool = True
    max_context_tokens: int = 8192

    @abstractmethod
    async def stream_messages(
        self,
        client: httpx.AsyncClient,
        target: ProviderTarget,
        request: CanonicalRequest,
        extra_headers: Mapping[str, str] | None = None,
    ) -> AsyncIterator[bytes]:
        raise NotImplementedError

    @abstractmethod
    async def count_tokens(
        self,
        client: httpx.AsyncClient,
        target: ProviderTarget,
        request: TokenCountRequest,
        extra_headers: Mapping[str, str] | None = None,
    ) -> int:
        raise NotImplementedError

    @abstractmethod
    async def create_message(
        self,
        client: httpx.AsyncClient,
        target: ProviderTarget,
        request: CanonicalRequest,
        extra_headers: Mapping[str, str] | None = None,
    ) -> CanonicalResponse:
        raise NotImplementedError
