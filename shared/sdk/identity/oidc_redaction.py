"""Step 52.2 -- OIDC secret / token detection (no network, no storage).

Pure text helpers used by the config validator and the no-secret-leak verifier.
They detect credential- and token-shaped literals so that no real OIDC secret,
JWT, OAuth code, tenant/group object ID, or real IdP issuer can be committed or
loaded as config. Field names, empty strings, ``<placeholder>`` tokens, and
``example.(com|org|net)`` documentation hosts are explicitly NOT secrets.
"""

from __future__ import annotations

import re

REDACTION_TOKEN = "***REDACTED***"

# Documentation hosts that are never treated as a real IdP issuer.
_EXAMPLE_HOSTS = ("example.com", "example.org", "example.net", "idp.example")

# Token / credential shapes. Each maps a regex to a human reason.
_SECRET_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("jwt", re.compile(r"eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]+")),
    ("private_key", re.compile(r"BEGIN [A-Z ]*PRIVATE KEY")),
    ("github_token", re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}")),
    ("openai_key", re.compile(r"sk-[A-Za-z0-9]{20,}")),
    ("aws_key", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("bearer_token", re.compile(r"[Bb]earer\s+[A-Za-z0-9._-]{16,}")),
    # 8-4-4-4-12 hex GUID: Entra tenant ID / group object ID shape.
    (
        "guid",
        re.compile(
            r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-" r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"
        ),
    ),
    # known real IdP issuer hosts (with a path/tenant) -> a real connection.
    (
        "real_idp_issuer",
        re.compile(
            r"https?://[^\s\"']*(login\.microsoftonline\.com|accounts\.google\.com|"
            r"\.okta\.com|\.auth0\.com|\.onmicrosoft\.com)[^\s\"']*",
            re.IGNORECASE,
        ),
    ),
]

# A secret-bearing key assigned a non-placeholder literal value.
_SECRET_ASSIGN = re.compile(
    r"(client_secret|clientsecret|signing_secret|refresh_token|access_token|"
    r"id_token|password|secret_key)\s*[:=]\s*"
    r"(?![\"']?\s*(\"\"|''|<[^>]*>)?\s*$)"  # not empty / not <placeholder>
    r"[\"']?([A-Za-z0-9/+=._-]{6,})",
    re.IGNORECASE,
)

# A real email address (allowing example.* documentation domains).
_EMAIL = re.compile(
    r"\b[A-Za-z0-9._%+-]+@(?!example\.(com|org|net))" r"[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"
)


def _is_placeholder(value: str) -> bool:
    v = value.strip().strip("\"'")
    if v in ("", "<redacted>", REDACTION_TOKEN):
        return True
    if v.startswith("<") and v.endswith(">"):
        return True
    return any(host in v for host in _EXAMPLE_HOSTS)


def find_secret_like(text: str) -> list[str]:
    """Return reasons for each secret/token-shaped match in ``text`` (deduped)."""
    reasons: list[str] = []
    for line in text.splitlines():
        for reason, pat in _SECRET_PATTERNS:
            m = pat.search(line)
            if m and not _is_placeholder(m.group(0)):
                reasons.append(f"{reason}: {line.strip()[:80]}")
        am = _SECRET_ASSIGN.search(line)
        if am and not _is_placeholder(am.group(3)):
            reasons.append(f"secret_literal: {line.strip()[:80]}")
        em = _EMAIL.search(line)
        if em:
            reasons.append(f"email: {line.strip()[:80]}")
    # dedupe, preserve order
    seen: set[str] = set()
    out: list[str] = []
    for r in reasons:
        if r not in seen:
            seen.add(r)
            out.append(r)
    return out


def contains_secret_like(text: str) -> bool:
    return bool(find_secret_like(text))


__all__ = ["REDACTION_TOKEN", "find_secret_like", "contains_secret_like"]
