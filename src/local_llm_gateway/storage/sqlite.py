from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from ..models import ApiKeyRecord, ApiKeyStatus

_SCHEMA = """
CREATE TABLE IF NOT EXISTS api_keys (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    prefix TEXT NOT NULL,
    key_hash TEXT NOT NULL UNIQUE,
    scopes TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    expires_at TEXT,
    last_used_at TEXT
)
"""


def _row_to_record(row: sqlite3.Row) -> ApiKeyRecord:
    return ApiKeyRecord(
        id=row["id"],
        name=row["name"],
        prefix=row["prefix"],
        key_hash=row["key_hash"],
        scopes=json.loads(row["scopes"]),
        status=ApiKeyStatus(row["status"]),
        created_at=row["created_at"],
        expires_at=row["expires_at"],
        last_used_at=row["last_used_at"],
    )


class KeyStore:
    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        parent = Path(db_path).parent
        if str(parent) not in ("", "."):
            parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    @contextmanager
    def _conn(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init_schema(self) -> None:
        with self._conn() as conn:
            conn.execute(_SCHEMA)

    def create(self, record: ApiKeyRecord) -> ApiKeyRecord:
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO api_keys (id, name, prefix, key_hash, scopes, status, created_at, expires_at, last_used_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    record.id,
                    record.name,
                    record.prefix,
                    record.key_hash,
                    json.dumps(record.scopes),
                    record.status.value,
                    record.created_at,
                    record.expires_at,
                    record.last_used_at,
                ),
            )
        return record

    def get_by_hash(self, key_hash: str) -> ApiKeyRecord | None:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM api_keys WHERE key_hash = ?", (key_hash,)
            ).fetchone()
        return _row_to_record(row) if row else None

    def list(self) -> list[ApiKeyRecord]:
        with self._conn() as conn:
            rows = conn.execute("SELECT * FROM api_keys ORDER BY created_at").fetchall()
        return [_row_to_record(row) for row in rows]

    def revoke(self, key_id: str) -> bool:
        with self._conn() as conn:
            cur = conn.execute(
                "UPDATE api_keys SET status = ? WHERE id = ?",
                (ApiKeyStatus.revoked.value, key_id),
            )
        return cur.rowcount > 0
