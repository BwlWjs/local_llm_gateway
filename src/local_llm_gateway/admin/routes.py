from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request

from ..models import ApiKeyRecord, ApiKeyStatus
from ..security import DEFAULT_SCOPES, admin_auth, generate_key, hash_key, key_prefix
from .schemas import KeyCreateRequest, KeyCreateResponse, KeyListItem

router = APIRouter(prefix="/api/v1")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _refresh(request: Request) -> None:
    state = request.app.state
    state.runtime.refresh_keys(state.key_store)


@router.post("/keys", response_model=KeyCreateResponse, dependencies=[Depends(admin_auth)])
def create_key(body: KeyCreateRequest, request: Request) -> KeyCreateResponse:
    key = generate_key()
    record = ApiKeyRecord(
        id=uuid4().hex,
        name=body.name,
        prefix=key_prefix(key),
        key_hash=hash_key(key),
        scopes=body.scopes if body.scopes is not None else list(DEFAULT_SCOPES),
        status=ApiKeyStatus.active,
        created_at=_now(),
        expires_at=body.expires_at,
        last_used_at=None,
    )
    request.app.state.key_store.create(record)
    _refresh(request)
    return KeyCreateResponse(key=key, record=record)


@router.get("/keys", response_model=list[KeyListItem], dependencies=[Depends(admin_auth)])
def list_keys(request: Request) -> list[KeyListItem]:
    return [
        KeyListItem(
            id=r.id,
            name=r.name,
            prefix=r.prefix,
            scopes=r.scopes,
            status=r.status.value,
            created_at=r.created_at,
            expires_at=r.expires_at,
            last_used_at=r.last_used_at,
        )
        for r in request.app.state.key_store.list()
    ]


@router.delete("/keys/{key_id}", dependencies=[Depends(admin_auth)])
def revoke_key(key_id: str, request: Request) -> dict[str, str]:
    if not request.app.state.key_store.revoke(key_id):
        raise HTTPException(status_code=404, detail={"code": "key_not_found", "detail": f"key not found: {key_id}"})
    _refresh(request)
    return {"id": key_id, "status": ApiKeyStatus.revoked.value}
