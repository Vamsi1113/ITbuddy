import json
import subprocess

import pytest

from tools import network, powershell


def test_check_network_connection_shape():
    out = network.check_network_connection()
    assert out["ok"] is True
    assert "website" in out and isinstance(out["internet_connected"], bool)
    assert len(json.dumps(out)) <= 1500


def test_check_dns_resolution_shape():
    out = network.check_dns_resolution()
    assert out["ok"] is True
    assert len(out["results"]) >= 1
    assert out["resolved"].endswith(f"/{len(out['results'])}")
    assert len(json.dumps(out)) <= 1500


def test_dns_failure_is_reported(monkeypatch):
    import socket

    def fail(*a, **k):
        raise socket.gaierror(11001, "getaddrinfo failed")

    monkeypatch.setattr(network.socket, "getaddrinfo", fail)
    out = network.check_dns_resolution()
    assert out["all_resolve"] is False and out["resolved"].startswith("0/")


def test_get_network_config():
    out = network.get_network_config()
    assert out["ok"] is True and isinstance(out["adapters"], list)
    assert len(json.dumps(out)) <= 1500


def test_flush_dns_uses_fixed_command_and_falls_back(monkeypatch):
    calls = []
    monkeypatch.setattr(powershell, "run_executable", lambda key: calls.append(key) or subprocess.CompletedProcess(
        [], 1, stdout="The requested operation requires elevation.", stderr=""))
    monkeypatch.setattr(powershell, "run_powershell", lambda key: calls.append(key) or "")
    out = network.flush_dns_cache()
    assert out["ok"] is True and out["method"] == "Clear-DnsClientCache"
    assert calls == ["flush_dns", "clear_dns_cache"]


def test_powershell_wrapper_only_runs_known_keys():
    with pytest.raises(powershell.CommandError):
        powershell.run_powershell("Remove-Item C:\\ -Recurse")
    with pytest.raises(powershell.CommandError):
        powershell.run_executable("format c:")
