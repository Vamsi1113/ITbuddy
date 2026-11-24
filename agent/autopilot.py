"""Autopilot: the general agent. It chains tools from every ready connector in a loop:

    think (model picks ONE tool or gives the final answer)
      -> read-only tool (R0): runs at once
      -> changing tool (R1/R2): the user approves the exact action first
      -> the result goes back to the model -> think again ... until it answers or runs out of steps

The model only chooses. Python decides what may run: every call passes safety.policy.check_step (tier,
allow-lists, read-only mode, tool budget) and is audited. Text that comes back from files, web pages, mail or
tools is data; the prompt tells the model never to follow instructions found in it, and the policy gate would
stop any action outside the allow-lists anyway.
"""
from __future__ import annotations

import json

from langgraph.config import get_stream_writer
from langgraph.types import interrupt

from agent import live, prompts
from agent.llm import ModelError, ask_json
from appconfig import cfg
from connectors.base import domain_ready
from safety import audit, policy
from safety.policy import PolicyError, ToolRunner
from tools.registry import R0, TOOLS, catalogue_text, validate_args

# Tools that add noise for a general agent (maintenance of the knowledge index, UI automation with fixed windows).
_EXCLUDED = {"report_kb_gap", "submit_kb_feedback", "draft_kb_article", "kb_index_stats", "get_kb_document",
             "match_runbook", "search_knowledge_base_rag", "find_similar_tickets", "run_browser_task"}

# Tools that operate an app window. After the user approves one for a window, the rest of the SAME task may use
# these on that window without asking for every click (each action is still audited and policy-checked).
UI_TOOLS = {"press_keys", "click_control", "type_text"}


def _window_key(tool: str, args: dict) -> str:
    return str(args.get("window") or args.get("name") or "").strip().lower()


def _ui_granted(granted: list, tool: str, args: dict) -> bool:
    key = _window_key(tool, args)
    return tool in UI_TOOLS and bool(key) and any(g in key or key in g for g in granted)


def _emit(text: str, tool: str | None = None, image: str | None = None) -> None:
    try:
        get_stream_writer()({"agent": "Autopilot", "tool": tool, "text": text, "image": image})
    except Exception:
        pass


def eligible_specs() -> list:
    """Tools the model may choose from: not R3, connector ready, and read-only tools only in read-only mode."""
    read_only = policy.is_read_only()
    out = []
    for spec in TOOLS.values():
        if spec.name in _EXCLUDED or spec.risk >= 3 or not domain_ready(spec.domain):
            continue
        if read_only and spec.risk != R0:
            continue
        out.append(spec)
    return sorted(out, key=lambda s: (s.domain, s.risk, s.name))


def _unavailable_text() -> str:
    """Connectors that are off or not set up, so the model says so instead of improvising."""
    from connectors.base import CONNECTORS
    lines = []
    for c in CONNECTORS.values():
        st = c.status()
        if st == "ready":
            continue
        if st == "disabled":
            lines.append(f"- {c.name} ({c.description}): switched off in config.yaml (connectors.{c.id}.enabled).")
        else:
            lines.append(f"- {c.name} ({c.description}): needs setup. Missing {', '.join(c.missing())} in the .env file. "
                         f"{c.setup}")
    if not lines:
        return ""
    return ("\n\nNOT AVAILABLE right now (no tools for these). If the request needs one, do not guess and do not "
            "suggest unrelated apps: give the final answer saying it needs setup and what to do:\n" + "\n".join(lines))


def _format_history(history: list, limit: int) -> str:
    if not history:
        return "(nothing done yet)"
    lines = []
    for i, h in enumerate(history, 1):
        if h.get("note"):
            lines.append(f"[{i}] {h['note']}")
            continue
        args = json.dumps(h["args"], default=str)[:200]
        lines.append(f"[{i}] {h['tool']}({args}) -> {json.dumps(h['result'], default=str)[:limit]}")
    return "\n".join(lines)


def think_node(state: dict) -> dict:
    steps = state.get("auto_steps", 0)
    max_steps = int(cfg("autopilot", "max_steps", default=8))
    history = list(state.get("auto_history") or [])
    specs = eligible_specs()
    by_name = {s.name: s for s in specs}
    system = (prompts.AUTOPILOT.replace("{catalogue}", catalogue_text(specs))
              + _unavailable_text())
    last = steps + 1 >= max_steps
    from agent.memory import as_text
    earlier = state.get("history") or []
    user = ((f"EARLIER CONVERSATION (for context only):\n{as_text(earlier, 1500)}\n\n" if earlier else "")
            + f"User request: {state['request'].strip()[:600]}\n\nWORK SO FAR:\n"
            f"{_format_history(history, int(cfg('autopilot', 'history_chars', default=700)))}\n\n"
            + ("This is your LAST step: give the final answer now." if last else "Choose the next step."))
    done = {(h["tool"], json.dumps(h["args"], sort_keys=True, default=str)) for h in history if h.get("tool")}

    def validate(d: dict) -> dict:
        action = str(d.get("action", "")).strip().lower()
        if action in ("final", "answer", "done", "finish"):
            text = d.get("answer")
            if not isinstance(text, str) or not text.strip():
                raise ValueError('a final reply needs a non-empty "answer"')
            return {"final": text.strip(), "thought": str(d.get("thought") or "")}
        if last:
            raise ValueError('this is the last step: reply with "action": "final" and an "answer"')
        name = str(d.get("tool") or "").strip()
        spec = by_name.get(name) or next((s for n, s in by_name.items() if n.lower() == name.lower()), None)
        if spec is None:
            raise ValueError(f'"{name}" is not in the tool list. Choose one of: {sorted(by_name)}')
        args = d.get("args") if isinstance(d.get("args"), dict) else {}
        try:
            clean = validate_args(spec, args)
            policy.check_step(spec.domain, spec.name, clean)
        except (ValueError, PolicyError) as e:
            raise ValueError(f"{e}. Fix the arguments, choose another tool, or give the final answer")
        if (spec.name, json.dumps(clean, sort_keys=True, default=str)) in done:
            raise ValueError("You already ran that exact step. Use its result, or give the final answer")
        return {"tool": spec.name, "args": clean, "domain": spec.domain, "risk": spec.risk,
                "thought": str(d.get("thought") or "")}

    _emit("Thinking about the next step")
    try:
        d = ask_json(system, user, validate)
    except ModelError as e:
        return {"outcome": "error", "error": str(e), "auto_next": "final"}
    audit.log_event(state["task_id"], "autopilot", agent="autopilot",
                    detail={k: d.get(k) for k in ("thought", "tool", "args", "final") if d.get(k)})
    if "final" in d:
        actions = state.get("auto_actions") or []
        text = d["final"]
        if actions:
            text += "\n\n**What I did:**\n" + "\n".join(f"- {a}" for a in actions)
        return {"auto_next": "final", "outcome": "done" if actions else "no_action",
                "proposal": {"diagnosis": text, "fix": None}}
    if d["risk"] != R0 and _ui_granted(state.get("auto_ui_windows") or [], d["tool"], d["args"]):
        _emit(f"Continuing in the window you already approved: {describe(d['tool'], d['args'])[0]}", d["tool"])
        return {"auto_pending": d, "auto_next": "run", "auto_approved": True}
    return {"auto_pending": d, "auto_next": "run" if d["risk"] == R0 else "approve"}


def _process_name(pid) -> str:
    try:
        import psutil
        return psutil.Process(int(pid)).name()
    except Exception:
        return "the process"


def describe(tool: str, args: dict) -> tuple[str, str]:
    """(summary, what will change) for the approval card. Shows the exact content the user is approving."""
    spec = TOOLS[tool]
    shown = {k: str(v).replace("_", " ") for k, v in args.items()}
    try:
        summary = spec.summary.format(**shown) if spec.summary else spec.description
    except (KeyError, IndexError):
        summary = spec.description
    if tool == "close_process" and args.get("pid"):
        summary = f"Close {_process_name(args['pid'])} (PID {args['pid']})"
    elif not spec.summary and args:                 # no template: say exactly what it will act on
        summary = f"{spec.description.rstrip('.')} ({', '.join(f'{k}: {v}' for k, v in shown.items())})"
    if tool == "run_powershell":
        body = f"**Exact command:**\n\n```\n{args['command']}\n```\n" + (f"\nWhy: {args.get('purpose')}\n" if args.get("purpose") else "")
    elif tool in ("mail_send", "mail_create_draft"):
        body = f"**To:** {args['to']}  \n**Subject:** {args['subject']}\n\n{args['body']}\n"
    elif tool == "write_text_file":
        preview = args["content"][:600] + ("..." if len(args["content"]) > 600 else "")
        body = f"**File:** `{args['path']}` ({args.get('mode', 'create')})\n\n```\n{preview}\n```\n"
    elif tool in UI_TOOLS or tool == "open_application":
        body = ("\n".join(f"- {k}: {v}" for k, v in args.items()) + "\n\n"
                "If you approve, Tobi can keep working in this window for the rest of this task (clicks, keys, typing) "
                "without asking again for each step. You can see every step in the live view.\n")
    elif tool == "calendar_create_event":
        body = (f"**{args['subject']}**  \n{args['start']} to {args['end']}" +
                (f"  \nInvites: {args['attendee']}" if args.get("attendee") else "") + "\n")
    else:
        body = "\n".join(f"- {k}: {v}" for k, v in args.items()) + ("\n" if args else "")
    return summary, f"{body}\n{spec.change_note}".strip()


def approval_node(state: dict) -> dict:
    p = state["auto_pending"]
    summary, changes = describe(p["tool"], p["args"])
    _emit(f"Waiting for your approval: {summary}", p["tool"])
    from agent import voice
    answer = interrupt({
        "agent": "Autopilot", "say": voice.offer(summary),
        "diagnosis": p.get("thought") or "Autopilot wants to take this step.",
        "summary": summary, "what_changes": changes, "risk": p["risk"], "steps": [summary],
    })
    approved = bool(answer.get("approved")) if isinstance(answer, dict) else bool(answer)
    audit.log_event(state["task_id"], "approval", agent="autopilot", tool=p["tool"], args=p["args"],
                    risk_level=p["risk"], detail="approved" if approved else "rejected")
    if approved:
        out = {"auto_approved": True}
        if p["tool"] in UI_TOOLS or p["tool"] == "open_application":      # one approval covers this window for the task
            key = _window_key(p["tool"], p["args"])
            if key:
                out["auto_ui_windows"] = list(state.get("auto_ui_windows") or []) + [key]
        return out
    history = list(state.get("auto_history") or [])
    history.append({"note": f"The user REJECTED {p['tool']}({json.dumps(p['args'], default=str)[:150]}). "
                            "Do not try the same action again; offer an alternative or give the final answer."})
    return {"auto_approved": False, "auto_history": history, "auto_steps": state.get("auto_steps", 0) + 1,
            "auto_pending": None}


def run_node(state: dict) -> dict:
    p = state["auto_pending"]
    spec = TOOLS[p["tool"]]
    runner = ToolRunner(state["task_id"], spec.domain, calls_made=state.get("tool_calls", 0))
    _emit(f"Running {p['tool']}", p["tool"])
    try:
        result = runner.run(p["tool"], p["args"], approved=bool(state.get("auto_approved")) or spec.risk == R0)
    except PolicyError as e:
        result = {"ok": False, "error": f"Blocked by the safety policy: {e}"}
    history = list(state.get("auto_history") or [])
    history.append({"tool": p["tool"], "args": p["args"], "result": result})
    actions = list(state.get("auto_actions") or [])
    if spec.risk > R0 and result.get("ok") is not False:
        actions.append(describe(p["tool"], p["args"])[0])
        _emit(f"Done: {describe(p['tool'], p['args'])[0]}", p["tool"], image=live.capture(state["task_id"], p["tool"]))
    return {"auto_history": history, "auto_actions": actions, "auto_steps": state.get("auto_steps", 0) + 1,
            "tool_calls": runner.calls_made, "auto_approved": False, "auto_pending": None}
