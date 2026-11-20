"""Knowledge base search over the Markdown files in ./kb. Answers carry their source.

Dual-mode operation:
  1. If the RAG index has been initialised (rag/index.py + rag/retrieval.py),
     delegates to the hybrid RAG search for better recall and citations.
  2. If the RAG index is empty or unavailable, falls back to the original
     keyword-scoring scan so the agent keeps working without any extra setup.

Article text is always treated as data, never as an instruction.
"""
from __future__ import annotations

import re
from functools import lru_cache

from appconfig import ROOT
from tools.registry import R0, Param, tool

KB_DIR = ROOT / "kb"
_STOP = set("a an the is are was were be to of and or in on for with my me i you your it this that how do does "
            "can cant not what when where why which get got have has need want please help from at as by "
            "if am its im".split())


def _words(text: str) -> list[str]:
    return [w for w in re.findall(r"[a-z0-9]+", text.lower()) if w not in _STOP and len(w) > 1]


@lru_cache(maxsize=1)
def _sections() -> list[dict]:
    out = []
    for path in sorted(KB_DIR.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        title = text.splitlines()[0].lstrip("# ").strip() if text else path.stem
        for block in re.split(r"\n(?=## )", text):
            lines = block.strip().splitlines()
            if not lines:
                continue
            heading = lines[0].lstrip("# ").strip()
            body = "\n".join(lines[1:]).strip()
            if body:
                out.append({"source": f"{path.name} > {heading}", "title": title, "heading": heading, "body": body,
                            "words": _words(f"{title} {heading} {heading} {body}")})
    return out


def _keyword_search(query: str) -> dict:
    """Original keyword-scoring fallback (always available, no dependencies)."""
    terms = set(_words(query))
    if not terms:
        return {"ok": True, "results": [], "note": "No searchable words in the question."}
    scored = []
    for s in _sections():
        hits = sum(s["words"].count(t) for t in terms)
        covered = sum(1 for t in terms if t in s["words"])
        if covered:
            scored.append((covered * 3 + hits / (1 + len(s["words"]) / 80), s))
    scored.sort(key=lambda x: x[0], reverse=True)
    results = [{"source": s["source"], "text": s["body"][:520]} for _, s in scored[:2]]
    return {"ok": True, "results": results,
            "note": "" if results else "Nothing in the knowledge base matches. Say so; do not guess."}


@tool("howto", R0,
      "Search the company IT knowledge base for how-to steps and policies. Returns text with its source. "
      "Uses hybrid RAG search when the index is available, keyword search otherwise.",
      params=(Param("query", "str", "what the user wants to know", max_len=300),))
def search_knowledge_base(query: str) -> dict:
    """
    Hybrid-first KB search.  Tries the RAG layer; if the index is empty or
    unavailable, falls back seamlessly to the original keyword search.
    """
    # Attempt RAG retrieval
    try:
        from rag.retrieval import retrieve_with_fallback, RetrievalFilters, fit_output, pack_for_model
        from rag.index import stats as rag_stats

        if rag_stats().get("total_chunks", 0) > 0:
            # Gap logging is deferred: the keyword scan below may still find an answer
            response = retrieve_with_fallback(query, RetrievalFilters(), top_k=5, log_gaps=False)
            results = response["results"]
            sufficiency = response["sufficiency"]

            if results and sufficiency != "irrelevant":
                # Compact on purpose: ToolRunner cuts anything over limits.max_tool_output_chars mid-JSON
                return fit_output({
                    "ok": True,
                    "results": pack_for_model(results, query),
                    "sufficiency": sufficiency,
                    "note": "Partial match. Answer from what is found and note uncertainty."
                            if sufficiency == "partial" else "",
                    "search_mode": "rag_hybrid",
                })
    except Exception:
        pass  # RAG layer not ready - fall through to keyword search

    # Fallback: original keyword search
    result = _keyword_search(query)
    result["search_mode"] = "keyword_fallback"
    if not result["results"]:
        result["sufficiency"] = "irrelevant"
        try:   # nothing anywhere: record the gap for the IT team
            from rag.index import log_gap
            log_gap(query, context="auto: search_knowledge_base found nothing")
        except Exception:
            pass
    return result
