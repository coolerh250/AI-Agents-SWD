"""Step 54.2 -- scan finding / report redaction.

Reuses the Step 53 committed-secret detector. Evidence snippets are truncated and
any secret/token shape is replaced with the redaction token so no secret value
can land in a scan report.
"""

from __future__ import annotations

import re

from shared.sdk.secrets_foundation.secret_redaction import (
    REDACTION_TOKEN,
    find_committed_secret,
    redact,
)

_MAX_EVIDENCE = 160

# coarse secret/token shapes to blank inside an evidence snippet
_SHAPES = [
    re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}"),
    re.compile(r"sk-[A-Za-z0-9]{20,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"eyJ[A-Za-z0-9_-]{6,}\.[A-Za-z0-9_-]{6,}\.[A-Za-z0-9_-]{6,}"),
    # full key block OR a standalone BEGIN/END PRIVATE KEY marker line
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"-{0,5}\b(BEGIN|END) [A-Z ]*PRIVATE KEY\b-{0,5}"),
    re.compile(r"\b[A-Za-z0-9+/]{32,}={0,2}\b"),  # long base64-ish blobs
]


def redact_evidence(text: str | None) -> str | None:
    """Return a bounded, secret-free evidence snippet (or None)."""
    if not text:
        return None
    snippet = text.strip()
    # if the whole snippet matches a committed-secret shape, drop the value
    if find_committed_secret(snippet):
        for pat in _SHAPES:
            snippet = pat.sub(REDACTION_TOKEN, snippet)
    if len(snippet) > _MAX_EVIDENCE:
        snippet = snippet[:_MAX_EVIDENCE] + "…"
    return snippet


def redact_report(obj: object) -> object:
    """Redact secret-shaped keys/values across a whole report object."""
    return redact(obj)


__all__ = ["redact_evidence", "redact_report", "REDACTION_TOKEN"]
