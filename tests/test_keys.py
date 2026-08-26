from __future__ import annotations

from uuid import uuid4

from local_llm_gateway.core.runtime import RuntimeSnapshot
from local_llm_gateway.models import ApiKeyRecord, ApiKeyStatus
from local_llm_gateway.security import generate_key, hash_key, key_prefix
from local_llm_gateway.storage.sqlite import KeyStore


def _record(key: str, name: str = "test") -> ApiKeyRecord:
    return ApiKeyRecord(
        id=uuid4().hex,
        name=name,
        prefix=key_prefix(key),
        key_hash=hash_key(key),
        scopes=["messages:create", "models:list"],
        status=ApiKeyStatus.active,
        created_at="2026-08-26T00:00:00+00:00",
    )


def test_store_roundtrip(tmp_path):
    store = KeyStore(str(tmp_path / "test.db"))
    key = generate_key()
    record = _record(key)
    store.create(record)

    records = store.list()
    assert len(records) == 1
    assert records[0].id == record.id
    assert records[0].key_hash == hash_key(key)

    fetched = store.get_by_hash(hash_key(key))
    assert fetched is not None
    assert fetched.id == record.id
    assert fetched.prefix == key_prefix(key)


def test_store_get_by_hash_missing(tmp_path):
    store = KeyStore(str(tmp_path / "test.db"))
    assert store.get_by_hash("deadbeef" * 8) is None


def test_store_revoke(tmp_path):
    store = KeyStore(str(tmp_path / "test.db"))
    key = generate_key()
    record = _record(key)
    store.create(record)

    assert store.revoke(record.id) is True
    fetched = store.get_by_hash(hash_key(key))
    assert fetched is not None
    assert fetched.status is ApiKeyStatus.revoked

    assert store.revoke("missing") is False


def test_runtime_refresh_and_lookup(tmp_path):
    store = KeyStore(str(tmp_path / "test.db"))
    key = generate_key()
    store.create(_record(key, name="a"))

    runtime = RuntimeSnapshot()
    runtime.refresh_keys(store)

    assert runtime.lookup_key(hash_key(key)) is not None
    assert runtime.lookup_key("deadbeef" * 8) is None
