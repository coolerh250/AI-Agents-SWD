"""Step 53 -- secret redaction (no network, no value access).

Detects committed secret/token shapes and redacts secret-shaped keys in any
serializable object. Reuses the Step 52.2 token detector and adds kubeconfig /
DB-URL-with-password / webhook / service-account-token shapes.
"""

from __future__ import annotations

import re
from typing import Any

from shared.sdk.identity import find_secret_like

REDACTION_TOKEN = "***REDACTED***"

# Key substrings that mark a value as secret-shaped (redact the value).
REDACT_KEY_SUBSTRINGS = (
    "secret",
    "token",
    "password",
    "passwd",
    "key",
    "private",
    "credential",
    "bearer",
    "cookie",
    "csrf",
    "jwt",
)

# Additional committed-value shapes beyond the Step 52.2 detector.
_EXTRA_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("kubeconfig", re.compile(r"(apiVersion:\s*v1[\s\S]*kind:\s*Config|current-context:)")),
    ("db_url_with_password", re.compile(r"\b\w+://[^\s:@/]+:[^\s:@/]+@[^\s/]+", re.IGNORECASE)),
    ("webhook_url", re.compile(r"https://hooks\.[^\s\"']+", re.IGNORECASE)),
    ("service_account_token", re.compile(r"\beyJhbGciOiJ[A-Za-z0-9_-]{8,}")),
]


def find_committed_secret(text: str) -> list[str]:
    """Return reasons for committed secret/token shapes (deduped)."""
    reasons = list(find_secret_like(text))
    for line in text.splitlines():
        for label, pat in _EXTRA_PATTERNS:
            m = pat.search(line)
            if not m:
                continue
            if label == "db_url_with_password":
                # allow postgres://postgres@host (no password) placeholders
                if "@" in m.group(0) and re.search(r"://[^\s:@/]+:[^\s:@/]+@", m.group(0)):
                    pwd = m.group(0).split("://", 1)[1].split("@", 1)[0]
                    if pwd.split(":", 1)[-1].lower() in ("", "password", "postgres", "changeme"):
                        continue
                else:
                    continue
            reasons.append(f"{label}: {line.strip()[:80]}")
    seen: set[str] = set()
    out: list[str] = []
    for r in reasons:
        if r not in seen:
            seen.add(r)
            out.append(r)
    return out


def _is_secret_key(key: str) -> bool:
    low = key.lower()
    return any(sub in low for sub in REDACT_KEY_SUBSTRINGS)


def redact(obj: Any) -> Any:
    """Return a copy with secret-shaped keys + secret-shaped string values redacted."""
    if isinstance(obj, dict):
        out: dict[Any, Any] = {}
        for k, v in obj.items():
            if isinstance(k, str) and _is_secret_key(k) and isinstance(v, str) and v:
                out[k] = REDACTION_TOKEN
            else:
                out[k] = redact(v)
        return out
    if isinstance(obj, list):
        return [redact(v) for v in obj]
    if isinstance(obj, str) and find_committed_secret(obj):
        return REDACTION_TOKEN
    return obj


def contains_committed_secret(text: str) -> bool:
    return bool(find_committed_secret(text))


__all__ = [
    "REDACTION_TOKEN",
    "REDACT_KEY_SUBSTRINGS",
    "find_committed_secret",
    "redact",
    "contains_committed_secret",
]
