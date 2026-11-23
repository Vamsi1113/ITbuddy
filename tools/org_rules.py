"""What the user may do here, from the organisation's rules for THEIR ODC: which printers to use, which Wi-Fi and VPN.

The rules live in config.yaml (organisation.odcs.<ODC>.printers / wifi / vpn): a structured list that Python checks,
so the answer is the same every time. The SOP documents (kb_sop/) explain and cite the same rules; this module
decides. Everything here is read-only except `print_file`, which needs the user's approval and only prints to a printer
that passed the checks below.

Printers: the catalogue lists the printers of the ODC (floor, colour, accepted file types, page limit, secure release,
who may use it). Tobi compares it with the printers installed on THIS computer, so it can say "use this one, it is
ready", "add this one first (here is how)", or "you may not use this one, and why". In a virtual desktop (AVD) only
printers redirected from the user's real PC or mapped by IT exist, so Tobi says so.
"""
from __future__ import annotations

import re
from pathlib import Path

from appconfig import cfg
from tools import powershell
from tools.registry import R0, R1, Param, tool

powershell.SCRIPTS.update({
    # one argument "file|printer": the file is opened with its own program's PrintTo verb, hidden, to that printer
    "print_file_to": (
        "$a=$env:ITB_ARG -split '\\|',2; if($a.Count -ne 2){throw 'bad argument'}; "
        "Start-Process -FilePath $a[0] -Verb PrintTo -ArgumentList ('\"'+$a[1]+'\"') -WindowStyle Hidden "
        "-ErrorAction Stop; 'ok'"
    ),
})

_REDIRECTED = re.compile(r"\s*\(redirected\s*\d*\)\s*$|\s*\(from [^)]+\)\s*$|\s*in session \d+\s*$", re.IGNORECASE)


def _base_name(name: str) -> str:
    """'HP Mono (redirected 2)' / '\\\\server\\queue' -> the plain queue name, lowercase."""
    n = _REDIRECTED.sub("", str(name or "")).strip().lower()
    return n.rsplit("\\", 1)[-1]


def odc_info(odc: str) -> dict:
    return (cfg("organisation", "odcs", default={}) or {}).get(odc) or {}


def installed_printers() -> list[dict]:
    from tools import printing
    try:
        return printing.collect_state()["printers"]
    except Exception:
        return []


def _match_installed(entry: dict, installed: list[dict]) -> dict | None:
    wanted = {_base_name(entry.get("name")), _base_name(entry.get("queue"))} - {""}
    for p in installed:
        if _base_name(p.get("Name")) in wanted:
            return p
    return None


def pdf_pages(path: Path) -> int | None:
    if path.suffix.lower() != ".pdf":
        return None
    try:
        from pypdf import PdfReader
        return len(PdfReader(str(path)).pages)
    except Exception:
        return None


def file_facts(file_name: str) -> dict:
    """{"name", "ext", "pages", "problems", "path"} for a document the user wants to print ({} when none is named)."""
    if not file_name:
        return {}
    from tools import printing
    info = printing.check_file(file_name)
    out = {"name": info.get("name", file_name), "found": info.get("found", False), "problems": info.get("problems", []),
           "path": info.get("path", ""), "ext": Path(info.get("name", file_name)).suffix.lower().lstrip("."), "pages": None}
    if out["path"]:
        out["pages"] = pdf_pages(Path(out["path"]))
    return out


def judge_printer(entry: dict, installed: list[dict], groups: list[str], floor: str, facts: dict) -> dict:
    """One printer of the ODC: can THIS user print THIS file on it right now, and what is the next step if not?"""
    local = _match_installed(entry, installed)
    reasons, blockers = [], []
    allowed_groups = [str(g).lower() for g in entry.get("allowed_groups") or []]
    if allowed_groups and not any(g.lower() in allowed_groups for g in groups):
        blockers.append(f"only members of {', '.join(entry['allowed_groups'])} may use it")
    accepts = [str(a).lower() for a in entry.get("accepts") or []]
    if facts.get("ext") and accepts and facts["ext"] not in accepts:
        blockers.append(f"it does not accept .{facts['ext']} files (accepted: {', '.join(accepts)})")
    maxp = entry.get("max_pages")
    if maxp and facts.get("pages") and facts["pages"] > int(maxp):
        reasons.append(f"{facts['pages']} pages is over its {maxp}-page limit: your manager must approve it first")
    if entry.get("secure_release"):
        reasons.append("secure release: tap your badge at the printer to collect it")
    if entry.get("approval"):
        reasons.append(str(entry["approval"]))
    if blockers:
        status = "not_allowed"
    elif local is None:
        status = "add_first"
    elif local.get("WorkOffline") or str(local.get("PrinterStatus")) in ("7",):
        status = "offline"
    else:
        status = "ready"
    row = {"printer": entry.get("name"), "status": status, "floor": str(entry.get("floor") or ""),
           "location": entry.get("location", ""), "colour": bool(entry.get("colour")),
           "accepts": entry.get("accepts") or [], "max_pages": maxp}
    if blockers:
        row["why_not"] = "; ".join(blockers)
    if reasons:
        row["conditions"] = reasons
    if status == "add_first" and entry.get("queue"):
        row["how_to_add"] = f"Settings > Bluetooth & devices > Printers & scanners > Add device > Add manually > {entry['queue']}"
    if floor and str(entry.get("floor") or "") == str(floor):
        row["on_your_floor"] = True
    return row


def print_options(file_name: str = "") -> dict:
    from tools import org_context, printing
    ctx = org_context.full_context()
    env, loc = ctx["environment"], ctx["location"]
    installed = installed_printers()
    virtual = [p["Name"] for p in installed if printing.is_virtual(p)]
    out = {"ok": True, "computer_type": env["kind"], "odc": loc["odc"] or "unknown", "floor": loc["floor"] or "unknown",
           "seat": loc["seat"] or "unknown", "located_by": loc["how"]}
    if env["kind"] == "avd":
        out["avd_note"] = ("This is a virtual desktop: only printers redirected from your own PC, or mapped by IT, "
                           "appear here. Redirection must be switched on in your remote desktop settings.")
    facts = file_facts(file_name)
    if facts:
        out["file"] = {k: facts[k] for k in ("name", "ext", "pages", "problems") if facts.get(k) not in (None, [], "")}
    if virtual:
        out["virtual_printers"] = virtual + ["(these save a file, they do not print on paper)"]
    if not loc["odc"]:
        out["note"] = ("The ODC is unknown, so the organisation's printers cannot be chosen for this user. Ask which ODC "
                       "they sit in (then use set_my_location), or list the installed printers.")
        out["installed_printers"] = [p.get("Name") for p in installed if not printing.is_virtual(p)][:8]
        return out
    entries = odc_info(loc["odc"]).get("printers") or []
    if not entries:
        out["note"] = f"No printers are listed for {loc['odc']} in the organisation rules."
        return out
    rows = [judge_printer(e, installed, ctx["groups"], loc["floor"], facts) for e in entries]
    order = {"ready": 0, "offline": 1, "add_first": 2, "not_allowed": 3}
    rows.sort(key=lambda r: (order[r["status"]], not r.get("on_your_floor"), r["printer"]))
    out["printers"] = rows[:6]
    ready = [r for r in rows if r["status"] == "ready"]
    out["summary"] = (f"{len(ready)} of {len(rows)} printers in {loc['odc']} are ready for you"
                      + (f"; best: {ready[0]['printer']}" if ready else ""))
    out["sop"] = odc_info(loc["odc"]).get("printing_sop", "")
    return out


# ------------------------------------------------------------------------------------------------ another ODC's printers
def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(text or "").lower()).strip()


def resolve_odc(text: str) -> str:
    """The ODC a user's words point at ("ODC B", "the Pune ODC", "block B"): its id, or "" when none is named."""
    q = _norm(text)
    for odc, info in (cfg("organisation", "odcs", default={}) or {}).items():
        names = {_norm(odc), _norm((info or {}).get("name", ""))} | {_norm(a) for a in (info or {}).get("aliases") or []}
        for n in names - {""}:
            if re.search(rf"(?<![a-z0-9]){re.escape(n)}(?![a-z0-9])", q):
                return odc
    return ""


def _access_policy(target: str) -> dict:
    """What the organisation says about people from other ODCs using THIS ODC's printers."""
    base = cfg("organisation", "printer_access", default={}) or {}
    own = odc_info(target).get("outside_printer_access") or {}
    return {"mode": own.get("mode") or base.get("default", "request"), "note": own.get("note", ""),
            "email": own.get("email") or base.get("request_email", ""), "portal": base.get("request_portal", ""),
            "approvers": base.get("approvers", ""), "turnaround": base.get("turnaround", ""), "sop": base.get("sop", "")}


def _own_options(ctx_odc: str, options: dict) -> list[dict]:
    keep = []
    for r in options.get("printers", [])[:3]:
        if r["status"] in ("ready", "add_first", "offline"):
            keep.append({"printer": r["printer"], "where": r.get("location", ""), "status": r["status"],
                         "colour": r.get("colour"), "accepts": r.get("accepts")})
    return keep


def printer_access_rules(target_text: str) -> dict:
    """Can this user use a printer in ANOTHER ODC? What the rules say, how to ask for access, and what to use meanwhile."""
    from tools import org_context
    ctx = org_context.full_context()
    loc = ctx["location"]
    odcs = cfg("organisation", "odcs", default={}) or {}
    target = resolve_odc(target_text)
    out = {"ok": True, "odc": loc["odc"] or "unknown", "floor": loc["floor"] or "unknown", "seat": loc["seat"] or "unknown",
           "located_by": loc["how"], "computer_type": ctx["environment"]["kind"], "target_odc": target or "unknown"}
    if target:
        out["target_name"] = (odcs.get(target) or {}).get("name", target)
    if not loc["odc"]:
        out["note"] = ("The user's own ODC is not known, so the access rules cannot be applied yet. Ask which ODC they "
                       "sit in (then use set_my_location)" + (f"; they want the printers of {out['target_name']}." if target else "."))
        out["known_odcs"] = sorted(odcs)
        return out
    if not target:
        out["note"] = "The user did not say which ODC's printer they mean. Ask which one."
        out["known_odcs"] = [k for k in sorted(odcs) if k != loc["odc"]]
        return out
    name = (odcs.get(target) or {}).get("name", target)
    out["target_name"] = name
    if target == loc["odc"]:
        out["access"] = "same_odc"
        out["note"] = f"{name} is the user's own ODC: its printers are the ones in get_my_print_options."
        return out
    policy = _access_policy(target)
    out["sop"] = policy["sop"]
    out["printers_there"] = [e.get("name") for e in odc_info(target).get("printers") or []][:4]
    own = print_options("")
    out["use_instead"] = _own_options(loc["odc"], own)
    out["other_devices"] = (odc_info(loc["odc"]).get("devices") or [])[:4]
    reason = "[your reason, for example the project or document]"
    if policy["mode"] == "not_possible":
        out["access"] = "not_possible"
        out["why"] = policy["note"] or f"{name} does not allow people from other ODCs to use its printers."
        return out
    out["access"] = "request_required"
    out["how_to_request"] = [f"Raise a request: {policy['portal']}" if policy["portal"] else "Raise a request with the IT Service Desk",
                             f"It is approved by {policy['approvers']}" + (f"; usually {policy['turnaround']}" if policy["turnaround"] else ""),
                             "Until it is approved, print on your own ODC's printers"]
    if policy["email"]:
        who = f"{loc['name'] or loc['odc']}" + (f", floor {loc['floor']}" if loc["floor"] else "") + (f", seat {loc['seat']}" if loc["seat"] else "")
        out["email"] = {"to": policy["email"], "subject": f"Printer access request: {name}",
                        "body": f"Hello, I sit in {who}. Please give me access to the printers in {name} "
                                f"({', '.join(out['printers_there'][:2])}) because {reason}. Thank you."}
    return out


@tool("workplace", R0, "Whether the user may use a printer in ANOTHER ODC (office block), what the SOP says, how to ask for "
      "access (request and email text), and which printers and devices of their own ODC to use meanwhile.",
      params=(Param("target", "str", "the user's words naming the other ODC, for example 'ODC B'", max_len=300),))
def get_printer_access_rules(target: str) -> dict:
    from rag.retrieval import fit_output
    return fit_output(printer_access_rules(target))


@tool("workplace", R1, "Raise a request (ticket) for access to the printers of ANOTHER ODC, with the user's ODC, floor and "
      "seat and the reason, so IT and the approvers get everything in one place.",
      params=(Param("target_odc", "str", "the other ODC, for example ODC B", max_len=60),
              Param("reason", "str", "why the user needs it, in the user's words", required=False, max_len=300)),
      change_note="A ticket is created for IT and the approvers. Nothing on your computer is changed, and no access is "
                  "given until it is approved.",
      summary="Raise a request for access to the {target_odc} printers")
def request_printer_access(target_odc: str, reason: str = "") -> dict:
    from tools import org_context, tickets
    target = resolve_odc(target_odc)
    if not target:
        return {"ok": False, "error": f"'{target_odc}' is not a known ODC",
                "known_odcs": sorted(cfg("organisation", "odcs", default={}) or {})}
    loc = org_context.detect_location()
    if not loc["odc"]:
        return {"ok": False, "error": "I do not know which ODC you sit in yet, so the request would be incomplete"}
    if target == loc["odc"]:
        return {"ok": False, "error": "That is your own ODC: you already have access to its printers"}
    policy = _access_policy(target)
    if policy["mode"] == "not_possible":
        return {"ok": False, "error": policy["note"] or "That ODC does not allow people from other ODCs to use its printers"}
    name = (cfg("organisation", "odcs", default={}) or {}).get(target, {}).get("name", target)
    summary = (f"Printer access request: a user from {loc['name'] or loc['odc']} (floor {loc['floor'] or '?'}, seat "
               f"{loc['seat'] or '?'}) needs to use the printers of {name}. Reason: {reason or 'not given'}. "
               f"Policy: {policy['sop'] or 'printer access policy'}; approvers: {policy['approvers'] or 'IT'}.")
    ticket = tickets.create_ticket(f"Printer access to {name}", summary, category="access_request", priority="P4",
                                   work_notes=f"Raised by Tobi after the user asked to print in {name}. Own ODC: {loc['odc']}.")
    return {"ok": True, "ticket": ticket.get("ref") or ticket.get("id"), "for": name, "approvers": policy["approvers"],
            "note": "No access is given until it is approved"}


# ------------------------------------------------------------------------------------------------ network
def network_options() -> dict:
    from tools import org_context
    ctx = org_context.full_context()
    env, loc, net = ctx["environment"], ctx["location"], ctx["network"]
    out = {"ok": True, "computer_type": env["kind"], "odc": loc["odc"] or "unknown", "located_by": loc["how"],
           "wifi_now": net["wifi"]["ssid"] if net["wifi"]["connected"] else "not on Wi-Fi",
           "vpn_now": "connected" if net["vpn"]["connected"] else "not connected"}
    if env["kind"] == "avd":
        out["avd_note"] = ("This is a virtual desktop: it uses the cloud network. Wi-Fi and VPN apply to the user's "
                           "own PC that connects to it, not to this session.")
    info = odc_info(loc["odc"])
    if not loc["odc"] or not info:
        out["note"] = "The ODC is unknown, so its Wi-Fi and VPN rules cannot be given. Ask which ODC the user sits in."
        return out
    wifi, vpn = info.get("wifi") or {}, info.get("vpn") or {}
    corp = [str(s) for s in wifi.get("corporate") or []]
    guest = [str(s) for s in wifi.get("guest") or []]
    out["allowed_wifi"] = {"corporate": corp, "guest": guest, "notes": wifi.get("notes", "")}
    out["vpn_rules"] = {k: vpn[k] for k in ("client", "gateway", "when_needed", "notes") if vpn.get(k)}
    guidance = []
    ssid = net["wifi"]["ssid"]
    if net["wifi"]["connected"]:
        if ssid in corp:
            guidance.append(f"You are on the corporate Wi-Fi ({ssid}): correct for {loc['odc']}.")
        elif ssid in guest:
            guidance.append(f"You are on the guest Wi-Fi ({ssid}). It cannot reach internal systems: switch to "
                            f"{' or '.join(corp) or 'the corporate network'}.")
        else:
            guidance.append(f"'{ssid}' is not a {loc['odc']} network. Company devices should use "
                            f"{' or '.join(corp) or 'the corporate network'}.")
    else:
        guidance.append("You are not on Wi-Fi" + (" (wired or virtual connection)." if env["kind"] != "physical" else "."))
    if vpn.get("when_needed"):
        guidance.append(f"VPN: {vpn['when_needed']}" + (f" Client: {vpn['client']}." if vpn.get("client") else ""))
    out["guidance"] = guidance
    out["sop"] = info.get("network_sop", "")
    return out


# ------------------------------------------------------------------------------------------------ tools
@tool("workplace", R0, "Which printers this user may use in their ODC, which are ready on this computer, which must "
      "be added first (with how), and which are not allowed and why. Optionally for one file the user wants to print.",
      params=(Param("file", "str", "file name the user wants to print, optional", required=False, max_len=120),))
def get_my_print_options(file: str = "") -> dict:
    from rag.retrieval import fit_output
    return fit_output(print_options(file))


@tool("workplace", R0, "Which Wi-Fi networks and VPN this user should use in their ODC, and whether the computer is on "
      "the right one now.")
def get_my_network_options() -> dict:
    from rag.retrieval import fit_output
    return fit_output(network_options())


@tool("workplace", R0, "The organisation's SOP text for a workplace topic (printing, Wi-Fi, VPN) that applies to this "
      "user's ODC, with the SOP id, version and section to cite.",
      params=(Param("topic", "str", "what the SOP should cover", max_len=300),))
def get_workplace_sop(topic: str) -> dict:
    from rag.tools_rag import lookup_sop
    return lookup_sop.__wrapped__(topic) if hasattr(lookup_sop, "__wrapped__") else lookup_sop(topic)


@tool("workplace", R1, "Print one file on one printer that is ready for this user. Only printers from the "
      "organisation's list that passed the checks; the file must be an accepted type.",
      params=(Param("file", "str", "file name or full path", max_len=200),
              Param("printer", "str", "printer name from get_my_print_options", max_len=100)),
      change_note="The file is sent to that printer and prints on paper. Printouts of confidential documents are "
                  "released with your badge where the SOP requires it.",
      summary="Print {file} on {printer}")
def print_file(file: str, printer: str) -> dict:
    facts = file_facts(file)
    if not facts.get("found"):
        return {"ok": False, "error": (facts.get("problems") or ["file not found"])[0]}
    if facts["problems"]:
        return {"ok": False, "error": "The file cannot be printed: " + "; ".join(facts["problems"])}
    options = print_options(file)
    row = next((r for r in options.get("printers", []) if r["printer"].lower() == str(printer).lower()), None)
    if row is None:
        return {"ok": False, "error": f"'{printer}' is not one of your ODC's printers", "choose_from":
                [r["printer"] for r in options.get("printers", []) if r["status"] == "ready"]}
    if row["status"] != "ready":
        return {"ok": False, "error": f"'{printer}' is not ready for you: {row.get('why_not') or row['status']}",
                "next_step": row.get("how_to_add", "")}
    installed = installed_printers()
    entry = next((e for e in odc_info(options["odc"]).get("printers") or [] if e.get("name") == row["printer"]), {})
    local = _match_installed(entry, installed)
    try:
        powershell.run_powershell("print_file_to", timeout=60, arg=f"{facts['path']}|{local['Name']}")
    except powershell.CommandError as e:
        return {"ok": False, "error": ("Windows could not send the file silently to the printer: " + str(e)[:160] +
                                       ". Open the file and press Ctrl+P, then choose " + row["printer"] + ".")}
    return {"ok": True, "file": facts["name"], "printer": row["printer"], "pages": facts.get("pages"),
            "conditions": row.get("conditions", []), "note": "sent to the printer queue"}
