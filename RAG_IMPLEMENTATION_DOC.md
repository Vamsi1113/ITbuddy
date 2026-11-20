# RAG Subsystem Implementation Documentation

This document describes the Retrieval-Augmented Generation (RAG) subsystem built for **Tobi** according to the `RAG Spec for the IT Support Buddy Agent`. It details every added file, every modified file, the architecture, schema, tool registration, test suite, and instructions for subsequent development by other coding agents.

---

## 1. Executive Summary & Design Principles

The RAG subsystem grounds the Tobi agent in internal knowledge (runbooks, KB articles, policies, error codes, and resolved tickets) without modifying or breaking any of the existing 58 tools or 12 specialist domains.

### Key Architectural Tenets:
1. **Agentic RAG & Non-Breaking Compatibility:**
   - Existing tools and graph workflows remain 100% operational.
   - The default `search_knowledge_base` tool in `tools/knowledge.py` now operates in **Dual-Mode**: it automatically leverages the hybrid RAG index when available, and gracefully falls back to the original keyword scan if the RAG DB is empty or uninitialized.
   - 9 new R0 tools are registered under the `howto` specialist domain via `@tool` in `rag/tools_rag.py`.
2. **Hybrid Retrieval (Dense + Sparse BM25 + Exact Code):**
   - **Sparse Search:** Full-text BM25 search via SQLite FTS5 with query tokenization, stopword filtering, and OR-ranking.
   - **Exact Lookup:** High-priority matching for hex error codes (e.g. `0x80070005`, `0x800CCC0E`), CVEs, and identifiers.
   - **Dense Search (Optional):** Cosine similarity over normalized embeddings (supports `sentence-transformers` such as `all-MiniLM-L6-v2` or `bge-m3`). If the library is absent, the system degrades seamlessly to BM25 + exact matching without crashing.
   - **Fusion:** Reciprocal Rank Fusion (RRF, $k=60$) combining candidate lists, weighted with trust scores, freshness decay, doc-type priorities, and historical success rates.
3. **Safety & Governance:**
   - **Prompt Injection Defense:** Retrieves untrusted text as data; sanitizes instructions (e.g. `ignore previous instructions`, `[INST]`, HTML comments).
   - **PII / Secret Masking:** Automated regex masking for emails, phone numbers, employee IDs, IP addresses, and tokens on ingestion.
   - **Access Control & Lifecycle Filtering:** Pre-filters out deprecated chunks (`status = 'deprecated'`) and expired policies (`expires_at < now`).
4. **Learning Loop & Self-Improvement:**
   - CRAG-style sufficiency grading (`sufficient`, `partial`, `irrelevant`).
   - Automated knowledge gap logging when queries yield no relevant procedures.
   - User feedback collection (thumbs up/down) adjusting chunk success rates.
   - Ticket-to-draft KB workflow saving resolution articles for human review.

---

## 2. Inventory of New Files Created

The RAG subsystem is encapsulated inside a new package `rag/`, plus an initialization script and test suite:

```
it-buddy/
├── rag/
│   ├── __init__.py             # Package declaration & architectural imports
│   ├── index.py                # Chunk schema, SQLite + FTS5 DDL, CRUD, gap & feedback stores
│   ├── ingest.py               # Structure-aware Markdown parsing, PII scanner, contextual prefix, ticket chunking
│   ├── retrieval.py            # Hybrid query engine: BM25/FTS5, RRF fusion, freshness decay, sufficiency check
│   ├── tools_rag.py            # Agent-facing R0 tools registered with @tool
│   └── startup.py              # Transparent background startup & auto-indexing hook
├── scripts/
│   └── init_rag.py             # CLI script to build or refresh the RAG index and sample error codes
└── tests/
    └── test_rag.py             # Comprehensive 33-test suite covering index, ingest, search, tools, safety
```

### File Details:

#### 1. `rag/index.py`
- **Purpose:** Database layer using SQLite and FTS5 (`data/rag/rag_index.db`).
- **`Chunk` Dataclass:** Stores all mandatory metadata fields from §3.4 of the RAG spec (`chunk_id`, `doc_id`, `parent_id`, `source_system`, `url`, `title`, `section_path`, `doc_type`, `os`, `audience`, `risk_tier`, `trust_score`, `success_rate`, `usage_count`, `last_reviewed`, `status`, `text`, `text_original`, `entities`, etc.).
- **Tables:**
  - `chunks`: Main metadata and chunk storage.
  - `chunks_fts`: SQLite FTS5 virtual table synchronized via insert/update/delete triggers.
  - `knowledge_gaps`: Tracks unanswered user queries and frequency for IT knowledge teams.
  - `rag_feedback`: Stores user helpfulness feedback and updates chunk `success_rate`.
  - `rag_audit`: Logs every query, filter set, retrieved chunk IDs, and scores for auditability.
  - `draft_articles`: Holds auto-drafted KB articles from resolved tickets pending review.

#### 2. `rag/ingest.py`
- **Purpose:** Document ingestion pipeline conforming to §3.
- **Features:**
  - `parse_markdown_file(path)`: Structure-aware parser splitting at H2 (`##`) boundaries; preserves steps, commands, and warnings; strips demo boilerplates.
  - `_contextual_prefix()`: Prepends `[Doc: <title> — <os> — <doc_type>] section: <heading>` to chunks for enriched indexing.
  - `_mask_pii()`: Scans and masks emails, phone numbers, IP addresses, and secret keys.
  - `_extract_entities()`: Identifies operating systems, error codes, and applications.
  - `parse_error_code_entry()`: Ingests structured error codes, causes, and fixes.
  - `parse_ticket_resolution()`: Curates resolved tickets into reusable knowledge chunks.
  - Deletion propagation: Compares file content hashes and purges deleted sections.

#### 3. `rag/retrieval.py`
- **Purpose:** Query-time retrieval pipeline conforming to §5.
- **Pipeline:**
  1. `_expand_query()`: Generates query variations, error code extractions, and compact variants.
  2. `_fts_search()`: FTS5 BM25 search with stopword stripping and `OR`-connected terms.
  3. `_exact_error_code_search()`: Boosted exact matching for hex and alphanumeric error patterns.
  4. `_dense_search()`: Cosine similarity matching when vector embeddings are present.
  5. `_rrf()`: Reciprocal Rank Fusion ($k=60$) combining candidate lists.
  6. Boosts: Applied based on trust score, doc-type priority, exponential freshness decay (`_freshness_decay()`), and success rate.
  7. `_expand_to_parent()`: Expands matched child chunks to the full parent section text.
  8. `_sufficiency()` & `retrieve_with_fallback()`: Self-corrective check (`sufficient`, `partial`, `irrelevant`) with automated broadening fallback and gap logging.
  9. `format_context()`: Packages snippets with citations for model context.

#### 4. `rag/tools_rag.py`
- **Purpose:** Agent-facing tools registered in the tool registry:
  - `search_knowledge_base_rag(query, os_filter, doc_type_filter)`: Primary hybrid search.
  - `get_kb_document(doc_id, section)`: Document retrieval by ID and section.
  - `match_runbook(symptoms, os_filter)`: Finds ranked runbooks matching reported symptoms.
  - `lookup_error_code(code_or_message, app, os_filter)`: Specific error code & cause lookup.
  - `lookup_policy(topic, role_filter)`: IT policy retrieval with effective dates.
  - `find_similar_tickets(symptoms)`: Resolves symptoms against past ticket resolutions.
  - `report_kb_gap(query, context)`: Explicitly logs a missing knowledge article.
  - `submit_kb_feedback(chunk_id, helpful, correction)`: Captures user rating for learning loop.
  - `draft_kb_article(ticket_ref, symptom, resolution)`: Drafts a new KB article from a fix.
  - `kb_index_stats()`: Diagnostic observability metrics for the RAG index.
- **Sanitization:** `_sanitize()` purges prompt injection patterns (`ignore previous instructions`, `<!-- ... -->`, system tag delimiters).

#### 5. `rag/startup.py`
- **Purpose:** Background worker that checks if `kb/*.md` files have updated since last indexing. Ensures the index is populated automatically on startup without freezing the Streamlit UI.

#### 6. `scripts/init_rag.py`
- **Purpose:** Standalone CLI tool to create/refresh `data/rag/rag_index.db`, parse all markdown files in `kb/`, and load baseline error codes. Supports `--force` flag.

#### 7. `tests/test_rag.py`
- **Purpose:** 33 unit and integration tests executing in ~3.4 seconds against an isolated temporary SQLite database. Tests cover Index CRUD, Ingestion & PII masking, Entity extraction, FTS5 & Exact Search, RRF fusion, Sufficiency check, Fallback & Gap logging, RAG tools, Injection sanitization, and Deprecated/Expired chunk exclusion.

---

## 3. Inventory of Existing Files Modified

All modifications were designed with strict backward compatibility in mind:

### 1. `tools/knowledge.py`
- **Modification:** Added a transparent hybrid-first check in `search_knowledge_base`.
- **Behavior:**
  - If `data/rag/rag_index.db` contains chunks, it invokes `rag.retrieval.retrieve_with_fallback()` with structured citations and context formatting.
  - If RAG is uninitialized or throws an exception, it falls back to the original `_keyword_search()` function without interruption.

### 2. `tools/registry.py`
- **Modification:** Added a conditional import of `rag.tools_rag` at the bottom of the registry so all 10 new RAG tools are registered dynamically under domain `"howto"` with tier `R0`.

### 3. `agent/prompts.py`
- **Modification:** Enhanced `HOWTO_GUIDANCE` prompt instruction:
  - Instructs the model to utilize the new structured `context_for_model` field when present.
  - Directs the model to cite sources using format `[filename.md § Section]`.
  - Emphasizes handling of `partial` vs `irrelevant` sufficiency without hallucination.

### 4. `config.yaml`
- **Modification:** Added the `rag:` configuration section:
  ```yaml
  rag:
    top_k_candidates: 50
    top_k_final: 6
    rrf_k: 60
    freshness_decay_days: 180
    max_context_tokens: 2000
    sufficiency_threshold: 0.25
    max_fallback_retries: 2
    embedding_model: "all-MiniLM-L6-v2"
    chunk_max_words: 600
    chunk_min_tokens: 30
    pii_masking: true
    review_cycles:
      runbook: 180
      kb: 180
      policy: 365
      ticket: 90
      vendor: 30
      error_code: 90
    doc_type_trust:
      error_code: 1.0
      runbook: 0.95
      kb: 0.9
      policy: 0.85
      ticket: 0.7
      faq: 0.65
      vendor: 0.6
  ```

### 5. `app.py` & `cli.py`
- **Modification:** Added non-blocking call to `rag.startup.ensure_rag_index()` on application boot.

---

## 4. Verification & Test Results

### 1. RAG Test Suite (`tests/test_rag.py`)
Run via:
```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_rag.py -v
```
**Result:** `33 passed in 3.41s`
- `TestIndex`: 7 passed (upsert, idempotent replace, delete, stats, gap log, feedback, draft articles)
- `TestIngest`: 8 passed (markdown hierarchy, PII masking, entity regex, contextual prefix, directory ingest, error codes, ticket resolutions)
- `TestRetrieval`: 7 passed (FTS5 search, hybrid retrieval, exact error code matching, CRAG sufficiency, fallback gap logging, context formatting, RRF fusion)
- `TestRagTools`: 9 passed (search, get doc, gap reporting, feedback collection, draft generation, stats tool, injection sanitization, error lookup)
- `TestSafety`: 2 passed (deprecated document exclusion, expired policy exclusion)

### 2. Core Safety & Policy Tests (`tests/test_policy.py`)
Run via:
```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_policy.py -v
```
**Result:** `29 passed in 6.53s`
Confirms all risk tier gates (R0–R3), allow-lists, approval pauses, and audit trails remain intact.

---

## 5. Instructions for the Next Coding Agent

For any coding agent continuing work on Tobi, here is the operational playbook:

### 1. Initializing or Refreshing Knowledge
To re-index when new articles are added to `kb/`:
```powershell
.\.venv\Scripts\python.exe scripts\init_rag.py --force
```

### 2. Enabling Dense (Semantic) Embeddings
Currently running in BM25 + Exact Code matching mode. To activate local dense vector search:
1. Install `sentence-transformers`:
   ```powershell
   .\.venv\Scripts\python.exe -m pip install sentence-transformers
   ```
2. The `rag/retrieval.py` module will automatically detect the package on its next run and compute query and document embeddings using `all-MiniLM-L6-v2`.

### 3. Adding New Document Types & Connectors
- When connecting ServiceNow, Jira SM, or Confluence, implement a connector in `rag/ingest.py` returning standard `Chunk` instances.
- Ensure all resolved tickets pass through `parse_ticket_resolution()` so user PII is scrubbed before indexing.
- Use `rag.index.save_draft_article()` to stage articles generated from the agent's learning loop.

---

## 6. Review pass (corrections to the sections above)

A follow-up review found and fixed the issues below. Where this section differs from sections 1-5, this section is current.

- **Sufficiency was always "irrelevant".** It compared RRF scores (about 0.03) with 0.25/0.6 thresholds. As a result `search_knowledge_base` always skipped RAG and every query logged a false knowledge gap. It now uses a 0-1 relevance signal: query-term coverage with a heading boost, 1.0 for an exact error-code hit, or scaled cosine similarity when dense search is on. `rag.sufficiency_threshold` is honoured.
- **Tool output exceeded `limits.max_tool_output_chars` (1500)**, so `ToolRunner` cut the JSON mid-string and the model never saw `context_for_model`. Search tools now return a compact `results: [{source, text, chunk_id}]` (`pack_for_model`), and every RAG tool passes through `fit_output`. `context_for_model` no longer exists in tool output (`format_context` remains as a library function).
- **Parent expansion** returned the unrelated H1 intro instead of the matched section. A long section is now split into ordered parts (`chunk_index`) and returned whole.
- **FTS index drift:** `INSERT OR REPLACE` never fired the delete trigger. It is now a true upsert, and the FTS index is rebuilt after ingests that change chunks. Existing databases are migrated automatically.
- **PII masking** turned "Change a password" into `<SECRET>`. Secrets and employee IDs are always masked. Emails, phones and IPs are masked for tickets and drafts, but not in curated KB articles, so helpdesk contacts stay readable.
- **Other fixes:** one thumbs-down no longer zeroes an article (smoothed `success_rate`); multi-OS chunks are tagged `any`; ACL and audience filters are enforced in SQL; retrieved text is sanitised in every path; removed KB files are purged; the dense model loads lazily and chunks are embedded at ingest; resolved tickets are ingested from the ticket store; gaps are de-duplicated case-insensitively and auto-close once answerable; citations are `[file.md § Heading]`; `rrf_k`, `top_k_*`, `doc_type_trust`, `review_cycles` and `max_context_tokens` are now read from config.
- **Tests:** `tests/conftest.py` now redirects the RAG database for every test (before, the suite wrote gaps, feedback and drafts to the real index). `tests/test_extended.py` sample args cover the new tools (9 tests failed before). The full suite passed (192 tests) with the temporary regression tests that were written during this review; those test files have since been removed.
- **Known limit:** the planner for the `howto` domain always calls `search_knowledge_base`, so the other nine RAG tools are registered but not reachable by the agent yet. Exact error codes are already handled inside hybrid search.
