"""Step 61 -- backup / restore / DR policy loading + environment validation.

Policy values read straight from the committed YAML so the dangerous toggles (production
restore / production failover / external upload / cloud write / cleanup execution / restore
execution / kind+ArgoCD teardown) cannot silently drift true in code.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from .models import ALLOWED_ENVIRONMENTS, ENV_NONPROD, FORBIDDEN_ENVIRONMENTS

ROOT = Path(__file__).resolve().parents[3]
POLICY_YAML = ROOT / "infra" / "dr" / "backup-restore-dr-operations-policy.yaml"


@lru_cache(maxsize=1)
def load_policy() -> dict[str, Any]:
    data = yaml.safe_load(POLICY_YAML.read_text(encoding="utf-8")) or {}
    return data.get("backupRestoreDr", {}) or {}


def is_production_environment(env: str) -> bool:
    return (env or "").strip().lower() in FORBIDDEN_ENVIRONMENTS


def is_environment_allowed(env: str) -> bool:
    env = (env or "").strip().lower()
    if env in FORBIDDEN_ENVIRONMENTS:
        return False
    allowed = load_policy().get("allowedEnvironments", list(ALLOWED_ENVIRONMENTS))
    return env in allowed


def validate_environment(env: str | None) -> tuple[str, str | None]:
    """Resolve + validate the target environment. Returns (env, blocked_reason)."""
    e = (env or ENV_NONPROD).strip().lower()
    if is_production_environment(e):
        return e, "production_environment_forbidden"
    if not is_environment_allowed(e):
        return e, f"environment_not_allowed:{e}"
    return e, None
