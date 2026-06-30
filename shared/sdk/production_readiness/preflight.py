"""Step 62 -- production rollout preflight loading.

Preflight checks are modeled / evaluated only. Rollout execution is disabled; the rollout
status is planning_only / blocked / not_started.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[3]
MODEL_YAML = ROOT / "infra" / "readiness" / "production-rollout-preflight-model.yaml"


@lru_cache(maxsize=1)
def _model() -> dict[str, Any]:
    data = yaml.safe_load(MODEL_YAML.read_text(encoding="utf-8")) or {}
    return data.get("productionRolloutPreflight", {}) or {}


def load_checks() -> list[dict[str, Any]]:
    return _model().get("checks", []) or []


def rollout_status() -> str:
    return str(_model().get("rolloutStatus", "not_started"))


def rollout_execution_enabled() -> bool:
    return bool(_model().get("rolloutExecutionEnabled", False))
