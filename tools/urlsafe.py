"""The one place that decides which web addresses may be opened or read (public http/https only)."""
from __future__ import annotations

import ipaddress
import re
from urllib.parse import urlparse

from appconfig import cfg


def clean_url(raw: str) -> str:
    """Turn what the user typed into one safe http(s) address, or raise ValueError.

    Allowed: public http/https websites, or a friendly name from desktop.website_aliases.
    Refused: other schemes (file:, javascript:, ms-settings: ...), addresses with a user name or password,
    localhost / private network addresses, and hostnames with non-ASCII look-alike characters."""
    text = str(raw or "").strip()
    text = (cfg("desktop", "website_aliases", default={}) or {}).get(text.lower(), text)
    if re.match(r"^[a-z][a-z0-9+.-]*:(?!\d)", text, re.IGNORECASE) and not re.match(r"^https?://", text, re.IGNORECASE):
        raise ValueError("Only http and https websites can be opened")
    if not re.match(r"^https?://", text, re.IGNORECASE):
        text = "https://" + text
    if len(text) > 500 or any(ch.isspace() or ord(ch) < 32 for ch in text):
        raise ValueError("That is not a valid website address")
    parts = urlparse(text)
    host = (parts.hostname or "").lower()
    if not host or parts.username or parts.password:
        raise ValueError("That is not a valid website address")
    if not host.isascii() or not re.fullmatch(r"[a-z0-9.-]+", host):
        raise ValueError("The website name has unusual characters, so it was not opened")
    if host == "localhost" or host.endswith((".local", ".internal", ".localhost", ".lan")):
        raise ValueError("Local and private network addresses cannot be opened")
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        if "." not in host:
            raise ValueError("That is not a valid website address")
    else:
        if not ip.is_global:
            raise ValueError("Local and private network addresses cannot be opened")
    return text
