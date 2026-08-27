from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass

import httpx

from ..models import (
    CanonicalRequest,
    CanonicalResponse,
    HealthResponse,
    ModelListResponse,
    ProviderTarget,
    TokenCountRequest,
    TokenCountResponse,
)
from ..protocols import estimate_request_tokens
from ..providers.registry import get_provider_adapter
from .errors import GatewayError
from .runtime import RuntimeSnapshot


@dataclass(slots=True)
class GatewayService:
    runtime: RuntimeSnapshot

    def health(self) -> HealthResponse:
        return HealthResponse()

    def list_models(self) -> ModelListResponse:
        return ModelListResponse(data=self.runtime.registry.list_models())

    def resolve(self, model_name: str) -> ProviderTarget:
        return self.runtime.registry.resolve(model_name)

    def _client(self) -> httpx.AsyncClient:
        if self.runtime.client is None:
            raise GatewayError(
                500, "client_not_ready", "runtime client is not initialized"
            )
        return self.runtime.client

    async def count_tokens(self, request: TokenCountRequest) -> TokenCountResponse:
        target = self.resolve(request.model)
        adapter = get_provider_adapter(target.provider)
        if not target.supports_count_tokens or not adapter.supports_count_tokens:
            return TokenCountResponse(input_tokens=estimate_request_tokens(request))
        try:
            input_tokens = await adapter.count_tokens(self._client(), target, request)
        except NotImplementedError:
            input_tokens = estimate_request_tokens(request)
        return TokenCountResponse(input_tokens=input_tokens)

    async def create_message(self, request: CanonicalRequest) -> CanonicalResponse:
        target = self.resolve(request.model)
        adapter = get_provider_adapter(target.provider)
        if not target.supports_messages or not getattr(
            adapter, "supports_messages", True
        ):
            raise GatewayError(
                501,
                "provider_unsupported",
                f"provider {target.provider} does not support messages",
            )
        try:
            return await adapter.create_message(self._client(), target, request)
        except NotImplementedError:
            raise GatewayError(
                501,
                "provider_unimplemented",
                f"provider {target.provider} does not implement create_message",
            ) from None

    def stream_message(self, request: CanonicalRequest) -> AsyncIterator[bytes]:
        target = self.resolve(request.model)
        adapter = get_provider_adapter(target.provider)
        if not target.supports_stream or not getattr(adapter, "supports_stream", True):
            raise GatewayError(
                501,
                "provider_unsupported",
                f"provider {target.provider} does not support streaming",
            )
        return adapter.stream_messages(self._client(), target, request)
