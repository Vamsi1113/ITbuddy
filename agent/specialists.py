"""The specialists. One generic engine serves every domain:

  plan(domain, request)            -> model picks 1-4 read-only tools from the domain's own list
  answer(domain, request, diag)    -> model answers from tool output and may pick ONE fix
  verify(domain, runner, state)    -> re-runs the diagnostics and compares before and after

A proposal is {"diagnosis", "fix", "reason", "summary", "what_changes", "steps": [{"tool", "args", "label"}]}.
"fix" is None (nothing to change), "escalate" (open a ticket) or a tool name.
Adding a capability = registering a tool in tools/. No change is needed here.
"""
from __future__ import annotations

import ctypes
import json
import os
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import psutil

from agent import prompts
from agent.llm import MalformedOutput, ask_json
from appconfig import cfg
from safety import policy
from safety.policy import PolicyError, ToolRunner
from tools import browser as browser_tools
from tools import tickets
from tools import printing
from tools.desktop import clean_url
from tools.software import find_installable, is_installed, wait_for_install
from tools.registry import TOOLS, catalogue_text, tools_for, validate_args

MAX_PLAN_TOOLS = 4


@dataclass(frozen=True)
class Domain:
    name: str
    label: str
    route_hint: str
    guidance: str = ""
    default_plan: tuple = field(default_factory=tuple)   # used if the model cannot produce a valid plan


DOMAINS: dict[str, Domain] = {d.name: d for d in (
    Domain("performance", "Performance",
           "which apps, programs, tasks or processes are running right now (what Task Manager shows); "
           "computer or an app is slow, freezing or lagging; something uses too much memory (RAM) or CPU; "
           "slow startup, restart needed, battery, computer name, model, serial number or Windows version.",
           "- For a slow computer always choose get_system_health and get_running_processes.\n"
           "- Name the process using the most memory. For close_process, \"pid\" must be the pid of "
           "largest_closable_process. Processes with \"closable\": false can never be closed.",
           (("get_system_health", {}), ("get_running_processes", {}))),
    Domain("storage", "Storage",
           "DISK space only (not memory/RAM): drive is full, low disk space, what uses disk space, temp files, "
           "recycle bin, app cache, disk health.",
           "- For a full disk always choose get_disk_usage and find_large_temp_folders.\n"
           "- State the free space and used percent, and how many MB can be freed.",
           (("get_disk_usage", {}), ("find_large_temp_folders", {}))),
    Domain("network", "Network",
           "no internet, Wi-Fi, websites not opening, DNS, VPN, proxy, a server or port unreachable, website "
           "certificate, call quality, wrong clock or time.",
           "- For 'websites do not open' choose check_network_connection and check_dns_resolution.\n"
           "- Propose flush_dns_cache when the network is connected but DNS lookups or websites fail, "
           "or when the user reports websites not opening and nothing else is wrong.",
           (("check_network_connection", {}), ("check_dns_resolution", {}), ("get_network_config", {}))),
    Domain("settings", "Settings",
           "is a Windows setting on or off, what is a setting's value (developer mode, dark mode, firewall, "
           "time zone, default browser, display, privacy), open a Settings page, switch dark mode or file extensions.",
           "- Report the setting's value exactly as TOOL OUTPUT gives it.\n"
           "- If the user asks to OPEN a settings page, the fix is open_settings_page with the matching page.\n"
           "- To change a personal preference the user asked for, use set_user_preference. For any other "
           "change the user asks for, use open_settings_page so the user can change it themselves.",
           (("read_common_settings", {}),)),
    Domain("software", "Software",
           "is a program installed, which version, what was installed recently, Windows Update status, "
           "is a program approved, wants a program installed.",
           "- Installing or removing software is never done here: choose the fix \"escalate\" for that.",
           (("find_installed_software", {}),)),
    Domain("devices", "Devices",
           "printer not printing, print queue stuck, printer offline, a document will not print, headset, microphone, "
           "speakers, camera, Bluetooth, monitor, keyboard, mouse, USB device not working.",
           "- Say which devices were found and their status.",
           (("list_problem_devices", {}),)),
    Domain("logs", "Crash and Error Log",
           "an app keeps crashing or freezing, blue screen, unexpected restart or shutdown, error messages, "
           "what went wrong recently.",
           "- Name the apps or sources with the most errors and when they last happened.",
           (("get_app_crashes", {}), ("get_recent_errors", {}))),
    Domain("security", "Security",
           "antivirus or firewall status, virus scan, threats found, suspicious link or phishing email.",
           "- Never suggest switching protection off.",
           (("get_antivirus_status", {}), ("get_firewall_status", {}))),
    Domain("account", "Account",
           "who am I signed in as, do I have admin rights, when does my password expire, account details.",
           "- Password resets, unlocks and MFA need IT: choose the fix \"escalate\" for those.",
           (("get_current_user", {}),)),
    Domain("workplace", "Workplace",
           "where the user is and what they may do there: which ODC / office / floor / seat I am in, which printer "
           "should I use or can I use, where can I print, which Wi-Fi or network can I connect to, which VPN, "
           "am I on a virtual desktop, print this file.",
           "- Use the facts in TOOL OUTPUT only: odc, floor, seat, located_by, printers (status ready / add_first / "
           "offline / not_allowed), conditions, how_to_add, allowed_wifi, vpn_rules, guidance.\n"
           "- Recommend ready printers first, the one on the user's floor first. For add_first give the how_to_add steps. "
           "For not_allowed say why_not. Mention every condition (secure release, approvals, page limits).\n"
           "- If odc is unknown say you could not tell where they sit and ask ONE question: which ODC (and floor or "
           "seat if they know). If they tell you, choose the fix set_my_location with odc, floor and seat.\n"
           "- If computer_type is avd, say this is a virtual desktop and use avd_note; do not claim the printers or "
           "Wi-Fi of the user's real PC are visible.\n"
           "- Another ODC's printer (access is request_required): say plainly that their ODC's printers are for people "
           "of that ODC and that access needs approval (cite the SOP); give the how_to_request steps in one line each; "
           "show the email text (to, subject, body) in a short block so they can copy it; offer the fix "
           "request_printer_access with target_odc and, if they gave one, the reason; then list their OWN ODC's printers "
           "(use_instead) and other_devices to continue with. If access is not_possible say why and do not offer a request.\n"
           "- If target_odc is unknown ask which ODC they mean; if the user's own ODC is unknown ask that first.\n"
           "- If the user asks to PRINT a file and a printer is ready, choose the fix print_file with the file and the "
           "best ready printer. If none is ready, explain what to do instead; never print on a printer that is not ready.\n"
           "- Cite the SOP from TOOL OUTPUT (the sop field or get_workplace_sop source) when you state a rule.",
           (("get_my_org_context", {}),)),
    Domain("howto", "Knowledge",
           "how do I ..., company IT policy, step-by-step instructions (connect VPN, add printer, out of office, "
           "report phishing, new starter, leaving).",
           prompts.HOWTO_GUIDANCE),
    Domain("it_request", "Service Desk",
           "needs IT staff: new hardware, access to an app or shared mailbox, password reset, install software, "
           "onboarding or offboarding, raise or check a ticket, talk to a person."),
    Domain("autopilot", "Autopilot",
           "multi-step tasks that need files, email, calendar, PowerShell, web pages, ServiceNow, Intune or several "
           "systems together: summarise my unread email, find a file and read it, what is on my calendar, "
           "look something up online, run a command."),
    Domain("computer_use", "Computer Use",
           "asks you to DO something on the computer for them: open a website or an app (open YouTube in Chrome, "
           "open Excel), search the web and open the result (search for a tool called HeyGen and open its website), "
           "open a folder, install an approved program (install Chrome, Zoom, 7-Zip), open Notepad and write or save "
           "something, open the test portal and download a report."),
)}

LABELS = {name: d.label for name, d in DOMAINS.items()}


# ---------------------------------------------------------------------------
# Plan: which read-only tools to run
# ---------------------------------------------------------------------------
_HOWTO_ERROR = re.compile(r"(?<!\w)(0x[0-9a-fA-F]{4,}|[A-Z]{2,}_[A-Z_]{2,}|error\s+(code\s+)?\d{3,})(?!\w)")
_HOWTO_POLICY = re.compile(r"(?<!\w)(policy|policies|byod|acceptable use|am i allowed|are we allowed|allowed to|"
                           r"company rules?|compliance)(?!\w)", re.IGNORECASE)
_HOWTO_SOP = re.compile(r"(?<!\w)(sops?|standard operating|procedures?|odc|am i allowed|are we allowed|allowed to|"
                        r"which printers?|what printers?|rules? for|company rules?|allowed|"
                        r"can\s+(?:i|we)\s+(?:print|use|install|bring|plug|connect|copy|share))(?!\w)", re.IGNORECASE)
_HOWTO_TICKETS = re.compile(r"(?<!\w)((similar|past|previous|earlier)\s+(tickets?|incidents?|cases?)|"
                            r"(happened|seen)\s+before)(?!\w)", re.IGNORECASE)


def route_howto(request: str) -> list[dict]:
    """Pick the best knowledge tool for a how-to request. Deterministic: no model call, no extra latency."""
    q = request.strip()[:300]
    if _HOWTO_ERROR.search(q):
        return [{"tool": "lookup_error_code", "args": {"code_or_message": q}}]
    if _HOWTO_TICKETS.search(q):
        return [{"tool": "find_similar_tickets", "args": {"symptoms": q}}]
    if _HOWTO_SOP.search(q) or _HOWTO_POLICY.search(q):
        tool = "lookup_sop" if "lookup_sop" in TOOLS else "lookup_policy"
        return [{"tool": tool, "args": {"topic": q}}]
    return [{"tool": "search_knowledge_base", "args": {"query": q}}]


_WP_OTHER_PLACE = re.compile(
    r"(?<!\w)(other|another|different|side|neighbou?ring|nearby|next|that|their)\s+(?:\w+\s+){0,2}(?:odc|block|office|floor|building|site|location)s?(?!\w)"
    r"|(?<!\w)odc\s*['\"\u2018\u2019]?[\w-]+", re.IGNORECASE)
_WP_NETWORK = re.compile(r"(?<!\w)(wi-?fi|wireless|ssid|vpn|network|internet|lan|connect(?:ed)? to)(?!\w)", re.IGNORECASE)
_WP_PRINT = re.compile(r"(?<!\w)(print|printer|printers|printing)(?!\w)", re.IGNORECASE)


_LEAD_WORDS = {"which", "what", "printer", "printers", "should", "i", "use", "for", "to", "on", "the", "my", "can", "please",
               "print", "send", "this", "that", "a", "me", "it", "want", "need", "where", "is", "do", "how", "with", "file"}


def _strip_lead_words(name: str) -> str:
    """'printer should I use for plan.pdf' -> 'plan.pdf': a file name picked out of a sentence may carry leading words."""
    words = (name or "").split()
    last_filler = max((i for i, w in enumerate(words[:-1]) if w.lower() in _LEAD_WORDS), default=-1)
    return " ".join(words[last_filler + 1:])


def route_workplace(request: str) -> list[dict]:
    """Which read-only checks answer a workplace question. Deterministic: no model call."""
    q = request.strip()[:300]
    steps = []
    from tools import org_rules
    if _WP_PRINT.search(q) and (_WP_OTHER_PLACE.search(q) or org_rules.resolve_odc(q)):
        # a printer somewhere else: what the rules say, how to ask for access, and what to use meanwhile
        return [{"tool": "get_printer_access_rules", "args": {"target": q}},
                {"tool": "get_workplace_sop", "args": {"topic": "printer access for other ODC request approval"}}]
    if _WP_PRINT.search(q):
        from tools import printing
        name = _strip_lead_words(printing.extract_file_name(q))
        steps.append({"tool": "get_my_print_options", "args": {"file": name} if name else {}})
        topic = "printing"
    elif _WP_NETWORK.search(q):
        steps.append({"tool": "get_my_network_options", "args": {}})
        topic = "wifi vpn network access"
    else:
        steps.append({"tool": "get_my_org_context", "args": {}})
        topic = ""
    if topic and "get_workplace_sop" in TOOLS:
        steps.append({"tool": "get_workplace_sop", "args": {"topic": f"{topic} {q}"[:300]}})      # the SOP text to cite
    return steps


def plan(domain: Domain, request: str) -> list[dict]:
    """Return [{"tool", "args"}]. Falls back to the domain's default plan if the model output stays malformed."""
    if domain.name == "workplace":
        return route_workplace(request)
    if domain.name == "howto":
        steps = route_howto(request)
        if all(st["tool"] in TOOLS for st in steps):   # RAG tools are optional; fall back to the base search
            return steps
        return [{"tool": "search_knowledge_base", "args": {"query": request.strip()[:300]}}]
    specs = tools_for(domain.name, read_only=True)
    names = {s.name for s in specs}
    system = (prompts.PLANNER.replace("{label}", domain.label).replace("{guidance}", domain.guidance)
              .replace("{catalogue}", catalogue_text(specs)))

    def validate(d: dict) -> list[dict]:
        items = d.get("tools")
        if not isinstance(items, list) or not items:
            raise ValueError('"tools" must be a list with 1 to 4 entries')
        out, seen = [], set()
        for item in items[:MAX_PLAN_TOOLS]:
            if isinstance(item, str):
                item = {"tool": item, "args": {}}
            name = str(item.get("tool", "")).strip()
            if name not in names:
                raise ValueError(f'"{name}" is not in the tool list. Choose from {sorted(names)}')
            args = validate_args(TOOLS[name], item.get("args") if isinstance(item.get("args"), dict) else {})
            key = (name, json.dumps(args, sort_keys=True))
            if key not in seen:
                seen.add(key)
                out.append({"tool": name, "args": args})
        return out

    try:
        return ask_json(system, f"User request: {request.strip()[:500]}", validate)
    except MalformedOutput:
        if not domain.default_plan:
            raise
        return [{"tool": t, "args": dict(a)} for t, a in domain.default_plan]


# ---------------------------------------------------------------------------
# Answer: diagnosis from tool output + at most one fix
# ---------------------------------------------------------------------------
def _describe(tool: str, args: dict, diagnostics: dict) -> tuple[str, str]:
    """(summary, what will change) for the approval card."""
    spec = TOOLS[tool]
    if tool == "close_process":
        try:
            p = psutil.Process(args["pid"])
            name, mem = p.name(), round(p.memory_info().rss / 1024 / 1024)
        except psutil.Error:
            name, mem = f"process {args['pid']}", "?"
        return (f"Close {name} (process {args['pid']})",
                f"{name} will be closed. It is using {mem} MB of memory. Unsaved work in that app will be lost.")
    if tool == "clean_approved_temp_files":
        temp = _first(diagnostics, "find_large_temp_folders")
        folders = ", ".join(f["folder"] for f in temp.get("folders", [])) or "the allowed temp folders"
        mb = temp.get("total_cleanable_mb", "?")
        age = cfg("storage", "min_file_age_minutes", default=60)
        return (f"Delete temporary files (about {mb} MB)",
                f"Temporary files older than {age} minutes will be deleted from: {folders}. About {mb} MB. "
                + spec.change_note)
    detail = ", ".join(f"{k}: {v}" for k, v in args.items())
    if spec.summary:
        summary = spec.summary.format(**{k: str(v).replace("_", " ") for k, v in args.items()})
    else:
        summary = spec.description.split(".")[0] + (f" ({detail})" if detail else "")
    return summary, spec.change_note or "This makes a small change on this computer."


def diag_keys(steps: list[dict]) -> list[str]:
    """Keys under which the outputs of planned steps are stored: 'tool', then 'tool#2' for a repeat."""
    keys, counts = [], {}
    for step in steps:
        n = counts[step["tool"]] = counts.get(step["tool"], 0) + 1
        keys.append(step["tool"] if n == 1 else f"{step['tool']}#{n}")
    return keys


def _first(diagnostics: dict, tool: str) -> dict:
    """Output of the first run of `tool` in the diagnostics (keys are 'tool' or 'tool#2')."""
    for key, value in diagnostics.items():
        if key.split("#")[0] == tool and isinstance(value, dict):
            return value
    return {}


def _match_fix(raw, fix_names: set) -> str | None:
    """Small models write the fix as 'close_process(pid=12)', 'Close Process' or null. Map it to a known name."""
    text = str(raw or "none").strip().lower().replace(" ", "_").replace("-", "_")
    if text in ("", "null", "no", "no_fix", "nothing", "n/a"):
        return "none"
    options = fix_names | {"none", "escalate"}
    if text in options:
        return text
    hits = [name for name in options if name in text]
    return hits[0] if len(hits) == 1 else None


def _collect_args(fix: str, reply: dict, diagnostics: dict) -> dict:
    """Arguments may sit in "args" or at the top level of the reply. Only declared names are taken."""
    names = [p.name for p in TOOLS[fix].params]
    given = reply.get("args") if isinstance(reply.get("args"), dict) else {}
    args = {n: given.get(n, reply.get(n)) for n in names if given.get(n, reply.get(n)) is not None}
    if fix == "close_process":
        # The only process the agent may propose is the largest closable one measured just now.
        closable = _first(diagnostics, "get_running_processes").get("largest_closable_process")
        if closable:
            args["pid"] = closable["pid"]
    return args


def _infer_settings_page(text: str) -> str | None:
    """Pick the Windows Settings page a request is about, for when the model leaves out the "page" argument."""
    from tools.settings import PAGES
    low = text.lower().replace("wi-fi", "wifi").replace("wi fi", "wifi")
    hits = [name for name in PAGES if re.search(r"(?<!\w)" + re.escape(name.replace("_", " ")) + r"(?!\w)", low)]
    return max(hits, key=len) if hits else None


def _with_next_choices(prompt: str) -> str:
    """Fill the pages and apps Tobi can open itself into a prompt."""
    from tools.settings import PAGES
    apps = ", ".join(sorted(cfg("desktop", "allowed_apps", default={}) or {}))
    return prompt.replace("{pages}", ", ".join(PAGES)).replace("{apps}", apps)


def closing_line(raw) -> str:
    """When there is no step Tobi can do itself, the model's friendly closing line (never a question that expects a button)."""
    if not isinstance(raw, dict) or str(raw.get("do") or "").strip().lower() not in ("", "none"):
        return ""
    line = re.sub(r"\s+", " ", str(raw.get("ask") or "")).strip()[:200]
    return line if line and not re.search(r"(?i)\bsay ok\b|\bjust say\b", line) else ""


def compose_note(request: str, history: list | None = None) -> dict:
    """Write the text the user asked to have in a note ("the steps to create a python file in VS Code and run it").
    Returns {"intro", "text", "title"}; the user sees the text on the approval card before anything is saved."""
    from agent.memory import as_text

    def validate(d: dict) -> dict:
        text = str(d.get("text") or "").replace("\r\n", "\n").strip()
        if not text:
            raise ValueError('"text" must be the note itself, non-empty')
        title = re.sub(r"[^\w .()-]", "", str(d.get("title") or "")).strip()[:60]
        return {"text": text[:6000], "title": title, "intro": str(d.get("intro") or "").strip()[:160]}

    earlier = f"EARLIER CONVERSATION:\n{as_text(history, 1500)}\n\n" if history else ""
    return ask_json(prompts.NOTE_WRITER, f"{earlier}User request: {request.strip()[:800]}", validate)


def next_step_offer(raw, diagnosis: str = "") -> dict:
    """The "next step" the model suggests, as a Yes/No offer Tobi can do itself (open a settings page or an allowed
    app). Anything unknown or unsafe is dropped silently: the answer is then given as it is."""
    if not isinstance(raw, dict) or policy.is_read_only():
        return {}
    ask = re.sub(r"\s+", " ", str(raw.get("ask") or "")).strip()[:160]
    do = str(raw.get("do") or "").strip().lower().replace(" ", "_")
    if do == "open_settings_page":
        from tools.settings import PAGES
        page = str(raw.get("page") or "").strip().lower().replace(" ", "_").replace("-", "_")
        if page not in PAGES:
            page = _infer_settings_page(f"{raw.get('page', '')} {ask}") or ""
        if page not in PAGES:
            return {}
        label = page.replace("_", " ")
        step = {"tool": "open_settings_page", "args": {"page": page}, "domain": "settings",
                "label": f"Open the {label} settings"}
        summary = f"Open the {label} settings"
    elif do == "open_application":
        apps = cfg("desktop", "allowed_apps", default={}) or {}
        name = str(raw.get("app") or "").strip().lower()
        if name not in apps:
            return {}
        step = {"tool": "open_application", "args": {"name": name}, "domain": "computer_use", "label": f"Open {name.title()}"}
        summary = f"Open {name.title()}"
    else:
        return {}
    # The question must name what will really open ("open Disk Management" must not open the Storage page)
    target = step["args"].get("page") or step["args"].get("name") or ""
    stems = {w[:4] for w in re.split(r"[\s_\-]+", target.lower()) if len(w) > 2 and w not in ("the", "and", "settings")}
    asked = {w[:4] for w in re.findall(r"[a-z]+", ask.lower())}
    if not ask or "?" not in ask or not stems <= asked:
        what = f"the {target.replace('_', ' ')} settings" if step["tool"] == "open_settings_page" else target.title()
        ask = f"Want me to open {what} for you?"
    return {"fix": "computer_use_task", "risk": policy.R1, "summary": summary, "offer": True, "ask": ask,
            "what_changes": "Nothing on your computer is changed.", "steps": [step], "expected_file": None,
            "verify": "steps_ok"}


def answer(domain: Domain, request: str, diagnostics: dict) -> dict:
    fixes = [] if policy.is_read_only() else tools_for(domain.name, read_only=False)
    fix_names = {f.name for f in fixes}
    fix_text = catalogue_text(fixes) if fixes else "(no changes are available for this specialist right now)"
    system = (prompts.ANSWER.replace("{label}", domain.label).replace("{guidance}", domain.guidance)
              .replace("{fixes}", fix_text))
    system = _with_next_choices(system)

    def validate(d: dict) -> dict:
        text = d.get("answer")
        if not isinstance(text, str) or not text.strip():
            raise ValueError('"answer" must be a non-empty string')
        fix = _match_fix(d.get("fix"), fix_names)
        if fix is None:
            raise ValueError(f'"fix" must be exactly one of {sorted(fix_names | {"none", "escalate"})}')
        out = {"answer": text.strip(), "fix": fix, "reason": str(d.get("reason") or "").strip(), "args": {},
               "next": d.get("next")}
        if fix in fix_names:
            args = _collect_args(fix, d, diagnostics)
            if fix == "open_settings_page" and not args.get("page"):
                page = _infer_settings_page(f"{request} {d.get('answer', '')} {d.get('reason', '')}")
                if page:
                    args["page"] = page
            try:
                out["args"] = policy.check_step(domain.name, fix, args)
            except PolicyError as e:
                raise ValueError(f"{e}. Choose valid arguments, or another fix, or \"none\"")
        return out

    user = f"User request: {request.strip()[:500]}\n\nTOOL OUTPUT:\n{json.dumps(diagnostics, default=str)}"
    d = ask_json(system, user, validate)
    proposal = {"diagnosis": _keep_warning(d["answer"], diagnostics), "reason": d["reason"], "fix": None}
    if d["fix"] == "none":
        proposal.update(next_step_offer(d.get("next"), d["answer"]))
        if not proposal.get("offer") and closing_line(d.get("next")):
            proposal["diagnosis"] += "\n\n" + closing_line(d.get("next"))
    if d["fix"] == "escalate":
        proposal.update(
            fix="escalate", risk=policy.R1, steps=[],
            summary="Open a ticket for the IT team",
            what_changes="A ticket will be created for the IT team with your request and what I found, "
                         "so you do not have to explain it again. Nothing on this computer is changed.")
    elif d["fix"] != "none":
        summary, changes = _describe(d["fix"], d["args"], diagnostics)
        proposal.update(fix=d["fix"], summary=summary, what_changes=changes,
                        risk=TOOLS[d["fix"]].risk,
                        steps=[{"tool": d["fix"], "args": d["args"], "label": summary}])
    return proposal


# ---------------------------------------------------------------------------
# Service desk intake (no tools needed to decide)
# ---------------------------------------------------------------------------
NO_KB_ANSWER = "NO_KB_ANSWER"
GENERAL_NOTE = "_General guidance from Tobi's own knowledge, not from your company's knowledge base._"


# "I don't have the steps for X in the knowledge base", "the articles I found only cover ...": the model found
# articles but they do not answer the question. Then Tobi answers from general knowledge instead of stopping there.
_KB_MISSED = re.compile(
    r"\b(?:i\s+)?(?:don'?t|do\s+not|couldn'?t|could\s+not|can'?t|cannot|didn'?t|did\s+not)\s+(?:have|find|see|locate)\b"
    r"[^.]{0,120}\b(?:knowledge\s*base|articles?|kb|documentation)\b"
    r"|\b(?:not|isn'?t|is\s+not)\s+(?:in|covered\s+(?:in|by))\s+(?:the|our|your)\s+(?:company\s+)?knowledge\s*base\b"
    r"|\b(?:the\s+)?articles?\s+(?:i\s+)?found\s+(?:only\s+)?(?:cover|are\s+about|talk\s+about|describe)\b"
    r"|\bno\s+(?:relevant\s+)?(?:article|information|steps)\b[^.]{0,60}\bknowledge\s*base\b",
    re.IGNORECASE)


def _keep_warning(answer_text: str, diagnostics: dict) -> str:
    """A how-to guide's "Before you start:" warning (back up, admin rights, BitLocker) is never dropped: when the answer
    cites that section but leaves the warning out, it is added as one line."""
    cited = re.findall(r"\[([^\]]+?)\s*§\s*([^\]]+)\]", answer_text or "")
    if not cited or re.search(r"(?i)\bback\s*up\b|\badministrator\b|\badmin rights\b", answer_text):
        return answer_text
    # The search result is a shortened excerpt, so the warning is read from the guide file itself.
    kb_dir = Path(__file__).resolve().parent.parent / "kb"
    for file_name, section in cited:
        path = kb_dir / Path(file_name.strip()).name
        if path.suffix != ".md" or not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        start = text.find(f"## {section.strip()}")
        if start < 0:
            continue
        end = text.find("\n## ", start + 3)
        m = re.search(r"Before you start:\s*(.+)", text[start:end if end > 0 else None])
        if m:
            return f"{answer_text}\n\n⚠️ **Before you start:** {m.group(1).strip()}"
    return answer_text


def kb_missed(answer_text: str) -> bool:
    """True when the knowledge-base answer is really "nothing here answers this"."""
    text = (answer_text or "").strip()
    return text.upper().startswith(NO_KB_ANSWER) or bool(_KB_MISSED.search(text[:400]))


def kb_found_something(diagnostics: dict) -> bool:
    """True when a knowledge tool returned something that may answer the question."""
    for out in diagnostics.values():
        if not isinstance(out, dict) or out.get("ok") is False:
            continue
        if out.get("results") and out.get("sufficiency") != "irrelevant":
            return True
        if out.get("policy_text") or out.get("similar_tickets") or (out.get("text") and out.get("citation")):
            return True
    return False


def general_answer(request: str, history: list | None = None) -> dict:
    """Answer a how-to question from the model's general knowledge when the knowledge base has nothing on it.
    Clearly labelled, and company-specific questions are escalated instead of guessed."""
    from agent.memory import as_text

    def validate(d: dict) -> dict:
        text = str(d.get("answer") or "").strip()
        if not text:
            raise ValueError('"answer" must be non-empty text')
        return {"answer": text[:2500], "escalate": bool(d.get("escalate")), "next": d.get("next")}

    earlier = f"EARLIER CONVERSATION:\n{as_text(history, 1500)}\n\n" if history else ""
    d = ask_json(_with_next_choices(prompts.GENERAL_ANSWER), f"{earlier}Question: {request.strip()[:500]}", validate)
    proposal = {"diagnosis": f"{d['answer']}\n\n{GENERAL_NOTE}", "reason": "general knowledge", "fix": None,
                "general": True}
    if not d["escalate"]:
        proposal.update(next_step_offer(d.get("next"), d["answer"]))
        if not proposal.get("offer") and closing_line(d.get("next")):
            proposal["diagnosis"] += "\n\n" + closing_line(d.get("next"))
    if d["escalate"]:
        proposal.update(
            diagnosis=d["answer"], fix="escalate", risk=policy.R1, steps=[],
            summary="Open a ticket for the IT team",
            what_changes="A ticket will be created for the IT team with your question, so you do not have to "
                         "explain it again. Nothing on this computer is changed.")
    return proposal


_ACCESS_ACTION = re.compile(r"(?<!\w)(raise|submit|create|file|make|apply|send|log|open)(?!\w).{0,40}?(?<!\w)(request|ticket|access)(?!\w)",
                            re.IGNORECASE)
_STATUS_WORD = {"ready": "ready", "add_first": "add it first", "offline": "offline"}


def wants_access_action(request: str) -> bool:
    """The user asks Tobi to DO the access request (raise it, apply), not just to explain how."""
    return bool(_ACCESS_ACTION.search(request or ""))


def access_proposal(out: dict) -> dict:
    """The answer to "can I use another ODC's printer?", written from the organisation's rules (no model needed):
    the rule, how to ask for access (request and email), and what to use meanwhile. Short, in plain words."""
    sop = out.get("sop") or "the printing SOP"
    name = out.get("target_name") or ""
    if out.get("odc") == "unknown":
        known = ", ".join(out.get("known_odcs") or [])
        want = f" You want the printers of {name}." if name else ""
        return {"diagnosis": f"I could not tell which ODC you sit in.{want} Tell me your ODC (for example: {known}) and, if you know "
                             "them, your floor and seat, and I will give you the exact steps.", "fix": None, "reason": ""}
    if out.get("target_odc") == "unknown":
        known = ", ".join(out.get("known_odcs") or [])
        return {"diagnosis": f"Which ODC's printer do you want to use? The ODCs I know are: {known}.", "fix": None, "reason": ""}
    if out.get("access") == "same_odc":
        return {"diagnosis": f"{name} is your own ODC, so its printers are already yours. Ask me \"which printer should I use?\" "
                             "and I will show which ones are ready on this computer.", "fix": None, "reason": ""}
    parts = []
    if out.get("access") == "not_possible":
        parts.append(f"**{name} printers**\n{out.get('why', '')} ({sop})")
    else:
        parts.append(f"**{name} printers**\nThey are for people of that ODC. Using them needs approval ({sop}).")
        how = out.get("how_to_request") or []
        if how:
            parts.append("**How to get access**\n" + "\n".join(f"{i}. {h}" for i, h in enumerate(how[:2], 1)))
        mail = out.get("email")
        if mail:
            parts.append(f"**Or send an email** to {mail['to']}\n> **Subject:** {mail['subject']}\n> {mail['body']}")
        parts.append("I can raise the request for you: tell me the reason (for example the project) and say \"raise it\".")
    use = out.get("use_instead") or []
    devices = out.get("other_devices") or []
    if use or devices:
        lines = [f"- {u['printer']}: {u.get('where', '')} ({_STATUS_WORD.get(u.get('status'), u.get('status'))})" for u in use]
        lines += [f"- {d}" for d in devices]
        parts.append("**Use these meanwhile (your own ODC)**\n" + "\n".join(lines))
    return {"diagnosis": "\n\n".join(parts), "fix": None, "reason": "", "access_rules": True}


def chat_reply(request: str, history: list | None = None) -> str:
    """A natural reply for greetings, thanks, small talk and vague messages (no checks on the computer needed)."""
    def validate(d: dict) -> dict:
        reply = str(d.get("reply") or "").strip()
        if not reply:
            raise ValueError('"reply" must be non-empty text')
        return {"reply": reply[:1200]}
    from agent.memory import as_text
    earlier = f"EARLIER CONVERSATION:\n{as_text(history)}\n\n" if history else ""
    return ask_json(prompts.CHAT, f"{earlier}User message: {request.strip()[:500]}", validate)["reply"]


def intake(request: str) -> dict:
    def validate(d: dict) -> dict:
        action = str(d.get("action", "")).strip().lower()
        if action not in ("create", "list", "status"):
            raise ValueError('"action" must be create, list or status')
        out = {"action": action, "ticket": str(d.get("ticket") or "").strip()}
        if action == "create":
            title = str(d.get("title") or "").strip()
            if not title:
                raise ValueError('"title" must not be empty')
            category = str(d.get("category") or "service_request").strip().lower()
            priority = str(d.get("priority") or "P3").strip().upper()
            out.update(title=title[:120],
                       category=category if category in tickets.CATEGORIES else "service_request",
                       priority=priority if priority in tickets.PRIORITIES else "P3",
                       summary=str(d.get("summary") or request).strip()[:800])
        elif action == "status" and not any(ch.isdigit() for ch in out["ticket"]):
            out["action"] = "list"
        return out

    return ask_json(prompts.IT_REQUEST, f"User request: {request.strip()[:600]}", validate)


# ---------------------------------------------------------------------------
# Verify: re-run the diagnostics and compare
# ---------------------------------------------------------------------------
def _verify_close_process(runner: ToolRunner, state: dict) -> dict:
    before = _first(state["diagnostics"], "get_system_health")
    after = runner.run("get_system_health")
    result = (state.get("fix_results") or [{}])[-1]
    closed = result.get("ok") and not result.get("still_running")
    rows = [
        {"metric": "Memory in use (%)", "before": before.get("ram_percent"), "after": after.get("ram_percent")},
        {"metric": "Memory in use (GB)", "before": before.get("ram_used_gb"), "after": after.get("ram_used_gb")},
        {"metric": "CPU in use (%)", "before": before.get("cpu_percent"), "after": after.get("cpu_percent")},
    ]
    b, a = before.get("ram_used_gb"), after.get("ram_used_gb")
    improved = a is not None and (b is None or a < b)
    fixed = bool(closed and improved)
    note = ("The process was closed and memory use went down." if fixed else
            "The process was closed, but memory use did not go down." if closed else
            "The process could not be closed.")
    return {"comparison": rows, "fixed": fixed, "note": note}


def _verify_disk_space(runner: ToolRunner, state: dict) -> dict:
    before = {d["drive"]: d for d in _first(state["diagnostics"], "get_disk_usage").get("drives", [])}
    after_out = runner.run("get_disk_usage")
    result = (state.get("fix_results") or [{}])[-1]
    rows = []
    for d in after_out.get("drives", []):
        b = before.get(d["drive"], {})
        rows.append({"metric": f"Free space on {d['drive']} (GB)", "before": b.get("free_gb"), "after": d["free_gb"]})
        rows.append({"metric": f"Used on {d['drive']} (%)", "before": b.get("used_percent"), "after": d["used_percent"]})
    freed = result.get("freed_mb") or 0
    removed = result.get("files_deleted", result.get("items_removed", 0))
    rows.append({"metric": "Items deleted", "before": 0, "after": removed})
    rows.append({"metric": "Space freed (MB)", "before": 0, "after": freed})
    fixed = bool(result.get("ok") and (freed > 0 or removed))
    return {"comparison": rows, "fixed": fixed,
            "note": f"{freed} MB was freed." if fixed else "No space could be freed."}


def _verify_dns(runner: ToolRunner, state: dict) -> dict:
    b_dns = _first(state["diagnostics"], "check_dns_resolution")
    b_net = _first(state["diagnostics"], "check_network_connection")
    a_dns = runner.run("check_dns_resolution")
    a_net = runner.run("check_network_connection")

    def site(net):
        w = net.get("website")
        return "not checked" if w is None else "opens" if w.get("opens") else "does not open"

    rows = [
        {"metric": "DNS lookups that work", "before": b_dns.get("resolved", "not checked"), "after": a_dns.get("resolved")},
        {"metric": f"Test website ({cfg('network', 'test_website')})", "before": site(b_net), "after": site(a_net)},
    ]
    fixed = bool(a_dns.get("all_resolve") and (a_net.get("website") or {}).get("opens"))
    return {"comparison": rows, "fixed": fixed,
            "note": "DNS lookups work and the test website opens." if fixed else
                    "DNS lookups or the test website still fail after the flush."}


def _flatten(value, prefix="") -> dict:
    out = {}
    if isinstance(value, dict):
        for k, v in value.items():
            out.update(_flatten(v, f"{prefix}{k}."))
    elif isinstance(value, list):
        if all(not isinstance(v, (dict, list)) for v in value):
            out[prefix.rstrip(".")] = ", ".join(str(v) for v in value)
        else:
            out[prefix + "count"] = len(value)
    else:
        out[prefix.rstrip(".")] = value
    return out


_NOISY = ("ms", "cpu_percent", "local_time", "uptime", "ok")


def _verify_generic(runner: ToolRunner, state: dict) -> dict:
    """Re-run the planned checks and list every value that changed."""
    rows = []
    steps = state.get("plan") or []
    for key, step in zip(diag_keys(steps), steps):
        if runner.calls_made >= runner.max_calls:
            break
        before = state["diagnostics"].get(key) or {}
        after = runner.run(step["tool"], step["args"])
        b, a = _flatten(before), _flatten(after)
        for name in a:
            if name.split(".")[-1] in _NOISY or name.endswith("_ms"):
                continue
            if name in b and b[name] != a[name] and len(rows) < 8:
                rows.append({"metric": f"{step['tool']}: {name}", "before": b[name], "after": a[name]})
    result = (state.get("fix_results") or [{}])[-1]
    fixed = bool(result.get("ok"))
    note = ("The action completed." + ("" if rows else " The re-check shows no other change.")) if fixed \
        else "The action did not complete."
    return {"comparison": rows, "fixed": fixed, "note": note}


# ---------------------------------------------------------------------------
# Printing: build the proposal from the troubleshooter's findings, and check afterwards that it worked
# ---------------------------------------------------------------------------
_FIX_ORDER = ["restart_print_spooler", "clear_print_queue", "set_printer_online", "set_default_printer", "open_settings_page"]
_LAYER_TITLES = {"computer": "On your computer", "file": "The file", "printer": "The printer itself",
                 "network": "The connection to the printer"}


def print_proposal(result: dict) -> dict:
    """The proposal for a printing request: fixes for what is wrong on the computer, steps for what is not."""
    findings, state, file_name = result["findings"], result["state"], result.get("file_name", "")
    problems = [f for f in findings if f["severity"] == "problem"]

    # 1. fixes the computer can do (deduplicated, in a sensible order)
    steps, fixable, seen = [], [], set()
    for f in sorted(problems, key=lambda f: _FIX_ORDER.index(f["fix"]["tool"]) if f["fix"] and f["fix"]["tool"] in _FIX_ORDER else 99):
        fix = f["fix"]
        if not fix:
            continue
        key = (fix["tool"], json.dumps(fix["args"], sort_keys=True))
        if key in seen:
            continue
        seen.add(key)
        spec = TOOLS[fix["tool"]]
        shown = {k: str(v).replace("_", " ") for k, v in fix["args"].items()}
        label = spec.summary.format(**shown) if spec.summary else spec.description
        steps.append({"tool": fix["tool"], "args": fix["args"], "domain": fix["domain"], "label": label})
        if not fix.get("assist"):
            fixable.append(f["id"])

    # Steps that only open a Windows page for the user are not a fix: they are offered as a simple yes / no question
    # under a short answer ("No printer is connected ... Want me to open the printer settings?").
    opens_page_only = bool(steps) and not fixable

    # 2. nothing wrong on the computer and a real printer exists: offer a test page to confirm
    real = [p for p in state["printers"] if not printing.is_virtual(p)]
    if not problems and real:
        target = next((p for p in real if p.get("Default")), real[0])["Name"]
        steps.append({"tool": "print_test_page", "args": {"printer_name": target}, "domain": "devices",
                      "label": f"Print a test page on {target}"})

    # 3. the explanation
    parts = ["I checked the print service, your printers, the print queue and the connection to the printer"
             + (f", and the file {file_name}" if file_name else "") + "."]
    for layer, title in _LAYER_TITLES.items():
        items = [f["what"] for f in findings if f["layer"] == layer]
        if items:
            parts.append(f"**{title}**\n" + "\n".join(f"- {x}" for x in items))
    if not problems:
        parts.append("I found no problem on the computer side, and the printer reports no error. "
                     + ("I can send a test page to confirm it prints." if real else ""))
        if not file_name:
            parts.append("If only one document fails, tell me its name and I will check the file itself.")
    user_steps, seen_steps = [], set()
    for f in problems:
        if f["fix"] and not f["fix"].get("assist"):
            continue
        for st in f["steps"]:
            if st not in seen_steps:
                seen_steps.add(st)
                user_steps.append(st)
    if user_steps:
        parts.append("**What you need to do**\n" + "\n".join(f"{i}. {st}" for i, st in enumerate(user_steps, 1)))
    needs_it = [f for f in problems if f["needs_it"]]
    if needs_it:
        parts.append("**Needs IT**\n" + "\n".join(f"- {f['what']}" for f in needs_it))
    if opens_page_only and [f["id"] for f in problems] == ["no-printer"]:
        virtual = ", ".join(p["Name"] for p in state["printers"] if printing.is_virtual(p)) or "virtual printers"
        parts = [f"No printer is connected to this computer right now. There's only {virtual}, which saves a file "
                 "instead of printing on paper." + (" An office printer is usually added from the company print server."
                                                     if file_name == "" else "")]

    proposal = {"diagnosis": "\n\n".join(parts), "reason": "", "fix": None, "file_name": file_name,
                "before_ids": [f["id"] for f in problems], "fixable_ids": fixable}
    if opens_page_only:
        proposal.update(fix="printing_fix", risk=max(TOOLS[st["tool"]].risk for st in steps), steps=steps,
                        summary="Open the printer settings", offer=True,
                        ask="Want me to open the printer settings so you can add one?",
                        what_changes="The Windows printer settings page opens. Nothing is changed.")
    elif steps:
        risk = max(TOOLS[st["tool"]].risk for st in steps)
        changes = "\n".join(f"- {st['label']}: {TOOLS[st['tool']].change_note}" for st in steps)
        proposal.update(fix="printing_fix", risk=risk, steps=steps,
                        summary=("Fix the printing problems on this computer" if fixable else
                                 "Open the printer settings" if problems else "Print a test page"),
                        what_changes=changes)
    elif needs_it:
        proposal.update(fix="escalate", risk=policy.R1, steps=[], summary="Open a ticket for the IT team",
                        what_changes="A ticket will be created for the IT team with what I found, so you do not have to "
                                     "explain it again. Nothing on this computer is changed.")
    return proposal


def _verify_printing(runner: ToolRunner, state: dict) -> dict:
    proposal = state["proposal"]
    runner.run("diagnose_printing", {"file": proposal.get("file_name", "")} if proposal.get("file_name") else {})
    after = printing.last()["findings"]
    after_problems = [f for f in after if f["severity"] == "problem"]
    after_ids = {f["id"] for f in after_problems}
    fixable = set(proposal.get("fixable_ids", []))
    failed = [r for r in (state.get("fix_results") or []) if r.get("ok") is False]
    still = fixable & after_ids

    computer_before = sum(1 for i in proposal.get("before_ids", []) if i in fixable)
    rows = [{"metric": "Problems the computer can fix", "before": computer_before, "after": len(still)},
            {"metric": "All problems found", "before": len(proposal.get("before_ids", [])), "after": len(after_ids)}]
    remaining_steps = []
    for f in after_problems:
        if f["id"] not in fixable:
            remaining_steps += [s for s in f["steps"] if s not in remaining_steps][:2]
    fixed = not still and not failed
    if failed:
        note = f"A step failed: {failed[0].get('error') or failed[0].get('output')}"
    elif still:
        note = "These problems are still there after the fix: " + "; ".join(f["what"] for f in after_problems if f["id"] in still)
    elif not fixable and proposal["steps"] and proposal["steps"][-1]["tool"] == "print_test_page":
        note = "The test page was sent. Check the printer's output tray. If nothing comes out, tell me and I will look again."
    else:
        note = "The problems on your computer are fixed."
    if fixed and remaining_steps:
        note += " Still to do on your side: " + " ".join(f"{i}. {s}" for i, s in enumerate(remaining_steps[:3], 1))
    return {"comparison": rows, "fixed": fixed, "note": note}


VERIFIERS = {
    "printing_fix": _verify_printing,
    "close_process": _verify_close_process,
    "clean_approved_temp_files": _verify_disk_space,
    "empty_recycle_bin": _verify_disk_space,
    "clear_app_cache": _verify_disk_space,
    "flush_dns_cache": _verify_dns,
}


def verify(runner: ToolRunner, state: dict) -> dict:
    if state["agent"] == "computer_use":
        return COMPUTER_USE.verify(runner, state)
    return VERIFIERS.get(state["proposal"]["fix"], _verify_generic)(runner, state)


# ---------------------------------------------------------------------------
# Computer Use: the model picks a predefined task, Python builds the steps
# ---------------------------------------------------------------------------
from tools.knownfolders import known_folder  # noqa: E402


def documents_folder() -> Path:
    return known_folder("Documents")


def health_note_text(health: dict, disks: dict) -> str:
    lines = [
        f"System health summary, {datetime.now():%d %b %Y %H:%M}",
        f"CPU in use: {health.get('cpu_percent')} percent of {health.get('cpu_cores')} cores",
        f"Memory in use: {health.get('ram_percent')} percent, "
        f"{health.get('ram_used_gb')} GB of {health.get('ram_total_gb')} GB",
        f"Time since last restart: {health.get('uptime_hours')} hours",
    ]
    for d in disks.get("drives", []):
        lines.append(f"Drive {d['drive']} {d['free_gb']} GB free of {d['total_gb']} GB, {d['used_percent']} percent used")
    lines.append("Written by Tobi from live measurements.")
    return "\n".join(lines)


class ComputerUse:
    name = "computer_use"

    # ---- deterministic parsing: the small local model is not needed to find a site, an app or a package ----
    _PREFIX = r"(?:(?:hi|hey|hello|please|pls|kindly|can you|could you|can u|would you|will you|i want to|i would like to|i need to|i want (?:you|u) to|i need (?:you|u) to|i(?:'|)d like (?:you|u) to|you can|go ahead and|let'?s|just)[\s,]+)*"
    _OPEN = re.compile(r"^\s*" + _PREFIX + r"(open|launch|start|run|go to|goto|visit|browse to|browse|show me|pull up|take me to|load)(?!\w)\s*(.*)$",
                       re.IGNORECASE | re.DOTALL)
    _LOCAL = re.compile(r"(?<!\w)(in|on)\s+my\s+(system|pc|laptop|computer|machine)(?!\w)|(?<!\w)installed(?!\w)", re.IGNORECASE)
    _OPEN_IT = re.compile(r"(?<!\w)(open|launch|start|run)\s+(it|that|this|them)(?!\w)", re.IGNORECASE)
    _INSTALL = re.compile(r"(?<!\w)install(?!\w)", re.IGNORECASE)
    _NOT_SIMPLE = re.compile(r"(?<!\w)(write|writing|written|type|typing|save|summary|download|report|note|notes|portal|health|"
                             r"and then|record|recording|explain|answer|steps|"
                             r"screenshot|capture|press|click|seconds?|minutes?|start a)(?!\w)", re.IGNORECASE)
    _DOMAIN = re.compile(r"(?<![\w@.-])((?:https?://)?(?:[a-z0-9-]+\.)+[a-z]{2,}(?:[/?#][^\s]*)?)", re.IGNORECASE)

    _FILE_EXT = {"exe", "bat", "cmd", "dll", "msi", "ps1", "vbs", "js", "py", "txt", "doc", "docx", "xls", "xlsx",
                 "pdf", "zip", "lnk", "sys", "ini", "log", "reg"}

    _PASSWORD = re.compile(r"(?<!\w)(reset|forgot|forgotten|unlock|recover|change|lost)(?!\w).{0,40}(?<!\w)(password|passcode|pin)(?!\w)|"
                           r"(?<!\w)(password|account)(?!\w).{0,25}(?<!\w)(reset|locked out|is locked|unlock)(?!\w)", re.IGNORECASE)
    # "my system pattern password": could be the Windows sign-in, the PIN / picture password or the company account
    _PASSWORD_UNCLEAR = re.compile(r"(?<!\w)(pattern|system|laptop|computer|pc|desktop|login|log\s*in|"
                                   r"lock\s*screen|screen\s*lock|device)(?!\w)", re.IGNORECASE)
    # Windows Hello PIN / picture password / fingerprint: the user changes it in Settings, no IT needed
    _HELLO = re.compile(r"(?<!\w)(pin|windows\s+hello|hello\s+pin|picture\s+password|fingerprint|face\s+(?:sign|recognition))(?!\w)",
                        re.IGNORECASE)
    _PASSWORD_WHICH = re.compile(r"(?<!\w)(company|work|email|e-mail|outlook|office|365|m365|microsoft account|domain|"
                                 r"network|vpn|teams|forgot|forgotten|locked out|is locked|expired|lost)(?!\w)", re.IGNORECASE)
    PASSWORD_QUESTION = ("Quick check so I send you to the right place. Which one do you mean?\n\n"
                         "1. Your Windows sign-in password (the one you type to unlock this PC)\n"
                         "2. Your PIN or picture password (Windows Hello)\n"
                         "3. Your company or email account password\n\n"
                         "Just reply with the number.")

    _SEARCH = re.compile(r"^\s*" + _PREFIX + r"(search(?:\s+the\s+web|\s+online|\s+google)?(?:\s+for)?|google|look\s*up|"
                         r"find(?:\s+me)?|research)(?!\w)\s*(.*)$", re.IGNORECASE | re.DOTALL)
    _NOT_WEB = re.compile(r"(?<!\w)(knowledge\s*base|kb|articles?|files?|folders?|documents?|e-?mails?|mail|calendar|downloads|"
                          r"powershell|tickets?|polic(?:y|ies)|driver|logs?)(?!\w)", re.IGNORECASE)
    _OPEN_CLAUSE = re.compile(r"(?:(?<!\w)(?:and|then)\s+)?(?<!\w)(?:open|go\s+to|visit|launch|take\s+me\s+to|show\s+me)(?!\w).*$",
                              re.IGNORECASE | re.DOTALL)
    _NOUNS = re.compile(r"(?<!\w)(a|an|the|me|for|tool|website|web\s*site|site|app|application|platform|service|called|named|"
                        r"web\s*page|page|online|about|please|pls|official)(?!\w)", re.IGNORECASE)
    _FOLDER = re.compile(r"(?<!\w)(downloads|documents|desktop)(?!\w)", re.IGNORECASE)

    @staticmethod
    def _tidy(text: str) -> str:
        return re.sub(r"\s+", " ", re.sub(r"^[\s:;,.\-]+|[\s:;,.!?\-]+$", "", text))

    def _browser_in(self, text: str) -> str:
        text = re.sub(r"(?i)google chrome", "chrome", text)
        text = re.sub(r"(?i)microsoft edge", "edge", text)
        browsers = cfg("desktop", "browsers", default={}) or {}
        return next((b for b in browsers if self._whole_word(b, text)), "default")

    def _search_pick(self, text: str) -> dict | None:
        """"search for X" -> search results page; "search for a tool called X and open it" -> find and open the site."""
        m = self._SEARCH.match(text)
        if not m or self._NOT_WEB.search(text):
            return None
        rest = m.group(2)
        browser = self._browser_in(rest)
        rest = re.sub(r"(?i)(?<!\w)(in|on|with|using)\s+(chrome|edge|firefox|google chrome|microsoft edge)(?!\w)", " ", rest)
        wants_open = bool(re.search(r"(?<!\w)(open|go\s+to|visit|launch|take\s+me\s+to)(?!\w)", rest, re.IGNORECASE))
        rest = self._OPEN_CLAUSE.sub("", rest)
        rest = re.sub(r"^\s*(the\s+web|online|google)\s*[:,\-]?\s*", "", rest, flags=re.IGNORECASE)
        if wants_open:
            rest = self._NOUNS.sub(" ", rest)
        query = self._tidy(rest)
        if not query or len(query) > 120:
            return None
        return {"task": "find_site" if wants_open else "search_web", "query": query, "browser": browser, "reason": ""}

    _QUOTED = re.compile(r'["\u201c\u201d](.{3,2000}?)["\u201c\u201d]', re.DOTALL)
    _NOTE_VERB = re.compile(r"(?<!\w)(write|type|put|paste|save|create|make|note\s+down)(?!\w)", re.IGNORECASE)
    _NOTE_TARGET = re.compile(r"(?<!\w)(notepad|note\s*pad|text\s*file|\.txt|new\s+note)(?!\w)", re.IGNORECASE)
    _NAME_TAIL = (r"[\"\u201c\u201d']?(.+?)[\"\u201c\u201d']?"
                  r"(?=\s+(?:and|in|on|to|at|into|inside)\b|\s*[.,;]|\s*$)")
    # "called X", "named X", "with a name X", "name it X" win over a bare "as X"
    _FILE_NAME = re.compile(r"(?:(?:with|under)\s+(?:a\s+|the\s+)?name(?:\s+of)?|named|called|name\s+(?:it|this|that)(?:\s+as)?|"
                            r"(?:file\s*)?name\s*(?:is|:)?)\s+(?:the\s+)?" + _NAME_TAIL, re.IGNORECASE)
    _FILE_NAME_AS = re.compile(r"(?<!\w)as\s+(?:the\s+)?" + _NAME_TAIL, re.IGNORECASE)
    _COMPOSE_VERB = re.compile(r"(?<!\w)(write|writing|written|type|typing|put|create|make|prepare|draft|jot|note\s+down|"
                               r"add|fill|save)(?!\w)", re.IGNORECASE)
    # what the user wants written, described rather than quoted: "the answer to ...", "the steps to ...", "about ..."
    _COMPOSE_WHAT = re.compile(r"(?<!\w)(answer|answers|steps|instructions|explanation|explain|explaining|summary|summari[sz]e|"
                               r"guide|checklist|list|notes?\s+(?:on|about|for)|how\s+to|how\s+do|what\s+(?:is|are)|"
                               r"why|about|describing|tips)(?!\w)", re.IGNORECASE)

    def _folder_and_name(self, text: str) -> tuple[str, str]:
        folder = next((f for f in ("Desktop", "Downloads", "Documents") if re.search(rf"(?<!\w){f}(?!\w)", text, re.IGNORECASE)),
                      "Documents")
        found = self._FILE_NAME.search(text) or self._FILE_NAME_AS.search(text)
        name = found.group(1).strip() if found else ""
        name = re.sub(r"(?i)^(?:an?\s+|the\s+)?(?:text\s*)?(?:file|note)\s+(?:called|named)\s+", "", name)
        name = re.sub(r"(?i)^(?:an?\s+|the\s+)?(?:text\s*)?(?:file|note)$", "", name)
        if len(name.split()) > 6 or self._COMPOSE_WHAT.search(name):   # "as the answer to ..." is not a file name
            name = ""
        return folder, name

    def _compose_pick(self, text: str) -> dict | None:
        """"create a notepad file with the steps to run python in vs code" -> write_note whose text Tobi writes first.
        The user describes the content instead of quoting it, so the model writes it and the user sees it before saving."""
        if self._QUOTED.search(text) or not self._NOTE_TARGET.search(text):
            return None
        if not (self._COMPOSE_VERB.search(text) and self._COMPOSE_WHAT.search(text)):
            return None
        folder, name = self._folder_and_name(text)
        return {"task": "write_note", "compose": True, "text": "", "filename": name, "folder": folder, "reason": ""}

    def _note_pick(self, text: str) -> dict | None:
        """"write "<text>" in a new Notepad and save it with the name X on the Desktop" -> a write_note task."""
        quoted = self._QUOTED.search(text)
        if not quoted:
            return None
        rest = text[:quoted.start()] + " <TEXT> " + text[quoted.end():]
        if not (self._NOTE_VERB.search(rest) and self._NOTE_TARGET.search(rest)):
            return None
        folder = next((f for f in ("Desktop", "Downloads", "Documents") if re.search(rf"(?<!\w){f}(?!\w)", rest, re.IGNORECASE)),
                      "Documents")
        found = self._FILE_NAME.search(rest) or self._FILE_NAME_AS.search(rest)
        name = found.group(1).strip() if found else ""
        name = re.sub(r"(?i)^(?:an?\s+|the\s+)?(?:text\s*)?(?:file|note)\s+(?:called|named)\s+", "", name)   # "a text file called X"
        name = re.sub(r"(?i)^(?:an?\s+|the\s+)?(?:text\s*)?(?:file|note)$", "", name)                       # "as a text file"
        return {"task": "write_note", "text": quoted.group(1).strip(), "filename": name,
                "folder": folder, "reason": ""}

    @staticmethod
    def _whole_word(word: str, text: str) -> bool:
        return re.search(r"(?<![\w+])" + re.escape(word) + r"(?![\w+])", text, re.IGNORECASE) is not None

    _PDF_WORD = re.compile(r"(?<![\w.])pdf(?!\w)", re.IGNORECASE)      # the word "pdf", not a file's ".pdf" ending
    _PDF_VERB = re.compile(r"(?<!\w)(convert|save|export|print|turn|make|create|change|write)(?!\w)", re.IGNORECASE)
    _PDF_WHAT = re.compile(
        r"(?<!\w)(?:convert|save|export|print|turn|make|create|change|write)(?!\w)\s+(?:me\s+)?(?:a\s+(?:copy|pdf)\s+of\s+)?"
        r"(?P<what>.+?)\s+(?:to|as|into|in)\s+(?:a\s+|an\s+|the\s+)?(?:\w+\s+)?pdf(?!\w)", re.IGNORECASE | re.DOTALL)
    _PDF_OF = re.compile(r"(?<!\w)pdf\s+(?:copy\s+)?(?:of|from)\s+(?P<what>.+)$", re.IGNORECASE | re.DOTALL)
    _PDF_HOW = re.compile(r"(?<!\w)(how\s+(?:do|can|could|to|should|would)|what\s+is|why|explain)(?!\w)", re.IGNORECASE)
    _PDF_CUT = re.compile(r"(?<!\w)(by|using|with|via|through|on\s+my\s+printer|from\s+my\s+printer)(?!\w).*$", re.IGNORECASE | re.DOTALL)
    _PDF_WHERE = re.compile(r"(?<!\w)(?:in|on|to|into|at|under)\s+(?:my\s+|the\s+)?(desktop|documents|downloads)(?!\w)", re.IGNORECASE)

    _SAVE_TO = re.compile(r"(?<!\w)(?:save|store|keep|put|place)\w*\s+(?:it|that|this|them|the\s+\w+|a\s+copy)?\s*"
                          r"(?:as\s+(?:a\s+)?\w+\s+)?(?:in|on|to|into|at|under)\s+(?:my\s+|the\s+)?(?P<place>[\w-]+)", re.IGNORECASE)
    _VIRTUAL_PRINTER = re.compile(r"(?<!\w)(?:print(?:er|ing)?\s+(?:service|option|to\s+(?:a\s+)?file)|virtual\s+printer|"
                                  r"microsoft\s+print|print\s+to\s+pdf)(?!\w)", re.IGNORECASE)
    _ANY_PLACE = re.compile(r"(?<!\w)(?:in|on|to|into|at|under|from)\s+(?:my\s+|the\s+)?(?P<place>[\w-]+)", re.IGNORECASE)
    _DOC_WORD = re.compile(r"(?<!\w)(file|document|documnet|doc|note|report|txt|word|excel|sheet|picture|photo|image)(?!\w)|"
                           r"\.[A-Za-z0-9]{2,5}(?![\w.])", re.IGNORECASE)

    @staticmethod
    def _place(word: str) -> str:
        """'destop' -> 'Desktop', 'documnets' -> 'Documents', anything else -> ''."""
        import difflib
        w = (word or "").lower()
        best = max(("desktop", "documents", "downloads"), key=lambda f: difflib.SequenceMatcher(None, w, f).ratio())
        return best.title() if difflib.SequenceMatcher(None, w, best).ratio() >= 0.75 else ""

    _DELETE = re.compile(r"(?<!\w)(delete|remove|trash|erase|get\s+rid\s+of|bin|discard)(?!\w)", re.IGNORECASE)
    _NOT_A_FILE = re.compile(r"(?<!\w)(app|apps|application|program|programs|software|account|user|users|printer|password|"
                             r"email|emails|mail|history|cookies|cache|temp|temporary|browser|extension|driver|update|"
                             r"all|every|everything|folder|folders|files)(?!\w)", re.IGNORECASE)
    _FILE_HINT = re.compile(r"(?<!\w)(file|pdf|document|doc|docx|txt|text|note|notes|report|sheet|excel|word|image|photo|"
                            r"picture|png|jpg|video|zip|csv|pptx?|slides)(?!\w)|\.[A-Za-z0-9]{2,5}(?![\w.])", re.IGNORECASE)

    def _delete_pick(self, text: str) -> dict | None:
        """"delete the RAGAS pdf in my desktop" -> delete_file. Programs, accounts, browser data, folders and
        "all my files" are not this (they are uninstalls, IT jobs or bulk deletions)."""
        if not self._DELETE.search(text) or self._PDF_HOW.search(text) or self._NOT_A_FILE.search(text):
            return None
        if not self._FILE_HINT.search(text):
            return None
        from tools.pdfprint import _FILLER, _explicit_name
        explicit = _explicit_name(text)
        keep_types = {"pdf", "txt", "text", "word", "excel", "docx", "xlsx", "csv", "png", "jpg", "image", "photo", "picture",
                      "video", "zip", "pptx", "ppt", "slides", "sheet", "notes", "note", "report"}
        tokens = [t for t in re.split(r"[^\w.-]+", text) if t and (t.lower() not in _FILLER or t.lower() in keep_types)
                  and not self._place(t) and not self._DELETE.fullmatch(t) and len(t) > 1]
        phrase = explicit or " ".join(tokens[:6])
        return {"task": "delete_file", "file": phrase, "reason": ""} if phrase else None

    def _open_file_pick(self, text: str) -> dict | None:
        """"open the RAGAS pdf" -> open that file (only when such a file really exists; else it is a site or an app)."""
        m = self._OPEN.match(text.strip())
        if not m or not self._FILE_HINT.search(text) or self._NOT_A_FILE.search(text):
            return None
        if self._NOT_SIMPLE.search(text) or len(m.group(2).split()) > 7:
            return None                                     # "open X and record / save ...": a multi-step job, not one file
        from tools import pdfprint
        if not pdfprint.find_documents(m.group(2), 1, kinds=None):
            return None
        return {"task": "open_file", "file": m.group(2).strip(" .?!"), "reason": ""}

    def plan_open_file(self, choice: dict) -> dict:
        from tools import pdfprint
        ranked = pdfprint._ranked(choice["file"], kinds=None)
        top = [p for s, p in ranked if ranked and ranked[0][0] - s < 0.05][:4]
        if not top:
            return {"diagnosis": f"I couldn't find a file called '{choice['file']}'. What's it called?", "fix": None, "reason": ""}
        if len(top) > 1 and not pdfprint.type_hint(choice["file"]):
            return {"diagnosis": "I found more than one: " + ", ".join(p.name for p in top) + ". Which one should I open?",
                    "fix": None, "reason": ""}
        target = top[0]
        return {"diagnosis": f"Found it: {target.name} in {target.parent}.", "fix": "computer_use_task", "reason": "",
                "risk": policy.R1, "summary": f"Open {target.name}",
                "what_changes": f"{target.name} opens in its usual program. Nothing is changed.",
                "steps": [{"tool": "open_file", "args": {"file": str(target)}, "domain": "computer_use", "label": f"Open {target.name}"}],
                "expected_file": None, "verify": "steps_ok"}

    def plan_delete_file(self, choice: dict) -> dict:
        """Delete one file: find it, say exactly which one, move it to the Recycle Bin after OK."""
        from tools import pdfprint
        phrase = choice["file"]
        ranked = pdfprint._ranked(phrase, kinds=None)
        say = lambda text: {"diagnosis": text, "fix": None, "reason": ""}      # noqa: E731
        if not ranked:
            return say(f"I looked through your folders and drives but couldn't find a file called '{phrase}'. "
                       "What's it called? Even part of the name is enough.")
        top = [p for s, p in ranked if ranked[0][0] - s < 0.05][:4]
        if len(top) > 1 and not pdfprint.type_hint(phrase):
            names = ", ".join(f"{p.name} ({p.parent.name})" for p in top)
            return say(f"I found more than one: {names}. Which one should I delete?")
        target = top[0]
        where = target.parent
        return {
            "diagnosis": f"Found it: {target.name} in {where}.",
            "fix": "computer_use_task", "reason": "", "risk": policy.R1,
            "summary": f"Move {target.name} to the Recycle Bin",
            "ask": f"Should I delete {target.name} from {where.name}? It goes to the Recycle Bin, so you can get it back.",
            "what_changes": f"{target} is moved to the Recycle Bin. You can restore it from there.",
            "steps": [{"tool": "delete_file", "args": {"file": str(target)}, "domain": "computer_use",
                       "label": f"Move {target.name} to the Recycle Bin"}],
            "expected_file": None, "verify": "deleted", "deleted_path": str(target),
        }

    def _pdf_pick(self, text: str) -> dict | None:
        """Turn a document into a PDF with the virtual printer. Recognises "convert my itbuddy test note to a pdf",
        "save my report as pdf on the desktop", and also requests with no word "pdf" in them such as "print the RAGAS
        document using my printer service and save it in desktop" (printing INTO a folder means a PDF file)."""
        if self._PDF_HOW.search(text):
            return None
        has_pdf = bool(self._PDF_WORD.search(text))
        save_to = self._SAVE_TO.search(text)
        save_place = self._place(save_to.group("place")) if save_to else ""
        into_file = bool(save_place) and re.search(r"(?<!\w)print\w*(?!\w)", text, re.IGNORECASE)
        if not (has_pdf or into_file or self._VIRTUAL_PRINTER.search(text)):
            return None
        if has_pdf and not (into_file or self._VIRTUAL_PRINTER.search(text) or self._PDF_VERB.search(text)):
            return None                                     # "pdf" is mentioned, but nothing asks to MAKE one
        if not (has_pdf or self._DOC_WORD.search(text)):
            return None
        folder = save_place
        if not folder:
            where = self._PDF_WHERE.search(text)
            folder = where.group(1).title() if where else ""
        phrase = ""
        m = (self._PDF_WHAT.search(text) or self._PDF_OF.search(text)) if has_pdf else None
        if m:
            what = self._PDF_WHERE.sub(" ", m.group("what"))
            what = self._PDF_CUT.sub("", what)
            words = [w for w in re.split(r"\s+", what.strip(" .,!?'\"")) if w]
            generic = {"my", "the", "a", "an", "this", "that", "file", "document", "documnet", "doc", "please", "pls", "called", "named"}
            while words and words[0].lower() in generic:
                words.pop(0)
            while words and words[-1].lower() in {"file", "document", "documnet", "doc"}:
                words.pop()
            phrase = " ".join(words).strip()
        if not phrase or len(phrase) > 120 or any(self._place(w) for w in phrase.split()[-1:]):
            # no clean "X to pdf" phrase: keep the words that can be part of a file name (the search ignores the rest)
            from tools.pdfprint import _FILLER, _explicit_name
            explicit = _explicit_name(text)
            if explicit:
                phrase = explicit
            else:
                tokens = [t for t in re.split(r"[^\w.-]+", text) if t and t.lower() not in _FILLER and not self._place(t)
                          and len(t) > 1]
                phrase = " ".join(tokens[:6])
        if not phrase:
            return None
        return {"task": "save_as_pdf", "file": phrase, "folder": folder, "reason": ""}

    def quick_pick(self, request: str) -> dict | None:
        """Recognise "open <site/app>" and "install <catalogue program>" without a model call. None = not one of these."""
        text = request.strip()
        low = text.lower()
        note = self._note_pick(text) or self._compose_pick(text)   # first: "write the steps to install X in notepad"
        if note:
            return note
        gone = self._delete_pick(text)
        if gone:
            return gone
        opened = self._open_file_pick(text)
        if opened:
            return opened
        pdf = self._pdf_pick(text)
        if pdf:
            return pdf
        if re.search(r"(?<!\w)(uninstall|remove|delete)(?!\w)", low):
            return None
        if self._PASSWORD.search(low) or (self._HELLO.search(low) and re.search(r"(?<!\w)(change|set|reset|forgot|update|new)(?!\w)", low)):
            if self._HELLO.search(low) and not re.search(r"(?<!\w)(company|email|outlook|account)(?!\w)", low):
                return {"task": "hello_sign_in", "reason": ""}
            if self._PASSWORD_UNCLEAR.search(low) and not self._PASSWORD_WHICH.search(low):
                return {"task": "clarify", "question": self.PASSWORD_QUESTION, "reason": ""}
            return {"task": "password_reset", "reason": ""}
        if self._INSTALL.search(low):
            entry = find_installable(text)
            return {"task": "install_software", "package": entry["name"], "reason": ""} if entry else None
        # "find chrome on my laptop and open it": it is installed here, so open the app (never search the web for it)
        if self._LOCAL.search(low) and re.search(r"(?<!\w)(open|launch|start|run)(?!\w)", low):
            apps = cfg("desktop", "allowed_apps", default={}) or {}
            local_app = next((n for n in sorted(apps, key=len, reverse=True) if self._whole_word(n, text)), None)
            if local_app:
                return {"task": "open_app", "app": local_app, "reason": ""}
        seen = self._see_app(text)                   # "can I see my task manager", "show me the calculator"
        if seen:
            return seen
        searched = self._search_pick(text)
        if searched:
            return searched
        m = self._OPEN.match(text)
        trailing = None if m else self._OPEN_IT.search(text)       # "... find vs code in my system, open it for me"
        if (not m and not trailing) or self._NOT_SIMPLE.search(low):
            return None
        rest = m.group(2).strip() if m else text.strip()
        rest = re.sub(r"(?i)google chrome", "chrome", rest)
        rest = re.sub(r"(?i)microsoft edge", "edge", rest)
        browsers = cfg("desktop", "browsers", default={}) or {}
        browser = next((b for b in browsers if self._whole_word(b, rest)), "default")
        # a web address, or a friendly site name
        url = None
        other = re.search(r"(?<!\w)([a-z][a-z0-9+.-]*:(?://|[\\])\S*)", rest, re.IGNORECASE)
        d = next((m for m in self._DOMAIN.finditer(rest)
                  if m.group(1).split("/")[0].rsplit(".", 1)[-1].lower() not in self._FILE_EXT), None)
        if other and not re.match(r"https?://", other.group(1), re.IGNORECASE):
            url = other.group(1)          # file:, ms-settings:, c:\ ... : plan_open_website refuses it with a clear reason
        elif d:
            url = d.group(1)
        else:
            aliases = cfg("desktop", "website_aliases", default={}) or {}
            for name in sorted(aliases, key=len, reverse=True):
                if self._whole_word(name, rest):
                    url = name
                    break
        if url:
            return {"task": "open_website", "url": url, "browser": browser, "reason": ""}
        folder = self._FOLDER.search(rest)
        if folder:
            return {"task": "open_folder", "folder": folder.group(1).title(), "reason": ""}
        named = (re.search(r"(?:website|web\s*site|site|tool|platform|web\s*page|service)\s+(?:called|named)\s*([\w][\w .\-]{1,40})", rest, re.IGNORECASE)
                 or re.search(r"(?:the\s+)?([\w][\w\-]{1,30})\s+(?:website|web\s*site|site)(?!\w)", rest, re.IGNORECASE)
                 or re.search(r"(?:website|web\s*site|site|tool|platform|web\s*page|service)\s+([\w][\w\-]{1,30})", rest, re.IGNORECASE))

        def site_term(raw: str) -> str:
            cleaned = re.sub(r"(?i)(?<!\w)(in|on|with|using)\s+(chrome|edge|firefox)(?!\w)", " ", raw)
            return self._tidy(self._NOUNS.sub(" ", cleaned))

        if named and not self._NOT_WEB.search(rest):               # "open the heygen site in chrome"
            term = site_term(named.group(1))
            if term and len(term.split()) <= 3 and not term.isdigit():
                return {"task": "find_site", "query": term, "browser": browser, "reason": ""}
        apps = cfg("desktop", "allowed_apps", default={}) or {}
        for name in sorted(apps, key=len, reverse=True):
            if self._whole_word(name, rest):
                return {"task": "open_app", "app": name, "reason": ""}
        # A site known only by name ("open heygen"): search for it, then open the best match once the user
        # approves the address.
        if self._NOT_WEB.search(rest):
            return None
        term = site_term(rest)
        if term.lower() in ("it", "that", "this", "them", "there"):
            return None
        if term and len(term.split()) <= 3 and not term.isdigit():
            return {"task": "find_site", "query": term, "browser": browser, "reason": ""}
        return None

    def _see_app(self, text: str) -> dict | None:
        """"see / show / view / bring up (my|the) <allowed app>": open that app. Only for apps on the allow-list."""
        apps = cfg("desktop", "allowed_apps", default={}) or {}
        for name in sorted(apps, key=len, reverse=True):
            if re.search(r"(?<!\w)(see|show|view|bring\s+up|display|pull\s+up)\s+(?:me\s+)?(?:my\s+|the\s+)?"
                         + re.escape(name) + r"(?!\w)", text, re.IGNORECASE):
                return {"task": "open_app", "app": name, "reason": ""}
        return None

    def plan_open_website(self, choice: dict) -> dict:
        url = clean_url(choice["url"])
        host = url.split("//", 1)[-1].split("/", 1)[0]
        browser = choice.get("browser") or "default"
        label = "your default browser" if browser == "default" else browser.title()
        return {
            "diagnosis": f"I can open {host} for you.", "fix": "computer_use_task", "reason": "", "risk": policy.R1,
            "summary": f"Open {host} in {label}",
            "what_changes": f"{label} will open {url}. Nothing on your computer is changed.",
            "steps": [{"tool": "open_website", "args": {"url": url, "browser": browser},
                       "label": f"Open {url} in {label}"}],
            "expected_file": None, "verify": "steps_ok",
        }

    @staticmethod
    def search_url(query: str) -> str:
        from urllib.parse import quote_plus
        template = str(cfg("desktop", "search_url", default="https://www.google.com/search?q={q}"))
        return template.replace("{q}", quote_plus(query))

    def plan_search_web(self, choice: dict) -> dict:
        """Open the search results page for the query in the chosen (default) browser."""
        query, browser = choice["query"], choice.get("browser") or "default"
        url = clean_url(self.search_url(query))
        label = "your default browser" if browser == "default" else browser.title()
        return {
            "diagnosis": f"I can search the web for \"{query}\" and show you the results.", "fix": "computer_use_task",
            "reason": "", "risk": policy.R1, "summary": f"Search the web for \"{query}\"",
            "what_changes": f"{label} will open a search for \"{query}\" ({url}). Nothing on your computer is changed.",
            "steps": [{"tool": "open_website", "args": {"url": url, "browser": browser},
                       "label": f"Search for \"{query}\" in {label}"}],
            "expected_file": None, "verify": "steps_ok",
        }

    @staticmethod
    def pick_site(results: list, term: str) -> dict | None:
        """The result whose address contains the name (heygen -> heygen.com), else the first result."""
        from urllib.parse import urlparse
        compact = re.sub(r"[^a-z0-9]", "", term.lower())
        for r in results:
            host = re.sub(r"[^a-z0-9]", "", (urlparse(r["url"]).hostname or "").lower())
            if compact and compact in host:
                return r
        return results[0] if results else None

    def plan_find_site(self, choice: dict, results: list, error: str = "") -> dict:
        """After the web search: propose opening the best match. Falls back to a search page if nothing was found."""
        term, browser = choice["query"], choice.get("browser") or "default"
        best = self.pick_site(results, term)
        if best is None:
            plan = self.plan_search_web({"query": term, "browser": browser})
            plan["diagnosis"] = (f"I could not find a clear website for \"{term}\" "
                                 f"({error or 'no search results'}), so I can open a web search for it instead.")
            return plan
        url = clean_url(best["url"])
        host = url.split("//", 1)[-1].split("/", 1)[0]
        label = "your default browser" if browser == "default" else browser.title()
        others = [r for r in results if r is not best][:2]
        more = ("  Other results: " + "; ".join(f"{r['title']} ({r['url'].split('//', 1)[-1].split('/', 1)[0]})"
                                                  for r in others)) if others else ""
        return {
            "diagnosis": f"I searched the web for \"{term}\". Best match: {best['title']} ({host}).{more}",
            "fix": "computer_use_task", "reason": "", "risk": policy.R1,
            "summary": f"Open {host} in {label}",
            "what_changes": f"{label} will open {url}. Check that this is the site you meant. Nothing on your computer is changed.",
            "steps": [{"tool": "open_website", "args": {"url": url, "browser": browser},
                       "label": f"Open {url} in {label}"}],
            "expected_file": None, "verify": "steps_ok",
        }

    def plan_save_as_pdf(self, choice: dict) -> dict:
        """Save a document as a PDF with the virtual printer: finds the file, says what will happen, verifies the PDF."""
        from tools import pdfprint
        phrase = choice["file"]
        found = pdfprint.find_documents(phrase, 4)
        source = pdfprint.resolve_document(phrase)
        say = lambda text: {"diagnosis": text, "fix": None, "reason": ""}      # noqa: E731
        if source is None:
            if found:
                names = ", ".join(p.name for p in found)
                return say(f"I found a few files that could be '{phrase}': {names}. Which one should I turn into a PDF?")
            return say(f"I looked through your folders and drives but couldn't find anything called '{phrase}'. "
                       "What's the file called? Even part of the name is enough.")
        ext = source.suffix.lower()
        if ext == ".pdf":
            return say(f"{source.name} is already a PDF, so there is nothing to convert.")
        if ext not in pdfprint.CONVERTIBLE:
            return say(f"{ext} files cannot be saved as a PDF with the printer. Open the file in its own program and use "
                       "Print > Microsoft Print to PDF there.")
        if not pdfprint.pdf_printer_installed():
            return say("The Microsoft Print to PDF printer is not installed on this computer, so I cannot make the PDF. "
                       "It can be switched on in Windows features, or IT can add it.")
        dest_name = choice.get("folder") or ("Desktop" if source.parent not in pdfprint._folders() else
                                             next((f for f in pdfprint.FOLDERS if pdfprint.folder_path(f) == source.parent), "Desktop"))
        target = pdfprint.free_path(pdfprint.folder_path(dest_name), pdfprint.safe_filename(source.stem, source.stem, "pdf"))
        label = f"Save {source.name} as {target.name} in {dest_name}"
        return {
            "diagnosis": (f"Found it: {source.name} ({source.parent}). I'll print it with Windows' virtual printer "
                          f"\"Microsoft Print to PDF\" and save it as {target.name} in {dest_name}."),
            "fix": "computer_use_task", "reason": "", "risk": policy.R1,
            "summary": f"Save {source.name} as a PDF in {dest_name}",
            "what_changes": (f"The file {source.name} is sent to the virtual printer \"Microsoft Print to PDF\" (nothing is printed "
                             f"on paper) and saved as {target} . Your original file is not changed."),
            "steps": [{"tool": "save_as_pdf", "args": {"file": str(source), "name": target.stem, "folder": dest_name},
                       "domain": "computer_use", "label": label}],
            "expected_file": str(target), "verify": "file",
        }

    def plan_open_folder(self, folder: str) -> dict:
        from connectors.base import CONNECTORS
        if CONNECTORS["files"].status() != "ready":
            raise PolicyError("The Files connector is switched off")
        return {
            "diagnosis": f"I can open your {folder} folder in File Explorer.", "fix": "computer_use_task", "reason": "",
            "risk": policy.R1, "summary": f"Open the {folder} folder",
            "what_changes": "File Explorer opens that folder. Nothing is changed.",
            "steps": [{"tool": "open_folder", "args": {"path": folder}, "domain": "files",
                       "label": f"Open the {folder} folder in File Explorer"}],
            "expected_file": None, "verify": "steps_ok",
        }

    _APP_NAMES = {"vscode": "VS Code", "vs code": "VS Code", "visual studio code": "Visual Studio Code",
                  "powerpoint": "PowerPoint", "onenote": "OneNote", "7-zip": "7-Zip", "notepad++": "Notepad++"}

    def plan_hello_sign_in(self) -> dict:
        """PIN / picture password / fingerprint: the user changes it in Settings themselves. Offer to open the page."""
        return {
            "diagnosis": "Got it, that one you can change yourself. It lives in Settings → Accounts → **Sign-in options**: "
                         "choose **PIN (Windows Hello)** → **Change PIN**, type your current PIN, then the new one twice. "
                         "Forgot the current one? On the same page there's an **I forgot my PIN** link.",
            "fix": "computer_use_task", "reason": "", "risk": policy.R1, "offer": True,
            "ask": "Want me to open Sign-in options for you?",
            "summary": "Open the Sign-in options settings",
            "what_changes": "The Settings app opens on Sign-in options. Nothing is changed.",
            "steps": [{"tool": "open_settings_page", "args": {"page": "sign_in_options"}, "domain": "settings",
                       "label": "Open Settings → Accounts → Sign-in options"}],
            "expected_file": None, "verify": "steps_ok",
        }

    def plan_open_app(self, app: str) -> dict:
        label = self._APP_NAMES.get(app, app.title())
        return {
            "diagnosis": f"I can open {label} for you.", "fix": "computer_use_task", "reason": "", "risk": policy.R1,
            "summary": f"Open {label}",
            "what_changes": f"{label} will open. Nothing on your computer is changed.",
            "steps": [{"tool": "open_application", "args": {"name": app}, "label": f"Open {label}"}],
            "expected_file": None, "verify": "steps_ok",
        }

    def plan_password_reset(self) -> dict:
        from connectors.base import CONNECTORS
        if CONNECTORS["directory"].status() != "ready":
            raise PolicyError("The account self-service connector is switched off")
        return {
            "diagnosis": ("I cannot reset or unlock a password myself: that needs your identity to be verified. "
                          "I can open your organisation's official self-service page, where you verify with MFA and "
                          "set the new password yourself."),
            "fix": "computer_use_task", "reason": "", "risk": policy.R1,
            "summary": "Open the password reset page",
            "what_changes": ("Your browser opens the official password reset page. Tobi never sees your password. "
                             "If the page does not work for you, ask me to raise a ticket."),
            "steps": [{"tool": "start_password_reset", "args": {}, "domain": "directory",
                       "label": "Open the password reset page"}],
            "expected_file": None, "verify": "steps_ok",
        }

    def plan_install(self, package: str) -> dict:
        entry = find_installable(package)
        if entry is None:
            raise PolicyError(f"'{package}' is not on the installable software list")
        if is_installed(entry):
            return {"diagnosis": f"{entry['name']} is already installed on this computer.", "fix": None, "reason": ""}
        return {
            "diagnosis": f"{entry['name']} is on the approved software list ({entry.get('how_to_get', 'approved')}).",
            "fix": "computer_use_task", "reason": "", "risk": policy.R2,
            "summary": f"Install {entry['name']}",
            "what_changes": (f"{entry['name']} will be downloaded and installed with winget (package "
                             f"{entry['winget_id']}). Windows may ask you to allow it: please accept. "
                             "This can take a few minutes, and I will check afterwards that it is installed."),
            "steps": [{"tool": "install_software", "args": {"package": entry["name"]},
                       "label": f"Install {entry['name']} with winget"}],
            "expected_file": None, "verify": "install", "package": entry["name"],
        }

    def pick_task(self, request: str) -> dict:
        quick = self.quick_pick(request)
        if quick:
            return quick
        tasks = cfg("browser", "allowed_tasks", default={}) or {}
        listing = "\n".join(f'  "{k}": {v}' for k, v in tasks.items())
        system = prompts.COMPUTER_USE.replace("{browser_tasks}", listing)

        def validate(d: dict) -> dict:
            task = str(d.get("task", "")).strip()
            if task not in ("write_health_note", "browser_task", "none"):
                raise ValueError('"task" must be write_health_note, browser_task or none')
            task_id = str(d.get("task_id") or "").strip()
            if task == "browser_task" and task_id not in tasks:
                raise ValueError(f'"task_id" must be one of {list(tasks)}')
            return {"task": task, "task_id": task_id, "reason": str(d.get("reason") or "")}

        return ask_json(system, f"User request: {request.strip()[:500]}", validate)

    def plan_health_note(self, health: dict, disks: dict) -> dict:
        target = documents_folder() / f"system_health_{datetime.now():%Y%m%d_%H%M%S}.txt"
        text = health_note_text(health, disks)
        steps = [
            {"tool": "write_text_file", "args": {"path": str(target), "content": text, "mode": "create"}, "domain": "files",
             "label": f"Save the health summary as {target.name} in Documents"},
            {"tool": "open_in_notepad", "args": {"path": str(target)}, "domain": "files",
             "label": f"Open {target.name} in Notepad"},
        ]
        return {
            "diagnosis": ("I measured the system health: CPU "
                          f"{health.get('cpu_percent')}%, memory {health.get('ram_percent')}% "
                          f"({health.get('ram_used_gb')} of {health.get('ram_total_gb')} GB)."),
            "fix": "computer_use_task", "reason": "", "risk": policy.R1,
            "summary": "Save the system health summary in Documents and open it in Notepad",
            "what_changes": (f"A new file will be saved as {target} and opened in Notepad. "
                             f"Nothing you have open in Notepad is touched.\n\n{text}"),
            "steps": steps, "expected_file": str(target), "expected_text": text,
        }

    @staticmethod
    def _safe_filename(raw: str, fallback: str) -> str:
        name = re.sub(r'[\\/:*?"<>|\x00-\x1f]', " ", raw or "")
        name = re.sub(r"\s+", " ", name).strip(" .")[:60]
        name = re.sub(r"(?i)\.txt$", "", name).strip(" .") or fallback
        if name.upper() in {"CON", "PRN", "AUX", "NUL", *[f"COM{i}" for i in range(1, 10)], *[f"LPT{i}" for i in range(1, 10)]}:
            name = f"{name} note"
        return name

    def plan_write_note(self, choice: dict) -> dict:
        """Save the user's text as <name>.txt in Desktop / Documents / Downloads and open it in Notepad."""
        text, folder_name = choice["text"], choice["folder"]
        if len(text) > 20000:
            raise PolicyError("The text is longer than 20000 characters")
        folder = known_folder(folder_name)
        base = self._safe_filename(choice.get("filename", ""), f"note {datetime.now():%Y-%m-%d %H%M%S}")
        target, n = folder / f"{base}.txt", 2
        while target.exists():                       # never replace an existing file
            target = folder / f"{base} ({n}).txt"
            n += 1
        # The file is written straight to its path (exact text, exact name), then opened in Notepad so you can see it.
        # Driving Notepad's own menus is unreliable (several windows, restored tabs) and would put the text into
        # tabs you already have open.
        steps = [
            {"tool": "write_text_file", "args": {"path": str(target), "content": text, "mode": "create"}, "domain": "files",
             "label": f"Save your text as {target.name} in {folder_name}"},
            {"tool": "open_in_notepad", "args": {"path": str(target)}, "domain": "files",
             "label": f"Open {target.name} in Notepad"},
        ]
        place = "on your Desktop" if folder_name == "Desktop" else f"in your {folder_name}"
        if choice.get("compose"):
            quoted = "\n".join(f"> {line}" if line.strip() else ">" for line in text.splitlines())
            extra = {"diagnosis": f"{choice.get('intro') or 'Here is what I wrote for you:'}\n\n{quoted}",
                     "ask": f"Shall I save this as {target.name} {place} and open it in Notepad?"}
        else:
            extra = {"diagnosis": f"I can save your text as {target.name} {place} and open it in Notepad."}
        return {
            **extra,
            "fix": "computer_use_task", "reason": "", "risk": policy.R1,
            "summary": f"Save your note as {target.name} in {folder_name}",
            "what_changes": (f"A new text file `{target}` is created with exactly the text below, then opened in Notepad. "
                             f"Nothing you already have open in Notepad is touched, and no existing file is replaced."
                             f"\n\n**Text:**\n\n> {text}"),
            "steps": steps, "expected_file": str(target), "expected_text": text,
        }

    def plan_browser_task(self, task_id: str) -> dict:
        description = (cfg("browser", "allowed_tasks", default={}) or {}).get(task_id, task_id)
        folder = browser_tools.download_folder()
        return {
            "diagnosis": "No diagnosis is needed for this task.",
            "fix": "computer_use_task", "reason": "", "risk": policy.R1,
            "summary": description,
            "what_changes": (f"A browser window will open the local test portal, click 'Download latest report' "
                             f"and save the file in {folder}."),
            "steps": [{"tool": "run_browser_task", "args": {"task_id": task_id},
                       "label": f"Run browser task '{task_id}': open the portal and download the report"}],
            "expected_file": None,
        }

    def verify(self, runner: ToolRunner, state: dict) -> dict:
        proposal = state["proposal"]
        results = state.get("fix_results") or [{}]
        if proposal.get("verify") == "deleted":
            ok = all(r.get("ok") for r in results) and not Path(proposal.get("deleted_path", "")).exists()
            return {"comparison": [{"metric": f"{Path(proposal['deleted_path']).name} on {Path(proposal['deleted_path']).parent.name}",
                                    "before": "there", "after": "in the Recycle Bin" if ok else "still there"}],
                    "fixed": ok, "note": "You can restore it from the Recycle Bin." if ok else
                    f"It could not be deleted: {results[-1].get('error', 'unknown error')}"}
        if proposal.get("verify") in ("steps_ok", "install"):
            ok = len(results) == len(proposal["steps"]) and all(r.get("ok") for r in results)
            if proposal["verify"] == "steps_ok":         # a simple task: a one-line "Done!", no Before/After table
                return {"comparison": [], "fixed": ok,
                        "note": "It was opened." if ok else
                                f"It could not be opened: {results[-1].get('error', 'unknown error')}"}
            entry = find_installable(proposal.get("package", ""))
            waited = wait_for_install(entry) if ok and entry else {"installed": False, "waited": 0, "exit_code": None}
            fixed = bool(ok and waited["installed"])
            note = (f"{proposal['package']} is now installed." if fixed else
                    f"The install did not finish or was not confirmed after {waited['waited']} seconds "
                    f"(winget exit code {waited['exit_code']})." if ok else
                    f"The install could not start: {results[-1].get('error', 'unknown error')}")
            return {"comparison": [{"metric": f"{proposal['package']} installed", "before": "no",
                                    "after": "yes" if fixed else "no"}], "fixed": fixed, "note": note}
        path = proposal.get("expected_file") or results[-1].get("saved_to")
        all_ok = all(r.get("ok") for r in results) and len(results) == len(proposal["steps"])
        check = (browser_tools.file_exists(path) if path
                 else {"exists": False, "fresh": False, "path": None, "size_bytes": 0})
        rows = [{"metric": f"New file saved: {check['path']}", "before": "no",
                 "after": f"yes ({check['size_bytes']} bytes)" if check["exists"] and check["fresh"] else "no"}]
        fixed = bool(all_ok and check["exists"] and check["fresh"])
        note = (f"The file was saved: {check['path']}" if fixed else "The file was not found after the task.")
        expected = proposal.get("expected_text")
        if fixed and expected:
            try:
                saved = Path(check["path"]).read_text(encoding="utf-8-sig", errors="replace")
            except OSError:
                saved = ""
            same = " ".join(saved.split()) == " ".join(expected.split())
            rows.append({"metric": "File holds your text", "before": "no", "after": "yes" if same else "no"})
            fixed = same
            note = (f"The file was saved with your text: {check['path']}" if same else
                    f"The file was saved ({check['path']}), but its content does not match the text you gave me.")
        return {"comparison": rows, "fixed": fixed, "note": note}


COMPUTER_USE = ComputerUse()
