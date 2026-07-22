"""Small durable case/event repository used for snapshots, replay and audit."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from threading import RLock
from typing import Any

from .domain import CaseState, DomainEvent, now_utc


class CaseNotFoundError(KeyError):
    pass


class VersionConflictError(RuntimeError):
    pass


class StateRepository:
    """The state ledger deliberately stores no raw credentials or LLM prompts."""

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
                  status TEXT NOT NULL, created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS demo_events (
                  event_id INTEGER PRIMARY KEY AUTOINCREMENT, case_id TEXT NOT NULL,
                  type TEXT NOT NULL, request_id TEXT NOT NULL, payload_json TEXT NOT NULL,
                  created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS demo_sessions (
                  session_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, role TEXT,
                  expires_at TEXT
                );
                CREATE INDEX IF NOT EXISTS ix_demo_events_case_id ON demo_events(case_id, event_id);
            """)

    def create_case(self, case: CaseState) -> CaseState:
        with self._lock, self._connection:
            self._connection.execute("INSERT INTO demo_cases(case_id, script_id, version, status, created_at) VALUES (?, ?, ?, ?, ?)", (case.case_id, case.script_id, case.version, case.status, case.created_at.isoformat()))
        return case

    def get_case(self, case_id: str) -> CaseState:
        row = self._connection.execute("SELECT * FROM demo_cases WHERE case_id = ?", (case_id,)).fetchone()
        if not row:
            raise CaseNotFoundError(case_id)
        return CaseState(case_id=row["case_id"], script_id=row["script_id"], version=row["version"], status=row["status"], created_at=row["created_at"])

    def update_case(self, case: CaseState, expected_version: int) -> CaseState:
        with self._lock, self._connection:
            result = self._connection.execute("UPDATE demo_cases SET script_id = ?, version = ?, status = ? WHERE case_id = ? AND version = ?", (case.script_id, case.version, case.status, case.case_id, expected_version))
            if result.rowcount != 1:
                raise VersionConflictError(case.case_id)
        return case

    def append_event(self, case_id: str, event_type: str, request_id: str, payload: dict[str, Any]) -> DomainEvent:
        created_at = now_utc()
        with self._lock, self._connection:
            cursor = self._connection.execute("INSERT INTO demo_events(case_id, type, request_id, payload_json, created_at) VALUES (?, ?, ?, ?, ?)", (case_id, event_type, request_id, json.dumps(payload, ensure_ascii=False, default=str), created_at.isoformat()))
        return DomainEvent(event_id=int(cursor.lastrowid), case_id=case_id, type=event_type, request_id=request_id, payload=payload, created_at=created_at)

    def events_after(self, case_id: str, after_event_id: int = 0) -> list[DomainEvent]:
        rows = self._connection.execute("SELECT * FROM demo_events WHERE case_id = ? AND event_id > ? ORDER BY event_id", (case_id, after_event_id)).fetchall()
        return [DomainEvent(event_id=row["event_id"], case_id=row["case_id"], type=row["type"], request_id=row["request_id"], payload=json.loads(row["payload_json"]), created_at=row["created_at"]) for row in rows]

    def find_publication(self, case_id: str, source_memory_id: str) -> dict[str, Any] | None:
        rows = self._connection.execute("SELECT payload_json FROM demo_events WHERE case_id = ? AND type = 'memory.published' ORDER BY event_id", (case_id,)).fetchall()
        for row in rows:
            payload = json.loads(row["payload_json"])
            if payload.get("source_memory_id") == source_memory_id:
                return payload
        return None

    def case_ids(self) -> list[str]:
        rows = self._connection.execute("SELECT case_id FROM demo_cases ORDER BY created_at").fetchall()
        return [str(row["case_id"]) for row in rows]

    def clear_all(self) -> None:
        """Remove the local ledger after the matching memory cards have been erased."""
        with self._lock, self._connection:
            self._connection.execute("DELETE FROM demo_sessions")
            self._connection.execute("DELETE FROM demo_events")
            self._connection.execute("DELETE FROM demo_cases")

    def aggregate_metrics(self) -> dict[str, int]:
        """Return aggregate-only metrics; payload text is never returned or exposed."""
        rows = self._connection.execute("SELECT type, payload_json FROM demo_events").fetchall()
        counts = {
            "cases_total": int(self._connection.execute("SELECT COUNT(*) FROM demo_cases").fetchone()[0]),
            "cases_ready": int(self._connection.execute("SELECT COUNT(*) FROM demo_cases WHERE status = 'ready'").fetchone()[0]),
            "events_total": len(rows),
            "publications_total": 0,
            "answers_total": 0,
            "fallbacks_total": 0,
            "retrievals_total": 0,
            "retrieval_duration_ms_total": 0,
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
