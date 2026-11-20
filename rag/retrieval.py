"""
Retrieval service (§5) – the full query-time pipeline.

Steps (§5):
  1. Query understanding (variants + error-code extraction)
  2. Hybrid retrieval: BM25/FTS5 (sparse) + dense kNN (if embeddings available)
     + exact error-code match
  3. Reciprocal Rank Fusion (RRF) for score merging
  4. Metadata pre-filter: status=approved, ACL, audience, OS, not expired (done in SQL, before ranking)
  5. Trust + freshness + doc_type + feedback boost for final ranking
  6. Section expansion: a split long section is returned whole
  7. Sufficiency check (CRAG-style): sufficient / partial / irrelevant, from a 0..1 relevance signal
  8. Context packaging with citations (sanitised: retrieved text is untrusted data)
  9. Fallback: broaden filters -> retry -> "don't know" + log gap

No dependencies beyond the stdlib + sqlite3. Dense search switches on when sentence-transformers is
installed and chunks carry embeddings (see rag/embed.py).
"""
from __future__ import annotations

import copy
import json
import math
import re
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from appconfig import cfg
from rag import embed as _embedder
from rag.index import (
    Chunk, get_conn, get_section_chunks, increment_usage_many, log_gap, log_rag_audit,
)

# Default trust order (§5.3). config.yaml `rag.doc_type_trust` overrides it.
_DEFAULT_DOC_TYPE_PRIORITY = {
    "error_code": 1.0, "runbook": 0.95, "kb": 0.9, "policy": 0.85, "ticket": 0.7, "faq": 0.65, "vendor": 0.6,
}


def _embed(text: str) -> list[float] | None:
    """Embed a query; None when dense search is unavailable (BM25 + exact match still work)."""
    return _embedder.embed(text)


# ---------------------------------------------------------------------------
# Untrusted-text hygiene (§6 / §7). Retrieved text is data; instructions hidden in it are stripped.
# ---------------------------------------------------------------------------
_INJECTION_PATTERNS = [
    re.compile(r"ignore\s+(previous|all|above|prior)\s+instructions?", re.IGNORECASE),
    re.compile(r"disregard\s+(the\s+)?(previous|all|above|prior|system)\s+(instructions?|prompt)", re.IGNORECASE),
    re.compile(r"you\s+are\s+now\s+a", re.IGNORECASE),
    re.compile(r"</?(system|user|assistant)>", re.IGNORECASE),
    re.compile(r"\[INST\]|\[/INST\]|<\|im_start\|>|<\|im_end\|>"),
    re.compile(r"<!--.*?-->", re.DOTALL),
    re.compile(r"act\s+as\s+(a\s+)?(different|new|another)", re.IGNORECASE),
    re.compile(r"forget\s+(everything|all|your|previous)", re.IGNORECASE),
]


def sanitize_text(text: str) -> str:
    """Remove prompt-injection patterns from retrieved text."""
    text = text or ""
    for pattern in _INJECTION_PATTERNS:
        text = pattern.sub("[REDACTED]", text)
    return text


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------
@dataclass
class RetrievalResult:
    chunk_id: str
    doc_id: str
    title: str
    section_path: str
    url: str
    text: str                      # the original (non-prefixed) body for display
    score: float = 0.0             # final ranking score (RRF x trust x freshness x ...)
    rrf_score: float = 0.0
    relevance: float = 0.0         # 0..1 "does this answer the question" signal used for sufficiency
    trust_score: float = 1.0
    success_rate: float = 1.0
    doc_type: str = "kb"
    os: str = "any"
    risk_tier: str = "R0"
    last_reviewed: str = ""
    version: str = "1"
    snippet: str = ""              # compressed excerpt
    citation: str = ""             # e.g. "[network_and_vpn.md § VPN keeps disconnecting]"
    source_system: str = "kb"
    # Full section text, set only when the matched chunk is one part of a longer, split section
    parent_text: str = ""
    parent_section: str = ""


# ---------------------------------------------------------------------------
# Retrieval filters
# ---------------------------------------------------------------------------
def _like_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


@dataclass
class RetrievalFilters:
    doc_types: list[str] = field(default_factory=list)   # empty = all
    os: str = ""                                          # e.g. "windows"
    audience: list[str] = field(default_factory=list)    # empty = all
    acl_groups: list[str] = field(default_factory=list)  # the user's group memberships
    status: str = "approved"
    exclude_expired: bool = True

    def to_sql_clauses(self) -> tuple[str, list]:
        """Return (WHERE clause fragment, parameters). Applied BEFORE ranking (pre-filter, §7)."""
        clauses: list[str] = ["status = ?"]
        params: list[Any] = [self.status]

        if self.doc_types:
            clauses.append(f"doc_type IN ({', '.join('?' * len(self.doc_types))})")
            params.extend(self.doc_types)

        if self.os and self.os != "any":
            clauses.append("(os = ? OR os = 'any')")
            params.append(self.os)

        if self.audience:
            clauses.append(f"audience IN ({', '.join('?' * len(self.audience))})")
            params.extend(self.audience)

        # Access control: open content is visible to everyone; restricted content only to listed groups
        acl = "(acl_groups IS NULL OR acl_groups = '' OR acl_groups = '[]'"
        for grp in self.acl_groups:
            acl += " OR acl_groups LIKE ? ESCAPE '\\'"
            params.append("%" + _like_escape(json.dumps(grp)) + "%")
        clauses.append(acl + ")")

        if self.exclude_expired:
            now = datetime.now(timezone.utc).isoformat(timespec="seconds")
            clauses.append("(expires_at = '' OR expires_at IS NULL OR expires_at > ?)")
            params.append(now)

        return " AND ".join(clauses), params


# ---------------------------------------------------------------------------
# Exact error-code lookup (§5.1 / §5.2)
# ---------------------------------------------------------------------------
_ERROR_CODE_RE = re.compile(
    r"\b(0x[0-9a-fA-F]{4,}|error\s+\d{3,}|[A-Z]{2,}_[A-Z_]{2,})\b"
)


def _extract_error_codes(query: str) -> list[str]:
    return sorted({m.group(0) for m in _ERROR_CODE_RE.finditer(query)})


def _exact_error_code_search(codes: list[str], filters: RetrievalFilters, top_k: int = 5) -> list[tuple[str, float]]:
    """Return (chunk_id, score) pairs for exact error-code matches."""
    if not codes:
        return []
    conn = get_conn()
    where_base, params_base = filters.to_sql_clauses()
    results: list[tuple[str, float]] = []
    seen: set[str] = set()
    for code in codes:
        pat = f"%{_like_escape(code)}%"
        rows = conn.execute(
            f"SELECT chunk_id FROM chunks WHERE {where_base} AND ("
            f"text LIKE ? ESCAPE '\\' OR symptom_keywords LIKE ? ESCAPE '\\') "
            f"ORDER BY (doc_type = 'error_code') DESC LIMIT ?",
            params_base + [pat, pat, top_k]
        ).fetchall()
        for row in rows:
            if row["chunk_id"] not in seen:
                seen.add(row["chunk_id"])
                results.append((row["chunk_id"], 2.0))  # exact match gets highest score
    return results


_STOP_WORDS = {
    "a", "about", "above", "after", "again", "against", "all", "am", "an", "and", "any", "are",
    "as", "at", "be", "because", "been", "before", "being", "below", "between", "both", "but",
    "by", "can", "cant", "cannot", "could", "did", "do", "does", "doing", "down", "during",
    "each", "few", "for", "from", "further", "had", "has", "have", "having", "he", "her",
    "here", "hers", "herself", "him", "himself", "his", "how", "i", "if", "in", "into", "is",
    "it", "its", "itself", "me", "more", "most", "my", "myself", "no", "nor", "not", "of",
    "off", "on", "once", "only", "or", "other", "ought", "our", "ours", "ourselves", "out",
    "over", "own", "same", "she", "should", "so", "some", "such", "than", "that", "the",
    "their", "theirs", "them", "themselves", "then", "there", "these", "they", "this",
    "those", "through", "to", "too", "under", "until", "up", "very", "was", "we", "were",
    "what", "when", "where", "which", "while", "who", "whom", "why", "with", "would",
    "you", "your", "yours", "yourself", "yourselves", "please", "help"
}


def _content_words(query: str) -> list[str]:
    words = [w for w in re.findall(r"[a-zA-Z0-9_]+", query.lower()) if w not in _STOP_WORDS and len(w) > 1]
    return words or [w for w in re.findall(r"[a-zA-Z0-9_]+", query.lower()) if len(w) > 1]


def _prepare_fts_query(query: str) -> str:
    """
    Format a query string for SQLite FTS5 BM25.
    Filters out common stopwords and connects content terms with OR so BM25
    can score documents based on keyword coverage and term frequency.
    """
    words = _content_words(query)
    if not words:
        return ""
    return " OR ".join(f'"{w}"' for w in dict.fromkeys(words))


# ---------------------------------------------------------------------------
# BM25 / FTS5 sparse search (§5.2)
# ---------------------------------------------------------------------------
_FILTER_COLUMNS = ("status", "doc_type", "os", "audience", "acl_groups", "expires_at")


def _qualify(where: str) -> str:
    """Prefix the filter columns with the chunks alias (chunks_fts has columns of its own)."""
    for col in _FILTER_COLUMNS:
        where = re.sub(rf"(?<![\w.]){col}(?!\w)", f"c.{col}", where)
    return where


def _fts_search(query: str, filters: RetrievalFilters, top_k: int = 50) -> list[tuple[str, float]]:
    """Full-text BM25 search using SQLite FTS5. Returns (chunk_id, score)."""
    fts_q = _prepare_fts_query(query)
    if not fts_q:
        return []

    conn = get_conn()
    where_base, params_base = filters.to_sql_clauses()

    try:
        rows = conn.execute(
            f"""
            SELECT c.chunk_id, bm25(chunks_fts) AS score
            FROM chunks_fts
            JOIN chunks c ON c.rowid = chunks_fts.rowid
            WHERE chunks_fts MATCH ?
              AND {_qualify(where_base)}
            ORDER BY score
            LIMIT ?
            """,
            [fts_q] + params_base + [top_k]
        ).fetchall()
        # FTS5 bm25() returns negative values (more negative = better match)
        return [(r["chunk_id"], abs(r["score"])) for r in rows]
    except sqlite3.OperationalError:
        return []  # damaged/missing FTS table: degrade to the other signals


# ---------------------------------------------------------------------------
# Dense search (§5.2) – only active when embeddings exist
# ---------------------------------------------------------------------------
def _dense_search(query_vec: list[float] | None, filters: RetrievalFilters,
                  top_k: int = 50) -> list[tuple[str, float]]:
    """Cosine similarity search over stored embeddings. Returns (chunk_id, score)."""
    if query_vec is None:
        return []
    import numpy as np
    q = np.asarray(query_vec, dtype=np.float32)
    if not np.any(q):
        return []
    ids, matrix = _vector_matrix(len(q))
    if matrix is None:
        return []
    where_base, params_base = filters.to_sql_clauses()
    allowed = {r[0] for r in get_conn().execute(
        f"SELECT chunk_id FROM chunks WHERE {where_base} AND embedding IS NOT NULL", params_base).fetchall()}
    scores = matrix @ q                                    # vectors are pre-normalised: dot = cosine
    order = np.argsort(-scores)
    out = []
    for i in order:
        if ids[i] in allowed:
            out.append((ids[i], float(scores[i])))
            if len(out) >= top_k:
                break
    return out


_VEC_CACHE: dict = {"key": None, "ids": [], "matrix": None}


def _vector_matrix(dims: int):
    """All stored vectors as one matrix, cached until the set of embedded chunks changes."""
    import numpy as np
    conn = get_conn()
    key = tuple(conn.execute("SELECT COUNT(*), COALESCE(SUM(LENGTH(embedding)), 0), COALESCE(MAX(rowid), 0) "
                             "FROM chunks WHERE embedding IS NOT NULL").fetchone()) + (dims, str(conn))
    if _VEC_CACHE["key"] != key:
        ids, rows = [], []
        for r in conn.execute("SELECT chunk_id, embedding FROM chunks WHERE embedding IS NOT NULL"):
            vec = _embedder.unpack(r["embedding"])
            if vec is not None and len(vec) == dims:          # skip vectors from a different model
                ids.append(r["chunk_id"])
                rows.append(vec)
        _VEC_CACHE.update(key=key, ids=ids, matrix=np.vstack(rows) if rows else None)
    return _VEC_CACHE["ids"], _VEC_CACHE["matrix"]


# ---------------------------------------------------------------------------
# Reciprocal Rank Fusion (§5.2)
# ---------------------------------------------------------------------------
def _rrf(ranked_lists: list[list[tuple[str, float]]], k: int | None = None) -> dict[str, float]:
    """Merge multiple ranked lists with RRF. Returns {chunk_id: rrf_score}."""
    if k is None:
        k = int(cfg("rag", "rrf_k", default=60))
    scores: dict[str, float] = {}
    for ranked in ranked_lists:
        for rank, (chunk_id, _) in enumerate(ranked, start=1):
            scores[chunk_id] = scores.get(chunk_id, 0.0) + 1.0 / (k + rank)
    return scores


# ---------------------------------------------------------------------------
# Freshness decay (§8)
# ---------------------------------------------------------------------------
def _freshness_decay(last_reviewed: str, decay_days: int | None = None, doc_type: str = "") -> float:
    """Exponential decay from 1.0 (just reviewed), never below 0.5. The review cycle can be set per doc_type."""
    if decay_days is None:
        decay_days = (cfg("rag", "review_cycles", doc_type, default=None) if doc_type else None) \
            or cfg("rag", "freshness_decay_days", default=180)
    if not last_reviewed:
        return 0.8  # unknown freshness
    try:
        reviewed = datetime.fromisoformat(last_reviewed)
        if reviewed.tzinfo is None:
            reviewed = reviewed.replace(tzinfo=timezone.utc)
        days_old = max(0, (datetime.now(timezone.utc) - reviewed).days)
        return max(0.5, math.exp(-days_old / max(1, int(decay_days))))
    except Exception:
        return 0.8


def _doc_type_boost(doc_type: str) -> float:
    configured = cfg("rag", "doc_type_trust", default=None) or {}
    return float(configured.get(doc_type, _DEFAULT_DOC_TYPE_PRIORITY.get(doc_type, 0.7)))


# ---------------------------------------------------------------------------
# Section expansion (§5.4): a long section is stored as several chunks; give the model all of it
# ---------------------------------------------------------------------------
def _expand_to_parent(chunk: Chunk) -> tuple[str, str]:
    """Return (full_section_text, section_path) when the chunk is one part of a split section, else ("", "")."""
    parts = get_section_chunks(chunk.doc_id, chunk.section_path)
    if len(parts) > 1:
        return "\n\n".join(p.text_original for p in parts), chunk.section_path
    return "", ""


# ---------------------------------------------------------------------------
# Context compression – extractive snippet (§5.4)
# ---------------------------------------------------------------------------
def _make_snippet(text: str, query: str, max_chars: int = 400) -> str:
    """Pick the sentences/lines that best overlap the query, kept in their original order."""
    if len(text) <= max_chars:
        return text
    words = set(_content_words(query))
    units = [u.strip() for u in re.split(r"(?<=[.!?])\s+|\n+", text) if u.strip()]
    scored = [(len(set(re.findall(r"[a-z0-9_]+", u.lower())) & words), i, u) for i, u in enumerate(units)]
    picked: list[tuple[int, str]] = []
    total = 0
    for _, i, u in sorted(scored, key=lambda x: (-x[0], x[1])):
        if total + len(u) > max_chars:
            continue
        picked.append((i, u))
        total += len(u) + 1
    if not picked:
        return text[:max_chars]
    return " ... ".join(u for _, u in sorted(picked))


# ---------------------------------------------------------------------------
# Relevance + sufficiency (§5.5 – CRAG-style)
# ---------------------------------------------------------------------------
def _stem(word: str) -> str:
    for suf in ("ing", "ed", "es", "s"):
        if len(word) > len(suf) + 3 and word.endswith(suf):
            return word[: -len(suf)]
    return word


def _stems(text: str) -> set[str]:
    return {_stem(w) for w in re.findall(r"[a-z0-9_]+", _normalise(text))}


def _normalise(text: str) -> str:
    t = (text or "").lower()
    for a, b in (("wi-fi", "wifi"), ("e-mail", "email"), ("log in", "login"), ("sign in", "signin")):
        t = t.replace(a, b)
    return t


def _relevance(query: str, row: dict, exact: bool = False, dense: float | None = None) -> float:
    """
    0..1 estimate of how well a chunk answers the query.
    = share of the query's content words found in the chunk (words in the title/heading count 1.5x),
    1.0 for an exact error-code hit, or the scaled cosine similarity when dense search is active.
    RRF scores cannot serve here: they only rank, and their scale (~0.03) says nothing about whether
    the text really answers the question.
    """
    if exact:
        return 1.0
    q_terms = {_stem(w) for w in _content_words(_normalise(query))}
    if not q_terms:
        return 0.0
    heading = _stems(f"{row.get('title', '')} {row.get('section_path', '')}")
    body = _stems(f"{row.get('text_original', '')} {row.get('symptom_keywords', '')}")
    matched = sum(1.5 if t in heading else 1.0 for t in q_terms if t in heading or t in body)
    coverage = min(1.0, matched / len(q_terms))
    if dense is not None and dense > 0.3:
        coverage = max(coverage, min(1.0, dense / 0.6))
    return coverage


def _heading_fraction(query: str, row: dict) -> float:
    """Share (0..1) of the question's content words that appear in the section's own title/heading.
    Used for ranking only: a section named after the problem beats one that merely mentions it."""
    q_terms = {_stem(w) for w in _content_words(_normalise(query))}
    if not q_terms:
        return 0.0
    heading = _stems(f"{row.get('title', '')} {row.get('section_path', '')}")
    return sum(1 for t in q_terms if t in heading) / len(q_terms)


def _sufficiency(results: list, top_score: float) -> str:
    """Classify retrieval quality from the best relevance (0..1): 'sufficient' | 'partial' | 'irrelevant'."""
    if not results:
        return "irrelevant"
    if top_score >= 0.6:
        return "sufficient"
    if top_score >= float(cfg("rag", "sufficiency_threshold", default=0.25)):
        return "partial"
    return "irrelevant"


# ---------------------------------------------------------------------------
# Query variants for multi-query retrieval (§5.1)
# ---------------------------------------------------------------------------
def _expand_query(query: str) -> list[str]:
    """Generate simple query variants (synonym/phrasing) without a model call."""
    variants = [query]
    codes = _extract_error_codes(query)
    if codes:
        variants.append(" ".join(codes))
    lower = query.lower()
    if re.search(r"wi-?fi", lower):
        variants.append(re.sub(r"(?i)wi-?fi", "wi fi", query))
    if any(w in lower for w in ("not working", "broken", "fail", "error", "can't", "cannot", "doesn't")):
        variants.append(f"how to fix: {query}")
    compact = " ".join(_content_words(query))
    if compact and compact != lower:
        variants.append(compact)
    return list(dict.fromkeys(variants))[:4]  # max 4 variants (§5.1)


# ---------------------------------------------------------------------------
# Citation
# ---------------------------------------------------------------------------
def make_citation(row: dict) -> str:
    """`[network_and_vpn.md § VPN keeps disconnecting]` – the format the agent is told to quote."""
    url = row.get("url", "") or ""
    section = row.get("section_path", "") or ""
    heading = section.split(" > ")[-1]
    if url.startswith("kb/"):
        name = url[3:].split("#")[0]
    elif url.startswith("ticket:"):
        return f"[ticket {url[7:]}]"
    elif url.startswith("https://learn.microsoft.com/"):
        title = row.get("title") or heading
        return f"[Microsoft Learn: {title} – {url.split('#')[0]}]"     # imported article: cite the real page
    elif row.get("doc_type") == "error_code":
        name = "error_code"
    else:
        name = row.get("doc_id", "") or "kb"
    return f"[{name} § {heading}]" if heading else f"[{name}]"


# ---------------------------------------------------------------------------
# Main hybrid search function
# ---------------------------------------------------------------------------
def hybrid_search(
    query: str,
    filters: RetrievalFilters | None = None,
    top_k: int | None = None,
    task_id: str = "",
    record: bool = True,
) -> list[RetrievalResult]:
    """
    Full hybrid retrieval pipeline (§5):
      dense kNN + BM25 + exact error-code -> RRF -> boost -> section-expand -> dedupe -> top_k
    `record=False` skips usage counters and the audit row (used for intermediate fallback attempts).
    """
    if filters is None:
        filters = RetrievalFilters()
    if top_k is None:
        top_k = int(cfg("rag", "top_k_final", default=6))
    candidates = int(cfg("rag", "top_k_candidates", default=50))

    variants = _expand_query(query)
    query_vec = _embed(query)

    codes = _extract_error_codes(query)
    exact_hits = _exact_error_code_search(codes, filters, top_k=10)
    exact_ids = {cid for cid, _ in exact_hits}

    ranked_lists: list[list[tuple[str, float]]] = []
    if exact_hits:
        ranked_lists.append(exact_hits)
    for variant in variants:
        hits = _fts_search(variant, filters, top_k=candidates)
        if hits:
            ranked_lists.append(hits)

    dense_hits = _dense_search(query_vec, filters, top_k=candidates)
    dense_scores = dict(dense_hits)
    if dense_hits:
        ranked_lists.append(dense_hits)

    rrf_scores = _rrf(ranked_lists)
    if not rrf_scores:
        if record:
            _record(task_id, query, filters, [])
        return []

    # Load every candidate row in one go
    conn = get_conn()
    ids = list(rrf_scores)
    rows: dict[str, dict] = {}
    for i in range(0, len(ids), 500):
        batch = ids[i:i + 500]
        for r in conn.execute(f"SELECT * FROM chunks WHERE chunk_id IN ({','.join('?' * len(batch))})", batch):
            rows[r["chunk_id"]] = dict(r)

    scored: list[tuple[float, str, dict]] = []
    for chunk_id, rrf_score in rrf_scores.items():
        row = rows.get(chunk_id)
        if row is None:
            continue
        success = row.get("success_rate")
        boost = (
            float(row.get("trust_score") or 1.0)
            * _freshness_decay(row.get("last_reviewed", ""), doc_type=row.get("doc_type", ""))
            * _doc_type_boost(row.get("doc_type", "kb"))
            * max(0.3, float(success if success is not None else 1.0))
        )
        # A section whose heading covers the question's words is a better answer than one that merely mentions them
        scored.append((rrf_score * boost * (0.7 + 0.8 * _heading_fraction(query, row)), chunk_id, row))
    scored.sort(key=lambda x: x[0], reverse=True)

    # De-duplicate: one result per document section (a split section can match through several parts)
    results: list[RetrievalResult] = []
    seen_sections: set[str] = set()
    for final_score, chunk_id, row in scored:
        key = f"{row['doc_id']}::{row['section_path']}"
        if key in seen_sections:
            continue
        seen_sections.add(key)

        parent_text, parent_section = _expand_to_parent(
            Chunk(chunk_id=chunk_id, doc_id=row["doc_id"], section_path=row["section_path"]))
        success = row.get("success_rate")
        results.append(RetrievalResult(
            chunk_id=chunk_id,
            doc_id=row["doc_id"],
            title=row.get("title", ""),
            section_path=row.get("section_path", ""),
            url=row.get("url", ""),
            text=row.get("text_original", ""),
            score=final_score,
            rrf_score=rrf_scores[chunk_id],
            relevance=_relevance(query, row, exact=chunk_id in exact_ids, dense=dense_scores.get(chunk_id)),
            trust_score=float(row.get("trust_score") or 1.0),
            success_rate=float(success if success is not None else 1.0),
            doc_type=row.get("doc_type", "kb"),
            os=row.get("os", "any"),
            risk_tier=row.get("risk_tier", "R0"),
            last_reviewed=row.get("last_reviewed", ""),
            version=row.get("version", "1"),
            snippet=_make_snippet(row.get("text_original", ""), query),
            citation=make_citation(row),
            source_system=row.get("source_system", "kb"),
            parent_text=parent_text,
            parent_section=parent_section,
        ))
        if len(results) >= top_k:
            break

    if record:
        _record(task_id, query, filters, results)
    return results


def _record(task_id: str, query: str, filters: RetrievalFilters, results: list[RetrievalResult]) -> None:
    """Usage counters + audit row for what was actually shown (§7)."""
    ids = [r.chunk_id for r in results]
    try:
        increment_usage_many(ids)
        log_rag_audit(
            task_id=task_id, query=query,
            filters={"doc_types": filters.doc_types, "os": filters.os, "audience": filters.audience,
                     "status": filters.status},
            result_ids=ids, scores=[round(r.score, 5) for r in results], shown_ids=ids,
        )
    except Exception:
        pass  # observability must never break an answer


def _best_relevance(results: list[RetrievalResult]) -> float:
    return max((r.relevance for r in results[:3]), default=0.0)


# ---------------------------------------------------------------------------
# Sufficiency-aware retrieval with auto-fallback (§5.5)
# ---------------------------------------------------------------------------
def retrieve_with_fallback(
    query: str,
    filters: RetrievalFilters | None = None,
    top_k: int | None = None,
    task_id: str = "",
    max_retries: int | None = None,
    broaden_doc_types: bool = False,
    log_gaps: bool = True,
) -> dict:
    """
    Retrieve with a CRAG-style sufficiency check and fallback.

    If the first pass is only partial/irrelevant and the caller narrowed the search (OS, and with
    `broaden_doc_types` also the doc type), retry with the narrowing removed and keep the best attempt.
    ACL / audience / status filters are never relaxed.
    Returns {"results", "sufficiency", "gap_logged", "relevance"}.
    """
    filters = filters or RetrievalFilters()
    if max_retries is None:
        max_retries = int(cfg("rag", "max_fallback_retries", default=2))

    attempts = [filters]
    if filters.os:
        f = copy.copy(filters)
        f.os = ""
        attempts.append(f)
    if broaden_doc_types and filters.doc_types:
        f = copy.copy(attempts[-1])
        f.doc_types = []
        attempts.append(f)
    attempts = attempts[: 1 + max(0, max_retries)]

    best: list[RetrievalResult] = []
    best_rel = -1.0
    best_filters = filters
    for f in attempts:
        res = hybrid_search(query, f, top_k, task_id, record=False)
        rel = _best_relevance(res)
        if rel > best_rel:
            best, best_rel, best_filters = res, rel, f
        if _sufficiency(res, rel) == "sufficient":
            break

    status = _sufficiency(best, max(best_rel, 0.0))
    _record(task_id, query, best_filters, best)

    gap_logged = False
    if status == "irrelevant" and log_gaps:
        log_gap(query, context=f"task_id={task_id}" if task_id else "auto: retrieval found nothing relevant",
                task_id=task_id)
        gap_logged = True

    return {"results": best, "sufficiency": status, "gap_logged": gap_logged, "relevance": max(best_rel, 0.0)}


def resolve_answerable_gaps() -> int:
    """Learning loop: close open knowledge gaps that the index can now answer. Returns how many were closed."""
    conn = get_conn()
    closed = 0
    for row in conn.execute("SELECT id, query FROM knowledge_gaps WHERE resolved = 0").fetchall():
        res = hybrid_search(row["query"], RetrievalFilters(), top_k=3, record=False)
        if _sufficiency(res, _best_relevance(res)) != "irrelevant":
            with conn:
                conn.execute("UPDATE knowledge_gaps SET resolved = 1 WHERE id = ?", (row["id"],))
            closed += 1
    return closed


# ---------------------------------------------------------------------------
# Format results as context for the LLM (§5.4)
# ---------------------------------------------------------------------------
def format_context(results: list[RetrievalResult], max_tokens: int | None = None) -> str:
    """
    Format top results as a structured context block for prompt injection.
    Each block is labelled with its citation and sanitised (retrieved text is untrusted data).
    """
    if not results:
        return "(No relevant knowledge base articles found.)"
    if max_tokens is None:
        max_tokens = int(cfg("rag", "max_context_tokens", default=2000))

    parts: list[str] = []
    total_chars = 0
    char_budget = max_tokens * 4  # rough chars-per-token estimate

    for r in results:
        body = sanitize_text(r.parent_text or r.text or r.snippet)
        freshness_note = f" | Reviewed: {r.last_reviewed[:10]}" if r.last_reviewed else ""
        block = f"--- {r.citation} | {r.doc_type.upper()}{freshness_note} ---\n{body}\n"
        if total_chars + len(block) > char_budget:
            block = f"--- {r.citation} ---\n{sanitize_text(r.snippet)}\n"
        if total_chars + len(block) > char_budget:
            break
        parts.append(block)
        total_chars += len(block)

    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Fitting output into the model's tool-output budget
# ---------------------------------------------------------------------------
def _tool_budget() -> int:
    """`limits.max_tool_output_chars` less headroom: ToolRunner cuts anything longer mid-JSON."""
    return int(cfg("limits", "max_tool_output_chars", default=1500)) - 120


def pack_for_model(results: list[RetrievalResult], query: str = "", max_text_chars: int | None = None,
                   max_items: int = 3) -> list[dict]:
    """
    Compact [{"source", "text", "chunk_id"}] for the model: the best result gets about half the budget,
    the rest share what is left, and long texts are cut down to the sentences that overlap the query.
    """
    budget = max_text_chars if max_text_chars is not None else _tool_budget() - 450
    picked = results[:max_items]
    out: list[dict] = []
    remaining = budget
    for i, r in enumerate(picked):
        left = len(picked) - i
        share = remaining if left == 1 else max(remaining // left, int(remaining * 0.5) if i == 0 else 0)
        share = max(120, min(share, remaining))
        body = sanitize_text(r.parent_text or r.text)
        if len(body) > share:
            body = _make_snippet(body, query, share)[:share]
        remaining -= len(body)
        out.append({"source": r.citation, "text": body, "chunk_id": r.chunk_id})
        if remaining <= 0:
            break
    return out


def fit_output(payload: dict, limit: int | None = None) -> dict:
    """
    Guarantee that a tool's JSON stays under the output limit, shrinking the longest text first
    (then dropping trailing list items), so the model never receives mid-JSON truncation.
    """
    limit = limit or _tool_budget()

    def size() -> int:
        return len(json.dumps(payload, default=str))

    def walk(node):
        if isinstance(node, dict):
            for k in list(node):
                yield node, k
                yield from walk(node[k])
        elif isinstance(node, list):
            for i in range(len(node)):
                yield node, i
                yield from walk(node[i])

    for _ in range(200):
        if size() <= limit:
            return payload
        longest = max(((c, k) for c, k in walk(payload) if isinstance(c[k], str) and len(c[k]) > 60),
                      key=lambda ck: len(ck[0][ck[1]]), default=None)
        if longest is not None:
            c, k = longest
            c[k] = c[k][: int(len(c[k]) * 0.75)].rstrip() + "..."
            continue
        lists = [c[k] for c, k in walk(payload) if isinstance(c[k], list) and len(c[k]) > 1]
        if not lists:
            break
        max(lists, key=len).pop()
    return payload
