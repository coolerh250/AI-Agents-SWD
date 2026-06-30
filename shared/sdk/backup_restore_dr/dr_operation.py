"""Step 61 -- DR operation builder + DR readiness evaluation.

A DR operation records governance state only. A forbidden operation type (production
failover / production restore / cross-region failover / production data overwrite) is
blocked. DR readiness is a governance judgement, NOT production DR ready: production_ready
and production_restore_ready are always false, and missing backup / restore evidence blocks
readiness.
"""

from __future__ import annotations

import uuid
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from . import policy
from .models import (
    DR_OPERATION_TYPES,
    FORBIDDEN_DR_OPERATION_TYPES,
    DROperation,
    DRReadinessResult,
)

ROOT = Path(__file__).resolve().parents[3]
MODEL_YAML = ROOT / "infra" / "dr" / "dr-operation-model.yaml"


class DROperationError(ValueError):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


@lru_cache(maxsize=1)
def _model() -> dict[str, Any]:
    data = yaml.safe_load(MODEL_YAML.read_text(encoding="utf-8")) or {}
    return data.get("drOperation", {}) or {}


def required_for_readiness() -> list[str]:
    return list(_model().get("requiredForReadiness", []) or [])


def build_dr_operation(
    *,
    operation_type: str,
    target_environment: str | None = None,
) -> DROperation:
    """Build + classify a DR operation. Forbidden / production operations are blocked."""
    op = (operation_type or "").strip()
    env, env_blocked = policy.validate_environment(target_environment)

    operation = DROperation(
        dr_operation_id=uuid.uuid4().hex,
        operation_type=op,
        target_environment=env,
    )
    if op in FORBIDDEN_DR_OPERATION_TYPES:
        operation.status = "blocked"
        operation.policy_decision = "blocked"
        operation.blocked_reason = f"forbidden_operation_type:{op}"
        return operation
    if op not in DR_OPERATION_TYPES:
        operation.status = "blocked"
        operation.policy_decision = "blocked"
        operation.blocked_reason = f"unknown_operation_type:{op}"
        return operation
    if env_blocked:
        operation.status = "blocked"
        operation.policy_decision = "blocked"
        operation.blocked_reason = env_blocked
        return operation
    operation.status = "recorded"
    operation.policy_decision = "recorded_nonproduction"
    return operation


def evaluate_readiness(
    *,
    target_environment: str | None,
    evidence: dict[str, Any] | None = None,
) -> DRReadinessResult:
    """Governance readiness judgement. Never production DR ready."""
    evidence = evidence or {}
    env, env_blocked = policy.validate_environment(target_environment)
    if env_blocked:
        return DRReadinessResult(decision="blocked_by_policy", blockers=[env_blocked])

    missing = [ref for ref in required_for_readiness() if not evidence.get(ref)]
    if missing:
        return DRReadinessResult(decision="blocked_by_missing_evidence", missing_evidence=missing)
    return DRReadinessResult(decision="ready_for_operator_review")
