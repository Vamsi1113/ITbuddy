"""The tool catalogue. Agents can only call tools registered here. There is no shell tool.

Every tool has a domain (the one specialist that may use it) and a risk tier:
  R0 read-only            runs automatically
  R1 low-impact change    needs user approval
  R2 medium change        needs user approval (shown with a stronger warning)
  R3 high / irreversible  never executed by the agent: it opens a ticket for IT instead
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

R0, R1, R2, R3 = 0, 1, 2, 3


@dataclass(frozen=True)
class Param:
    name: str
    type: str = "str"                       # "str" or "int"
    description: str = ""
    choices: tuple | Callable[[], list] | None = None
    required: bool = True
    max_len: int = 200

    def allowed(self) -> list | None:
        if self.choices is None:
            return None
        return list(self.choices() if callable(self.choices) else self.choices)


@dataclass(frozen=True)
class ToolSpec:
    name: str
    func: Callable[..., dict]
    domain: str
    risk: int
    description: str
    params: tuple = ()
    change_note: str = ""                   # shown on the approval card for R1/R2 tools
    summary: str = ""                       # approval card title; may use {argument} placeholders


TOOLS: dict[str, ToolSpec] = {}


def tool(domain: str, risk: int, description: str, params: tuple = (), change_note: str = "", summary: str = ""):
    def register(func):
        TOOLS[func.__name__] = ToolSpec(func.__name__, func, domain, risk, description, tuple(params),
                                        change_note, summary)
        return func
    return register


def validate_args(spec: ToolSpec, args: dict | None) -> dict:
    """Type and allow-list check of tool arguments. Raises ValueError with a message the model can act on."""
    args = dict(args or {})
    known = {p.name for p in spec.params}
    extra = set(args) - known
    if extra:
        raise ValueError(f"{spec.name} does not take {sorted(extra)}")
    clean = {}
    for p in spec.params:
        value = args.get(p.name)
        if value is None or value == "":
            if p.required:
                raise ValueError(f'{spec.name} needs "{p.name}"')
            continue
        if p.type == "int":
            if isinstance(value, bool):
                raise ValueError(f'"{p.name}" must be a whole number')
            try:
                value = int(value)
            except (TypeError, ValueError):
                raise ValueError(f'"{p.name}" must be a whole number')
        else:
            if not isinstance(value, str):
                raise ValueError(f'"{p.name}" must be text')
            value = value.strip()
            if len(value) > p.max_len:
                raise ValueError(f'"{p.name}" is too long')
        allowed = p.allowed()
        if allowed is not None:
            lookup = {str(a).lower(): a for a in allowed}
            if str(value).lower() not in lookup:
                raise ValueError(f'"{p.name}" must be one of {allowed}')
            value = lookup[str(value).lower()]
        clean[p.name] = value
    return clean


def tools_for(domain: str, *, read_only: bool | None = None) -> list[ToolSpec]:
    out = [t for t in TOOLS.values() if t.domain == domain]
    if read_only is True:
        out = [t for t in out if t.risk == R0]
    elif read_only is False:
        out = [t for t in out if t.risk in (R1, R2)]
    return out


def catalogue_text(specs: list[ToolSpec]) -> str:
    """Compact tool list for a prompt."""
    lines = []
    for t in specs:
        parts = []
        for p in t.params:
            allowed = p.allowed()
            hint = f" one of {allowed}" if allowed is not None and len(allowed) <= 40 else f" ({p.description})" if p.description else ""
            parts.append(f"{p.name}: {p.type}{hint}{'' if p.required else ', optional'}")
        lines.append(f"- {t.name}({'; '.join(parts)}): {t.description}")
    return "\n".join(lines)


# Importing the modules registers their tools. Keep this at the bottom.
from tools import (account, automation, browser, desktop, devices, knowledge, logs, network,  # noqa: E402,F401
                   org_context, performance, printing, security, settings, software, storage, tickets)

# RAG tools – import after base tools so they can override/extend the howto domain.
# Safe to import even if optional RAG dependencies are absent (graceful degradation).
try:
    from rag import tools_rag  # noqa: F401
except Exception:
    pass  # RAG index not initialised yet; tools will be registered on first ingest


# Connectors: files, PowerShell, web, Microsoft 365 / Intune / Defender, ServiceNow. Each registers its own tools.
try:
    from connectors import files, msgraph, servicenow, shell, web  # noqa: F401
except Exception:  # a broken connector must never stop the original tools
    import logging
    logging.getLogger("connectors").exception("Connectors could not be loaded")
