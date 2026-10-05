"""Central URL validation for persisted sources and live targets."""

from __future__ import annotations

import ipaddress
import re
from urllib.parse import urlsplit


def validate_https_url(value: object, *, live: bool = False, nullable: bool = False) -> str | None:
    if nullable and value is None:
        return None
    if not isinstance(value, str) or any(ord(character) < 32 for character in value):
        raise ValueError("invalid source URL")
    if "?" in value:
        raise ValueError("source URL query strings are not allowed")
    parsed = urlsplit(value)
    if "@" in parsed.netloc:
        raise ValueError("URL userinfo is not allowed")
    if "%" in parsed.netloc:
        raise ValueError("encoded URL authority is not allowed")
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password or parsed.fragment:
        raise ValueError("invalid source URL")
    try:
        if parsed.port not in {None, 443}:
            raise ValueError("invalid source URL port")
    except ValueError as exc:
        raise ValueError("invalid source URL port") from exc
    host = parsed.hostname.rstrip(".").lower()
    try:
        ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        raise ValueError("IP source targets are not allowed")
    labels = host.split(".")
    if len(labels) < 2 or labels[-1].isdigit() or any(
        not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]*[a-z0-9])?", label) for label in labels
    ):
        raise ValueError("invalid source hostname")
    if host == "localhost" or host.endswith((".localhost", ".local", ".internal", ".invalid", ".test")):
        raise ValueError("reserved source hostname")
    if live and (
        host in {"example.com", "example.org", "example.net"}
        or host.endswith((".example", ".example.com", ".example.org", ".example.net"))
    ):
        raise ValueError("fixture live target hostname")
    return value
