"""Built-in ticket desk (SQLite). Stands in for an ITSM system such as ServiceNow or Jira.

The agent opens a ticket whenever it cannot or may not solve something itself, with a full
context package so the user never has to repeat themselves. An ITSM connector can replace
create_ticket() later without touching the agents.
"""
from __future__ import annotations

import sqlite3
import threading
from datetime import datetime, timezone

import appconfig
from tools.registry import R0, R1, Param, tool

_lock = threading.Lock()
PRIORITIES = ("P1", "P2", "P3", "P4")
CATEGORIES = ("incident", "service_request", "access_request", "hardware_request", "software_request",
              "security", "question")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS tickets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created TEXT NOT NULL,
    updated TEXT NOT NULL,
    task_id TEXT,
    title TEXT NOT NULL,
    category TEXT NOT NULL,
    priority TEXT NOT NULL,
    status TEXT NOT NULL,          -- open | in_progress | resolved | closed
    requester TEXT,
    summary TEXT,
    work_notes TEXT
);
"""


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(appconfig.data_path("audit_db"))
    conn.executescript(_SCHEMA)
    conn.row_factory = sqlite3.Row
    return conn


def ticket_ref(ticket_id: int) -> str:
    return f"ITB-{ticket_id:04d}"


def create_ticket(title: str, summary: str, *, category: str = "incident", priority: str = "P3",
                  task_id: str | None = None, work_notes: str = "") -> dict:
    import getpass

    category = category if category in CATEGORIES else "incident"
    priority = priority if priority in PRIORITIES else "P3"
    with _lock, _connect() as conn:
        cur = conn.execute(
            "INSERT INTO tickets (created, updated, task_id, title, category, priority, status, requester, summary, work_notes)"
            " VALUES (?, ?, ?, ?, ?, ?, 'open', ?, ?, ?)",
            (_now(), _now(), task_id, title[:120], category, priority, getpass.getuser(), summary[:3000], work_notes[:4000]),
        )
        ticket_id = cur.lastrowid
    return {"id": ticket_id, "ref": ticket_ref(ticket_id), "priority": priority, "category": category}


def add_work_note(ticket_id: int, note: str) -> None:
    with _lock, _connect() as conn:
        conn.execute("UPDATE tickets SET work_notes = COALESCE(work_notes, '') || ?, updated = ? WHERE id = ?",
                     (f"\n[{_now()}] {note[:1500]}", _now(), ticket_id))


def set_status(ticket_id: int, status: str) -> None:
    with _lock, _connect() as conn:
        conn.execute("UPDATE tickets SET status = ?, updated = ? WHERE id = ?", (status, _now(), ticket_id))


def all_tickets(limit: int = 200) -> list[dict]:
    with _lock, _connect() as conn:
        return [dict(r) for r in conn.execute("SELECT * FROM tickets ORDER BY id DESC LIMIT ?", (limit,))]


def _parse_ref(ticket: str) -> int | None:
    digits = "".join(ch for ch in str(ticket) if ch.isdigit())
    return int(digits) if digits else None


@tool("it_request", R0, "List this user's most recent IT tickets and their status.")
def list_my_tickets() -> dict:
    rows = all_tickets(8)
    return {"ok": True, "count": len(rows),
            "tickets": [{"ref": ticket_ref(r["id"]), "title": r["title"][:60], "status": r["status"],
                         "priority": r["priority"], "created": r["created"][:16].replace("T", " ")} for r in rows]}


@tool("it_request", R0, "Status and details of one ticket by its reference, for example ITB-0003.",
      params=(Param("ticket", "str", "ticket reference", max_len=20),))
def get_ticket(ticket: str) -> dict:
    ticket_id = _parse_ref(ticket)
    if ticket_id is None:
        return {"ok": False, "error": "Give a ticket reference such as ITB-0003"}
    with _lock, _connect() as conn:
        row = conn.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
    if row is None:
        return {"ok": False, "error": f"No ticket {ticket_ref(ticket_id)}"}
    return {"ok": True, "ref": ticket_ref(row["id"]), "title": row["title"], "status": row["status"],
            "priority": row["priority"], "category": row["category"], "created": row["created"][:16].replace("T", " "),
            "summary": (row["summary"] or "")[:500]}


@tool("it_request", R1, "Raise a ticket for the IT team (for things IT staff must do, or when nothing else worked).",
      params=(Param("title", "str", "short title", max_len=120),
              Param("summary", "str", "what is needed and what was already tried", max_len=800),
              Param("priority", "str", "P1 team blocked or security emergency, P2 one person cannot work, "
                                       "P3 normal, P4 question", choices=PRIORITIES, required=False)),
      change_note="A ticket is created in the built-in ticket desk for the IT team, with the text shown.",
      summary="Raise a ticket: {title}")
def raise_ticket(title: str, summary: str, priority: str = "P3") -> dict:
    t = create_ticket(title, summary, priority=priority or "P3")
    return {"ok": True, "ref": t["ref"], "priority": t["priority"]}
