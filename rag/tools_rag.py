"""
Agent-facing RAG tools (§6 of the RAG spec).

These tools integrate into the existing tool registry exactly like every
other Tobi tool: @tool decorator, domain "howto", risk R0.

Tool surface:
  search_knowledge_base_rag  – hybrid search, replaces the old keyword search
  get_kb_document            – return a full document or section by doc_id
  match_runbook              – ranked runbooks for a symptom set
  lookup_error_code          – exact + fuzzy error-code lookup
  lookup_policy              – policy text with effective date
  find_similar_tickets       – past resolved tickets for a symptom
  report_kb_gap              – log a knowledge gap
  submit_kb_feedback         – thumbs-up / thumbs-down on a retrieval
  draft_kb_article           – draft a KB article from a resolved ticket

All tools are read-only (R0). They return structured data + citations;
the calling agent must NEVER take action solely based on retrieved text
without the existing policy gate.

Prompt-injection safety (§6): all retrieved text is data, treated as
untrusted. The agent uses it to inform an answer, not as a command.
Instructions hidden in KB text are stripped by _sanitize().
"""
from __future__ import annotations

import re
from typing import Any

from appconfig import ROOT
from tools.registry import R0, Param, tool
from rag.index import (
    get_chunk, get_conn, log_gap, log_feedback, save_draft_article, stats as rag_stats
)
from rag.ingest import _mask_pii
from rag.retrieval import (
    RetrievalFilters, fit_output, pack_for_model, retrieve_with_fallback, sanitize_text
)

# Prompt-injection sanitisation (§6 / §7) lives in rag.retrieval so format_context and
# tools/knowledge.py use the very same filter. Kept under its old name here.
_sanitize = sanitize_text


def _no_answer(response: dict) -> bool:
    """True when retrieval found nothing worth showing (so tools must not present weak matches as answers)."""
    return not response["results"] or response["sufficiency"] == "irrelevant"


# ---------------------------------------------------------------------------
# Tool: kb.search  (the upgraded replacement for search_knowledge_base)
# ---------------------------------------------------------------------------
@tool(
    "howto", R0,
    "Search the IT knowledge base, runbooks, policies and KB articles using hybrid "
    "semantic + keyword search. Returns the most relevant passages with citations. "
    "Use for how-to questions, company policy, troubleshooting steps, error codes.",
    params=(
        Param("query", "str", "What the user wants to know (up to 300 characters)", max_len=300),
        Param("os_filter", "str", "Limit results to this OS: windows, macos, linux, any",
              choices=("windows", "macos", "linux", "any"), required=False),
        Param("doc_type_filter", "str",
              "Limit to a doc type: kb, runbook, policy, ticket, error_code, faq, any",
              choices=("kb", "runbook", "policy", "ticket", "error_code", "faq", "any"),
              required=False),
    )
)
def search_knowledge_base_rag(query: str, os_filter: str = "any",
                               doc_type_filter: str = "any") -> dict:
    """Hybrid RAG search replacing the original keyword-only search."""
    filters = RetrievalFilters(
        os=os_filter if os_filter != "any" else "",
        doc_types=[doc_type_filter] if doc_type_filter not in ("any", "") else [],
    )
    response = retrieve_with_fallback(query, filters, top_k=5, broaden_doc_types=True)
    results = response["results"]
    sufficiency = response["sufficiency"]

    if _no_answer(response):
        note = ("Nothing in the knowledge base matches this query. "
                "Say so clearly; do not guess or invent procedures.")
        return {"ok": True, "results": [], "sufficiency": "irrelevant",
                "note": note, "gap_logged": response["gap_logged"]}

    note = ""
    if sufficiency == "partial":
        note = ("Partial match only. Answer from what is found, "
                "and note uncertainty where information is incomplete.")

    return fit_output({
        "ok": True,
        "results": pack_for_model(results, query),
        "sufficiency": sufficiency,
        "note": note,
    })


# ---------------------------------------------------------------------------
# Tool: kb.get_document
# ---------------------------------------------------------------------------
@tool(
    "howto", R0,
    "Return the full text of a specific KB document or section by its doc_id "
    "(e.g. 'network_and_vpn') and optional section name.",
    params=(
        Param("doc_id", "str", "Document ID, e.g. network_and_vpn", max_len=100),
        Param("section", "str", "Optional section heading to narrow down", required=False, max_len=200),
    )
)
def get_kb_document(doc_id: str, section: str = "") -> dict:
    conn = get_conn()
    # Same lifecycle/ACL pre-filter as search: deprecated, draft, expired or restricted chunks stay hidden
    where, params = RetrievalFilters().to_sql_clauses()
    sql = f"SELECT * FROM chunks WHERE doc_id = ? AND {where}"
    args: list = [doc_id] + params
    if section:
        sql += " AND section_path LIKE ? ESCAPE '\\'"
        args.append("%" + section.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%")
    rows = conn.execute(sql + " ORDER BY rowid, chunk_index", args).fetchall()

    if not rows:
        return {"ok": False, "error": f"No document found for doc_id='{doc_id}'"}

    full_text = "\n\n".join(_sanitize(r["text_original"]) for r in rows)
    first = dict(rows[0])
    return fit_output({
        "ok": True,
        "doc_id": doc_id,
        "title": first.get("title", ""),
        "text": full_text[:900],
        "sections": [r["section_path"] for r in rows][:8],
        "last_reviewed": first.get("last_reviewed", ""),
        "version": first.get("version", "1"),
        "url": first.get("url", ""),
    })


# ---------------------------------------------------------------------------
# Tool: runbook.match
# ---------------------------------------------------------------------------
@tool(
    "howto", R0,
    "Find the best matching runbook or how-to procedure for a set of symptoms. "
    "Returns ranked runbooks with prerequisites and risk tier.",
    params=(
        Param("symptoms", "str", "Comma-separated symptom keywords or a short description", max_len=300),
        Param("os_filter", "str", "Target OS: windows, macos, linux, any",
              choices=("windows", "macos", "linux", "any"), required=False),
    )
)
def match_runbook(symptoms: str, os_filter: str = "any") -> dict:
    filters = RetrievalFilters(
        doc_types=["runbook", "kb"],
        os=os_filter if os_filter != "any" else "",
    )
    response = retrieve_with_fallback(symptoms, filters, top_k=4)
    results = response["results"]
    if _no_answer(response):
        return {"ok": True, "runbooks": [], "sufficiency": "irrelevant", "note": "No matching runbooks found."}

    runbooks = []
    for r in results:
        runbooks.append({
            "title": r.title,
            "section": r.section_path,
            "url": r.url,
            "snippet": _sanitize(r.snippet)[:400],
            "doc_type": r.doc_type,
            "os": r.os,
            "risk_tier": r.risk_tier,
            "trust": round(r.trust_score, 2),
            "citation": r.citation,
        })
    return fit_output({"ok": True, "runbooks": runbooks, "sufficiency": response["sufficiency"]})


# ---------------------------------------------------------------------------
# Tool: kb.error_lookup
# ---------------------------------------------------------------------------
@tool(
    "howto", R0,
    "Look up an error code or error message in the knowledge base. "
    "Returns the error meaning, known causes and recommended fixes with citations.",
    params=(
        Param("code_or_message", "str", "The error code (e.g. 0x80070005) or error message text", max_len=200),
        Param("app", "str", "Optional application name to narrow results", required=False, max_len=100),
        Param("os_filter", "str", "OS filter: windows, macos, linux, any",
              choices=("windows", "macos", "linux", "any"), required=False),
    )
)
def lookup_error_code(code_or_message: str, app: str = "", os_filter: str = "any") -> dict:
    # First try exact error-code collection, then fall back to general search
    filters = RetrievalFilters(
        doc_types=["error_code", "kb", "runbook"],
        os=os_filter if os_filter != "any" else "",
    )
    query = code_or_message
    if app:
        query = f"{app} {code_or_message}"

    response = retrieve_with_fallback(query, filters, top_k=4)
    results = response["results"]

    if _no_answer(response):
        return {
            "ok": True,
            "error_info": None,
            "note": f"No information found for '{code_or_message}'. Try a live diagnostic or escalate.",
        }

    top = results[0]
    return fit_output({
        "ok": True,
        "error_code": code_or_message,
        "app": app,
        "text": _sanitize(top.text)[:600],
        "citation": top.citation,
        "additional_sources": [_sanitize(r.snippet)[:200] + f" {r.citation}" for r in results[1:]],
        "sufficiency": response["sufficiency"],
    })


# ---------------------------------------------------------------------------
# Tool: kb.policy_lookup
# ---------------------------------------------------------------------------
@tool(
    "howto", R0,
    "Look up a company IT policy by topic. Returns the policy text, "
    "effective date and owner.",
    params=(
        Param("topic", "str", "Policy topic, e.g. 'password policy', 'BYOD', 'acceptable use'", max_len=200),
        Param("role_filter", "str", "Audience: end_user, L1, L2, admin, any",
              choices=("end_user", "L1", "L2", "admin", "any"), required=False),
    )
)
def lookup_policy(topic: str, role_filter: str = "any") -> dict:
    filters = RetrievalFilters(doc_types=["policy", "kb"])
    response = retrieve_with_fallback(topic, filters, top_k=3)
    results = response["results"]
    if _no_answer(response):
        return {"ok": True, "policy": None,
                "note": "No policy article found. Raise a ticket or consult the intranet."}

    top = results[0]
    return fit_output({
        "ok": True,
        "topic": topic,
        "policy_text": _sanitize(top.text)[:800],
        "effective_date": top.last_reviewed[:10] if top.last_reviewed else "unknown",
        "version": top.version,
        "citation": top.citation,
        "url": top.url,
        "sufficiency": response["sufficiency"],
    })


# ---------------------------------------------------------------------------
# Tool: sop.lookup  (the organisation's SOPs, only those that apply to this user's ODC and groups)
# ---------------------------------------------------------------------------
def _compact_tables(text: str) -> str:
    """Markdown tables -> one line per row ("Printer: X; Colour: Black and white"): the same facts in far fewer
    characters, so a rule after a table is not cut off by the output limit."""
    lines, header, out = text.splitlines(), None, []
    for line in lines:
        cells = [c.strip() for c in line.strip().strip("|").split("|")] if line.strip().startswith("|") else None
        if cells is None:
            header = None
            out.append(line)
        elif all(set(c) <= set("-: ") for c in cells):
            continue                                            # the | --- | line
        elif header is None:
            header = cells
        else:
            out.append("- " + "; ".join(f"{h}: {v}" for h, v in zip(header, cells) if v))
    return re.sub(r"\n{3,}", "\n\n", "\n".join(out)).strip()


@tool(
    "howto", R0,
    "Look up the organisation's SOP (standard operating procedure) and rules for a topic, for example printing, "
    "USB drives, software requests or temp files. Returns only the SOPs that apply to this user's ODC and groups, "
    "with the SOP id, version and section to cite.",
    params=(Param("topic", "str", "what the SOP should cover, in the user's words", max_len=300),),
)
def lookup_sop(topic: str) -> dict:
    from tools.org_context import detect_odc, user_groups
    odc = detect_odc()
    groups = user_groups()
    # the organisation's SOPs first; general company policy articles only when no SOP answers it
    wide = 4 if odc["odc"] else 10                      # ODC unknown: look wider so every ODC's SOP can be shown
    response = retrieve_with_fallback(topic, RetrievalFilters(doc_types=["sop"], odc=odc["odc"], acl_groups=groups),
                                      top_k=wide, log_gaps=False)
    if response["sufficiency"] != "sufficient":
        # no strong SOP match: search SOPs and company policy articles together and keep the better answer
        both = retrieve_with_fallback(topic, RetrievalFilters(doc_types=["sop", "policy"], odc=odc["odc"],
                                                              acl_groups=groups), top_k=wide)
        if both["relevance"] > response["relevance"] or _no_answer(response):
            response = both
    your_odc = odc["odc"] or "unknown"
    if _no_answer(response):
        return {"ok": True, "your_odc": your_odc, "results": [], "sufficiency": response["sufficiency"],
                "note": "No SOP covers this for your ODC. Do not guess a company rule: offer a ticket."}
    results = []
    rows = [r for r in response["results"] if r.doc_type in ("sop", "policy")]
    if not odc["odc"]:
        # ODC unknown: take the best section of EACH ODC first, so every ODC's rule fits in the answer
        firsts, seen = [], set()
        for r in rows:
            if r.region not in seen:
                seen.add(r.region)
                firsts.append(r)
        rows = firsts + [r for r in rows if r not in firsts]
    budget = 420 if odc["odc"] else 330                 # 3 full sections fit in the tool output limit
    for r in rows[:3]:
        scope = r.region.strip("|").replace("|", ", ") or "all ODCs"
        text = _compact_tables(_sanitize(r.parent_text or r.text))
        if len(text) > budget:
            text = text[:budget].rsplit(" ", 1)[0] + " ..."
        results.append({"source": r.citation, "applies_to": scope, "effective_date": r.effective_date or "",
                        "text": text})
    out = {"ok": True, "your_odc": your_odc, "odc_detected_by": odc["how"],
           "sufficiency": response["sufficiency"], "results": results}
    if not odc["odc"]:
        out["note"] = ("The user's ODC could not be detected. Say so, give each ODC's rule separately (applies_to), "
                       "and ask which ODC they are in.")
    return fit_output(out)


# ---------------------------------------------------------------------------
# Tool: tickets.find_similar
# ---------------------------------------------------------------------------
@tool(
    "howto", R0,
    "Search for previously resolved tickets that match the current symptoms. "
    "Returns past resolutions that may help diagnose or fix the current issue.",
    params=(
        Param("symptoms", "str", "Short description of the current symptoms", max_len=300),
    )
)
def find_similar_tickets(symptoms: str) -> dict:
    filters = RetrievalFilters(doc_types=["ticket"])
    response = retrieve_with_fallback(symptoms, filters, top_k=4, log_gaps=False)
    results = response["results"]
    if _no_answer(response):
        return {"ok": True, "similar_tickets": [],
                "note": "No similar resolved tickets found."}

    tickets = [{
        "ticket_ref": r.section_path,
        "title": r.title,
        "resolution_summary": _sanitize(r.snippet)[:400],
        "citation": r.citation,
        "trust": round(r.trust_score, 2),
    } for r in results]

    return fit_output({"ok": True, "similar_tickets": tickets, "sufficiency": response["sufficiency"]})


# ---------------------------------------------------------------------------
# Tool: kb.report_gap
# ---------------------------------------------------------------------------
@tool(
    "howto", R0,
    "Report that the knowledge base has no useful information for a query. "
    "Logs the gap so the IT team can create a KB article.",
    params=(
        Param("query", "str", "The query that could not be answered from the knowledge base", max_len=300),
        Param("context", "str", "Brief context about what the user was trying to do", required=False, max_len=300),
    )
)
def report_kb_gap(query: str, context: str = "") -> dict:
    query, _ = _mask_pii(query)
    context, _ = _mask_pii(context)
    log_gap(query, context)
    return {
        "ok": True,
        "logged": True,
        "message": "Knowledge gap has been recorded. The IT team will be notified to create an article.",
    }


# ---------------------------------------------------------------------------
# Tool: kb.feedback
# ---------------------------------------------------------------------------
@tool(
    "howto", R0,
    "Submit feedback on the usefulness of a knowledge base answer. "
    "Positive feedback boosts the article; negative feedback flags it for review.",
    params=(
        Param("chunk_id", "str", "The chunk_id from the search result that was used", max_len=50),
        Param("helpful", "str", "Was the answer helpful? yes or no",
              choices=("yes", "no")),
        Param("correction", "str", "Optional correction or note if the answer was wrong",
              required=False, max_len=500),
    )
)
def submit_kb_feedback(chunk_id: str, helpful: str, correction: str = "") -> dict:
    if get_chunk(chunk_id) is None:
        return {"ok": False, "error": f"Unknown chunk_id '{chunk_id}'. Use the chunk_id from a search result."}
    is_helpful = helpful.lower() == "yes"
    correction, _ = _mask_pii(correction)
    log_feedback(chunk_id, is_helpful, correction=correction)
    return {
        "ok": True,
        "recorded": True,
        "message": "Thank you – your feedback helps improve the knowledge base.",
    }


# ---------------------------------------------------------------------------
# Tool: kb.draft_article  (§11 learning loop)
# ---------------------------------------------------------------------------
@tool(
    "howto", R0,
    "Draft a knowledge base article from a resolved ticket. "
    "The draft goes to the IT team for review before being published.",
    params=(
        Param("ticket_ref", "str", "The ticket reference (e.g. ITB-0012)", max_len=20),
        Param("symptom", "str", "One-sentence description of the problem", max_len=300),
        Param("resolution", "str", "The resolution that worked, in step form", max_len=1000),
    )
)
def draft_kb_article(ticket_ref: str, symptom: str, resolution: str) -> dict:
    # Drafts come from tickets: scrub personal data and secrets before they are stored for review
    symptom, _ = _mask_pii(symptom)
    resolution, _ = _mask_pii(resolution)
    ticket_ref, _ = _mask_pii(ticket_ref)
    title = f"How to fix: {symptom[:80]}"
    content = (
        f"# {title}\n\n"
        f"**Source ticket:** {ticket_ref}\n\n"
        f"## Symptom\n{symptom}\n\n"
        f"## Resolution\n{resolution}\n\n"
        f"*Draft — pending review by the IT team before publishing.*"
    )
    article_id = save_draft_article(ticket_ref, title, content)
    return {
        "ok": True,
        "draft_id": article_id,
        "title": title,
        "message": f"Draft KB article #{article_id} saved. It will be reviewed by the IT team "
                   f"before being published to the knowledge base.",
    }


# ---------------------------------------------------------------------------
# Tool: kb.index_stats  (admin / observability)
# ---------------------------------------------------------------------------
@tool(
    "howto", R0,
    "Show current knowledge base index statistics: total chunks, breakdown by type, "
    "open knowledge gaps, and pending draft articles.",
    params=()
)
def kb_index_stats() -> dict:
    s = rag_stats()
    return {"ok": True, **s}
