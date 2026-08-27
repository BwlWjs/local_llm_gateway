from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from .config import settings
from .core.errors import GatewayError
from .models import ModelInfo, ProviderTarget


@dataclass
class ModelRegistry:
    raw: str = settings.model_map_raw
    defaults: dict[str, Any] = field(default_factory=dict)
    provider_caps: dict[str, Any] = field(default_factory=dict)
    _mapping_cache: dict[str, Any] | None = field(
        default=None, repr=False, compare=False
    )

    def __post_init__(self) -> None:
        if not self.defaults:
            self.defaults = settings.model_defaults
        if not self.provider_caps:
            self.provider_caps = settings.provider_caps

    def resolve(self, logical_model: str) -> ProviderTarget:
        mapping = self._mapping()

        item = mapping.get(logical_model, {})
        if not isinstance(item, dict):
            item = {}
        default_item = (
            self.defaults.get(logical_model, {})
            if isinstance(self.defaults, dict)
            else {}
        )
        if not isinstance(default_item, dict):
            default_item = {}
        if not item and not default_item:
            raise GatewayError(
                404, "route_not_found", f"model route not found: {logical_model}"
            )
        provider = str(
            item.get("provider")
            or default_item.get("provider")
            or settings.provider_default
        )
        model = str(item.get("model") or default_item.get("model") or logical_model)
        base_url = (
            settings.ollama_base_url if provider == "ollama" else settings.vllm_base_url
        )
        caps = (
            self.provider_caps.get(provider, {})
            if isinstance(self.provider_caps, dict)
            else {}
        )
        return ProviderTarget(
            provider=provider,
            model=model,
            base_url=base_url,
            display_name=item.get("display_name") or default_item.get("display_name"),
            supports_messages=bool(caps.get("supports_messages", True)),
            supports_stream=bool(caps.get("supports_stream", True)),
            supports_count_tokens=bool(caps.get("supports_count_tokens", True)),
            supports_tools=bool(caps.get("supports_tools", True)),
            supports_system=bool(caps.get("supports_system", True)),
            max_context_tokens=int(caps.get("max_context_tokens", 8192)),
        )

    def list_models(self) -> list[ModelInfo]:
        mapping = self._mapping()

        items: list[ModelInfo] = []
        visible_models = (
            {**self.defaults, **mapping} if isinstance(self.defaults, dict) else mapping
        )
        for logical_name, raw_item in visible_models.items():
            if not isinstance(raw_item, dict):
                continue
            display_name = (
                raw_item.get("display_name")
                or str(logical_name).replace("_", " ").replace("-", " ").title()
            )
            provider = str(raw_item.get("provider", settings.provider_default))
            items.append(
                ModelInfo(
                    id=str(logical_name),
                    display_name=display_name,
                    provider=provider,
                    owned_by="local",
                )
            )

        if not items:
            items.append(
                ModelInfo(
                    id="local-coder",
                    display_name="Local Coder",
                    provider=settings.provider_default,
                    owned_by="local",
                )
            )
        return items

    def _mapping(self) -> dict[str, Any]:
        if self._mapping_cache is None:
            try:
                value = json.loads(self.raw)
            except json.JSONDecodeError:
                value = {}
            self._mapping_cache = value if isinstance(value, dict) else {}
        return self._mapping_cache
