"""Answers end with a next step Tobi can do itself ("Want me to open the VPN settings? Just say OK")."""
import pytest
from langgraph.checkpoint.memory import MemorySaver

from agent import graph as graph_module
from agent import runner, specialists


def test_a_settings_page_becomes_a_yes_no_offer():
    out = specialists.next_step_offer({"do": "open_settings_page", "page": "vpn", "ask": "Want me to open the VPN settings for you? Just say OK."})
    assert out["offer"] is True and out["ask"].startswith("Want me to open the VPN settings")
    assert out["steps"] == [{"tool": "open_settings_page", "args": {"page": "vpn"}, "domain": "settings", "label": "Open the vpn settings"}]


def test_a_missing_question_gets_a_friendly_default():
    out = specialists.next_step_offer({"do": "open_application", "app": "outlook"})
    assert out["ask"].endswith("Just say OK.") and out["steps"][0]["args"] == {"name": "outlook"}


@pytest.mark.parametrize("raw", [None, "open it", {"do": "none"}, {"do": "open_settings_page", "page": "the moon"},
                                 {"do": "open_application", "app": "malware.exe"}, {"do": "run_powershell"}])
def test_unknown_or_unsafe_suggestions_are_dropped(raw):
    assert specialists.next_step_offer(raw) == {}


def test_the_whole_flow_asks_then_does_the_step(monkeypatch):
    monkeypatch.setattr(graph_module.router, "route", lambda request: {"agent": "howto", "question": ""})
    monkeypatch.setattr(graph_module, "_run", lambda *a, **k: {"ok": True})
    monkeypatch.setattr(specialists, "kb_found_something", lambda d: False)
    monkeypatch.setattr(specialists, "general_answer", lambda request, history=None: {
        "diagnosis": "Sure! Open your VPN app and connect.", "fix": None, "reason": "",
        **specialists.next_step_offer({"do": "open_settings_page", "page": "vpn", "ask": "Want me to open the VPN settings? Just say OK."})})
    graph = graph_module.build_graph(MemorySaver())
    first = runner.start(graph, "How do I connect to the VPN?")
    card = first["approval"]
    assert card["style"] == "offer" and card["say"] == "Want me to open the VPN settings? Just say OK." and "VPN app" in card["diagnosis"]
    assert runner.resume(graph, first["task_id"], True)["state"]["outcome"] == "fixed"


def test_without_a_step_the_answer_still_ends_warmly():
    assert specialists.closing_line({"do": "none", "ask": "If you get stuck, tell me what it says and I'll help."}).startswith("If you get stuck")
    assert specialists.closing_line({"do": "none", "ask": "Want me to do it? Just say OK."}) == ""
    assert specialists.closing_line({"do": "open_application", "ask": "x"}) == ""
