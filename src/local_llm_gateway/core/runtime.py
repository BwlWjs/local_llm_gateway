from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import httpx

from ..config import settings
from ..models import ApiKeyRecord
from ..router import ModelRegistry


@dataclass(slots=True)
class RuntimeSnapshot:
    registry: ModelRegistry = field(default_factory=ModelRegistry)
    client: httpx.AsyncClient | None = None
    keys_by_hash: dict[str, ApiKeyRecord] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def refresh_keys(self, store: Any) -> None:
        self.keys_by_hash = {record.key_hash: record for record in store.list()}

    def lookup_key(self, key_hash: str) -> ApiKeyRecord | None:
        return self.keys_by_hash.get(key_hash)

    @property
    def request_timeout_s(self) -> float:
        return settings.request_timeout_s
