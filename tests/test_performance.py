import json
import os
import subprocess
import sys

import psutil

from tools import performance


def test_system_health_has_real_numbers():
    out = performance.get_system_health()
    assert out["ok"] is True
    assert 0 <= out["cpu_percent"] <= 100
    assert 0 < out["ram_percent"] <= 100
    assert out["ram_total_gb"] > 0 and out["uptime_hours"] >= 0
    assert len(json.dumps(out)) <= 1500


def test_running_processes_top_five():
    out = performance.get_running_processes()
    assert out["ok"] is True
    assert 1 <= len(out["top_by_memory"]) <= 5 and 1 <= len(out["top_by_cpu"]) <= 5
    mem = [p["memory_mb"] for p in out["top_by_memory"]]
    assert mem == sorted(mem, reverse=True)
    assert all({"pid", "name", "closable"} <= set(p) for p in out["top_by_memory"])
    assert len(json.dumps(out)) <= 1500


def test_protected_and_own_processes_are_refused():
    assert performance.protection_reason(4) is not None            # System
    assert performance.protection_reason(os.getpid()) is not None  # IT Buddy itself
    assert performance.protection_reason(os.getppid()) is not None
    assert performance.protection_reason(999_999_999) is not None  # does not exist
    for p in psutil.process_iter(["name"]):
        if (p.info["name"] or "").lower() in ("svchost.exe", "explorer.exe", "lsass.exe"):
            assert performance.protection_reason(p.pid) is not None


def test_close_process_rejects_bad_arguments():
    for bad in ("12", -1, 0, None, True, 3.5):
        assert performance.close_process(bad)["ok"] is False
    assert performance.close_process(os.getpid())["ok"] is False
    assert psutil.pid_exists(os.getpid())


def test_close_process_closes_a_user_process(monkeypatch):
    # A throwaway child process. python.exe is on the protected list, so lift that for this test only.
    child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
    try:
        monkeypatch.setattr(performance, "_protected_names", lambda: set())
        out = performance.close_process(child.pid)
        assert out["ok"] is True and out["still_running"] is False
        assert child.wait(timeout=5) is not None
    finally:
        if child.poll() is None:
            child.kill()
