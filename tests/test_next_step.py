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
    assert out["ask"] == "Want me to open Outlook for you?" and out["steps"][0]["args"] == {"name": "outlook"}


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


def test_the_question_always_names_what_will_really_open():
    out = specialists.next_step_offer({"do": "open_settings_page", "page": "disks_and_volumes",
                                       "ask": "Want me to open the Disk Management tool for you?"})
    assert out["ask"] == "Want me to open the disks and volumes settings for you?"
    out = specialists.next_step_offer({"do": "open_application", "app": "task manager", "ask": "Shall I open it?"})
    assert out["ask"] == "Want me to open Task Manager for you?"
    keep = "Want me to open the Disks & volumes settings so you can see the layout?"
    assert specialists.next_step_offer({"do": "open_settings_page", "page": "disks_and_volumes", "ask": keep})["ask"] == keep


@pytest.mark.parametrize("text", [
    "I don't have the steps for partitioning your C drive in the knowledge base. The articles only cover space.",
    "The articles I found only cover freeing up space when the disk is full.",
    "NO_KB_ANSWER", "That is not covered in the knowledge base."])
def test_a_knowledge_base_miss_falls_back_to_general_knowledge(text):
    assert specialists.kb_missed(text)


def test_a_real_answer_is_not_a_miss():
    assert not specialists.kb_missed("Sure! Open Disk Management, right-click C: and choose Shrink Volume. "
                                     "[howto_disks_and_drives.md § Split the C drive]")


def test_a_guides_warning_is_never_dropped():
    src = "howto_disks_and_drives.md § Split the C drive to make a new D drive (create a partition)"
    out = specialists._keep_warning(f"Open Disk Management and shrink C:. [{src}]", {})
    assert "**Before you start:** back up important files" in out and "administrator rights" in out
    said = f"Back up first, then open Disk Management. [{src}]"
    assert specialists._keep_warning(said, {}) == said
    other = "Press Win + P. [howto_windows_everyday.md § Use two screens or a projector]"
    assert specialists._keep_warning(other, {}) == other
