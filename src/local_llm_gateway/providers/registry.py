from __future__ import annotations

from ..core.errors import GatewayError
from .base import ProviderAdapter
from .ollama import OllamaAdapter
from .vllm import VllmAdapter


def get_provider_adapter(name: str) -> ProviderAdapter:
    match name:
        case "ollama":
            return OllamaAdapter()
        case "vllm":
            return VllmAdapter()
        case _:
            raise GatewayError(501, "provider_unsupported", f"unknown provider: {name}")
