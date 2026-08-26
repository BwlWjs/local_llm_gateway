from __future__ import annotations

from local_llm_gateway.models import Scope
from local_llm_gateway.security import (
    DEFAULT_SCOPES,
    KEY_PREFIX,
    generate_key,
    hash_key,
    key_prefix,
    verify_key,
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
