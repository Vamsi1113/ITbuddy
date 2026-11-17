"""SQLite audit log: every request, tool call, approval decision and result (FR-16)."""
from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime, timezone

from appconfig import data_path

_lock = threading.Lock()

_SCHEMA = """
CREATE TABLE IF NOT EXISTS audit (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    task_id TEXT NOT NULL,
    event TEXT NOT NULL,          -- request | route | tool_call | approval | result | error | report
    agent TEXT,
    tool TEXT,
    args TEXT,
    risk_level INTEGER,
    detail TEXT
);
CREATE TABLE IF NOT EXISTS tasks (
    task_id TEXT PRIMARY KEY,
    started TEXT NOT NULL,
    finished TEXT,
    request TEXT NOT NULL,
    agent TEXT,
    outcome TEXT,                 -- running | fixed | not_fixed | rejected | refused | no_action | error
    summary TEXT
);
"""


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _connect(db_path=None) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path or data_path("audit_db"))
    conn.executescript(_SCHEMA)
    return conn


def _dump(value) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return json.dumps(value, default=str)[:4000]


def log_event(task_id: str, event: str, *, agent=None, tool=None, args=None,
              risk_level=None, detail=None, db_path=None) -> None:
    with _lock, _connect(db_path) as conn:
        conn.execute(
            "INSERT INTO audit (ts, task_id, event, agent, tool, args, risk_level, detail)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (_now(), task_id, event, agent, tool, _dump(args), risk_level, _dump(detail)),
        )


def start_task(task_id: str, request: str, db_path=None) -> None:
    with _lock, _connect(db_path) as conn:
        conn.execute(
            "INSERT OR IGNORE INTO tasks (task_id, started, request, outcome) VALUES (?, ?, ?, 'running')",
            (task_id, _now(), request),
        )
    log_event(task_id, "request", detail=request, db_path=db_path)


def finish_task(task_id: str, agent: str | None, outcome: str, summary: str, db_path=None) -> None:
    with _lock, _connect(db_path) as conn:
        conn.execute(
            "UPDATE tasks SET finished = ?, agent = ?, outcome = ?, summary = ? WHERE task_id = ?",
            (_now(), agent, outcome, summary[:2000], task_id),
        )


def list_tasks(limit: int = 100, db_path=None) -> list[dict]:
    with _lock, _connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM tasks ORDER BY started DESC LIMIT ?", (limit,)
        ).fetchall()
    return [dict(r) for r in rows]


def task_events(task_id: str, db_path=None) -> list[dict]:
    with _lock, _connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT ts, event, agent, tool, args, risk_level, detail FROM audit"
            " WHERE task_id = ? ORDER BY id", (task_id,)
        ).fetchall()
    return [dict(r) for r in rows]
