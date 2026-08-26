from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class GatewayError(Exception):
    status_code: int
    code: str
    detail: str
    extra: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        super().__init__(self.detail)

