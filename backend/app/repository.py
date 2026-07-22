"""Durable SQLite state for cases, authorization, idempotency and cleanup.

The database is intentionally the coordination point for a deployment.  It
contains identifiers and metadata only; credentials, requests, prompts and
memory-card bodies never enter this ledger.
"""

from __future__ import annotations

import hashlib
import json
import secrets
import sqlite3
import time
from datetime import timedelta
from pathlib import Path
from threading import RLock
from typing import Any

from .domain import CaseState, DomainEvent, now_utc


class CaseNotFoundError(KeyError):
    pass


class VersionConflictError(RuntimeError):
    pass


class StateRepository:
    """A small shared-state repository suitable for one SQLite-backed demo.

    SQLite's unique constraints make publication idempotency and request
    quotas work across Uvicorn workers sharing the same mounted state file.
    A horizontally scaled production deployment should replace this component
    with a managed transactional database before adding independent volumes.
    """

    def __init__(self, path: str) -> None:
        self.path = path
        if path != ":memory:":
            Path(path).expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(path, check_same_thread=False)
        self._connection.row_factory = sqlite3.Row
        self._lock = RLock()
        self._initialize()

    def _initialize(self) -> None:
        with self._connection:
            self._connection.executescript("""
                CREATE TABLE IF NOT EXISTS demo_cases (
                  case_id TEXT PRIMARY KEY, script_id TEXT, version INTEGER NOT NULL,
                  status TEXT NOT NULL, created_at TEXT NOT NULL, epoch INTEGER NOT NULL DEFAULT 0
                );
                CREATE TABLE IF NOT EXISTS demo_events (
                  event_id INTEGER PRIMARY KEY AUTOINCREMENT, case_id TEXT NOT NULL,
                  type TEXT NOT NULL, request_id TEXT NOT NULL, payload_json TEXT NOT NULL,
                  created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS demo_publications (
                  case_id TEXT NOT NULL, source_memory_id TEXT NOT NULL,
                  public_card_id TEXT, status TEXT NOT NULL, created_at TEXT NOT NULL,
                  PRIMARY KEY(case_id, source_memory_id)
                );
                CREATE TABLE IF NOT EXISTS demo_access_sessions (
                  token_hash TEXT PRIMARY KEY, principal TEXT NOT NULL,
                  csrf_token_hash TEXT NOT NULL, expires_at TEXT NOT NULL,
                  created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS demo_rate_limits (
                  scope TEXT NOT NULL, caller_hash TEXT NOT NULL,
                  window_start INTEGER NOT NULL, count INTEGER NOT NULL,
                  PRIMARY KEY(scope, caller_hash, window_start)
                );
                CREATE TABLE IF NOT EXISTS demo_sse_connections (
                  connection_id TEXT PRIMARY KEY, caller_hash TEXT NOT NULL,
                  expires_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS demo_cleanup_tasks (
                  case_id TEXT NOT NULL, memory_id TEXT NOT NULL, agent_id TEXT NOT NULL,
                  status TEXT NOT NULL, attempts INTEGER NOT NULL DEFAULT 0,
                  created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                  PRIMARY KEY(case_id, memory_id)
                );
                CREATE INDEX IF NOT EXISTS ix_demo_events_case_id ON demo_events(case_id, event_id);
                CREATE INDEX IF NOT EXISTS ix_demo_access_sessions_expires ON demo_access_sessions(expires_at);
                CREATE INDEX IF NOT EXISTS ix_demo_sse_connections_caller ON demo_sse_connections(caller_hash, expires_at);
            """)
            columns = {str(row["name"]) for row in self._connection.execute("PRAGMA table_info(demo_cases)")}
            if "epoch" not in columns:
                self._connection.execute("ALTER TABLE demo_cases ADD COLUMN epoch INTEGER NOT NULL DEFAULT 0")

    @staticmethod
    def _hash(value: str) -> str:
        return hashlib.sha256(value.encode("utf-8")).hexdigest()

    def create_case(self, case: CaseState) -> CaseState:
        with self._lock, self._connection:
            self._connection.execute(
                "INSERT INTO demo_cases(case_id, script_id, version, status, created_at, epoch) VALUES (?, ?, ?, ?, ?, ?)",
                (case.case_id, case.script_id, case.version, case.status, case.created_at.isoformat(), case.epoch),
            )
        return case

    def get_case(self, case_id: str) -> CaseState:
        with self._lock:
            row = self._connection.execute("SELECT * FROM demo_cases WHERE case_id = ?", (case_id,)).fetchone()
        if not row:
            raise CaseNotFoundError(case_id)
        return CaseState(
            case_id=row["case_id"], script_id=row["script_id"], version=row["version"],
            status=row["status"], epoch=row["epoch"], created_at=row["created_at"],
        )

    def update_case(self, case: CaseState, expected_version: int) -> CaseState:
        with self._lock, self._connection:
            result = self._connection.execute(
                "UPDATE demo_cases SET script_id = ?, version = ?, status = ?, epoch = ? WHERE case_id = ? AND version = ?",
                (case.script_id, case.version, case.status, case.epoch, case.case_id, expected_version),
            )
            if result.rowcount != 1:
                raise VersionConflictError(case.case_id)
        return case

    def append_event(self, case_id: str, event_type: str, request_id: str, payload: dict[str, Any]) -> DomainEvent:
        created_at = now_utc()
        with self._lock, self._connection:
            cursor = self._connection.execute(
                "INSERT INTO demo_events(case_id, type, request_id, payload_json, created_at) VALUES (?, ?, ?, ?, ?)",
                (case_id, event_type, request_id, json.dumps(payload, ensure_ascii=False, default=str), created_at.isoformat()),
            )
        return DomainEvent(event_id=int(cursor.lastrowid), case_id=case_id, type=event_type, request_id=request_id, payload=payload, created_at=created_at)

    def events_after(self, case_id: str, after_event_id: int = 0) -> list[DomainEvent]:
        with self._lock:
            rows = self._connection.execute(
                "SELECT * FROM demo_events WHERE case_id = ? AND event_id > ? ORDER BY event_id", (case_id, after_event_id)
            ).fetchall()
        return [
            DomainEvent(event_id=row["event_id"], case_id=row["case_id"], type=row["type"], request_id=row["request_id"], payload=json.loads(row["payload_json"]), created_at=row["created_at"])
            for row in rows
        ]

    def begin_publication(self, case_id: str, source_memory_id: str) -> tuple[dict[str, Any], bool]:
        """Reserve a source card.  The unique key is the cross-worker lock."""
        with self._lock, self._connection:
            row = self._connection.execute(
                "SELECT * FROM demo_publications WHERE case_id = ? AND source_memory_id = ?", (case_id, source_memory_id)
            ).fetchone()
            if row:
                return dict(row), False
            created_at = now_utc().isoformat()
            self._connection.execute(
                "INSERT INTO demo_publications(case_id, source_memory_id, public_card_id, status, created_at) VALUES (?, ?, NULL, 'pending', ?)",
                (case_id, source_memory_id, created_at),
            )
        return {"case_id": case_id, "source_memory_id": source_memory_id, "public_card_id": None, "status": "pending", "created_at": created_at}, True

    def complete_publication(self, case_id: str, source_memory_id: str, public_card_id: str) -> None:
        with self._lock, self._connection:
            result = self._connection.execute(
                "UPDATE demo_publications SET public_card_id = ?, status = 'ready' WHERE case_id = ? AND source_memory_id = ? AND status = 'pending'",
                (public_card_id, case_id, source_memory_id),
            )
            if result.rowcount != 1:
                # A second worker may reconcile the same immutable public
                # card between its remote write and this local completion.
                # Treat that exact ready state as an idempotent completion,
                # while rejecting a genuinely different reservation outcome.
                row = self._connection.execute(
                    "SELECT public_card_id, status FROM demo_publications WHERE case_id = ? AND source_memory_id = ?",
                    (case_id, source_memory_id),
                ).fetchone()
                if row and row["status"] == "ready" and row["public_card_id"] == public_card_id:
                    return
                raise RuntimeError("publication reservation was lost")

    def abandon_publication(self, case_id: str, source_memory_id: str) -> None:
        with self._lock, self._connection:
            self._connection.execute(
                "DELETE FROM demo_publications WHERE case_id = ? AND source_memory_id = ?",
                (case_id, source_memory_id),
            )

    def find_publication(self, case_id: str, source_memory_id: str) -> dict[str, Any] | None:
        with self._lock:
            row = self._connection.execute(
                "SELECT * FROM demo_publications WHERE case_id = ? AND source_memory_id = ?", (case_id, source_memory_id)
            ).fetchone()
        return dict(row) if row else None

    def create_access_session(self, principal: str, ttl_seconds: int) -> tuple[str, str]:
        token = secrets.token_urlsafe(32)
        csrf_token = secrets.token_urlsafe(24)
        now = now_utc()
        expires_at = now + timedelta(seconds=ttl_seconds)
        with self._lock, self._connection:
            self._connection.execute(
                "INSERT INTO demo_access_sessions(token_hash, principal, csrf_token_hash, expires_at, created_at) VALUES (?, ?, ?, ?, ?)",
                (self._hash(token), principal, self._hash(csrf_token), expires_at.isoformat(), now.isoformat()),
            )
        return token, csrf_token

    def access_session(self, token: str) -> dict[str, str] | None:
        token_hash = self._hash(token)
        now = now_utc().isoformat()
        with self._lock, self._connection:
            self._connection.execute("DELETE FROM demo_access_sessions WHERE expires_at <= ?", (now,))
            row = self._connection.execute(
                "SELECT principal, csrf_token_hash FROM demo_access_sessions WHERE token_hash = ?", (token_hash,)
            ).fetchone()
        if not row:
            return None
        return {"principal": str(row["principal"]), "csrf_token_hash": str(row["csrf_token_hash"]), "token_hash": token_hash}

    def revoke_access_session(self, token: str) -> None:
        with self._lock, self._connection:
            self._connection.execute("DELETE FROM demo_access_sessions WHERE token_hash = ?", (self._hash(token),))

    def consume_rate_limit(self, scope: str, caller: str, limit: int, *, window_seconds: int = 60) -> bool:
        if limit <= 0:
            return False
        window_start = int(time.time()) // window_seconds * window_seconds
        caller_hash = self._hash(caller)
        with self._lock, self._connection:
            self._connection.execute("DELETE FROM demo_rate_limits WHERE window_start < ?", (window_start - window_seconds * 2,))
            row = self._connection.execute(
                "SELECT count FROM demo_rate_limits WHERE scope = ? AND caller_hash = ? AND window_start = ?",
                (scope, caller_hash, window_start),
            ).fetchone()
            if row and int(row["count"]) >= limit:
                return False
            if row:
                self._connection.execute(
                    "UPDATE demo_rate_limits SET count = count + 1 WHERE scope = ? AND caller_hash = ? AND window_start = ?",
                    (scope, caller_hash, window_start),
                )
            else:
                self._connection.execute(
                    "INSERT INTO demo_rate_limits(scope, caller_hash, window_start, count) VALUES (?, ?, ?, 1)",
                    (scope, caller_hash, window_start),
                )
        return True

    def acquire_sse_connection(self, caller: str, limit: int, lifetime_seconds: int) -> str | None:
        connection_id = secrets.token_urlsafe(18)
        now = now_utc()
        expires_at = (now + timedelta(seconds=lifetime_seconds)).isoformat()
        caller_hash = self._hash(caller)
        with self._lock, self._connection:
            self._connection.execute("DELETE FROM demo_sse_connections WHERE expires_at <= ?", (now.isoformat(),))
            active = int(self._connection.execute(
                "SELECT COUNT(*) FROM demo_sse_connections WHERE caller_hash = ?", (caller_hash,)
            ).fetchone()[0])
            if active >= limit:
                return None
            self._connection.execute(
                "INSERT INTO demo_sse_connections(connection_id, caller_hash, expires_at) VALUES (?, ?, ?)",
                (connection_id, caller_hash, expires_at),
            )
        return connection_id

    def release_sse_connection(self, connection_id: str) -> None:
        with self._lock, self._connection:
            self._connection.execute("DELETE FROM demo_sse_connections WHERE connection_id = ?", (connection_id,))

    def add_cleanup_task(self, case_id: str, memory_id: str, agent_id: str) -> None:
        now = now_utc().isoformat()
        with self._lock, self._connection:
            self._connection.execute(
                "INSERT OR IGNORE INTO demo_cleanup_tasks(case_id, memory_id, agent_id, status, attempts, created_at, updated_at) VALUES (?, ?, ?, 'pending', 0, ?, ?)",
                (case_id, memory_id, agent_id, now, now),
            )

    def complete_cleanup_task(self, case_id: str, memory_id: str) -> None:
        with self._lock, self._connection:
            self._connection.execute(
                "UPDATE demo_cleanup_tasks SET status = 'done', attempts = attempts + 1, updated_at = ? WHERE case_id = ? AND memory_id = ?",
                (now_utc().isoformat(), case_id, memory_id),
            )

    def fail_cleanup_task(self, case_id: str, memory_id: str) -> None:
        with self._lock, self._connection:
            self._connection.execute(
                "UPDATE demo_cleanup_tasks SET attempts = attempts + 1, updated_at = ? WHERE case_id = ? AND memory_id = ?",
                (now_utc().isoformat(), case_id, memory_id),
            )

    def pending_cleanup(self, case_id: str) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._connection.execute(
                "SELECT * FROM demo_cleanup_tasks WHERE case_id = ? AND status = 'pending' ORDER BY created_at", (case_id,)
            ).fetchall()
        return [dict(row) for row in rows]

    def clear_completed_cleanup(self, case_id: str) -> None:
        with self._lock, self._connection:
            self._connection.execute("DELETE FROM demo_cleanup_tasks WHERE case_id = ? AND status = 'done'", (case_id,))

    def delete_case(self, case_id: str) -> None:
        """Remove one local case only after remote cleanup has succeeded."""
        with self._lock, self._connection:
            self._connection.execute("DELETE FROM demo_cleanup_tasks WHERE case_id = ?", (case_id,))
            self._connection.execute("DELETE FROM demo_publications WHERE case_id = ?", (case_id,))
            self._connection.execute("DELETE FROM demo_events WHERE case_id = ?", (case_id,))
            self._connection.execute("DELETE FROM demo_cases WHERE case_id = ?", (case_id,))

    def case_ids(self) -> list[str]:
        with self._lock:
            rows = self._connection.execute("SELECT case_id FROM demo_cases ORDER BY created_at").fetchall()
        return [str(row["case_id"]) for row in rows]

    def clear_all(self) -> None:
        """Remove the local ledger only after matching remote cards were erased."""
        with self._lock, self._connection:
            self._connection.execute("DELETE FROM demo_access_sessions")
            self._connection.execute("DELETE FROM demo_rate_limits")
            self._connection.execute("DELETE FROM demo_sse_connections")
            self._connection.execute("DELETE FROM demo_cleanup_tasks")
            self._connection.execute("DELETE FROM demo_publications")
            self._connection.execute("DELETE FROM demo_events")
            self._connection.execute("DELETE FROM demo_cases")

    def aggregate_metrics(self) -> dict[str, int]:
        """Return aggregate-only metrics; event payload text is never exposed."""
        with self._lock:
            rows = self._connection.execute("SELECT type, payload_json FROM demo_events").fetchall()
            counts = {
                "cases_total": int(self._connection.execute("SELECT COUNT(*) FROM demo_cases").fetchone()[0]),
                "cases_ready": int(self._connection.execute("SELECT COUNT(*) FROM demo_cases WHERE status = 'ready'").fetchone()[0]),
                "events_total": len(rows), "publications_total": 0, "answers_total": 0,
                "fallbacks_total": 0, "retrievals_total": 0, "retrieval_duration_ms_total": 0,
            }
        for row in rows:
            event_type = str(row["type"])
            if event_type == "memory.published":
                counts["publications_total"] += 1
            elif event_type == "answer.completed":
                counts["answers_total"] += 1
            elif event_type == "agent.fallback":
                counts["fallbacks_total"] += 1
            elif event_type == "retrieval.completed":
                counts["retrievals_total"] += 1
                try:
                    counts["retrieval_duration_ms_total"] += int(json.loads(row["payload_json"]).get("duration_ms", 0))
                except (TypeError, ValueError, json.JSONDecodeError):
                    continue
        return counts

    def operational_metrics(self) -> dict[str, int]:
        """Small gauges intended for a Prometheus scrape, never identifiers."""
        with self._lock:
            return {
                "sse_connections_active": int(self._connection.execute("SELECT COUNT(*) FROM demo_sse_connections").fetchone()[0]),
                "cleanup_tasks_pending": int(self._connection.execute("SELECT COUNT(*) FROM demo_cleanup_tasks WHERE status = 'pending'").fetchone()[0]),
            }
