from __future__ import annotations

from datetime import UTC

from fastapi.testclient import TestClient

from local_llm_gateway.core.runtime import RuntimeSnapshot
from local_llm_gateway.main import app
from local_llm_gateway.models import ApiKeyRecord, ApiKeyStatus
from local_llm_gateway.security import DEFAULT_SCOPES, hash_key
from local_llm_gateway.storage.sqlite import KeyStore


def test_full_key_lifecycle(tmp_path):
    store = KeyStore(str(tmp_path / "test.db"))
    runtime = RuntimeSnapshot()
    runtime.refresh_keys(store)

    app.state.key_store = store
    app.state.runtime = runtime

    client = TestClient(app)

    # no key -> 401
    assert client.get("/v1/models").status_code == 401

    # create key via admin
    resp = client.post("/api/v1/keys", json={"name": "claude-code"})
    assert resp.status_code == 200
    body = resp.json()
    key = body["key"]
    key_id = body["record"]["id"]
    assert key.startswith("mr_")

    # x-api-key (Anthropic) works
    assert client.get("/v1/models", headers={"x-api-key": key}).status_code == 200

    # Authorization: Bearer (OpenAI) also works
    assert (
        client.get("/v1/models", headers={"Authorization": f"Bearer {key}"}).status_code
        == 200
    )

    # revoke
    assert client.delete(f"/api/v1/keys/{key_id}").status_code == 200

    # revoked key -> 401
    assert client.get("/v1/models", headers={"x-api-key": key}).status_code == 401

    # list shows metadata only, no plaintext / hash
    listing = client.get("/api/v1/keys").json()
    assert len(listing) == 1
    assert listing[0]["prefix"] == key[:10]
    assert "key" not in listing[0]
    assert "key_hash" not in listing[0]


def test_expired_key_rejected(tmp_path):
    from datetime import datetime, timedelta

    store = KeyStore(str(tmp_path / "test.db"))
    runtime = RuntimeSnapshot()

    expired = datetime.now(UTC) - timedelta(hours=1)
    resp = store.create(
        ApiKeyRecord(
            id="expired",
            name="expired-key",
            prefix="mr_expired",
            key_hash=hash_key("mr_expired_secret"),
            scopes=list(DEFAULT_SCOPES),
            status=ApiKeyStatus.active,
            created_at=datetime.now(UTC).isoformat(),
            expires_at=expired.isoformat(),
        )
    )
    runtime.refresh_keys(store)

    app.state.key_store = store
    app.state.runtime = runtime

    client = TestClient(app)

    response = client.get("/v1/models", headers={"x-api-key": "mr_expired_secret"})

    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "invalid_api_key"
    assert resp.expires_at is not None
