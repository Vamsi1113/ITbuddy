import os
import time

import pytest

from agent import graph as graph_module
from agent import runner
from safety import audit, policy
from safety.policy import PolicyError, ToolRunner
from tools import registry
from tools.registry import TOOLS, ToolSpec


def test_catalogue_has_no_shell_and_no_r3_tools():
    assert len(TOOLS) >= 50
    # The only shell-like tool is the PowerShell connector's run_powershell: it must need approval (R2), be
    # deny-listed in Python, and be the only one.
    shellish = [name for name in TOOLS if "shell" in name or "exec" in name or "command" in name]
    assert shellish == ["run_powershell"] and TOOLS["run_powershell"].risk == 2
    assert {t.risk for t in TOOLS.values()} <= {0, 1, 2}      # R3 is never executable
    for t in TOOLS.values():
        if t.risk >= 1:
            assert t.change_note or t.domain == "computer_use", f"{t.name} needs a change note for the approval card"
    from agent.specialists import DOMAINS
    from connectors.base import CONNECTORS
    known = set(DOMAINS) | {d for c in CONNECTORS.values() for d in c.domains}
    assert {t.domain for t in TOOLS.values()} <= known


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

    monkeypatch.setitem(TOOLS, "get_disk_usage", ToolSpec("get_disk_usage", slow, "storage", 0, ""))
    monkeypatch.setattr(policy, "cfg", lambda *k, default=None: 0.2 if k[-1] == "tool_timeout_seconds" else
                        {"max_tool_output_chars": 1500, "max_tool_calls_per_request": 10}.get(k[-1], default))
    out = ToolRunner("t5", "storage").run("get_disk_usage")
    assert out["ok"] is False and "timed out" in out["error"]
    monkeypatch.setitem(TOOLS, "get_disk_usage", ToolSpec("get_disk_usage", broken, "storage", 0, ""))
    out = ToolRunner("t5", "storage").run("get_disk_usage")
    assert out["ok"] is False and "boom" in out["error"]


def test_long_output_is_truncated(monkeypatch):
    monkeypatch.setitem(TOOLS, "get_disk_usage",
                        ToolSpec("get_disk_usage", lambda: {"ok": True, "blob": "x" * 5000}, "storage", 0, ""))
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
    "Is the firewall on?", "When does my password expire?", "Is Zoom installed on this computer?",
    "Is developer mode on or off?", "What was installed recently?", "Which apps crashed this week?",
])
def test_normal_requests_are_not_flagged(text):
    assert not policy.is_sensitive_request(text)


# --- whole-graph checks with the model replaced by fixed answers -----------------
@pytest.fixture
def fake_graph(monkeypatch):
    from langgraph.checkpoint.memory import MemorySaver

    monkeypatch.setattr(graph_module.router, "route", lambda request: {"agent": "network", "question": ""})
    def fake_model(system, user, validate):
        if '"tools"' in system:   # the planning call
            return validate({"tools": [{"tool": "check_dns_resolution", "args": {}}]})
        return validate({"answer": "DNS lookups fail.", "fix": "flush_dns_cache", "args": {}, "reason": "stale"})

    monkeypatch.setattr("agent.specialists.ask_json", fake_model)
    flushed = []
    monkeypatch.setitem(TOOLS, "flush_dns_cache", ToolSpec(
        "flush_dns_cache", lambda: flushed.append(1) or {"ok": True, "output": "flushed"}, "network", 1,
        "Flush the DNS cache.", (), "The DNS cache will be cleared."))
    return graph_module.build_graph(MemorySaver()), flushed


def test_graph_pauses_then_runs_fix_on_approval(fake_graph):
    graph, flushed = fake_graph
    result = runner.start(graph, "websites do not open")
    assert result["status"] == "needs_approval" and flushed == []
    assert result["approval"]["steps"] == ["Flush the DNS cache"]
    result = runner.resume(graph, result["task_id"], True)
    assert flushed == [1]
    assert result["state"]["outcome"] in ("fixed", "not_fixed") and result["state"]["comparison"]
    events = [e["event"] for e in audit.task_events(result["task_id"])]
    for needed in ("request", "route", "plan", "tool_call", "proposal", "approval", "result", "report"):
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
    state = result["state"]
    assert state["outcome"] == "escalated" and state["ticket"]["ref"] in state["report"]
    assert not any(e["event"] == "tool_call" for e in audit.task_events(result["task_id"]))
    from tools import tickets
    assert tickets.all_tickets()[0]["category"] == "software_request"


def test_read_only_mode_blocks_every_change():
    policy.set_read_only(True)
    try:
        with pytest.raises(PolicyError, match="Read-only"):
            ToolRunner("t7", "network").run("flush_dns_cache", approved=True)
        assert ToolRunner("t7", "storage").run("get_disk_usage")["ok"] is True
    finally:
        policy.set_read_only(None)


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
