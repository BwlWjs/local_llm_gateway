from __future__ import annotations

from datetime import UTC, datetime, timedelta

from local_llm_gateway.models import ApiKeyRecord, ApiKeyStatus, Scope
from local_llm_gateway.security import (
    DEFAULT_SCOPES,
    KEY_PREFIX,
    generate_key,
    hash_key,
    is_expired,
    key_prefix,
    verify_key,
)


def _record(expires_at: str | None) -> ApiKeyRecord:
    return ApiKeyRecord(
        id="k1",
        name="test",
        prefix="mr_test",
        key_hash="h",
        scopes=list(DEFAULT_SCOPES),
        status=ApiKeyStatus.active,
        created_at="2026-01-01T00:00:00+00:00",
        expires_at=expires_at,
    )


def test_generate_key_format():
    key = generate_key()
    assert key.startswith(KEY_PREFIX)
    assert len(key) > len(KEY_PREFIX) + 20


def test_generate_key_unique():
    keys = {generate_key() for _ in range(100)}
    assert len(keys) == 100


def test_hash_key_deterministic():
    assert hash_key("mr_abc") == hash_key("mr_abc")
    assert hash_key("mr_abc") != hash_key("mr_abd")


def test_hash_key_is_hex():
    digest = hash_key("mr_abc")
    assert len(digest) == 64
    int(digest, 16)


def test_verify_key():
    key = generate_key()
    digest = hash_key(key)
    assert verify_key(key, digest) is True
    assert verify_key("mr_wrong", digest) is False


def test_key_prefix():
    key = "mr_abcdefghijk"
    assert key_prefix(key) == key[:10]
    assert len(key_prefix(key)) == 10


def test_default_scopes_cover_gateway():
    assert Scope.messages_create.value in DEFAULT_SCOPES
    assert Scope.tokens_count.value in DEFAULT_SCOPES
    assert Scope.models_list.value in DEFAULT_SCOPES


def test_key_without_expiry_never_expires():
    assert is_expired(_record(None)) is False


def test_key_with_future_expiry_not_expired():
    future = (datetime.now(UTC) + timedelta(days=1)).isoformat()
    assert is_expired(_record(future)) is False


def test_key_with_past_expiry_is_expired():
    past = (datetime.now(UTC) - timedelta(seconds=1)).isoformat()
    assert is_expired(_record(past)) is True


def test_key_with_naive_past_expiry_is_expired():
    past = (datetime.now(UTC) - timedelta(hours=1)).replace(tzinfo=None).isoformat()
    assert is_expired(_record(past)) is True


def test_key_with_invalid_expiry_format_not_expired():
    assert is_expired(_record("not-a-date")) is False
