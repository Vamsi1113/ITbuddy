import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


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
