"""Step 59 -- sandbox GitHub policy loading + mode resolution.

Policy values are read straight from the committed YAML so the dangerous toggles
(merge / ready-for-review / workflow dispatch / production branch / non-sandbox repo)
cannot silently drift true in code.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from .models import ALLOWED_MODES, MODE_DRY_RUN, MODE_LIVE_SANDBOX

ROOT = Path(__file__).resolve().parents[3]
POLICY_YAML = ROOT / "infra" / "github" / "sandbox-github-draft-pr-policy.yaml"

LIVE_ENV = "SANDBOX_GITHUB_LIVE"
TOKEN_ENV = "SANDBOX_GITHUB_TOKEN"


@lru_cache(maxsize=1)
def load_policy() -> dict[str, Any]:
    data = yaml.safe_load(POLICY_YAML.read_text(encoding="utf-8")) or {}
    return data.get("sandboxGitHub", {}) or {}


def live_mode_requested_enabled() -> bool:
    return os.environ.get(LIVE_ENV, "false").strip().lower() == "true"


def has_credential() -> bool:
    return bool(os.environ.get(TOKEN_ENV, "").strip())


def default_mode() -> str:
    return str(load_policy().get("defaultMode", MODE_DRY_RUN))


def forbidden_base_branches() -> tuple[str, ...]:
    return tuple(load_policy().get("forbiddenBaseBranches", []) or [])


def resolve_mode(requested: str | None) -> tuple[str, str | None]:
    """Resolve the effective mode. Returns (mode, blocked_reason).

    dry_run is always permitted. live_sandbox requires the explicit env flag AND a
    credential; otherwise the request is blocked (never a faked live success).
    """
    policy = load_policy()
    req = (requested or default_mode()).strip()
    if req not in ALLOWED_MODES:
        return MODE_DRY_RUN, f"invalid_mode:{req}"
    if req == MODE_DRY_RUN:
        return MODE_DRY_RUN, None
    # live_sandbox
    if MODE_LIVE_SANDBOX not in (policy.get("allowedMode") or []):
        return MODE_LIVE_SANDBOX, "live_sandbox_not_allowed_by_policy"
    if not live_mode_requested_enabled():
        return MODE_LIVE_SANDBOX, "live_sandbox_not_enabled"
    if not has_credential():
        return MODE_LIVE_SANDBOX, "live_sandbox_no_credential"
    return MODE_LIVE_SANDBOX, None


def live_mode_effective() -> bool:
    """True only when live_sandbox is allowed, enabled, and has a credential."""
    mode, blocked = resolve_mode(MODE_LIVE_SANDBOX)
    return mode == MODE_LIVE_SANDBOX and blocked is None
