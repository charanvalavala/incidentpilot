from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import UTC, datetime
from typing import Any

from incidentpilot.config import DATABASE_PATH


@contextmanager
def connect():
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(DATABASE_PATH)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    try:
        yield db
        db.commit()
    finally:
        db.close()


def initialize():
    with connect() as db:
        db.executescript(
            """
            CREATE TABLE IF NOT EXISTS incidents (
                id TEXT PRIMARY KEY,
                scenario TEXT NOT NULL,
                status TEXT NOT NULL,
                state TEXT NOT NULL,
                version INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                incident_id TEXT NOT NULL REFERENCES incidents(id) ON DELETE CASCADE,
                event_type TEXT NOT NULL,
                payload TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS events_by_incident ON events(incident_id, id);
            """
        )


def now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def create_incident(incident_id: str, scenario: str, state: dict[str, Any]):
    timestamp = now()
    with connect() as db:
        db.execute("DELETE FROM incidents WHERE id IN (SELECT id FROM incidents ORDER BY created_at DESC LIMIT -1 OFFSET 249)")
        db.execute(
            "INSERT INTO incidents(id, scenario, status, state, version, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (incident_id, scenario, "investigating", json.dumps(state), 1, timestamp, timestamp),
        )
        append_event(db, incident_id, "incident.created", {"scenario": scenario, "status": "investigating"}, timestamp)


def append_event(db: sqlite3.Connection, incident_id: str, event_type: str, payload: dict[str, Any], timestamp: str | None = None):
    db.execute(
        "INSERT INTO events(incident_id, event_type, payload, created_at) VALUES (?, ?, ?, ?)",
        (incident_id, event_type, json.dumps(payload), timestamp or now()),
    )


def get_incident(incident_id: str) -> dict[str, Any] | None:
    with connect() as db:
        row = db.execute("SELECT * FROM incidents WHERE id = ?", (incident_id,)).fetchone()
        if row is None:
            return None
        item = dict(row)
        item["state"] = json.loads(item["state"])
        return item


class ConcurrentUpdateError(ValueError):
    pass


def update_incident(incident_id: str, state: dict[str, Any], status: str, event_type: str, payload: dict[str, Any], expected_version: int | None = None, expected_status: str | None = None):
    timestamp = now()
    with connect() as db:
        conditions = ["id = ?"]
        values: list[Any] = [json.dumps(state), status, timestamp, incident_id]
        if expected_version is not None:
            conditions.append("version = ?")
            values.append(expected_version)
        if expected_status is not None:
            conditions.append("status = ?")
            values.append(expected_status)
        cursor = db.execute(
            f"UPDATE incidents SET state = ?, status = ?, version = version + 1, updated_at = ? WHERE {' AND '.join(conditions)}",
            values,
        )
        if cursor.rowcount != 1:
            raise ConcurrentUpdateError("The incident changed before this decision was saved. Refresh and try again.")
        append_event(db, incident_id, event_type, payload, timestamp)


def events(incident_id: str) -> list[dict[str, Any]]:
    with connect() as db:
        rows = db.execute("SELECT event_type, payload, created_at FROM events WHERE incident_id = ? ORDER BY id", (incident_id,)).fetchall()
        return [{**dict(row), "payload": json.loads(row["payload"])} for row in rows]


def recent_incidents(limit: int = 20) -> list[dict[str, Any]]:
    with connect() as db:
        rows = db.execute("SELECT id, scenario, status, version, created_at, updated_at FROM incidents ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
        return [dict(row) for row in rows]
