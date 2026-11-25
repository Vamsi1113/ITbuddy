"""The short "Steps taken" summary: WHY Tobi answered the way it did, in a few plain lines.

It leads with what the organisation's rules say (your ODC, floor and seat, the SOP, which printers or networks are
allowed) and with where the answer came from, instead of listing the tools that ran. Built by Python from the data of
the task, so it is always consistent and never invented by the model.

Each line is "**Label:** short text". Labels, in order:
  You         who/where Tobi took the user to be (ODC, floor, seat, and how it knew)
  This PC     the kind of computer (virtual desktop, physical PC)
  Rule        what the SOP / organisation allows (printers, file types, limits, Wi-Fi, VPN)
  File        the document that was checked
  Source      the SOP section, knowledge article or Microsoft page the answer came from
  Checked     what was measured on this computer (only when it matters)
  Result      what was changed (or that nothing was), and whether the user approved it
"""
from __future__ import annotations

import re

from appconfig import cfg

MAX_LINES = 7
MAX_CHARS = 120

_LOCATED = {
    "you told tobi": "you told me",
    "set in configuration": "set by your IT team",
    "your security group": "from your security group",
}

# What each check means in plain words (only used for the "Checked" line).
_CHECKED = {
    "get_system_health": "CPU and memory", "get_running_processes": "running programs", "get_disk_usage": "disk space",
    "find_large_temp_folders": "temp files", "get_user_folder_sizes": "your folders", "check_network_connection": "internet",
    "check_dns_resolution": "DNS", "get_wifi_info": "Wi-Fi", "get_network_config": "network settings",
    "check_port": "a network port", "diagnose_printing": "printers, queue and connection", "list_problem_devices": "devices",
    "get_app_crashes": "app crashes", "get_recent_errors": "recent errors", "get_antivirus_status": "antivirus",
    "get_firewall_status": "firewall", "find_installed_software": "installed software", "get_windows_update_status":
    "Windows Update", "get_current_user": "your account", "read_setting": "a Windows setting",
}
# Tools whose results are already shown through a Rule / Source line.
_SILENT = {"get_my_org_context", "get_my_print_options", "get_my_network_options", "get_workplace_sop", "lookup_sop",
           "search_knowledge_base", "search_knowledge_base_rag", "lookup_policy", "lookup_error_code", "match_runbook",
           "find_similar_tickets", "get_kb_document", "kb_index_stats", "report_kb_gap", "submit_kb_feedback",
           "draft_kb_article"}


def _short(text: str, limit: int = MAX_CHARS) -> str:
    text = re.sub(r"\s+", " ", str(text or "")).strip()
    return text if len(text) <= limit else text[: limit - 1].rsplit(" ", 1)[0] + "…"


def _line(label: str, text: str) -> str:
    return f"**{label}:** {_short(text)}"


def _outputs(state: dict) -> dict:
    """tool name -> its (last) output, from a specialist's diagnostics or Autopilot's history."""
    out = {}
    for key, value in (state.get("diagnostics") or {}).items():
        if isinstance(value, dict):
            out[re.sub(r"#\d+$", "", key)] = value
    for item in state.get("auto_history") or []:
        if item.get("tool") and isinstance(item.get("result"), dict):
            out[item["tool"]] = item["result"]
    return out


def _odc_name(odc: str) -> str:
    info = (cfg("organisation", "odcs", default={}) or {}).get(odc) or {}
    return info.get("name") or odc


def _sop_label(citation: str) -> str:
    """'[SOP-IT-PRN-005 Printing in Pune ODC 1 v1.4 § Approved printers]' -> 'SOP-IT-PRN-005 v1.4 · Approved printers'."""
    m = re.match(r"\[(SOP-[\w-]+)\s.*?\sv([\w.]+)\s§\s(.+)\]$", citation or "")
    if m:
        return f"{m.group(1)} v{m.group(2)} · {m.group(3)}"
    m = re.match(r"\[Microsoft Learn: (.+?) – https?://\S+\]$", citation or "")
    if m:
        return f"Microsoft Learn · {m.group(1)}"
    m = re.match(r"\[(.+?) § (.+)\]$", citation or "")
    if m:
        return f"{m.group(1)} · {m.group(2)}"
    return (citation or "").strip("[]")


def _context_lines(out: dict) -> list[str]:
    ctx = (out.get("get_my_print_options") or out.get("get_my_network_options") or out.get("get_printer_access_rules")
           or out.get("get_my_org_context"))
    if not ctx:
        return []
    lines = []
    odc = ctx.get("odc")
    if odc and odc != "unknown":
        where = [_odc_name(odc)]
        if ctx.get("floor") not in (None, "", "unknown"):
            where.append(f"floor {ctx['floor']}")
        if ctx.get("seat") not in (None, "", "unknown"):
            where.append(f"seat {ctx['seat']}")
        how = str(ctx.get("located_by") or "")
        how = _LOCATED.get(how.lower(), how.replace("seat table (", "seat table (").strip())
        how = re.sub(r"^(this PC's|the remote PC's) network \(.*\)$", r"from \1 network", how)
        lines.append(_line("You", " · ".join(where) + (f" ({how})" if how else "")))
    else:
        lines.append(_line("You", "ODC not known, so I could not apply any office rules"))
    kind = ctx.get("computer_type")
    if kind == "avd":
        lines.append(_line("This PC", "virtual desktop (AVD)" + (": Wi-Fi and VPN are your own PC's" if "allowed_wifi" in ctx else "")))
    elif kind in ("virtual_machine", "remote_desktop"):
        lines.append(_line("This PC", "virtual machine"))
    return lines


def _access_lines(out: dict) -> list[str]:
    acc = out.get("get_printer_access_rules")
    if not acc:
        return []
    name = acc.get("target_name") or acc.get("target_odc")
    sop = f" ({acc['sop']})" if acc.get("sop") else ""
    if acc.get("odc") == "unknown":
        lines = [_line("Rule", f"I need your own ODC to check access to {name}" if acc.get("target_name") else
                       "I need your own ODC, and the ODC whose printer you mean")]
    elif acc.get("access") == "request_required":
        lines = [_line("Rule", f"{name} printers are for that ODC: other ODCs need approval{sop}")]
        if acc.get("how_to_request"):
            lines.append(_line("Rule", acc["how_to_request"][1].replace("It is approved by", "approved by")))
    elif acc.get("access") == "not_possible":
        lines = [_line("Rule", f"{name} does not allow other ODCs to use its printers{sop}")]
    elif acc.get("access") == "same_odc":
        lines = [_line("Rule", f"{name} is your own ODC")]
    else:
        lines = [_line("Rule", "no other ODC was named, so nothing to check")]
    use = acc.get("use_instead") or []
    if use:
        lines.append(_line("This PC", "your ODC's printers: " + ", ".join(u["printer"] for u in use[:3])))
    return lines


def _rule_lines(out: dict) -> list[str]:
    lines = _access_lines(out)
    opts = out.get("get_my_print_options")
    if opts and opts.get("printers"):
        rows = opts["printers"]
        sop = opts.get("sop") or ""
        allowed = [r for r in rows if r.get("status") != "not_allowed"]
        refused = [r for r in rows if r.get("status") == "not_allowed"]
        names = ", ".join(r["printer"] for r in allowed) or "none"
        lines.append(_line("Rule", f"allowed printers: {names}" + (f" ({sop})" if sop else "")))
        for r in refused[:2]:
            lines.append(_line("Rule", f"{r['printer']} not allowed: {r.get('why_not', 'not for you')}"))
        best = (allowed or rows)[0]
        accepts = "/".join(str(a).upper() for a in best.get("accepts") or [])
        limit = f", max {best['max_pages']} pages" if best.get("max_pages") else ""
        extra = [c for c in best.get("conditions", []) if "page limit" not in c]
        takes = f"{best['printer']} takes {accepts}{limit}" if accepts else ""
        if takes or extra:
            lines.append(_line("Rule", "; ".join(x for x in ([takes] + extra[:1]) if x)))
        if best.get("status") == "add_first":
            lines.append(_line("This PC", f"{best['printer']} is not added here yet"))
        elif best.get("status") == "offline":
            lines.append(_line("This PC", f"{best['printer']} is offline"))
        elif best.get("status") == "ready":
            lines.append(_line("This PC", f"{best['printer']} is ready"))
    elif opts and opts.get("note"):
        lines.append(_line("Rule", "no office printer list applies without your ODC"))
    net = out.get("get_my_network_options")
    if net and net.get("allowed_wifi"):
        wifi = net["allowed_wifi"]
        nets = ", ".join(wifi.get("corporate") or []) or "none"
        guest = ", ".join(wifi.get("guest") or [])
        lines.append(_line("Rule", f"company Wi-Fi: {nets}" + (f"; guest: {guest}" if guest else "; no guest Wi-Fi")
                           + (f" ({net['sop']})" if net.get("sop") else "")))
        vpn = (net.get("vpn_rules") or {}).get("when_needed")
        if vpn:
            lines.append(_line("Rule", "VPN: " + vpn))
    return lines


def _file_line(out: dict) -> list[str]:
    f = (out.get("get_my_print_options") or {}).get("file")
    if not f:
        return []
    bits = [f.get("name", "")]
    if f.get("pages"):
        bits.append(f"{f['pages']} pages")
    text = " · ".join(b for b in bits if b)
    if f.get("problems"):
        text += f" ({f['problems'][0]})"
    return [_line("File", text)]


def _saved_pdf_lines(state: dict) -> list[str]:
    """Save-as-PDF: which document became which PDF, and that nothing was printed on paper."""
    for r in state.get("fix_results") or []:
        if isinstance(r, dict) and r.get("saved_as") and r.get("from"):
            folder = str(r.get("folder") or "").replace("\\", "/").rstrip("/").split("/")[-1]
            return [_line("File", f"{r['from']} → {r.get('file_name', '')} ({folder})"),
                    _line("Rule", "saved with the virtual printer: nothing printed on paper, original unchanged")]
    return []


def _source_lines(out: dict, proposal: dict) -> list[str]:
    cites: list[str] = []
    for tool in ("get_workplace_sop", "lookup_sop", "search_knowledge_base", "search_knowledge_base_rag", "lookup_policy"):
        res = out.get(tool) or {}
        for r in res.get("results") or []:
            src = r.get("source") if isinstance(r, dict) else None
            if src:
                cites.append(_sop_label(src))
        if res.get("citation"):
            cites.append(_sop_label(res["citation"]))
    err = (out.get("lookup_error_code") or {}).get("citation")
    if err:
        cites.append(_sop_label(err))
    cites = list(dict.fromkeys(cites))
    if proposal.get("general"):
        return [_line("Source", "no company article covers this, so general Windows guidance")]
    return [_line("Source", c) for c in cites[:2]]


def _checked_line(out: dict) -> list[str]:
    names = [_CHECKED[t] for t in out if t in _CHECKED]
    if not names:
        extra = [t.replace("_", " ").removeprefix("get ") for t in out if t not in _SILENT and t not in _CHECKED]
        names = extra[:3]
    return [_line("Checked", ", ".join(list(dict.fromkeys(names))[:4]))] if names else []


def _result_line(state: dict) -> list[str]:
    outcome = state.get("outcome")
    proposal = state.get("proposal") or {}
    if outcome == "chat":
        return []
    if outcome == "refused":
        return [_line("Result", f"blocked by the safety policy: {state.get('error', '')}")]
    if outcome == "escalated":
        t = state.get("ticket") or {}
        return [_line("Result", f"ticket {t.get('ref', '')} opened for IT" if t else "passed to IT, nothing changed")]
    if outcome == "rejected":
        return [_line("Result", "you declined, so nothing was changed")]
    if outcome in ("fixed", "done", "not_fixed"):
        what = proposal.get("summary") or "a change"
        tail = "you approved it first" + ("" if outcome in ("fixed", "done") else "; it did not fully work")
        return [_line("Result", f"{what} ({tail})")]
    if outcome == "error":
        return [_line("Result", "stopped with an error, nothing was changed")]
    return [_line("Result", "nothing was changed")]


def build(state: dict) -> list[str]:
    """The lines for the "Steps taken" panel of this task (empty for plain chat)."""
    if state.get("outcome") == "chat":
        return []
    if state.get("outcome") == "done" and not state.get("auto_history"):   # a small "opened X": nothing to explain
        return []
    out = _outputs(state)
    proposal = state.get("proposal") or {}
    lines: list[str] = []
    orig, request = state.get("original_request"), state.get("request")
    if orig and request and orig != request:
        lines.append(_line("You said", f"“{_short(orig, 40)}” → {_short(request, 70)}"))
    lines += _context_lines(out)
    lines += _rule_lines(out)
    lines += _file_line(out)
    lines += _saved_pdf_lines(state)
    lines += _source_lines(out, proposal)
    if not any(l.startswith(("**Rule", "**Source")) for l in lines):
        lines += _checked_line(out)                     # measurements matter when no rule or source explains the answer
    result = _result_line(state)
    # one "This PC" line (kind of computer + printer state), placed right after the "You" lines
    pc = [l.split(":** ", 1)[1] for l in lines if l.startswith("**This PC:**")]
    rest = [l for l in lines if not l.startswith("**This PC:**")]
    if pc:
        after_you = max((i + 1 for i, l in enumerate(rest) if l.startswith("**You")), default=0)
        rest.insert(after_you, _line("This PC", "; ".join(pc)))
    seen, final = set(), []
    for l in rest:
        if l not in seen:
            seen.add(l)
            final.append(l)
    if not final and (state.get("agent") == "computer_use" or state.get("outcome") == "done"):
        return []                    # a simple computer task with nothing to explain: no "Steps taken" panel at all
    return final[:MAX_LINES - len(result)] + result              # the result line is always kept
