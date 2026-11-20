"""
RAG chunk schema and SQLite-backed index store.

Collections:
  kb_chunks          – main KB / runbook / policy chunks
  ticket_resolutions – curated resolved tickets
  error_codes        – error-code catalog (exact + sparse-heavy)

No external vector-DB dependency: we use SQLite + sqlite-vec (optional)
for dense search and SQLite FTS5 for BM25/sparse search.
If sqlite-vec is not installed the dense path is skipped and the system
falls back to FTS5-only (still a large improvement over the original
single-file keyword scan).

Schema: every chunk carries the full metadata spec from §3.4 of the RAG spec.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from appconfig import ROOT

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
RAG_DIR = ROOT / "data" / "rag"
RAG_DIR.mkdir(parents=True, exist_ok=True)
RAG_DB = RAG_DIR / "rag_index.db"

_lock = threading.RLock()

# ---------------------------------------------------------------------------
# Chunk dataclass  (§3.4 mandatory metadata schema)
# ---------------------------------------------------------------------------
@dataclass
class Chunk:
    # Identity
    chunk_id: str = ""
    doc_id: str = ""
    parent_id: str = ""          # first chunk of the same section when a long section was split
    chunk_index: int = 0         # position of this chunk inside its section (0 = first)

    # Source provenance
    source_system: str = "kb"    # kb | ticket | vendor | error_code | policy
    url: str = ""
    title: str = ""
    section_path: str = ""       # e.g. "Network and VPN > Connect to the VPN"

    # Classification
    doc_type: str = "kb"         # runbook|kb|policy|ticket|vendor|error_code|faq
    os: str = "any"              # windows|macos|linux|ios|android|any
    os_version_range: str = ""
    app: str = ""
    app_version_range: str = ""
    device_models: list = field(default_factory=list)

    # Audience / access
    audience: str = "end_user"   # end_user|L1|L2|L3|admin
    department: str = ""
    region: str = ""
    acl_groups: list = field(default_factory=list)   # empty = everyone
    pii_flag: bool = False

    # Risk / quality
    risk_tier: str = "R0"        # R0–R3 (risk of the procedure described)
    requires_approval: bool = False
    trust_score: float = 1.0     # 0–1
    success_rate: float = 1.0    # from feedback loop
    usage_count: int = 0

    # Lifecycle
    owner: str = ""
    author: str = ""
    created_at: str = ""
    last_modified: str = ""
    last_reviewed: str = ""
    effective_date: str = ""
    expires_at: str = ""
    version: str = "1"
    status: str = "approved"     # draft|approved|deprecated

    # Content
    text: str = ""               # enriched text (context prefix + body)
    text_original: str = ""      # original body for display / citation
    language: str = "en"
    content_hash: str = ""

    # Synthetic enrichment
    hypothetical_questions: list = field(default_factory=list)
    symptom_keywords: list = field(default_factory=list)
    summary: str = ""
    entities: dict = field(default_factory=dict)   # {apps:[], os:[], error_codes:[]}

    # Dense embedding (stored as JSON list; None = not yet embedded)
    embedding: list | None = None

    def compute_hash(self) -> "Chunk":
        self.content_hash = hashlib.sha256(self.text_original.encode()).hexdigest()[:16]
        return self

    def to_row(self) -> dict:
        d = asdict(self)
        # Serialize list/dict fields to JSON for SQLite storage
        for key in ("device_models", "acl_groups", "hypothetical_questions",
                    "symptom_keywords", "entities"):
            d[key] = json.dumps(d[key])
        emb = d["embedding"]
        if isinstance(emb, str):                       # already packed (read back from the index)
            d["embedding"] = emb
        else:
            from rag.embed import pack
            d["embedding"] = pack(emb) if emb else None     # float16 + base64: small even for 2048-dim vectors
        return d

    @classmethod
    def from_row(cls, row: dict) -> "Chunk":
        for key in ("device_models", "acl_groups", "hypothetical_questions",
                    "symptom_keywords", "entities"):
            if isinstance(row.get(key), str):
                row[key] = json.loads(row[key]) if row[key] else []
        if isinstance(row.get("embedding"), str) and not row["embedding"].startswith("f16:"):
            row["embedding"] = json.loads(row["embedding"]) if row["embedding"] else None   # older JSON vectors
        return cls(**{k: v for k, v in row.items() if k in cls.__dataclass_fields__})


# ---------------------------------------------------------------------------
# DDL
# ---------------------------------------------------------------------------
_SCHEMA = """
PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS chunks (
    chunk_id          TEXT PRIMARY KEY,
    doc_id            TEXT NOT NULL,
    parent_id         TEXT DEFAULT '',
    chunk_index       INTEGER DEFAULT 0,
    source_system     TEXT DEFAULT 'kb',
    url               TEXT DEFAULT '',
    title             TEXT DEFAULT '',
    section_path      TEXT DEFAULT '',
    doc_type          TEXT DEFAULT 'kb',
    os                TEXT DEFAULT 'any',
    os_version_range  TEXT DEFAULT '',
    app               TEXT DEFAULT '',
    app_version_range TEXT DEFAULT '',
    device_models     TEXT DEFAULT '[]',
    audience          TEXT DEFAULT 'end_user',
    department        TEXT DEFAULT '',
    region            TEXT DEFAULT '',
    acl_groups        TEXT DEFAULT '[]',
    pii_flag          INTEGER DEFAULT 0,
    risk_tier         TEXT DEFAULT 'R0',
    requires_approval INTEGER DEFAULT 0,
    trust_score       REAL DEFAULT 1.0,
    success_rate      REAL DEFAULT 1.0,
    usage_count       INTEGER DEFAULT 0,
    owner             TEXT DEFAULT '',
    author            TEXT DEFAULT '',
    created_at        TEXT DEFAULT '',
    last_modified     TEXT DEFAULT '',
    last_reviewed     TEXT DEFAULT '',
    effective_date    TEXT DEFAULT '',
    expires_at        TEXT DEFAULT '',
    version           TEXT DEFAULT '1',
    status            TEXT DEFAULT 'approved',
    text              TEXT NOT NULL,
    text_original     TEXT NOT NULL,
    language          TEXT DEFAULT 'en',
    content_hash      TEXT DEFAULT '',
    hypothetical_questions TEXT DEFAULT '[]',
    symptom_keywords  TEXT DEFAULT '[]',
    summary           TEXT DEFAULT '',
    entities          TEXT DEFAULT '{}',
    embedding         TEXT
);

-- Full-text search (BM25 / sparse search)
CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
    chunk_id UNINDEXED,
    text,
    hypothetical_questions,
    symptom_keywords,
    content='chunks',
    content_rowid='rowid'
);

-- Triggers to keep FTS in sync
CREATE TRIGGER IF NOT EXISTS chunks_ai AFTER INSERT ON chunks BEGIN
    INSERT INTO chunks_fts(rowid, chunk_id, text, hypothetical_questions, symptom_keywords)
    VALUES (new.rowid, new.chunk_id, new.text, new.hypothetical_questions, new.symptom_keywords);
END;

CREATE TRIGGER IF NOT EXISTS chunks_ad AFTER DELETE ON chunks BEGIN
    INSERT INTO chunks_fts(chunks_fts, rowid, chunk_id, text, hypothetical_questions, symptom_keywords)
    VALUES ('delete', old.rowid, old.chunk_id, old.text, old.hypothetical_questions, old.symptom_keywords);
END;

CREATE TRIGGER IF NOT EXISTS chunks_au AFTER UPDATE ON chunks BEGIN
    INSERT INTO chunks_fts(chunks_fts, rowid, chunk_id, text, hypothetical_questions, symptom_keywords)
    VALUES ('delete', old.rowid, old.chunk_id, old.text, old.hypothetical_questions, old.symptom_keywords);
    INSERT INTO chunks_fts(rowid, chunk_id, text, hypothetical_questions, symptom_keywords)
    VALUES (new.rowid, new.chunk_id, new.text, new.hypothetical_questions, new.symptom_keywords);
END;

-- Payload indexes for fast metadata pre-filtering
CREATE INDEX IF NOT EXISTS idx_chunks_doc_type   ON chunks(doc_type);
CREATE INDEX IF NOT EXISTS idx_chunks_status      ON chunks(status);
CREATE INDEX IF NOT EXISTS idx_chunks_os          ON chunks(os);
CREATE INDEX IF NOT EXISTS idx_chunks_doc_id      ON chunks(doc_id);
CREATE INDEX IF NOT EXISTS idx_chunks_source      ON chunks(source_system);
CREATE INDEX IF NOT EXISTS idx_chunks_expires_at  ON chunks(expires_at);

-- Knowledge gap queue (§11 / §5.5)
CREATE TABLE IF NOT EXISTS knowledge_gaps (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    ts        TEXT NOT NULL,
    query     TEXT NOT NULL,
    context   TEXT DEFAULT '',
    frequency INTEGER DEFAULT 1,
    resolved  INTEGER DEFAULT 0
);

-- Feedback signals (§11 / learning loop)
CREATE TABLE IF NOT EXISTS rag_feedback (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    ts        TEXT NOT NULL,
    chunk_id  TEXT NOT NULL,
    answer_id TEXT DEFAULT '',
    helpful   INTEGER NOT NULL,   -- 1 / 0
    correction TEXT DEFAULT ''
);

-- Audit log for RAG retrievals (§7)
CREATE TABLE IF NOT EXISTS rag_audit (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    ts         TEXT NOT NULL,
    task_id    TEXT DEFAULT '',
    query      TEXT NOT NULL,
    filters    TEXT DEFAULT '{}',
    result_ids TEXT DEFAULT '[]',
    scores     TEXT DEFAULT '[]',
    shown_ids  TEXT DEFAULT '[]'
);

-- Draft KB articles waiting for human review (§11)
CREATE TABLE IF NOT EXISTS draft_articles (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    ts         TEXT NOT NULL,
    ticket_id  TEXT DEFAULT '',
    title      TEXT NOT NULL,
    content    TEXT NOT NULL,
    status     TEXT DEFAULT 'pending_review',  -- pending_review | approved | rejected
    reviewer   TEXT DEFAULT '',
    reviewed_at TEXT DEFAULT ''
);
"""


def _migrate(conn: sqlite3.Connection) -> None:
    """Bring an index created by an older version up to the current schema."""
    cols = {r[1] for r in conn.execute("PRAGMA table_info(chunks)")}
    if "chunk_index" not in cols:
        conn.execute("ALTER TABLE chunks ADD COLUMN chunk_index INTEGER DEFAULT 0")
        conn.commit()
        rebuild_fts(conn)  # older versions could leave stale FTS rows behind


def rebuild_fts(conn: sqlite3.Connection | None = None) -> None:
    """Re-create the full-text index from the chunks table (cheap at KB scale)."""
    conn = conn or get_conn()
    with _lock:
        conn.execute("INSERT INTO chunks_fts(chunks_fts) VALUES('rebuild')")
        conn.commit()


def _connect(db_path: Path | None = None) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path or RAG_DB), check_same_thread=False, timeout=15)
    conn.row_factory = sqlite3.Row
    conn.executescript(_SCHEMA)
    _migrate(conn)
    return conn


# Module-level shared connection (WAL mode is safe for concurrent reads)
_conn: sqlite3.Connection | None = None


def get_conn() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        with _lock:
            if _conn is None:
                _conn = _connect()
    return _conn


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------
def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def upsert_chunk(chunk: Chunk) -> None:
    """Insert or replace a chunk. Thread-safe."""
    if not chunk.chunk_id:
        raise ValueError("chunk_id must be set before upserting")
    if not chunk.created_at:
        chunk.created_at = _now()
    chunk.last_modified = _now()
    row = chunk.to_row()
    cols = ", ".join(row.keys())
    placeholders = ", ".join("?" for _ in row)
    updates = ", ".join(f"{k} = excluded.{k}" for k in row if k not in ("chunk_id", "created_at"))
    # A true upsert keeps the rowid and fires the AFTER UPDATE trigger. INSERT OR REPLACE does not
    # fire delete triggers, which used to leave stale rows behind in the FTS index.
    sql = (f"INSERT INTO chunks ({cols}) VALUES ({placeholders}) "
           f"ON CONFLICT(chunk_id) DO UPDATE SET {updates}")
    with _lock, get_conn() as conn:
        conn.execute(sql, list(row.values()))


def delete_chunk(chunk_id: str) -> None:
    with _lock, get_conn() as conn:
        conn.execute("DELETE FROM chunks WHERE chunk_id = ?", (chunk_id,))


def get_chunk(chunk_id: str) -> Chunk | None:
    row = get_conn().execute(
        "SELECT * FROM chunks WHERE chunk_id = ?", (chunk_id,)
    ).fetchone()
    return Chunk.from_row(dict(row)) if row else None


def get_document_chunks(doc_id: str) -> list[Chunk]:
    rows = get_conn().execute(
        "SELECT * FROM chunks WHERE doc_id = ? ORDER BY rowid", (doc_id,)
    ).fetchall()
    return [Chunk.from_row(dict(r)) for r in rows]


def list_doc_ids(url_prefix: str = "") -> list[str]:
    """Distinct doc_ids, optionally limited to chunks whose url starts with url_prefix."""
    if url_prefix:
        rows = get_conn().execute("SELECT DISTINCT doc_id FROM chunks WHERE url LIKE ?", (url_prefix + "%",))
    else:
        rows = get_conn().execute("SELECT DISTINCT doc_id FROM chunks")
    return [r[0] for r in rows.fetchall()]


def delete_document(doc_id: str) -> int:
    with _lock, get_conn() as conn:
        return conn.execute("DELETE FROM chunks WHERE doc_id = ?", (doc_id,)).rowcount


def get_section_chunks(doc_id: str, section_path: str) -> list[Chunk]:
    """All chunks of one section, in reading order (a long section is split into several)."""
    rows = get_conn().execute(
        "SELECT * FROM chunks WHERE doc_id = ? AND section_path = ? ORDER BY chunk_index",
        (doc_id, section_path)).fetchall()
    return [Chunk.from_row(dict(r)) for r in rows]


def get_parent_chunk(chunk: Chunk) -> Chunk | None:
    if not chunk.parent_id:
        return None
    return get_chunk(chunk.parent_id)


# ---------------------------------------------------------------------------
# Feedback + gap logging
# ---------------------------------------------------------------------------
def log_gap(query: str, context: str = "", task_id: str = "") -> None:
    """Log a knowledge gap for the gap queue."""
    conn = get_conn()
    query = " ".join(query.split())[:300]
    if not query:
        return
    with _lock, conn:
        # Same question (ignoring case) already open -> just bump its frequency
        existing = conn.execute(
            "SELECT id FROM knowledge_gaps WHERE lower(query) = lower(?) AND resolved = 0", (query,)
        ).fetchone()
        if existing:
            conn.execute(
                "UPDATE knowledge_gaps SET frequency = frequency + 1 WHERE id = ?",
                (existing["id"],)
            )
        else:
            conn.execute(
                "INSERT INTO knowledge_gaps (ts, query, context) VALUES (?, ?, ?)",
                (_now(), query, context)
            )


def log_feedback(chunk_id: str, helpful: bool, answer_id: str = "", correction: str = "") -> None:
    with _lock, get_conn() as conn:
        conn.execute(
            "INSERT INTO rag_feedback (ts, chunk_id, answer_id, helpful, correction) VALUES (?, ?, ?, ?, ?)",
            (_now(), chunk_id, answer_id, int(helpful), correction)
        )
    # Update success_rate on the chunk
    _update_chunk_success_rate(chunk_id)


def _update_chunk_success_rate(chunk_id: str) -> None:
    conn = get_conn()
    row = conn.execute(
        "SELECT COALESCE(SUM(helpful), 0), COUNT(*) FROM rag_feedback WHERE chunk_id = ?", (chunk_id,)
    ).fetchone()
    if row and row[1]:
        # Smoothed with a prior of 2 "helpful" votes so one thumbs-down cannot bury an article.
        rate = (row[0] + 2.0) / (row[1] + 2.0)
        with _lock, conn:
            conn.execute("UPDATE chunks SET success_rate = ? WHERE chunk_id = ?", (rate, chunk_id))


def increment_usage(chunk_id: str) -> None:
    with _lock, get_conn() as conn:
        conn.execute(
            "UPDATE chunks SET usage_count = usage_count + 1 WHERE chunk_id = ?",
            (chunk_id,)
        )


def increment_usage_many(chunk_ids: list[str]) -> None:
    if not chunk_ids:
        return
    with _lock, get_conn() as conn:
        conn.executemany("UPDATE chunks SET usage_count = usage_count + 1 WHERE chunk_id = ?",
                         [(c,) for c in chunk_ids])


def log_rag_audit(task_id: str, query: str, filters: dict,
                  result_ids: list[str], scores: list[float], shown_ids: list[str]) -> None:
    with _lock, get_conn() as conn:
        conn.execute(
            "INSERT INTO rag_audit (ts, task_id, query, filters, result_ids, scores, shown_ids) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (_now(), task_id, query, json.dumps(filters),
             json.dumps(result_ids), json.dumps(scores), json.dumps(shown_ids))
        )


def save_draft_article(ticket_id: str, title: str, content: str) -> int:
    with _lock, get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO draft_articles (ts, ticket_id, title, content) VALUES (?, ?, ?, ?)",
            (_now(), ticket_id, title, content)
        )
        return cur.lastrowid


def list_draft_articles(status: str = "pending_review") -> list[dict]:
    rows = get_conn().execute(
        "SELECT * FROM draft_articles WHERE status = ? ORDER BY ts DESC", (status,)
    ).fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Utility: list all chunks (for admin / debugging)
# ---------------------------------------------------------------------------
def stats() -> dict:
    conn = get_conn()
    total = conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
    by_type = conn.execute(
        "SELECT doc_type, COUNT(*) as n FROM chunks GROUP BY doc_type"
    ).fetchall()
    gaps = conn.execute(
        "SELECT COUNT(*) FROM knowledge_gaps WHERE resolved = 0"
    ).fetchone()[0]
    drafts = conn.execute(
        "SELECT COUNT(*) FROM draft_articles WHERE status = 'pending_review'"
    ).fetchone()[0]
    return {
        "total_chunks": total,
        "by_doc_type": {r["doc_type"]: r["n"] for r in by_type},
        "open_gaps": gaps,
        "pending_drafts": drafts,
    }
