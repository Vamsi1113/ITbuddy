"""Requests to write an answer into Notepad: Tobi writes the text, shows it, then saves and opens it (not an empty Notepad)."""
import pytest
from langgraph.checkpoint.memory import MemorySaver

from agent import basis
from agent import graph as graph_module
from agent import runner, specialists
from agent.specialists import COMPUTER_USE

ASKED = ("can u create a notepad file by writing the answer for what are the steps to create a python file in vs code "
         "and how to run it")


@pytest.mark.parametrize("text", [ASKED, "write the steps to install python in a notepad file",
                                  "make a text file on my desktop explaining how to map a network drive",
                                  "put a checklist for my first day in notepad and save it as first day"])
def test_described_content_is_written_not_just_opened(text):
    pick = COMPUTER_USE.quick_pick(text)
    assert pick["task"] == "write_note" and pick["compose"] is True


def test_names_and_folders_are_kept_but_a_description_is_not_a_name():
    assert COMPUTER_USE.quick_pick("put a checklist for my first day in notepad and save it as first day")["filename"] == "first day"
    assert COMPUTER_USE.quick_pick("make a text file on my desktop explaining how to map a network drive")["folder"] == "Desktop"
    assert COMPUTER_USE.quick_pick(ASKED)["filename"] == ""


@pytest.mark.parametrize("text, task", [("open notepad", "open_app"), ('write "hello" in notepad', "write_note")])
def test_simple_and_quoted_requests_are_unchanged(text, task):
    pick = COMPUTER_USE.quick_pick(text)
    assert pick["task"] == task and not pick.get("compose")


def test_the_whole_flow_shows_the_text_then_saves_it(monkeypatch):
    monkeypatch.setattr(graph_module.router, "route", lambda request: {"agent": "computer_use", "question": ""})
    monkeypatch.setattr(specialists, "compose_note", lambda request, history=None: {
        "intro": "Here you go, all written up:", "title": "Tobi test zq7 note",
        "text": "Create a Python file in VS Code\n\n1. File > New File\n2. Save it as hello.py"})
    graph = graph_module.build_graph(MemorySaver())
    first = runner.start(graph, ASKED)
    card = first["approval"]
    assert "> 1. File > New File" in card["diagnosis"] and card["diagnosis"].startswith("Here you go")
    assert card["say"] == "Shall I save this as Tobi test zq7 note.txt in your Documents and open it in Notepad?"
    assert card["steps"][0].startswith("Save your text as Tobi test zq7 note.txt")


def test_a_simple_task_has_no_table_and_no_steps_panel():
    state = {"outcome": "fixed", "agent": "computer_use", "proposal": {"summary": "Open Notepad"}, "diagnostics": {}}
    assert basis.build(state) == []


# --- unclear requests: one short question first ------------------------------------------------------
@pytest.mark.parametrize("text, task", [("how do i change my system pattern password", "clarify"),
                                        ("change my laptop password", "clarify"),
                                        ("How do I change my Windows Hello PIN?", "hello_sign_in"),
                                        ("set up fingerprint sign in", "hello_sign_in"),
                                        ("how do I change my Windows sign-in password", "password_reset"),
                                        ("forgot my windows password", "password_reset"),
                                        ("How do I change my company account password", "password_reset")])
def test_which_password_is_asked_only_when_unclear(text, task):
    assert COMPUTER_USE.quick_pick(text)["task"] == task


def test_an_unclear_password_question_gets_numbered_options_and_no_ticket(monkeypatch):
    monkeypatch.setattr(graph_module, "_open_ticket", lambda *a, **k: pytest.fail("no ticket for a question"))
    result = runner.start(graph_module.build_graph(MemorySaver()), "how do i change my system pattern password")
    state = result["state"]
    assert result["status"] == "done" and state["outcome"] == "chat"
    assert "1. Your Windows sign-in password" in state["report"] and "2. Your PIN" in state["report"]


def test_a_pin_change_is_a_yes_no_offer_to_open_sign_in_options(monkeypatch):
    monkeypatch.setattr(graph_module, "_open_ticket", lambda *a, **k: pytest.fail("no ticket"))
    card = runner.start(graph_module.build_graph(MemorySaver()), "how do I change my PIN")["approval"]
    assert card["style"] == "offer" and card["say"] == "Want me to open Sign-in options for you?" and "Change PIN" in card["diagnosis"]
