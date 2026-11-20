"""Connector registry: what Tobi can reach, whether it is switched on, and whether it is set up.

A connector groups the tools for one system (local files, PowerShell, the web, Microsoft 365, Intune,
ServiceNow ...). Switching one on is `connectors.<id>.enabled: true` in config.yaml; credentials come from
environment variables (the .env file), never from config.yaml or code. A tool whose connector is not ready
returns a clear "needs setup" message instead of failing, and the Autopilot agent does not offer it to the model.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field

from appconfig import cfg


@dataclass(frozen=True)
class Connector:
    id: str
    name: str
    description: str
    kind: str                          # builtin | local | cloud
    domains: tuple = ()                # the tool domains this connector provides
    needs: tuple = ()                  # environment variables that must be set (credentials, ids)
    setup: str = ""                    # how to set it up, shown in the interface
    always_on: bool = False            # built-in capabilities have no switch

    def settings(self) -> dict:
        return cfg("connectors", self.id, default={}) or {}

    def enabled(self) -> bool:
        return True if self.always_on else bool(self.settings().get("enabled", False))

    def missing(self) -> list[str]:
        return [v for v in self.needs if not os.environ.get(v)]

    def status(self) -> str:
        if not self.enabled():
            return "disabled"
        return "needs setup" if self.missing() else "ready"

    def tool_names(self) -> list[str]:
        from tools.registry import TOOLS
        return sorted(t.name for t in TOOLS.values() if t.domain in self.domains)


CONNECTORS: dict[str, Connector] = {}
_BY_DOMAIN: dict[str, Connector] = {}


def register(connector: Connector) -> Connector:
    CONNECTORS[connector.id] = connector
    for d in connector.domains:
        _BY_DOMAIN[d] = connector
    return connector


def for_domain(domain: str) -> Connector | None:
    return _BY_DOMAIN.get(domain)


def domain_ready(domain: str) -> bool:
    """Domains no connector claims (the original specialists) are always available."""
    c = _BY_DOMAIN.get(domain)
    return c is None or c.status() == "ready"


def ensure(connector_id: str) -> dict | None:
    """None when the connector is ready; otherwise an error result a tool can return as it is."""
    c = CONNECTORS[connector_id]
    st = c.status()
    if st == "ready":
        return None
    if st == "disabled":
        return {"ok": False, "error": f"The {c.name} connector is switched off. Set connectors.{c.id}.enabled: true "
                                      "in config.yaml to use it."}
    return {"ok": False, "error": f"The {c.name} connector needs setup: set {', '.join(c.missing())} in the .env file. "
                                  f"{c.setup}".strip()}


# ---------------------------------------------------------------------------
# The catalogue. Built-ins describe what the original specialists already do.
# ---------------------------------------------------------------------------
register(Connector("system", "This computer (diagnostics and fixes)", "CPU, memory, disk, network, settings, software, "
                   "logs, security status, devices and the safe fixes for them.", "builtin",
                   ("performance", "storage", "network", "settings", "software", "logs", "security", "account", "devices"),
                   always_on=True))
register(Connector("knowledge", "Knowledge base (RAG)", "Company how-to articles, policies and error codes, searched "
                   "with hybrid retrieval and cited.", "builtin", ("howto",), always_on=True))
register(Connector("tickets", "Built-in ticket desk", "Raises and tracks tickets for IT staff.", "builtin",
                   ("it_request",), always_on=True))
register(Connector("desktop", "Desktop and browser control", "Opens apps and websites, installs approved software, "
                   "operates Notepad and the test portal.", "builtin", ("computer_use",), always_on=True))
register(Connector("files", "Files", "Read, search and write files inside folders you allow.", "local", ("files",),
                   setup="Folders are listed under connectors.files.folders in config.yaml."))
register(Connector("shell", "PowerShell", "Run a PowerShell command after you approve the exact command.", "local",
                   ("shell",)))
register(Connector("web", "Web reader", "Read public web pages and search the web (text only, treated as untrusted).",
                   "local", ("web",)))
register(Connector("directory", "Account self-service", "Password reset and account unlock through your organisation's "
                   "own verified self-service page.", "cloud", ("directory",)))
register(Connector("microsoft365", "Microsoft 365 (mail, calendar, profile)", "Read and send mail, calendar, "
                   "account details, through Microsoft Graph with your own sign-in.", "cloud", ("m365",),
                   ("M365_CLIENT_ID",),
                   "Register a public-client app in Entra ID (Allow public client flows) with the Graph "
                   "permissions listed in config.yaml, then put its client id in M365_CLIENT_ID "
                   "(and M365_TENANT_ID if not 'organizations')."))
register(Connector("intune", "Intune (managed devices)", "Device compliance and remote sync through Microsoft Graph.",
                   "cloud", ("intune",), ("M365_CLIENT_ID",), "Uses the same Entra app as Microsoft 365."))
register(Connector("defender", "Defender (security alerts)", "Read security alerts through Microsoft Graph.", "cloud",
                   ("defender",), ("M365_CLIENT_ID",), "Uses the same Entra app as Microsoft 365."))
register(Connector("servicenow", "ServiceNow (ITSM)", "Create and read incidents in ServiceNow.", "cloud",
                   ("servicenow",), ("SERVICENOW_INSTANCE", "SERVICENOW_USER", "SERVICENOW_PASSWORD"),
                   "Set the instance name (for example dev12345), a service account and its password."))


# ---------------------------------------------------------------------------
# Argument guards: per-tool allow-list checks run by the policy gate (safety/policy.check_args).
# A guard raises ValueError with a message the user can read.
# ---------------------------------------------------------------------------
GUARDS: dict = {}


def guard(tool_name: str):
    def register_guard(fn):
        GUARDS[tool_name] = fn
        return fn
    return register_guard
