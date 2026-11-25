"""Questions are answered, not turned into changes; "memory" means RAM or storage; small offers end as "Done"."""
import pytest
from langgraph.checkpoint.memory import MemorySaver

from agent import graph as graph_module
from agent import runner, specialists

HEALTH = {"ok": True, "ram_available_gb": 7.7, "ram_total_gb": 15.9}
DISKS = {"ok": True, "drives": [{"drive": "C:", "total_gb": 126.4, "free_gb": 10.24, "used_percent": 91.9}]}


@pytest.mark.parametrize("text, unclear", [("can i know what is exact memeory left", True), ("how much memory do I have", True),
                                           ("how much RAM is free", False), ("which app uses most memory", False),
                                           ("how much storage space is left", False)])
def test_memory_is_unclear_only_when_it_could_be_either(text, unclear):
    assert specialists.memory_is_unclear(text) is unclear


def test_unclear_memory_gets_both_storage_and_ram(monkeypatch):
    monkeypatch.setattr(graph_module.router, "route", lambda request: {"agent": "performance", "question": ""})
    monkeypatch.setattr(graph_module, "_run", lambda runner_, tool, args, **k: HEALTH if tool == "get_system_health" else DISKS)
    monkeypatch.setattr("agent.specialists.ask_json", lambda *a, **k: pytest.fail("measured facts need no model"))
    state = runner.start(graph_module.build_graph(MemorySaver()), "can i know what is exact memeory left")["state"]
    assert "**Storage, C: drive:** 10.24 GB free of 126.4 GB (91.9% used)" in state["report"]
    assert "**RAM (working memory):** 7.7 GB free of 15.9 GB" in state["report"] and "getting full" in state["report"]
    assert state["outcome"] == "no_action"


@pytest.mark.parametrize("text, asks", [("I want to know about my storage not my ram", True),
                                        ("How much free space is on my C drive?", True), ("can you check my storage", True),
                                        ("my disk is full", False), ("clean my temp files", False),
                                        ("my computer is slow, fix it", False)])
def test_questions_are_told_apart_from_requests_for_a_change(text, asks):
    assert specialists.only_asks(text) is asks


def test_a_question_gets_an_answer_and_the_change_only_as_a_yes_no_offer(monkeypatch):
    monkeypatch.setattr(specialists, "ask_json", lambda *a, **k: {
        "answer": "Your C: drive has 10.24 GB free out of 126.4 GB. That's quite full. Want me to clean temp files?",
        "fix": "clean_approved_temp_files", "reason": "", "args": {}, "next": None})
    proposal = specialists.answer(specialists.DOMAINS["storage"], "I want to know about my storage not my ram", {})
    assert proposal["offer"] is True and proposal["recheck"] is True
    assert proposal["ask"] == "Want me to delete old temporary files?"            # never "about ? MB"
    assert proposal["diagnosis"].endswith("That's quite full.")                    # the question is asked once, by the offer


def test_a_problem_report_still_gets_the_normal_approval(monkeypatch):
    monkeypatch.setattr(specialists, "ask_json", lambda *a, **k: {
        "answer": "C: is 92% full.", "fix": "clean_approved_temp_files", "reason": "", "args": {}, "next": None})
    proposal = specialists.answer(specialists.DOMAINS["storage"], "my disk is full", {})
    assert not proposal.get("offer")


def test_no_extra_closing_line_after_the_answers_own_question(monkeypatch):
    monkeypatch.setattr(specialists, "ask_json", lambda *a, **k: {
        "answer": "C: has 10 GB free. Want me to look for large temporary files?", "fix": "none", "reason": "", "args": {},
        "next": {"do": "none", "ask": "Let me know if you'd like to free up some space."}})
    proposal = specialists.answer(specialists.DOMAINS["storage"], "I want to know about my storage", {})
    assert proposal["diagnosis"] == "C: has 10 GB free. Want me to look for large temporary files?"
