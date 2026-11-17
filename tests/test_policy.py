import os
import time

import pytest

from agent import graph as graph_module
from agent import runner
from safety import audit, policy
from safety.policy import PolicyError, ToolRunner
from tools import registry
from tools.registry import TOOLS, ToolSpec


def test_catalogue_is_exactly_14_tools_max_4_per_agent():
    assert len(TOOLS) == 14
    for agent in ("performance", "storage", "network", "computer_use"):
        assert 1 <= len(registry.tools_for(agent)) <= 4
    assert not any("shell" in name or "exec" in name for name in TOOLS)
    assert {t.risk_level for t in TOOLS.values()} == {1, 2}


def test_level_1_runs_and_is_audited():
    r = ToolRunner("t1", "storage")
    out = r.run("get_disk_usage")
    assert out["ok"] is True and r.calls_made == 1
    events = audit.task_events("t1")
    assert events[-1]["event"] == "tool_call" and events[-1]["tool"] == "get_disk_usage"


def test_level_2_needs_approval():
    r = ToolRunner("t2", "network")
    with pytest.raises(PolicyError, match="approval"):
        r.run("flush_dns_cache")
    assert r.calls_made == 0
    assert audit.task_events("t2")[-1]["event"] == "blocked"


def test_agent_cannot_use_another_agents_tool_or_unknown_tool():
    r = ToolRunner("t3", "storage")
    with pytest.raises(PolicyError):
        r.run("flush_dns_cache", approved=True)
    with pytest.raises(PolicyError):
        r.run("run_shell", {"command": "dir"}, approved=True)


def test_allow_lists():
    with pytest.raises(PolicyError):
        policy.check_args("open_application", {"name": "powershell"})
    with pytest.raises(PolicyError):
        policy.check_args("open_application", {"name": "cmd"})
    policy.check_args("open_application", {"name": "notepad"})
    with pytest.raises(PolicyError):
        policy.check_args("run_browser_task", {"task_id": "open_any_url"})
    with pytest.raises(PolicyError):
        policy.check_args("type_text", {"window": "Windows PowerShell", "text": "x"})
    with pytest.raises(PolicyError):
        policy.check_args("click_control", {"window": "Registry Editor", "control_name": "OK"})
    with pytest.raises(PolicyError):
        policy.check_args("close_process", {"pid": os.getpid()})
    with pytest.raises(PolicyError):
        policy.check_args("close_process", {"pid": "4"})


def test_tool_call_limit():
    r = ToolRunner("t4", "storage", calls_made=10)
    with pytest.raises(PolicyError, match="limit"):
        r.run("get_disk_usage")


def test_timeout_and_failure_are_reported_not_hidden(monkeypatch):
    def slow():
        time.sleep(2)
        return {"ok": True}

    def broken():
        raise RuntimeError("boom")

    monkeypatch.setitem(TOOLS, "get_disk_usage", ToolSpec("get_disk_usage", slow, "storage", 1, ""))
    monkeypatch.setattr(policy, "cfg", lambda *k, default=None: 0.2 if k[-1] == "tool_timeout_seconds" else
                        {"max_tool_output_chars": 1500, "max_tool_calls_per_request": 10}.get(k[-1], default))
    out = ToolRunner("t5", "storage").run("get_disk_usage")
    assert out["ok"] is False and "timed out" in out["error"]
    monkeypatch.setitem(TOOLS, "get_disk_usage", ToolSpec("get_disk_usage", broken, "storage", 1, ""))
    out = ToolRunner("t5", "storage").run("get_disk_usage")
    assert out["ok"] is False and "boom" in out["error"]


def test_long_output_is_truncated(monkeypatch):
    monkeypatch.setitem(TOOLS, "get_disk_usage",
                        ToolSpec("get_disk_usage", lambda: {"ok": True, "blob": "x" * 5000}, "storage", 1, ""))
    out = ToolRunner("t6", "storage").run("get_disk_usage")
    assert out["truncated"] is True and len(out["data"]) <= 1500


@pytest.mark.parametrize("text", [
    "Install Chrome for me", "Reset my password", "Give me admin rights", "Edit the registry",
    "Turn off the firewall", "Delete all files in my Documents", "Change permissions on this folder",
])
def test_sensitive_requests_are_detected(text):
    assert policy.is_sensitive_request(text)


@pytest.mark.parametrize("text", [
    "My computer is very slow.", "My C drive is almost full.", "Wi-Fi is connected but websites do not open.",
])
def test_normal_requests_are_not_flagged(text):
    assert not policy.is_sensitive_request(text)


# --- whole-graph checks with the model replaced by fixed answers -----------------
@pytest.fixture
def fake_graph(monkeypatch):
    from langgraph.checkpoint.memory import MemorySaver

    monkeypatch.setattr(graph_module.router, "route", lambda request: {"agent": "network", "question": ""})
    monkeypatch.setattr("agent.specialists.ask_json", lambda system, user, validate: validate(
        {"diagnosis": "DNS lookups fail.", "fix": "flush_dns_cache", "reason": "clear stale entries"}))
    flushed = []
    monkeypatch.setitem(TOOLS, "flush_dns_cache", ToolSpec(
        "flush_dns_cache", lambda: flushed.append(1) or {"ok": True, "output": "flushed"}, "network", 2, ""))
    return graph_module.build_graph(MemorySaver()), flushed


def test_graph_pauses_then_runs_fix_on_approval(fake_graph):
    graph, flushed = fake_graph
    result = runner.start(graph, "websites do not open")
    assert result["status"] == "needs_approval" and flushed == []
    assert result["approval"]["steps"] == ["Run ipconfig /flushdns"]
    result = runner.resume(graph, result["task_id"], True)
    assert flushed == [1]
    assert result["state"]["outcome"] in ("fixed", "not_fixed") and result["state"]["comparison"]
    events = [e["event"] for e in audit.task_events(result["task_id"])]
    for needed in ("request", "route", "tool_call", "proposal", "approval", "result", "report"):
        assert needed in events
    assert audit.list_tasks()[0]["outcome"] == result["state"]["outcome"]


def test_reject_changes_nothing_and_is_logged(fake_graph):
    graph, flushed = fake_graph
    result = runner.start(graph, "websites do not open")
    result = runner.resume(graph, result["task_id"], False)
    assert flushed == [] and result["state"]["outcome"] == "rejected"
    assert "nothing was changed" in result["state"]["report"]
    approvals = [e for e in audit.task_events(result["task_id"]) if e["event"] == "approval"]
    assert approvals and approvals[0]["detail"] == "rejected"


def test_sensitive_request_is_refused_without_model_or_tools(monkeypatch):
    from langgraph.checkpoint.memory import MemorySaver

    def no_model(*a, **k):
        raise AssertionError("the model must not be called for a Level 3 request")

    monkeypatch.setattr(graph_module.router, "route", no_model)
    result = runner.start(graph_module.build_graph(MemorySaver()), "Please install Zoom and give me admin rights")
    assert result["state"]["outcome"] == "refused" and "contact IT" in result["state"]["report"]
    assert not any(e["event"] == "tool_call" for e in audit.task_events(result["task_id"]))


def test_malformed_model_output_stops_after_retries(monkeypatch):
    from agent import llm

    calls = []

    class FakeLLM:
        def invoke(self, messages):
            calls.append(1)
            return type("R", (), {"content": "sure, I will help!"})()

    monkeypatch.setattr(llm, "get_llm", lambda: FakeLLM())
    with pytest.raises(llm.ModelError, match="malformed"):
        llm.ask_json("s", "u", lambda d: d)
    assert len(calls) == 3  # first try + 2 retries
