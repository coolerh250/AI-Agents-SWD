"""Stage 28 — path / change-type / content / diff policy checks.

Pure, side-effect-free helpers. No LLM, no IO. Used by the deterministic
generator (to refuse unsafe writes) and by the verifier scripts.
"""

from __future__ import annotations

import fnmatch
import re
from typing import Iterable

#: Allowlisted path prefixes. Generated artifacts MUST live under one
#: of these. Trailing slashes are required so partial-prefix matches
#: (e.g. ``docs/`` matching ``docs/operations/secrets-management.md``)
#: never escape the safe zone.
DEFAULT_ALLOWED_PATHS: tuple[str, ...] = (
    "docs/generated/",
    "apps/demo-generated/",
    "tests/generated/",
    "source/generated/",
)

#: Denylist patterns. Any file_path matching ANY of these is refused —
#: even if it sits under an allowlisted prefix. The list is intentionally
#: paranoid: infra / CI / secrets / migrations / progress log are
#: untouchable by the controlled generator.
DEFAULT_DENIED_PATHS: tuple[str, ...] = (
    ".github/*",
    ".github/**",
    "infra/*",
    "infra/**",
    "migrations/*",
    "migrations/**",
    "shared/sdk/secrets/*",
    "shared/sdk/secrets/**",
    "docs/operations/secrets-management.md",
    "docker-compose*.yml",
    "infra/docker-compose/*",
    "infra/docker-compose/**",
    "*secret*",
    "*.pem",
    "*.key",
    "*.env",
    "*.env.*",
    "source/progress.md",
)

#: Allowed change types. Stage 28 disables ``delete`` outright.
_ALLOWED_CHANGE_TYPES = ("create", "update")

#: Regex hits that almost certainly indicate a real secret literal or
#: a destructive shell payload. The list is short on purpose — we'd
#: rather reject too aggressively than leak a real token.
_SECRET_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("github_token", re.compile(r"\bghp_[A-Za-z0-9]{20,}\b")),
    ("github_token_pat", re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b")),
    ("aws_access_key", re.compile(r"\bAKIA[0-9A-Z]{12,}\b")),
    ("slack_token", re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}\b")),
    ("private_key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("password_assignment", re.compile(r"(?i)(password|passwd|pwd)\s*=\s*['\"][^'\"]{4,}['\"]")),
    ("bearer_token", re.compile(r"(?i)bearer\s+[A-Za-z0-9_\-\.=]{20,}")),
    ("openai_key", re.compile(r"\bsk-[A-Za-z0-9]{20,}\b")),
    ("hashicorp_token", re.compile(r"\bhvs\.[A-Za-z0-9_\-]{20,}\b")),
)

_DESTRUCTIVE_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    # ``rm -rf <path>`` — shell form
    ("rm_rf", re.compile(r"\brm\s+-rf\b")),
    # ``['rm', '-rf', ...]`` — Python / shell-list form (quoted args)
    ("rm_rf_quoted", re.compile(r"""['"]rm['"]\s*,\s*['"]-rf['"]""")),
    ("drop_database", re.compile(r"(?i)\bdrop\s+(database|schema|table)\b")),
    ("truncate_table", re.compile(r"(?i)\btruncate\s+table\b")),
    ("force_push", re.compile(r"\bgit\s+push\s+.*--force\b")),
    ("kubectl_delete_ns", re.compile(r"\bkubectl\s+delete\s+(ns|namespace)\b")),
    ("shutdown", re.compile(r"\b(shutdown|halt|reboot)\s+-?\w*")),
)


def _normalise(file_path: str) -> str:
    """Normalise a candidate file path for matching.

    * strip leading ``./``
    * collapse ``\\`` -> ``/`` (Windows paths only — POSIX paths pass
      through untouched)
    * refuse empty
    """
    if not file_path:
        return ""
    p = file_path.replace("\\", "/").strip()
    while p.startswith("./"):
        p = p[2:]
    return p


def validate_allowed_path(
    file_path: str,
    *,
    allowed: Iterable[str] = DEFAULT_ALLOWED_PATHS,
    denied: Iterable[str] = DEFAULT_DENIED_PATHS,
) -> tuple[bool, str]:
    """Return ``(ok, reason)``.

    ``ok=True`` iff:
      1. ``file_path`` is non-empty and not absolute
      2. it doesn't escape via ``..``
      3. it sits under at least one ``allowed`` prefix
      4. it matches NO ``denied`` glob

    A denylist hit always wins over an allowlist match.
    """
    p = _normalise(file_path)
    if not p:
        return False, "empty_path"
    if p.startswith("/") or (len(p) >= 2 and p[1] == ":"):
        return False, "absolute_path"
    if ".." in p.split("/"):
        return False, "path_traversal"
    for pattern in denied:
        if fnmatch.fnmatch(p, pattern) or fnmatch.fnmatch(p.lower(), pattern.lower()):
            return False, f"denied:{pattern}"
        # Also match by basename so "*secret*" catches "API_secret.env".
        basename = p.rsplit("/", 1)[-1]
        if fnmatch.fnmatch(basename, pattern) or fnmatch.fnmatch(basename.lower(), pattern.lower()):
            return False, f"denied:{pattern}"
    for prefix in allowed:
        prefix_n = _normalise(prefix)
        if prefix_n and p.startswith(prefix_n):
            return True, f"allowed:{prefix_n}"
    return False, "not_in_allowlist"


def validate_change_type(change_type: str) -> tuple[bool, str]:
    """Reject ``delete``; allow ``create`` / ``update``."""
    ct = (change_type or "").strip().lower()
    if ct not in _ALLOWED_CHANGE_TYPES:
        return False, f"disallowed_change_type:{ct or 'empty'}"
    return True, f"change_type:{ct}"


def validate_no_secret_content(content: str) -> tuple[bool, str]:
    """Refuse any content that smells like a real secret literal."""
    if content is None:
        return True, "empty_content"
    for name, pattern in _SECRET_PATTERNS:
        if pattern.search(content):
            return False, f"secret_like:{name}"
    return True, "no_secret_signature"


def validate_no_destructive_change(diff: str) -> tuple[bool, str]:
    """Refuse diffs that contain destructive shell / SQL / git payloads."""
    if not diff:
        return True, "empty_diff"
    for name, pattern in _DESTRUCTIVE_PATTERNS:
        if pattern.search(diff):
            return False, f"destructive:{name}"
    return True, "no_destructive_signature"


def classify_change_risk(changed_files: list[dict | str]) -> dict[str, object]:
    """Return a risk descriptor for ``changed_files``.

    Heuristics are intentionally simple:

    * ``low`` when all files are docs / tests under the allowlist.
    * ``medium`` when at least one file is application code.
    * ``high`` if the file count exceeds 10, or any file path falls
      outside the allowlist (the caller will block at that point, but
      we still mark the residual risk).
    """
    if not changed_files:
        return {"risk_level": "low", "reason": "no_files", "files_count": 0}

    docs_count = 0
    tests_count = 0
    app_count = 0
    outside_allow = 0
    paths: list[str] = []
    for entry in changed_files:
        path = entry if isinstance(entry, str) else str((entry or {}).get("file_path") or "")
        paths.append(path)
        ok, _ = validate_allowed_path(path)
        if not ok:
            outside_allow += 1
            continue
        p = _normalise(path)
        if p.startswith("docs/generated/"):
            docs_count += 1
        elif p.startswith("tests/generated/"):
            tests_count += 1
        elif p.startswith("apps/demo-generated/") or p.startswith("source/generated/"):
            app_count += 1
    level = "low"
    reason = "docs_only"
    if outside_allow:
        level = "high"
        reason = f"outside_allowlist:{outside_allow}"
    elif app_count:
        level = "medium"
        reason = f"app_code:{app_count}"
    elif tests_count and not docs_count and not app_count:
        level = "low"
        reason = "tests_only"
    if len(changed_files) > 10:
        level = "high"
        reason = f"too_many_files:{len(changed_files)}"
    return {
        "risk_level": level,
        "reason": reason,
        "files_count": len(changed_files),
        "docs_count": docs_count,
        "tests_count": tests_count,
        "app_count": app_count,
        "outside_allow": outside_allow,
        "paths": paths,
    }
