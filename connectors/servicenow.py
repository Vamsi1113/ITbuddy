"""ServiceNow connector: create and read incidents through the REST Table API.

Credentials come from the .env file (SERVICENOW_INSTANCE, SERVICENOW_USER, SERVICENOW_PASSWORD), use a
dedicated low-privilege service account. Creating an incident is R1 (approval); reading is R0.
NOTE: this module was tested against mocked responses, not a live instance.
"""
from __future__ import annotations

import os
import re

import requests

from connectors.base import ensure, guard
from tools.registry import R0, R1, Param, tool

_INSTANCE = re.compile(r"[a-z0-9-]{3,40}")


def _base() -> str:
    instance = os.environ["SERVICENOW_INSTANCE"].strip().lower().replace(".service-now.com", "")
    if not _INSTANCE.fullmatch(instance):
        raise ValueError("SERVICENOW_INSTANCE must be just the instance name, for example dev12345")
    return f"https://{instance}.service-now.com/api/now/table/incident"


def _call(method: str, url: str, **kw) -> dict:
    r = requests.request(method, url, auth=(os.environ["SERVICENOW_USER"], os.environ["SERVICENOW_PASSWORD"]),
                         headers={"Accept": "application/json"}, timeout=20, **kw)
    if r.status_code >= 400:
        raise requests.RequestException(f"ServiceNow said {r.status_code}: {r.text[:150]}")
    return r.json()


def _safe(fn):
    def run(*a, **k):
        try:
            return fn(*a, **k)
        except (requests.RequestException, ValueError) as e:
            return {"ok": False, "error": str(e)[:250]}
    run.__name__ = fn.__name__
    run.__doc__ = fn.__doc__
    return run


@guard("servicenow_create_incident")
def _guard_create(args: dict) -> None:
    if not str(args.get("short_description", "")).strip() or len(str(args["short_description"])) > 160:
        raise ValueError("short_description must be 1 to 160 characters")
    if len(str(args.get("description", ""))) > 2000:
        raise ValueError("description is longer than 2000 characters")


@tool("servicenow", R1, "Create an incident in ServiceNow for the IT team.",
      params=(Param("short_description", "str", "one-line title", max_len=160),
              Param("description", "str", "details and what was already tried", max_len=2000, required=False),
              Param("urgency", "str", "1 high, 2 medium, 3 low", choices=("1", "2", "3"), required=False)),
      change_note="An incident is created in ServiceNow under the service account, with the text shown.",
      summary="Create a ServiceNow incident: {short_description}")
@_safe
def servicenow_create_incident(short_description: str, description: str = "", urgency: str = "3") -> dict:
    if (e := ensure("servicenow")):
        return e
    j = _call("POST", _base(), json={"short_description": short_description, "description": description,
                                     "urgency": urgency or "3", "caller_id": os.environ["SERVICENOW_USER"]})
    rec = j.get("result", {})
    return {"ok": True, "number": rec.get("number"), "state": rec.get("state")}


@tool("servicenow", R0, "Look up a ServiceNow incident by its number (for example INC0010023).",
      params=(Param("incident", "str", "incident number", max_len=20),))
@_safe
def servicenow_get_incident(incident: str) -> dict:
    if (e := ensure("servicenow")):
        return e
    if not re.fullmatch(r"INC\d{5,10}", incident.strip().upper()):
        return {"ok": False, "error": "An incident number looks like INC0010023"}
    j = _call("GET", _base(), params={"number": incident.strip().upper(), "sysparm_limit": 1,
                                      "sysparm_fields": "number,short_description,state,priority,opened_at,assigned_to"})
    rows = j.get("result", [])
    return {"ok": True, "incident": rows[0] if rows else None, **({} if rows else {"note": "No such incident"})}


@tool("servicenow", R0, "List the most recent open ServiceNow incidents raised by the service account.")
@_safe
def servicenow_recent_incidents() -> dict:
    if (e := ensure("servicenow")):
        return e
    j = _call("GET", _base(), params={"sysparm_limit": 6, "sysparm_query": "active=true^ORDERBYDESCsys_created_on",
                                      "sysparm_fields": "number,short_description,state,priority"})
    return {"ok": True, "incidents": j.get("result", [])}
