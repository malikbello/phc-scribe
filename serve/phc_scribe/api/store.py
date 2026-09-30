"""Append-only record store (SQLite). A record is a list of events: drafted, then
confirmed or amended; the current state is the latest record body. Nothing is updated
in place, so every change keeps its provenance."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
import uuid
from datetime import UTC, datetime
from typing import Any

SCHEMA = """
CREATE TABLE IF NOT EXISTS records (
    id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    idempotency_key TEXT NOT NULL,
    client TEXT NOT NULL,
    request_hash TEXT NOT NULL,
    UNIQUE (client, idempotency_key)
);
CREATE TABLE IF NOT EXISTS events (
    record_id TEXT NOT NULL REFERENCES records(id),
    seq INTEGER NOT NULL,
    type TEXT NOT NULL,
    at TEXT NOT NULL,
    actor TEXT,
    reason TEXT,
    body TEXT NOT NULL,
    PRIMARY KEY (record_id, seq)
);
"""


class IdempotencyConflict(Exception):
    """The same Idempotency-Key was reused with a different request body."""


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds")


def request_hash(payload: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


class RecordStore:
    def __init__(self, path: str):
        self._db = sqlite3.connect(path, check_same_thread=False)
        self._db.executescript(SCHEMA)
        self._lock = threading.Lock()

    def create(
        self, client: str, key: str, payload: dict[str, Any], actor: str | None
    ) -> tuple[str, bool]:
        """(record id, created). A replay with the same key and body returns the first id."""
        h = request_hash(payload)
        with self._lock, self._db:
            row = self._db.execute(
                "SELECT id, request_hash FROM records WHERE client = ? AND idempotency_key = ?",
                (client, key),
            ).fetchone()
            if row:
                if row[1] != h:
                    raise IdempotencyConflict
                return row[0], False
            rid = str(uuid.uuid4())
            self._db.execute(
                "INSERT INTO records VALUES (?, ?, ?, ?, ?)", (rid, _now(), key, client, h)
            )
            self._append(rid, "drafted", payload, actor, None)
            return rid, True

    def append(
        self, rid: str, type_: str, body: dict[str, Any], actor: str | None, reason: str | None
    ) -> None:
        with self._lock, self._db:
            self._append(rid, type_, body, actor, reason)

    def _append(self, rid, type_, body, actor, reason) -> None:
        seq = self._db.execute(
            "SELECT COALESCE(MAX(seq), 0) + 1 FROM events WHERE record_id = ?", (rid,)
        ).fetchone()[0]
        self._db.execute(
            "INSERT INTO events VALUES (?, ?, ?, ?, ?, ?, ?)",
            (rid, seq, type_, _now(), actor, reason, json.dumps(body)),
        )

    def get(self, rid: str, client: str) -> dict[str, Any] | None:
        with self._lock:
            row = self._db.execute(
                "SELECT created_at FROM records WHERE id = ? AND client = ?", (rid, client)
            ).fetchone()
            if not row:
                return None
            events = self._db.execute(
                "SELECT seq, type, at, actor, reason, body FROM events"
                " WHERE record_id = ? ORDER BY seq",
                (rid,),
            ).fetchall()
        history = [
            {"seq": s, "type": t, "at": at, "actor": a, "reason": r, "body": json.loads(b)}
            for s, t, at, a, r, b in events
        ]
        status = "draft"
        record = history[0]["body"]["record"]
        for ev in history[1:]:
            if ev["type"] == "amended":
                record = ev["body"]["record"]
                status = "amended"
            elif ev["type"] == "confirmed":
                status = "confirmed"
        return {
            "id": rid,
            "created_at": row[0],
            "status": status,
            "record": record,
            "events": history,
        }
