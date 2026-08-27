from __future__ import annotations

import hashlib
import hmac
import secrets
from collections.abc import Callable
from datetime import UTC, datetime

from fastapi import Depends, HTTPException, Request

from .config import settings
from .models import ApiKeyRecord, ApiKeyStatus, Scope

KEY_PREFIX = "mr_"
PREFIX_LENGTH = 10

DEFAULT_SCOPES = [
    Scope.messages_create.value,
    Scope.tokens_count.value,
    Scope.models_list.value,
]


def generate_key() -> str:
    return KEY_PREFIX + secrets.token_urlsafe(32)


def hash_key(key: str) -> str:
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def key_prefix(key: str) -> str:
    return key[:PREFIX_LENGTH]


def verify_key(key: str, key_hash: str) -> bool:
    return hmac.compare_digest(hash_key(key), key_hash)


def is_expired(record: ApiKeyRecord, now: datetime | None = None) -> bool:
    expires_at = record.expires_at
    if not expires_at:
        return False
    try:
        expires = datetime.fromisoformat(expires_at)
    except ValueError:
        return False
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=UTC)
    return (now or datetime.now(UTC)) >= expires


def _extract_key(request: Request) -> str | None:
    api_key = request.headers.get("x-api-key")
    if api_key:
        return api_key.strip()
    authorization = request.headers.get("authorization")
    if authorization and authorization.lower().startswith("bearer "):
        return authorization[7:].strip()
    return None


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status_code=401, detail={"code": "invalid_api_key", "detail": detail}
    )


def api_key_auth(request: Request) -> ApiKeyRecord:
    key = _extract_key(request)
    if not key:
        raise _unauthorized("missing API key")
    record = request.app.state.runtime.lookup_key(hash_key(key))
    if record is None:
        raise _unauthorized("invalid API key")
    if record.status is not ApiKeyStatus.active:
        raise _unauthorized("API key is revoked")
    if is_expired(record):
        raise _unauthorized("API key is expired")
    return record


def require_scope(scope: Scope) -> Callable[..., ApiKeyRecord]:
    def _dependency(record: ApiKeyRecord = Depends(api_key_auth)) -> ApiKeyRecord:  # noqa: B008
        if scope.value not in record.scopes:
            raise HTTPException(
                status_code=403,
                detail={
                    "code": "insufficient_scope",
                    "detail": f"missing scope: {scope.value}",
                },
            )
        return record

    return _dependency


def admin_auth(request: Request) -> None:
    token = settings.admin_token
    if not token:
        return
    authorization = request.headers.get("authorization")
    provided = (
        authorization[7:].strip()
        if (authorization and authorization.lower().startswith("bearer "))
        else None
    )
    if provided is None or not hmac.compare_digest(provided, token):
        raise HTTPException(
            status_code=401,
            detail={"code": "admin_unauthorized", "detail": "invalid admin token"},
        )
