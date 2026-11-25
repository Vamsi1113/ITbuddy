"""LangGraph workflow: route -> diagnose -> policy gate -> approval -> execute -> verify -> report.

The approval node only calls interrupt(), so nothing is re-run when the graph resumes.
"""
from __future__ import annotations

import json
import sqlite3
from typing import TypedDict

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.config import get_stream_writer
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from agent import autopilot, basis, live, memory, router, specialists, voice
from agent.llm import ModelError
from agent.specialists import COMPUTER_USE, DOMAINS, LABELS
from appconfig import cfg, data_path
from safety import audit, policy
from safety.policy import PolicyError, ToolRunner
from safety.redact import redact
from tools import printing, tickets


class State(TypedDict, total=False):
    task_id: str
    request: str
    agent: str             # a domain name, or "none"
    question: str
    plan: list             # [{"tool", "args"}] read-only checks chosen for this request
    diagnostics: dict      # tool name -> tool output (the "before" measurements)
    proposal: dict         # diagnosis, fix, summary, what_changes, steps
    decision: str          # approved | rejected
    fix_results: list
    comparison: list       # [{"metric", "before", "after"}]
    verify_note: str
    ticket: dict           # {"ref", "priority", "category"} when a ticket was opened
    secret_found: bool
    outcome: str           # fixed | not_fixed | rejected | refused | no_action | escalated | unsupported | chat | error
    cu_choice: dict        # Computer Use: the task already picked while routing
    history: list          # earlier turns of this chat [{"role": "user"|"assistant", "text"}]
    original_request: str  # what the user typed, before a follow-up was made standalone
    report: str
    error: str
    basis: list            # the short "Steps taken" lines: the rules, sources and checks behind the answer
    tool_calls: int
    mode: str              # "autopilot" forces the general agent
    auto_history: list     # Autopilot: what it did and saw so far
    auto_pending: dict     # Autopilot: the step waiting to run or to be approved
    auto_next: str         # run | approve | final
    auto_approved: bool
    auto_steps: int
    auto_actions: list     # changes Autopilot made, for the report
    auto_ui_windows: list  # app windows the user already approved for hands-on work in this task


def _emit(agent: str | None, text: str, tool: str | None = None, image: str | None = None) -> None:
    """Live status line for the interface (optionally with a screenshot of what just happened)."""
    try:
        get_stream_writer()({"agent": LABELS.get(agent or "", "Tobi"), "tool": tool, "text": text, "image": image})
    except Exception:
        pass  # not running inside a stream


def _runner(state: State, agent: str | None = None) -> ToolRunner:
    return ToolRunner(state["task_id"], agent or state["agent"], calls_made=state.get("tool_calls", 0))


def _run(runner: ToolRunner, tool: str, args: dict | None = None, approved: bool = False, label: str = "") -> dict:
    _emit(runner.agent, label or f"Running {tool}", tool)
    result = runner.run(tool, args, approved=approved)
    if result.get("ok") is False:
        _emit(runner.agent, f"{tool} failed: {result.get('error') or result.get('output')}", tool)
    elif approved:      # a change was made: show what the screen looks like now
        _emit(runner.agent, f"Done: {label or tool}", tool, image=live.capture(runner.task_id, tool))
    return result


def _open_ticket(state: State, title: str, summary: str, category: str = "incident", priority: str = "P3") -> dict:
    """Open a ticket with the full context package, so the user never has to repeat themselves."""
    notes = []
    for key, out in (state.get("diagnostics") or {}).items():
        notes.append(f"{key}: {json.dumps(out, default=str)[:400]}")
    proposal = state.get("proposal") or {}
    if proposal.get("summary"):
        notes.append(f"Fix proposed: {proposal['summary']} (decision: {state.get('decision', 'n/a')})")
    for r in state.get("fix_results") or []:
        notes.append(f"Fix result: {json.dumps(r, default=str)[:300]}")
    ticket = tickets.create_ticket(title, summary, category=category, priority=priority,
                                   task_id=state["task_id"], work_notes="\n".join(notes))
    audit.log_event(state["task_id"], "ticket", agent=state.get("agent"), detail=ticket)
    _emit(state.get("agent"), f"Opened ticket {ticket['ref']} for IT")
    return ticket


# ---------------------------------------------------------------------------
# Nodes
# ---------------------------------------------------------------------------
def route_node(state: State) -> dict:
    task_id = state["task_id"]
    request, secret_found = redact(state["request"])
    original = request
    history = state.get("history") or []
    if memory.needs_context(request, history):
        # a follow-up ("close the biggest one"): make it a complete request from the earlier conversation
        _emit(None, "Reading the earlier conversation")
        request, more_secrets = redact(memory.standalone(request, history))
        secret_found = secret_found or more_secrets
        if request != original:
            _emit(None, f"Understood as: {request[:120]}")
    audit.start_task(task_id, request)
    if request != original:
        audit.log_event(task_id, "context", detail={"typed": original, "understood_as": request})
    base = {"request": request, "original_request": original, "secret_found": secret_found, "tool_calls": 0}
    sensitive = policy.sensitive_reason(request)
    if sensitive:
        reasons = policy.sensitive_reasons(request)
        quick = COMPUTER_USE.quick_pick(request)
        # Only when it is the ONLY sensitive part of the request:
        #  - an approved-catalogue install (user approves first)
        #  - a password reset/unlock, which is answered by opening the official self-service page
        if quick and ((quick["task"] == "install_software" and reasons == {policy.R3_SOFTWARE})
                      or (quick["task"] in ("password_reset", "clarify", "hello_sign_in") and reasons == {policy.R3_PASSWORD})):
            sensitive = None
    if sensitive:
        category, why = sensitive
        audit.log_event(task_id, "route", agent="it_request", detail=f"R3 request, not executed: {why}")
        ticket = _open_ticket({**state, **base, "agent": "it_request"}, request[:100],
                              f"{request}\n\nNot done by Tobi: {why}.", category, "P3")
        return {**base, "agent": "it_request", "outcome": "escalated", "ticket": ticket, "error": why}
    if state.get("mode") == "autopilot":
        _emit("autopilot", "Autopilot mode: working it out step by step")
        return {**base, "agent": "autopilot"}
    _emit(None, "Router is choosing a specialist")
    try:
        choice = router.route(request)
    except ModelError as e:
        return {**base, "agent": "none", "outcome": "error", "error": str(e)}
    if (choice["agent"] == "devices" and printing.is_print_request(request) and not printing.is_print_problem(request)
            and not printing.is_print_status(request)):
        choice = {"agent": "workplace", "question": ""}         # nothing is broken: do not troubleshoot, answer from the rules
    audit.log_event(task_id, "route", agent=choice["agent"], detail=choice)
    if choice["agent"] == "none":
        # greetings, thanks, small talk, general or vague messages: a natural reply, not a list of features
        _emit(None, "Writing a reply")
        try:
            return {**base, "agent": "none", "outcome": "chat",
                    "question": specialists.chat_reply(original, history)}
        except ModelError as e:
            return {**base, "agent": "none", "outcome": "error", "error": str(e)}
    if choice["agent"] == "computer_use" and not COMPUTER_USE.quick_pick(request):
        # not one of the fixed computer tasks: the general agent can still work it out with its tools
        try:
            picked = COMPUTER_USE.pick_task(request)
        except ModelError:
            picked = {"task": "none"}
        if picked["task"] == "none":
            _emit("autopilot", "This needs a few steps: Autopilot is working it out")
            return {**base, "agent": "autopilot"}
        _emit("computer_use", f"Routed to the {LABELS['computer_use']} agent")
        return {**base, "agent": "computer_use", "cu_choice": picked}
    _emit(choice["agent"], f"Routed to the {LABELS[choice['agent']]} agent")
    return {**base, "agent": choice["agent"]}


def diagnose_node(state: State) -> dict:
    agent = state["agent"]
    try:
        if agent == "computer_use":
            return _diagnose_computer_use(state)
        if agent == "it_request":
            return _service_desk(state)
        if agent == "devices" and (printing.is_print_problem(state["request"]) or printing.is_print_status(state["request"])):
            return _diagnose_printing(state)
        if agent in ("performance", "storage") and specialists.memory_is_unclear(state["request"]):
            return _memory_overview(state)
        return _diagnose(state, DOMAINS[agent])
    except (ModelError, PolicyError) as e:
        return {"outcome": "error", "error": str(e)}


def _memory_overview(state: State) -> dict:
    """ "How much memory is left?": people mean storage as often as RAM, so measure both and say both."""
    _emit(state["agent"], "Checking your storage and memory")
    perf, disk = _runner(state, "performance"), _runner(state, "storage")
    health = _run(perf, "get_system_health", {})
    drives = _run(disk, "get_disk_usage", {})
    text = specialists.memory_overview_text(health, drives)
    return {"diagnostics": {"get_system_health": health, "get_disk_usage": drives},
            "tool_calls": perf.calls_made + disk.calls_made, "outcome": "no_action",
            "proposal": {"diagnosis": text, "fix": None, "reason": ""}}


def _diagnose(state: State, domain) -> dict:
    agent = domain.name
    runner = _runner(state)
    _emit(agent, "Choosing which checks to run")
    steps = specialists.plan(domain, state["request"])
    audit.log_event(state["task_id"], "plan", agent=agent, detail=steps)
    diagnostics = {}
    for key, step in zip(specialists.diag_keys(steps), steps):
        diagnostics[key] = _run(runner, step["tool"], step["args"])
    failed = [f"{t}: {o.get('error')}" for t, o in diagnostics.items() if o.get("ok") is False]
    if diagnostics and len(failed) == len(diagnostics):
        return {"plan": steps, "diagnostics": diagnostics, "tool_calls": runner.calls_made, "outcome": "error",
                "error": "The checks failed: " + "; ".join(failed)}
    general = agent == "howto" and bool(cfg("rag", "general_knowledge_fallback", default=True))
    access = diagnostics.get("get_printer_access_rules")
    if agent == "workplace" and access and access.get("ok") and not specialists.wants_access_action(state["request"]):
        # another ODC's printer: the answer comes straight from the organisation's rules, not from the model
        proposal = specialists.access_proposal(access)
        audit.log_event(state["task_id"], "proposal", agent=agent, tool=None,
                        detail={"diagnosis": proposal["diagnosis"][:200]})
        return {"plan": steps, "diagnostics": diagnostics, "proposal": proposal, "tool_calls": runner.calls_made,
                "outcome": "no_action"}
    try:
        if general and not specialists.kb_found_something(diagnostics):
            proposal = None                       # nothing in the knowledge base: skip straight to general knowledge
        else:
            _emit(agent, "Writing the answer (the local model can take a minute)")
            proposal = specialists.answer(domain, state["request"], diagnostics)
            if general and not proposal.get("fix") and specialists.kb_missed(proposal["diagnosis"]):
                proposal = None                   # the articles found do not answer this question
        if proposal is None:
            _emit(agent, "Nothing in the knowledge base: answering from general knowledge")
            proposal = specialists.general_answer(state["request"], state.get("history"))
    except ModelError as e:
        return {"plan": steps, "diagnostics": diagnostics, "tool_calls": runner.calls_made,
                "outcome": "error", "error": str(e)}
    audit.log_event(state["task_id"], "proposal", agent=agent, tool=proposal.get("fix"),
                    detail={k: proposal.get(k) for k in ("diagnosis", "summary", "reason")})
    out = {"plan": steps, "diagnostics": diagnostics, "proposal": proposal, "tool_calls": runner.calls_made}
    if not proposal["fix"]:
        out["outcome"] = "no_action"
    return out


def _diagnose_printing(state: State) -> dict:
    """Printing: one read-only pass over every layer, then fixes for the computer side and steps for the rest."""
    runner = _runner(state, "devices")
    file_name = printing.extract_file_name(state["request"])
    _emit("devices", "Checking the print service, printers, queue and connection")
    found = _run(runner, "diagnose_printing", {"file": file_name} if file_name else {}, label="Troubleshooting printing")
    if found.get("ok") is False:
        return {"diagnostics": {"diagnose_printing": found}, "tool_calls": runner.calls_made, "outcome": "error",
                "error": f"The printing checks failed: {found.get('error')}"}
    proposal = specialists.print_proposal(printing.last())
    audit.log_event(state["task_id"], "proposal", agent="devices", tool=proposal.get("fix"),
                    detail={k: proposal.get(k) for k in ("diagnosis", "summary")})
    out = {"diagnostics": {"diagnose_printing": found}, "proposal": proposal, "tool_calls": runner.calls_made}
    if not proposal["fix"]:
        out["outcome"] = "no_action"
    return out


def _service_desk(state: State) -> dict:
    _emit("it_request", "Reading the request")
    choice = specialists.intake(state["request"])
    audit.log_event(state["task_id"], "proposal", agent="it_request", detail=choice)
    runner = _runner(state)
    if choice["action"] == "create":
        ticket = _open_ticket(state, choice["title"], choice["summary"], choice["category"], choice["priority"])
        return {"ticket": ticket, "outcome": "escalated",
                "proposal": {"diagnosis": f"I understood your request as: {choice['summary']}", "fix": "escalate"}}
    if choice["action"] == "status":
        out = _run(runner, "get_ticket", {"ticket": choice["ticket"]})
        text = (f"Ticket {out['ref']} \"{out['title']}\" is {out['status']} (priority {out['priority']}, opened "
                f"{out['created']})." if out.get("ok") else out.get("error", "I could not find that ticket."))
    else:
        out = _run(runner, "list_my_tickets")
        rows = out.get("tickets", [])
        text = ("You have no tickets yet." if not rows else "Your most recent tickets:\n\n" + "\n".join(
            f"- **{t['ref']}** {t['title']} — {t['status']}, {t['priority']}, opened {t['created']}" for t in rows))
    return {"diagnostics": {"tickets": out}, "tool_calls": runner.calls_made, "outcome": "no_action",
            "proposal": {"diagnosis": text, "fix": None}}


def _diagnose_computer_use(state: State) -> dict:
    _emit("computer_use", "Working out which task this is")
    choice = state.get("cu_choice") or COMPUTER_USE.pick_task(state["request"])
    audit.log_event(state["task_id"], "proposal", agent="computer_use", detail=choice)
    if choice["task"] == "none":
        return {"outcome": "unsupported", "question":
                "I can open websites, apps and folders, search the web and open a result, install approved software, "
                "write text you put in quotes into Notepad and save it, write a system health note in Notepad, "
                "or download the latest report from the test portal. Tell me which one you want, for example "
                "\"open youtube.com in Chrome\" or \"install 7-Zip\". For anything else, tell me what the problem is."}
    if policy.is_read_only():
        return {"outcome": "refused", "error": "Read-only mode is on, so no changes can be made."}
    try:
        if choice["task"] == "open_website":
            return {"diagnostics": {}, "proposal": COMPUTER_USE.plan_open_website(choice)}
        if choice["task"] == "open_app":
            return {"diagnostics": {}, "proposal": COMPUTER_USE.plan_open_app(choice["app"])}
        if choice["task"] == "write_note":
            if choice.get("compose"):            # the user described the content: write it first, show it, then save
                _emit("computer_use", "Writing the note for you")
                try:
                    wrote = specialists.compose_note(state["request"], state.get("history"))
                except ModelError as e:
                    return {"outcome": "error", "error": f"I could not write the note: {e}"}
                choice = {**choice, "text": wrote["text"], "intro": wrote["intro"],
                          "filename": choice.get("filename") or wrote["title"]}
            return {"diagnostics": {}, "proposal": COMPUTER_USE.plan_write_note(choice)}
        if choice["task"] == "open_folder":
            return {"diagnostics": {}, "proposal": COMPUTER_USE.plan_open_folder(choice["folder"])}
        if choice["task"] == "open_file":
            proposal = COMPUTER_USE.plan_open_file(choice)
            return {"diagnostics": {}, "proposal": proposal, **({} if proposal["fix"] else {"outcome": "no_action"})}
        if choice["task"] == "delete_file":
            proposal = COMPUTER_USE.plan_delete_file(choice)
            return {"diagnostics": {}, "proposal": proposal, **({} if proposal["fix"] else {"outcome": "no_action"})}
        if choice["task"] == "save_as_pdf":
            proposal = COMPUTER_USE.plan_save_as_pdf(choice)
            return {"diagnostics": {}, "proposal": proposal, **({} if proposal["fix"] else {"outcome": "no_action"})}
        if choice["task"] == "search_web":
            return {"diagnostics": {}, "proposal": COMPUTER_USE.plan_search_web(choice)}
        if choice["task"] == "find_site":
            # Search agent: look the site up on the web first (read-only), then propose opening the best match.
            wr = _runner(state, "web")
            found = _run(wr, "web_search", {"query": f"{choice['query']} official website"},
                         label=f"Searching the web for {choice['query']}")
            return {"diagnostics": {"web_search": found}, "tool_calls": wr.calls_made,
                    "proposal": COMPUTER_USE.plan_find_site(choice, found.get("results") or [], found.get("error", ""))}
        if choice["task"] == "install_software":
            proposal = COMPUTER_USE.plan_install(choice["package"])
            return {"diagnostics": {}, "proposal": proposal, **({} if proposal["fix"] else {"outcome": "no_action"})}
    except (ValueError, PolicyError) as e:
        return {"outcome": "refused", "error": f"{e}."}
    if choice["task"] == "clarify":           # the request could mean different things: ask first, do nothing yet
        return {"outcome": "chat", "question": choice["question"]}
    if choice["task"] == "hello_sign_in":
        return {"diagnostics": {}, "proposal": COMPUTER_USE.plan_hello_sign_in()}
    if choice["task"] == "password_reset":
        try:
            return {"diagnostics": {}, "proposal": COMPUTER_USE.plan_password_reset()}
        except PolicyError as e:
            return {"outcome": "refused", "error": f"{e}."}
    if choice["task"] == "browser_task":
        return {"diagnostics": {}, "proposal": COMPUTER_USE.plan_browser_task(choice["task_id"])}
    # The health numbers come from the Performance and Storage agents' read-only tools.
    perf = _runner(state, "performance")
    health = _run(perf, "get_system_health", label="Collecting system health")
    stor = ToolRunner(state["task_id"], "storage", calls_made=perf.calls_made)
    disks = _run(stor, "get_disk_usage", label="Collecting disk usage")
    if health.get("ok") is False:
        return {"tool_calls": stor.calls_made, "outcome": "error",
                "error": f"Could not read the system health: {health.get('error')}"}
    return {"diagnostics": {"get_system_health": health, "get_disk_usage": disks},
            "proposal": COMPUTER_USE.plan_health_note(health, disks), "tool_calls": stor.calls_made}


def gate_node(state: State) -> dict:
    """Policy gate: Python checks tier, allow-lists, read-only mode and the tool budget before anything pauses or runs."""
    steps = state["proposal"]["steps"]
    try:
        for step in steps:
            step["args"] = policy.check_step(step.get("domain") or state["agent"], step["tool"], step["args"])
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
        "say": proposal.get("ask") or voice.offer(proposal["summary"]),
        "style": "offer" if proposal.get("offer") else "action",
        "diagnosis": proposal["diagnosis"],
        "summary": proposal["summary"],
        "what_changes": proposal["what_changes"],
        "risk": proposal.get("risk", policy.R1),
        "steps": [s["label"] for s in proposal["steps"]],
    })
    approved = bool(answer.get("approved")) if isinstance(answer, dict) else bool(answer)
    decision = "approved" if approved else "rejected"
    audit.log_event(state["task_id"], "approval", agent=state["agent"], tool=proposal["fix"],
                    args=[s["args"] for s in proposal["steps"]], risk_level=proposal.get("risk", policy.R1),
                    detail=decision)
    return {"decision": decision, **({} if approved else {"outcome": "rejected"})}


def execute_node(state: State) -> dict:
    if state["proposal"]["fix"] == "escalate":   # the approved action is "open a ticket"
        ticket = _open_ticket(state, state["request"][:100],
                              f"{state['request']}\n\nTobi's finding: {state['proposal']['diagnosis']}",
                              "security" if state["agent"] == "security" else "incident")
        return {"ticket": ticket, "outcome": "escalated"}
    runner = _runner(state)
    results = []
    for step in state["proposal"]["steps"]:
        try:
            if step.get("domain"):      # a step may use a tool from another domain (for example the directory connector)
                runner.agent = step["domain"]
            result = _run(runner, step["tool"], step["args"], approved=True, label=step["label"])
        except PolicyError as e:
            result = {"ok": False, "error": str(e)}
        results.append(result)
        if result.get("ok") is False:
            break  # stop the plan at the first failed step
    return {"fix_results": results, "tool_calls": runner.calls_made}


def verify_node(state: State) -> dict:
    agent = state["agent"]
    proposal = state.get("proposal") or {}
    if proposal.get("offer") and not proposal.get("recheck"):   # a small extra the user said yes to: nothing to re-check
        ok = all(r.get("ok") is not False for r in state.get("fix_results", []))
        # "done", not "fixed": opening a page is not a verified fix, so no "Done and verified" badge
        return {"comparison": [], "verify_note": "", "outcome": "done" if ok else "not_fixed"}
    _emit(agent, "Checking the result: running the checks again")
    runner = _runner(state)
    try:
        v = specialists.verify(runner, state)
    except PolicyError as e:
        v = {"comparison": [], "fixed": False, "note": f"Could not verify: {e}"}
    # A fix whose step failed is never reported as fixed, whatever the re-check shows.
    if any(r.get("ok") is False for r in state.get("fix_results", [])):
        v["fixed"] = False
        v["note"] = "The fix did not complete, so the problem is not confirmed as solved."
    audit.log_event(state["task_id"], "result", agent=agent, detail=v)
    if v["fixed"] and agent == "computer_use":
        v["comparison"] = []          # a simple task that worked: a one-line "Done!", no Before/After table
    simple = v["fixed"] and proposal.get("verify") == "steps_ok"     # "opened X": done, but nothing to verify
    out = {"comparison": v["comparison"], "verify_note": v["note"],
           "outcome": "done" if simple else "fixed" if v["fixed"] else "not_fixed", "tool_calls": runner.calls_made}
    if not v["fixed"] and agent != "computer_use":       # a computer task that did not work is not an IT incident
        merged = {**state, **out}
        out["ticket"] = _open_ticket(merged, state["request"][:100],
                                     f"{state['request']}\n\nTobi tried: {state['proposal'].get('summary')}. "
                                     f"Result: {v['note']}", "incident", "P3")
    return out


def _alternatives(agent: str) -> str:
    return {
        "performance": "Other options: save your work and close the app yourself, restart the computer, or ask me to raise a ticket.",
        "storage": "Other options: empty the Recycle Bin, move large files to a network or cloud folder, or ask me to raise a ticket.",
        "network": "Other options: turn Wi-Fi off and on, restart the computer, or ask me to raise a ticket.",
        "computer_use": "You can do the task by hand, or ask again with different wording.",
    }.get(agent, "You can make the change yourself, or ask me to raise a ticket for IT.")


def _ticket_line(ticket: dict | None) -> str:
    if not ticket:
        return ""
    return (f"I opened ticket **{ticket['ref']}** (priority {ticket['priority']}) for the IT team with everything "
            "I found, so you do not need to explain it again. Ask me \"status of " + ticket["ref"] + "\" any time.")


def report_node(state: State) -> dict:
    outcome = state.get("outcome", "error")
    agent = state.get("agent")
    proposal = state.get("proposal") or {}
    ticket = state.get("ticket")
    parts = []
    if outcome == "escalated" and not proposal:
        parts.append(f"I can't do this myself. {state.get('error')}.")
        parts.append(_ticket_line(ticket))
    elif outcome == "escalated":
        parts.append(proposal.get("diagnosis", ""))
        parts.append(_ticket_line(ticket))
    elif outcome == "refused":
        parts.append(f"The safety policy blocked this action: {state.get('error')} Nothing was changed.")
    elif outcome == "chat":
        parts.append(state.get("question") or "Hi! What can I help you with today?")
    elif outcome == "unsupported":
        parts.append(state.get("question") or
                     "I did not understand that as an IT request. Tell me what is wrong with your computer, "
                     "account, network, printer or software, or ask me how to do something.")
    elif outcome == "error":
        parts.append(f"I had to stop: {state.get('error')} Nothing was changed.")
    else:
        if outcome == "rejected" and proposal.get("offer"):
            parts.append("No problem! Just ask if you need anything else.")
            outcome = "chat"                          # a "no thanks" to a small offer: a plain reply, no status badge
        elif outcome == "rejected":
            parts.append(voice.declined() + " " + _alternatives(agent))
        elif outcome in ("fixed", "done", "not_fixed"):
            # the diagnosis was already on the approval card: now just say what happened, like a person would
            failed = [r for r in state.get("fix_results", []) if r.get("ok") is False]
            if outcome in ("fixed", "done"):
                parts.append(voice.done(proposal.get("summary", ""), state.get("verify_note", "")))
            else:
                why = (failed[0].get("error") or failed[0].get("output")) if failed else state.get("verify_note")
                parts.append(voice.failed(proposal.get("summary", ""), str(why or "")))
                if ticket:
                    parts.append(_ticket_line(ticket))
        else:
            parts.append(proposal.get("diagnosis", ""))
    if state.get("secret_found"):
        parts.append("⚠️ Your message contained what looks like a password or key. I removed it before reading "
                     "or logging the message. Never share passwords in chat; if it was real, change it now.")
    report = "\n\n".join(p.strip() for p in parts if p and p.strip())
    audit.log_event(state["task_id"], "report", agent=agent, detail={"outcome": outcome, "report": report})
    audit.finish_task(state["task_id"], agent, outcome, report)
    try:
        lines = basis.build({**state, "outcome": outcome})
    except Exception:                  # the explanation must never break an answer
        lines = []
    return {"report": report, "outcome": outcome, "basis": lines}


# ---------------------------------------------------------------------------
# Wiring
# ---------------------------------------------------------------------------
def _next_or_report(next_node: str):
    return lambda state: "report" if state.get("outcome") else next_node


def _after_route(state: State) -> str:
    if state.get("outcome"):
        return "report"
    return "auto_think" if state.get("agent") == "autopilot" else "diagnose"


def _after_think(state: State) -> str:
    if state.get("outcome") or state.get("auto_next") == "final":
        return "report"
    return "auto_run" if state.get("auto_next") == "run" else "auto_approval"


def build_graph(checkpointer=None):
    g = StateGraph(State)
    g.add_node("route", route_node)
    g.add_node("diagnose", diagnose_node)
    g.add_node("gate", gate_node)
    g.add_node("approval", approval_node)
    g.add_node("execute", execute_node)
    g.add_node("verify", verify_node)
    g.add_node("report", report_node)
    g.add_node("auto_think", autopilot.think_node)
    g.add_node("auto_approval", autopilot.approval_node)
    g.add_node("auto_run", autopilot.run_node)
    g.add_edge(START, "route")
    g.add_conditional_edges("route", _after_route, ["diagnose", "auto_think", "report"])
    g.add_conditional_edges("auto_think", _after_think, ["auto_run", "auto_approval", "report"])
    g.add_conditional_edges("auto_approval", lambda s: "auto_run" if s.get("auto_approved") else "auto_think",
                            ["auto_run", "auto_think"])
    g.add_edge("auto_run", "auto_think")
    g.add_conditional_edges("diagnose", _next_or_report("gate"), ["gate", "report"])
    g.add_conditional_edges("gate", _next_or_report("approval"), ["approval", "report"])
    g.add_conditional_edges("approval", _next_or_report("execute"), ["execute", "report"])
    g.add_conditional_edges("execute", _next_or_report("verify"), ["verify", "report"])
    g.add_edge("verify", "report")
    g.add_edge("report", END)
    if checkpointer is None:
        conn = sqlite3.connect(data_path("checkpoint_db"), check_same_thread=False)
        checkpointer = SqliteSaver(conn)
    return g.compile(checkpointer=checkpointer)
