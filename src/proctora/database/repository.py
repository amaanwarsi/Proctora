from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from proctora.database.schema import SQLITE_SCHEMA


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


class DatabaseError(Exception):
    pass


class ExamTokenError(DatabaseError):
    pass


class SessionConflictError(DatabaseError):
    pass


class DeviceReuseBlockedError(DatabaseError):
    pass


@dataclass
class ExamRecord:
    id: int
    name: str
    duration: int
    settings: dict[str, Any]
    is_active: bool
    created_at: str

    @property
    def exam_url(self) -> str:
        return str(self.settings.get("exam_url", "about:blank"))


class DatabaseRepository:
    def __init__(self, database_path: str) -> None:
        self.database_path = database_path
        if self.database_path != ":memory:":
            Path(self.database_path).parent.mkdir(parents=True, exist_ok=True)

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def initialize(self) -> None:
        with self.connect() as connection:
            connection.executescript(SQLITE_SCHEMA)

    def seed_exam_token(
        self,
        *,
        token: str,
        exam_name: str,
        duration: int,
        exam_url: str,
        thresholds: dict[str, Any] | None = None,
        expires_at: str | None = None,
    ) -> int:
        settings = {"exam_url": exam_url, "thresholds": thresholds or {}}
        with self.connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO exams (name, duration, settings, is_active)
                VALUES (?, ?, ?, 1)
                """,
                (exam_name, duration, json.dumps(settings)),
            )
            exam_id = int(cursor.lastrowid)
            connection.execute(
                """
                INSERT INTO exam_tokens (exam_id, token, expires_at)
                VALUES (?, ?, ?)
                """,
                (exam_id, token, expires_at),
            )
            return exam_id

    def resolve_exam_by_token(self, token: str, *, now: str | None = None) -> ExamRecord:
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT e.id, e.name, e.duration, e.settings, e.is_active, e.created_at, t.expires_at
                FROM exam_tokens t
                JOIN exams e ON e.id = t.exam_id
                WHERE t.token = ?
                """,
                (token,),
            ).fetchone()

        if row is None:
            raise ExamTokenError("Invalid exam token.")

        if not row["is_active"]:
            raise ExamTokenError("Exam is inactive.")

        current_time = now or utc_now()
        expires_at = row["expires_at"]
        if expires_at and expires_at <= current_time:
            raise ExamTokenError("Exam token has expired.")

        return ExamRecord(
            id=row["id"],
            name=row["name"],
            duration=row["duration"],
            settings=json.loads(row["settings"] or "{}"),
            is_active=bool(row["is_active"]),
            created_at=row["created_at"],
        )

    def start_session(
        self,
        *,
        candidate_name: str,
        exam_token: str,
        device_signature: str,
    ) -> int:
        exam = self.resolve_exam_by_token(exam_token)
        with self.connect() as connection:
            active_row = connection.execute(
                """
                SELECT id
                FROM sessions
                WHERE exam_id = ? AND device_signature = ? AND status = 'active'
                """,
                (exam.id, device_signature),
            ).fetchone()
            if active_row:
                raise SessionConflictError("An active session already exists for this device.")

            completed_row = connection.execute(
                """
                SELECT id
                FROM sessions
                WHERE exam_id = ? AND device_signature = ?
                  AND status IN ('submitted', 'cancelled', 'quit')
                LIMIT 1
                """,
                (exam.id, device_signature),
            ).fetchone()
            if completed_row:
                raise DeviceReuseBlockedError(
                    "This device has already completed the exam and cannot re-enter."
                )

            candidate_cursor = connection.execute(
                "INSERT INTO candidates (name) VALUES (?)",
                (candidate_name,),
            )
            candidate_id = int(candidate_cursor.lastrowid)

            session_cursor = connection.execute(
                """
                INSERT INTO sessions (candidate_id, exam_id, device_signature, status)
                VALUES (?, ?, ?, 'active')
                """,
                (candidate_id, exam.id, device_signature),
            )
            return int(session_cursor.lastrowid)

    def log_event(
        self,
        *,
        session_id: int,
        event_type: str,
        payload: dict[str, Any] | None = None,
        created_at: str | None = None,
    ) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO events_log (session_id, event_type, payload, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (
                    session_id,
                    event_type,
                    json.dumps(payload or {}),
                    created_at or utc_now(),
                ),
            )

    def increment_violation(
        self,
        *,
        session_id: int,
        violation_type: str,
        increment: int = 1,
        triggered_at: str | None = None,
    ) -> None:
        timestamp = triggered_at or utc_now()
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO violations (session_id, type, count, last_triggered_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(session_id, type) DO UPDATE SET
                    count = violations.count + excluded.count,
                    last_triggered_at = excluded.last_triggered_at
                """,
                (session_id, violation_type, increment, timestamp),
            )

    def complete_session(
        self,
        *,
        session_id: int,
        final_status: str,
        event_timeline: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        if final_status not in {"submitted", "cancelled", "quit"}:
            raise DatabaseError("Invalid final status.")

        completed_at = utc_now()
        with self.connect() as connection:
            session_row = connection.execute(
                """
                SELECT s.id, s.exam_id, s.candidate_id, s.status, s.started_at, c.name AS candidate_name
                FROM sessions s
                JOIN candidates c ON c.id = s.candidate_id
                WHERE s.id = ?
                """,
                (session_id,),
            ).fetchone()
            if session_row is None:
                raise DatabaseError("Session not found.")

            connection.execute(
                """
                UPDATE sessions
                SET status = ?, ended_at = ?
                WHERE id = ?
                """,
                (final_status, completed_at, session_id),
            )

            violation_rows = connection.execute(
                """
                SELECT type, count, last_triggered_at
                FROM violations
                WHERE session_id = ?
                ORDER BY type
                """,
                (session_id,),
            ).fetchall()

            events = connection.execute(
                """
                SELECT event_type, payload, created_at
                FROM events_log
                WHERE session_id = ?
                ORDER BY created_at
                """,
                (session_id,),
            ).fetchall()

            violation_summary = {
                row["type"]: {
                    "count": row["count"],
                    "last_triggered_at": row["last_triggered_at"],
                }
                for row in violation_rows
            }
            event_summary = [
                {
                    "event_type": row["event_type"],
                    "payload": json.loads(row["payload"] or "{}"),
                    "created_at": row["created_at"],
                }
                for row in events
            ]
            if event_timeline:
                event_summary.extend(event_timeline)

            payload = {
                "candidate_name": session_row["candidate_name"],
                "exam_id": session_row["exam_id"],
                "session_id": session_id,
                "final_status": final_status,
                "violation_summary": violation_summary,
                "timestamps": {
                    "started_at": session_row["started_at"],
                    "ended_at": completed_at,
                },
                "event_timeline": event_summary,
            }

            connection.execute(
                """
                INSERT INTO exam_results (session_id, final_status, payload, created_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(session_id) DO UPDATE SET
                    final_status = excluded.final_status,
                    payload = excluded.payload,
                    created_at = excluded.created_at
                """,
                (session_id, final_status, json.dumps(payload), completed_at),
            )

            return payload
