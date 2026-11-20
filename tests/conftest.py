import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import os  # noqa: E402

os.environ["IT_BUDDY_NO_DENSE"] = "1"      # tests never call the hosted embedding model


@pytest.fixture(autouse=True)
def _temp_audit_db(tmp_path, monkeypatch):
    """Tests never write to the real audit log."""
    import appconfig

    real = appconfig.data_path

    def fake(key):
        return tmp_path / f"{key}.db" if key in ("audit_db", "checkpoint_db") else real(key)

    monkeypatch.setattr(appconfig, "data_path", fake)
    import safety.audit
    monkeypatch.setattr(safety.audit, "data_path", fake)


@pytest.fixture(autouse=True)
def _temp_rag_db(tmp_path, monkeypatch):
    """Tests never touch the real RAG index (gaps, feedback, drafts and usage counters are written to it)."""
    import rag.index as idx
    monkeypatch.setattr(idx, "RAG_DB", tmp_path / "rag_index.db")
    monkeypatch.setattr(idx, "_conn", None)
    yield
    if idx._conn is not None:
        idx._conn.close()
