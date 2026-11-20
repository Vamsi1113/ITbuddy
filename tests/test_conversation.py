"""Natural conversation: greetings get a real reply, and requests that are not one of the fixed computer tasks
go to the general agent instead of a canned list of features."""
import pytest
from langgraph.checkpoint.memory import MemorySaver

from agent import graph as graph_module
from agent import runner
from agent.specialists import COMPUTER_USE

CANNED = "I can open websites, apps and folders"


def test_greeting_gets_a_conversational_reply_without_a_status(monkeypatch):
    monkeypatch.setattr(graph_module.router, "route", lambda request: {"agent": "none", "question": ""})
    monkeypatch.setattr(graph_module.specialists, "chat_reply",
                        lambda request, history=None: "Good morning! How can I help?")
    state = runner.start(graph_module.build_graph(MemorySaver()), "Hi gd morning tobi")["state"]
    assert state["outcome"] == "chat"
    assert state["report"] == "Good morning! How can I help?"


def test_unknown_computer_task_goes_to_autopilot_not_a_canned_list(monkeypatch):
    monkeypatch.setattr(graph_module.router, "route", lambda request: {"agent": "computer_use", "question": ""})
    monkeypatch.setattr(graph_module.COMPUTER_USE, "pick_task", lambda request: {"task": "none"})
    seen = {}

    def fake_think(state):
        seen["agent"] = state["agent"]
        return {"auto_next": "final", "outcome": "no_action",
                "proposal": {"diagnosis": "Chrome and Explorer are running.", "fix": None}}

    monkeypatch.setattr(graph_module.autopilot, "think_node", fake_think)
    state = runner.start(graph_module.build_graph(MemorySaver()), "check what apps are being running")["state"]
    assert seen["agent"] == "autopilot"
    assert CANNED not in state.get("report", "")


@pytest.mark.parametrize("text", ["Ok can see my task manager", "show me the task manager", "can I see my calculator"])
def test_see_my_app_opens_it(text):
    pick = COMPUTER_USE.quick_pick(text)
    assert pick and pick["task"] == "open_app"


@pytest.mark.parametrize("text", ["can you see whether wifi is on", "show my disk space"])
def test_see_without_an_app_is_not_a_computer_task(text):
    assert not COMPUTER_USE.quick_pick(text)


# --- conversation memory -------------------------------------------------------------
from agent import memory  # noqa: E402

HISTORY = [{"role": "user", "text": "what apps are running?"},
           {"role": "assistant", "text": "chrome.exe (900 MB, PID 4242) and notepad.exe (20 MB, PID 77)."}]


def test_memory_keeps_recent_turns_and_redacts_secrets():
    conv = memory.Conversation(max_turns=3)
    conv.add("user", "my password is Hunter2Secret!")
    for i in range(4):
        conv.add("assistant", f"reply {i}")
    turns = conv.turns()
    assert len(turns) == 3 and turns[-1]["text"] == "reply 3"
    conv.clear()
    conv.add("user", "password: Hunter2Secret!")
    assert "Hunter2Secret" not in conv.turns()[0]["text"]


@pytest.mark.parametrize("text, needed", [
    ("close it", True), ("what about chrome?", True), ("yes", True),
    ("My printer in the second floor office is not printing anything since this morning at all", False),
])
def test_follow_ups_are_detected(text, needed):
    assert memory.needs_context(text, HISTORY) is needed
    assert memory.needs_context(text, []) is False


def test_follow_up_is_made_standalone_before_routing(monkeypatch):
    monkeypatch.setattr("agent.llm.ask_json", lambda system, user, validate:
                        validate({"request": "close chrome.exe (PID 4242)"}) if "EARLIER CONVERSATION" in user else None)
    routed = {}

    def fake_route(request):
        routed["request"] = request
        return {"agent": "none", "question": ""}

    monkeypatch.setattr(graph_module.router, "route", fake_route)
    monkeypatch.setattr(graph_module.specialists, "chat_reply", lambda request, history=None: "ok")
    state = runner.start(graph_module.build_graph(MemorySaver()), "close it", history=HISTORY)["state"]
    assert routed["request"] == "close chrome.exe (PID 4242)"
    assert state["original_request"] == "close it"


def test_memory_never_breaks_a_request_when_the_model_fails(monkeypatch):
    from agent.llm import ModelError

    def broken(*a, **k):
        raise ModelError("offline")

    monkeypatch.setattr("agent.llm.ask_json", broken)
    assert memory.standalone("close it", HISTORY) == "close it"
