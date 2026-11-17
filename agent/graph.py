"""LangGraph workflow: route -> diagnose -> policy gate -> approval -> execute -> verify -> report.

The approval node only calls interrupt(), so nothing is re-run when the graph resumes.
"""
from __future__ import annotations

import sqlite3
from typing import TypedDict

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.config import get_stream_writer
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from agent import router
from agent.llm import ModelError
from agent.specialists import LABELS, SPECIALISTS
from appconfig import cfg, data_path
from safety import audit, policy
from safety.policy import PolicyError, ToolRunner
from tools.registry import TOOLS


class State(TypedDict, total=False):
    task_id: str
    request: str
    agent: str             # performance | storage | network | computer_use | none | refused
    question: str
    diagnostics: dict      # tool name -> tool output (the "before" measurements)
    proposal: dict         # diagnosis, fix, summary, what_changes, steps
    decision: str          # approved | rejected
    fix_results: list
    comparison: list       # [{"metric", "before", "after"}]
    verify_note: str
    outcome: str           # fixed | not_fixed | rejected | refused | no_action | unsupported | error
    report: str
    error: str
    tool_calls: int


def _emit(agent: str | None, text: str, tool: str | None = None) -> None:
    """Live status line for the interface (FR-2)."""
    try:
        get_stream_writer()({"agent": LABELS.get(agent or "", "IT Buddy"), "tool": tool, "text": text})
    except Exception:
        pass  # not running inside a stream


def _runner(state: State, agent: str | None = None) -> ToolRunner:
    return ToolRunner(state["task_id"], agent or state["agent"], calls_made=state.get("tool_calls", 0))


def _run(runner: ToolRunner, tool: str, args: dict | None = None, approved: bool = False, label: str = "") -> dict:
    _emit(runner.agent, label or f"Running {tool}", tool)
    result = runner.run(tool, args, approved=approved)
    if result.get("ok") is False:
        _emit(runner.agent, f"{tool} failed: {result.get('error') or result.get('output')}", tool)
    return result


# ---------------------------------------------------------------------------
# Nodes
# ---------------------------------------------------------------------------
def route_node(state: State) -> dict:
    task_id, request = state["task_id"], state["request"]
    audit.start_task(task_id, request)
    if policy.is_sensitive_request(request):
        audit.log_event(task_id, "route", agent="refused", detail="Level 3 request refused by policy")
        return {"agent": "refused", "outcome": "refused", "tool_calls": 0}
    _emit(None, "Router is choosing a specialist")
    try:
        choice = router.route(request)
    except ModelError as e:
        return {"agent": "none", "outcome": "error", "error": str(e), "tool_calls": 0}
    audit.log_event(task_id, "route", agent=choice["agent"], detail=choice)
    if choice["agent"] == "none":
        return {"agent": "none", "outcome": "unsupported", "question": choice["question"], "tool_calls": 0}
    _emit(choice["agent"], f"Routed to the {LABELS[choice['agent']]} agent")
    return {"agent": choice["agent"], "tool_calls": 0}


def diagnose_node(state: State) -> dict:
    agent = state["agent"]
    spec = SPECIALISTS[agent]
    runner = _runner(state)
    try:
        if agent == "computer_use":
            return _diagnose_computer_use(state, spec)
        diagnostics = {tool: _run(runner, tool) for tool in spec.diagnostic_tools}
        failed = [f"{t}: {o.get('error')}" for t, o in diagnostics.items() if o.get("ok") is False]
        if len(failed) == len(diagnostics):
            return {"diagnostics": diagnostics, "tool_calls": runner.calls_made, "outcome": "error",
                    "error": "The diagnostic tools failed: " + "; ".join(failed)}
        _emit(agent, "Writing the diagnosis (the local model can take a minute)")
        proposal = spec.propose(state["request"], diagnostics)
    except ModelError as e:
        return {"tool_calls": runner.calls_made, "outcome": "error", "error": str(e)}
    except PolicyError as e:
        return {"tool_calls": runner.calls_made, "outcome": "error", "error": str(e)}
    audit.log_event(state["task_id"], "proposal", agent=agent, tool=proposal.get("fix"),
                    detail={k: proposal.get(k) for k in ("diagnosis", "summary", "reason")})
    out = {"diagnostics": diagnostics, "proposal": proposal, "tool_calls": runner.calls_made}
    if not proposal.get("fix"):
        out["outcome"] = "no_action"
    return out


def _diagnose_computer_use(state: State, spec) -> dict:
    _emit("computer_use", "Working out which task this is")
    choice = spec.pick_task(state["request"])
    audit.log_event(state["task_id"], "proposal", agent="computer_use", detail=choice)
    if choice["task"] == "none":
        return {"outcome": "unsupported", "question": ""}
    if choice["task"] == "browser_task":
        return {"diagnostics": {}, "proposal": spec.plan_browser_task(choice["task_id"])}
    # The health numbers come from the Performance and Storage agents' read-only tools.
    perf = _runner(state, "performance")
    health = _run(perf, "get_system_health", label="Collecting system health")
    stor = ToolRunner(state["task_id"], "storage", calls_made=perf.calls_made)
    disks = _run(stor, "get_disk_usage", label="Collecting disk usage")
    if health.get("ok") is False:
        return {"tool_calls": stor.calls_made, "outcome": "error",
                "error": f"Could not read the system health: {health.get('error')}"}
    return {"diagnostics": {"get_system_health": health, "get_disk_usage": disks},
            "proposal": spec.plan_health_note(health, disks), "tool_calls": stor.calls_made}


def gate_node(state: State) -> dict:
    """Policy gate: Python checks risk level, allow-lists and the tool budget before anything pauses or runs."""
    steps = state["proposal"]["steps"]
    try:
        for step in steps:
            spec = TOOLS.get(step["tool"])
            if spec is None or spec.agent != state["agent"]:
                raise PolicyError(f"'{step['tool']}' is not a tool of the {LABELS[state['agent']]} agent")
            if spec.risk_level >= policy.SENSITIVE:
                raise PolicyError("This is a sensitive (Level 3) action. Please contact IT.")
            policy.check_args(step["tool"], step["args"])
        limit = int(cfg("limits", "max_tool_calls_per_request", default=10))
        if state.get("tool_calls", 0) + len(steps) > limit:
            raise PolicyError(f"This plan needs more than the {limit} tool calls allowed per request")
    except PolicyError as e:
        audit.log_event(state["task_id"], "blocked", agent=state["agent"], detail=str(e))
        return {"outcome": "refused", "error": str(e)}
    _emit(state["agent"], "Waiting for your approval")
    return {}


def approval_node(state: State) -> dict:
    proposal = state["proposal"]
    answer = interrupt({
        "agent": LABELS[state["agent"]],
        "diagnosis": proposal["diagnosis"],
        "summary": proposal["summary"],
        "what_changes": proposal["what_changes"],
        "steps": [s["label"] for s in proposal["steps"]],
    })
    approved = bool(answer.get("approved")) if isinstance(answer, dict) else bool(answer)
    decision = "approved" if approved else "rejected"
    audit.log_event(state["task_id"], "approval", agent=state["agent"], tool=proposal["fix"],
                    args=[s["args"] for s in proposal["steps"]], risk_level=policy.NEEDS_APPROVAL, detail=decision)
    return {"decision": decision, **({} if approved else {"outcome": "rejected"})}


def execute_node(state: State) -> dict:
    runner = _runner(state)
    results = []
    for step in state["proposal"]["steps"]:
        try:
            result = _run(runner, step["tool"], step["args"], approved=True, label=step["label"])
        except PolicyError as e:
            result = {"ok": False, "error": str(e)}
        results.append(result)
        if result.get("ok") is False:
            break  # stop the plan at the first failed step
    return {"fix_results": results, "tool_calls": runner.calls_made}


def verify_node(state: State) -> dict:
    agent = state["agent"]
    _emit(agent, "Checking the result: running the diagnostic again")
    runner = _runner(state)
    try:
        v = SPECIALISTS[agent].verify(runner, state)
    except PolicyError as e:
        return {"outcome": "not_fixed", "verify_note": f"Could not verify: {e}", "tool_calls": runner.calls_made}
    # A fix whose step failed is never reported as fixed, whatever the re-check shows.
    step_failed = any(r.get("ok") is False for r in state.get("fix_results", []))
    if step_failed:
        v["fixed"] = False
        v["note"] = "The fix did not complete, so the problem is not confirmed as solved."
    audit.log_event(state["task_id"], "result", agent=agent, detail=v)
    return {"comparison": v["comparison"], "verify_note": v["note"],
            "outcome": "fixed" if v["fixed"] else "not_fixed", "tool_calls": runner.calls_made}


def _alternatives(agent: str) -> str:
    return {
        "performance": "Other options: save your work and close the app yourself, restart the computer, or contact IT.",
        "storage": "Other options: empty the Recycle Bin, move large files to a network or cloud folder, or contact IT.",
        "network": "Other options: turn Wi-Fi off and on, restart the computer, or contact IT.",
        "computer_use": "You can do the task by hand, or ask again with different wording.",
    }.get(agent, "")


def report_node(state: State) -> dict:
    outcome = state.get("outcome", "error")
    agent = state.get("agent")
    proposal = state.get("proposal") or {}
    parts = []
    if outcome == "refused" and agent == "refused":
        parts.append("I can't help with this request. It involves a sensitive change (for example installing "
                     "software, passwords, permissions, security settings, the registry or deleting your files). "
                     "Please contact IT.")
    elif outcome == "refused":
        parts.append(f"The safety policy blocked this action: {state.get('error')} Nothing was changed. Please contact IT.")
    elif outcome == "unsupported":
        parts.append(state.get("question") or
                     "This request is not supported. I can help with a slow computer, a full disk, internet or "
                     "DNS problems, writing a system health note in Notepad, and downloading the test portal report.")
    elif outcome == "error":
        parts.append(f"I had to stop: {state.get('error')} Nothing was changed.")
    else:
        parts.append(proposal.get("diagnosis", ""))
        if outcome == "no_action":
            parts.append("No fix is needed or available from my tool list, so nothing was changed. "
                         + (proposal.get("reason") or ""))
        elif outcome == "rejected":
            parts.append(f"You rejected the fix ({proposal.get('summary')}), so nothing was changed. "
                         + _alternatives(agent))
        else:
            failed = [r for r in state.get("fix_results", []) if r.get("ok") is False]
            parts.append(f"Action taken: {proposal.get('summary')}.")
            if failed:
                parts.append(f"A step failed: {failed[0].get('error') or failed[0].get('output')}")
            if outcome == "fixed":
                parts.append(f"Verified: {state.get('verify_note')}")
            else:
                parts.append(f"The problem remains: {state.get('verify_note')} I will not retry. "
                             "Please contact IT so they can look into it.")
    report = "\n\n".join(p.strip() for p in parts if p and p.strip())
    audit.log_event(state["task_id"], "report", agent=agent, detail={"outcome": outcome, "report": report})
    audit.finish_task(state["task_id"], agent, outcome, report)
    return {"report": report, "outcome": outcome}


# ---------------------------------------------------------------------------
# Wiring
# ---------------------------------------------------------------------------
def _next_or_report(next_node: str):
    return lambda state: "report" if state.get("outcome") else next_node


def build_graph(checkpointer=None):
    g = StateGraph(State)
    g.add_node("route", route_node)
    g.add_node("diagnose", diagnose_node)
    g.add_node("gate", gate_node)
    g.add_node("approval", approval_node)
    g.add_node("execute", execute_node)
    g.add_node("verify", verify_node)
    g.add_node("report", report_node)
    g.add_edge(START, "route")
    g.add_conditional_edges("route", _next_or_report("diagnose"), ["diagnose", "report"])
    g.add_conditional_edges("diagnose", _next_or_report("gate"), ["gate", "report"])
    g.add_conditional_edges("gate", _next_or_report("approval"), ["approval", "report"])
    g.add_conditional_edges("approval", _next_or_report("execute"), ["execute", "report"])
    g.add_edge("execute", "verify")
    g.add_edge("verify", "report")
    g.add_edge("report", END)
    if checkpointer is None:
        conn = sqlite3.connect(data_path("checkpoint_db"), check_same_thread=False)
        checkpointer = SqliteSaver(conn)
    return g.compile(checkpointer=checkpointer)
