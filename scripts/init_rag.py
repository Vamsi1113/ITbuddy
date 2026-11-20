"""
RAG index initialisation script.

Run this once after setup (or whenever KB files change):
  .venv\\Scripts\\python.exe scripts\\init_rag.py

What it does:
  1. Creates the RAG SQLite database with schema (data/rag/rag_index.db)
  2. Ingests all KB markdown files in kb/*.md
  3. Optionally ingests sample error codes
  4. Optionally generates embeddings (requires sentence-transformers)
  5. Reports stats

Re-running is safe (incremental: only changed files are re-indexed).
Add --force to re-index everything from scratch.
"""
import sys
import argparse
from pathlib import Path

# Make sure we can import from the project root
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main():
    parser = argparse.ArgumentParser(description="Initialise or refresh the Tobi RAG index.")
    parser.add_argument("--force", action="store_true", help="Re-index all files from scratch")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    args = parser.parse_args()

    print("=" * 60)
    print("Tobi RAG Index Initialisation")
    print("=" * 60)

    # Step 1: DB schema
    print("\n[1/3] Creating / verifying RAG database schema...")
    from rag.index import get_conn, stats as rag_stats, RAG_DB
    get_conn()  # triggers schema creation
    print(f"      Database: {RAG_DB}")

    # Step 2: Ingest KB files
    print("\n[2/3] Ingesting KB markdown files...")
    from rag.ingest import ingest_kb_files
    ingest_stats = ingest_kb_files(force=args.force)
    print(f"      Files scanned : {ingest_stats['files_scanned']}")
    print(f"      Chunks added  : {ingest_stats['chunks_added']}")
    print(f"      Chunks skipped: {ingest_stats['chunks_skipped']} (unchanged)")

    # Step 3: Sample error codes (optional demo data)
    print("\n[3/3] Ingesting sample error code catalog...")
    from rag.ingest import ingest_error_codes
    from rag.error_catalog import SAMPLE_ERROR_CODES as sample_errors
    n = ingest_error_codes(sample_errors)
    print(f"      Sample error codes indexed: {n}")

    # Resolved tickets (learning loop) and embeddings
    from rag.ingest import ingest_resolved_tickets, backfill_embeddings
    try:
        print(f"      Resolved tickets indexed: {ingest_resolved_tickets()}")
    except Exception as exc:
        print(f"      (ticket ingestion skipped: {exc})")
    embedded = backfill_embeddings()
    if embedded:
        print(f"      Embeddings generated: {embedded}")

    from rag.retrieval import resolve_answerable_gaps
    closed = resolve_answerable_gaps()
    if closed:
        print(f"      Knowledge gaps now answerable (closed): {closed}")

    # Final stats
    print("\n--- Index Summary ---")
    s = rag_stats()
    print(f"  Total chunks  : {s['total_chunks']}")
    for dt, count in s.get("by_doc_type", {}).items():
        print(f"    {dt:<20}: {count}")
    print(f"  Open gaps     : {s['open_gaps']}")

    # Check embedding availability
    print("\n--- Embedding ---")
    try:
        from rag.embed import dense_enabled, model_name, provider
        if dense_enabled():
            print(f"  Vector search ENABLED: {provider()} / {model_name()} (new chunks are embedded automatically)")
        else:
            print("  Vector search disabled (no NVIDIA_API_KEY, rag.embedding_provider is none, or the local "
                  "library is missing): keyword search only.")
    except ImportError:
        print("  sentence-transformers: NOT INSTALLED")
        print("  Dense (semantic) search is disabled; using BM25 (keyword) search only.")
        print("  To enable: pip install sentence-transformers")

    print("\nRAG index ready. The agent will use hybrid search automatically.")
    print("=" * 60)


if __name__ == "__main__":
    main()
