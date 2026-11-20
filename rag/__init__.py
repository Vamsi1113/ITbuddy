"""RAG (Retrieval-Augmented Generation) subsystem for Tobi.

Architecture:
  Connectors → Ingestion pipeline → Index stores → Retrieval service → Agent tools

The rag package is optional-dependency-safe: it degrades to the existing
keyword search when sqlite-vec / rank_bm25 / sentence-transformers are absent.
Import order: index → ingest → retrieval → tools_rag
"""
