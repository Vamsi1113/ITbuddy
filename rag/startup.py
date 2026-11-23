"""
RAG startup helper: initialises the index on first run and refreshes
it when KB files have changed. Called once from app.py and cli.py.

This keeps the RAG layer transparent to the existing code: it activates
automatically when it can and silently degrades otherwise (failures are logged, never raised).
"""
from __future__ import annotations

import logging
import threading

from appconfig import ROOT

log = logging.getLogger("rag.startup")

KB_DIR = ROOT / "kb"
_INIT_DONE = False
_INIT_LOCK = threading.Lock()


def _last_kb_mtime() -> float:
    """Return the most recent mtime of any .md file in kb/."""
    mtimes = [p.stat().st_mtime for p in KB_DIR.glob("*.md")]
    return max(mtimes) if mtimes else 0.0


def _get_indexed_mtime() -> float:
    """Timestamp of the last ingest of KB content (chunks are stamped with their index time)."""
    try:
        from datetime import datetime
        from rag.index import get_conn
        row = get_conn().execute(
            "SELECT MAX(last_modified) FROM chunks WHERE url LIKE 'kb/%'"
        ).fetchone()
        if row and row[0]:
            return datetime.fromisoformat(row[0]).timestamp()
    except Exception:
        pass
    return 0.0


def _kb_files_changed() -> bool:
    """True when kb/*.md differs from the index: new/edited files, or files that were removed."""
    from rag.index import list_doc_ids
    on_disk = {p.stem for p in KB_DIR.glob("*.md")}
    indexed = set(list_doc_ids("kb/"))
    return on_disk != indexed or _last_kb_mtime() > _get_indexed_mtime()


def ensure_rag_index(background: bool = True) -> None:
    """
    Ensure the RAG index exists and is up-to-date.
    If background=True, runs ingestion in a daemon thread so the UI is not blocked during startup.
    """
    global _INIT_DONE
    if _INIT_DONE:
        return
    with _INIT_LOCK:
        if _INIT_DONE:
            return
        _INIT_DONE = True

    def _run():
        try:
            from rag.index import get_conn, stats
            get_conn()  # ensure schema is created / migrated

            from rag.ingest import (
                backfill_embeddings, ingest_error_codes, ingest_kb_files, ingest_resolved_tickets,
                ingest_vendor_files,
            )
            current = stats()
            if current["total_chunks"] == 0 or _kb_files_changed():
                ingest_kb_files(force=False)
            ingest_vendor_files()                  # imported Microsoft Learn articles (only changed files)
            from rag.sop_ingest import ingest_sop_files
            ingest_sop_files()                     # the organisation's SOPs in kb_sop/ (only changed files)
            if not current["by_doc_type"].get("error_code"):
                from rag.error_catalog import SAMPLE_ERROR_CODES
                ingest_error_codes(SAMPLE_ERROR_CODES)
            try:
                ingest_resolved_tickets()          # learn from resolved tickets
            except Exception as exc:               # ticket store optional
                log.info("Ticket ingestion skipped: %s", exc)
            backfill_embeddings()                  # no-op unless dense search is available
            from rag.retrieval import resolve_answerable_gaps
            resolve_answerable_gaps()              # close gaps that new/edited articles now answer
        except Exception:
            log.exception("RAG index initialisation failed; falling back to keyword search")

    if background:
        threading.Thread(target=_run, daemon=True, name="rag-init").start()
    else:
        _run()
