from __future__ import annotations

from pydantic import BaseModel

from ..models import ApiKeyRecord


class KeyCreateRequest(BaseModel):
    name: str = "default"
    scopes: list[str] | None = None
    expires_at: str | None = None


class KeyCreateResponse(BaseModel):
    key: str
    record: ApiKeyRecord


class KeyListItem(BaseModel):
    id: str
    name: str
    prefix: str
    scopes: list[str]
    status: str
    created_at: str
    expires_at: str | None = None
    last_used_at: str | None = None
