"""Router: one short model call that picks a specialist."""
from __future__ import annotations

from agent import prompts
from agent.llm import ask_json
import re

from agent.specialists import COMPUTER_USE, DOMAINS
from tools import printing

AGENTS = tuple(DOMAINS)


def _validate(data: dict) -> dict:
    agent = str(data.get("agent", "")).strip().lower().replace(" ", "_").replace("-", "_")
    if agent not in AGENTS + ("none",):
        raise ValueError(f'"agent" must be one of {AGENTS + ("none",)}')
    return {"agent": agent, "question": str(data.get("question") or "").strip()}


def system_prompt() -> str:
    listing = "\n".join(f"{d.name}: {d.route_hint}" for d in DOMAINS.values())
    return prompts.ROUTER.replace("{domains}", listing)


_HOWTO_QUESTION = re.compile(r"^\s*(?:(?:hi|hey|hello|please|pls)[\s,]+)*how\s+(?:do|can|could|would|should|to)(?!\w)",
                            re.IGNORECASE)


_AUTOPILOT = re.compile(
    r"^\s*(?:(?:hi|hey|hello|please|pls|can you|could you|can u|would you)[\s,]+)*"
    r"(show|read|list|summari[sz]e|find|search|send|write|draft|compose|schedule|create|check|get|fetch|what'?s|what is|"
    r"do i have|any new|look up|google)(?!\w).{0,80}?(?<!\w)(e-?mails?|inbox|calendar|meetings?|appointments?|folders?|"
    r"files?|documents?|powershell|servicenow|incidents?|intune|web ?page|online)(?!\w)", re.IGNORECASE)


_WORKPLACE = re.compile(
    r"(?<!\w)((?:which|what)\s+(?:printers?|wi-?fi|wifi\s+network|networks?|vpn|ssid)|"
    r"(?:where|which\s+\w+)\s+(?:can|should|do)\s+i\s+print|where\s+(?:do|can|should)\s+i\s+(?:print|connect)|"
    r"(?:which|what)\s+(?:odc|floor|seat|office)\s+(?:am|is)|where\s+am\s+i\s+(?:sitting|located)|my\s+(?:odc|seat|floor)|"
    r"i\s+(?:am|m|sit|work)\s+(?:in|at|from)\s+(?:odc|the\s+\w+\s+odc)|are\s+we\s+on\s+(?:avd|a\s+virtual)|"
    r"(?:am\s+i|is\s+this)\s+(?:on|in)\s+(?:an?\s+)?(?:avd|virtual\s+desktop|physical)|"
    r"(?:print|send)\s+(?:this|that|the|my|a)?\s*[\w\-. ()]{1,60}\.(?:pdf|docx?|xlsx?|pptx?|txt|png|jpe?g)|"
    r"printers?\s+(?:available|near|on\s+my\s+floor|in\s+my))(?!\w)", re.IGNORECASE)
_SOP_QUESTION = re.compile(
    r"(?<!\w)(sops?|standard operating procedures?|(?:which|what) printers?\s+(?:can|may|am|should|do)|"
    r"am i allowed|are we allowed|allowed to|(?:rules?|polic(?:y|ies))\s+(?:for|on|about)|in my odc|my odc|"
    r"(?:is|are)\s+[\w\s-]{1,40}?\s+allowed|can\s+(?:i|we)\s+(?!not\b)(?:print|use|install|bring|plug|connect|copy|share))(?!\w)",
    re.IGNORECASE)
_SCREEN_TASK = re.compile(
    r"(?<!\w)(record(?:ing)?(?!\w).{0,30}(?<!\w)(?:screen|desktop|display)(?!\w)|"
    r"screen\s*record(?:ing)?|take\s+(?:a\s+|me\s+a\s+)?screen\s*shot|screen\s*shot\s+(?:of|my)|capture\s+(?:my\s+|the\s+)?screen)",
    re.IGNORECASE)
_HOW_ANYWHERE = re.compile(r"(?<!\w)how\s+(?:do|can|could|to|should|would)(?!\w)|(?<!\w)(?:explain|tell me about|what is)(?!\w)",
                           re.IGNORECASE)


def fast_route(request: str) -> dict | None:
    """Obvious requests are routed in Python, so a small model cannot send "open YouTube" to the knowledge base."""
    if COMPUTER_USE.quick_pick(request):
        return {"agent": "computer_use", "question": ""}
    if re.search(r"(?<!\w)(power ?shell|servicenow|intune)(?!\w)", request, re.IGNORECASE):
        return {"agent": "autopilot", "question": ""}
    if _AUTOPILOT.match(request) and not _HOWTO_QUESTION.match(request):
        return {"agent": "autopilot", "question": ""}
    if _HOWTO_QUESTION.match(request):
        return {"agent": "howto", "question": ""}
    if _WORKPLACE.search(request) and not _HOW_ANYWHERE.search(request):
        return {"agent": "workplace", "question": ""}
    if _SOP_QUESTION.search(request):
        return {"agent": "howto", "question": ""}              # what the SOP says: before any troubleshooting
    if printing.is_print_request(request):
        return {"agent": "devices", "question": ""}
    if _SCREEN_TASK.search(request) and not _HOW_ANYWHERE.search(request):
        return {"agent": "autopilot", "question": ""}          # recordings and screenshots: the general agent's tools
    return None


def route(request: str) -> dict:
    """Return {"agent": ..., "question": ...}. Raises ModelError if the model fails."""
    fast = fast_route(request)
    if fast:
        return fast
    return ask_json(system_prompt(), f"Request: {request.strip()[:500]}", _validate)
