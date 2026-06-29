"""Step 60 -- rollback requirement validation.

A rollback plan + evidence are required before a candidate is ready for operator review.
Defining a rollback plan does NOT trigger a rollback; production rollback is future-only.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[3]
MODEL_YAML = ROOT / "infra" / "release" / "rollback-requirement-model.yaml"

REQUIRED_FIELDS = ("rollback_owner", "rollback_trigger", "rollback_steps", "rollback_validation")


@lru_cache(maxsize=1)
def _model() -> dict[str, Any]:
    data = yaml.safe_load(MODEL_YAML.read_text(encoding="utf-8")) or {}
    return data.get("rollbackRequirement", {}) or {}


def plan_required() -> bool:
    return bool(_model().get("rollback_plan_required", True))


def validate_rollback(plan: dict[str, Any] | None) -> tuple[bool, list[str]]:
    """Returns (valid, missing_fields). An empty/None plan is invalid when required."""
    plan = plan or {}
    missing = [f for f in REQUIRED_FIELDS if not plan.get(f)]
    return (not missing), missing
