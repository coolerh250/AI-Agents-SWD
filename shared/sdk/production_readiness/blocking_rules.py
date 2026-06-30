"""Step 62 -- production readiness blocking rule evaluation.

Loads the committed blocking rules and evaluates them against marker availability +
requested-action context. Hard rules (production action / counts) must stay inactive;
prerequisite rules (production environment / non-production-only) cap the decision at
ready_for_operator_review.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from .models import REQUIRED_MARKERS, BlockingRuleResult

ROOT = Path(__file__).resolve().parents[3]
RULES_YAML = ROOT / "infra" / "readiness" / "production-readiness-blocking-rules.yaml"

# Map a required marker to the missing-evidence rule it activates.
_MARKER_TO_RULE = {
    "IDENTITY_FOUNDATION_BASELINE_VERIFY": "missing_identity_evidence",
    "SECRET_MANAGEMENT_FOUNDATION_BASELINE_VERIFY": "missing_secret_evidence",
    "APPLICATION_SECURITY_SUPPLY_CHAIN_BASELINE_VERIFY": "missing_security_evidence",
    "NONPRODUCTION_KUBERNETES_RUNTIME_SMOKE_VERIFY": "missing_runtime_evidence",
    "NONPRODUCTION_ARGOCD_MANUAL_SYNC_BASELINE_VERIFY": "missing_gitops_evidence",
    "RELEASE_DEPLOYMENT_GOVERNANCE_BASELINE_VERIFY": "missing_release_evidence",
    "BACKUP_RESTORE_DR_OPERATIONS_BASELINE_VERIFY": "missing_dr_evidence",
}


@lru_cache(maxsize=1)
def _rules() -> list[dict[str, Any]]:
    data = yaml.safe_load(RULES_YAML.read_text(encoding="utf-8")) or {}
    return data.get("productionReadinessBlockingRules", {}).get("rules", []) or []


def evaluate(
    *,
    marker_status: dict[str, str] | None = None,
    production_action_requested: bool = False,
    production_executed_true_count: int = 0,
) -> list[BlockingRuleResult]:
    """Evaluate every blocking rule. Returns results with the live ``active`` state."""
    marker_status = marker_status or {}
    missing = {
        rule
        for marker, rule in _MARKER_TO_RULE.items()
        if marker_status.get(marker, "PASS") != "PASS"
    }
    results: list[BlockingRuleResult] = []
    for r in _rules():
        name = r["name"]
        active = bool(r.get("currently_active", False))
        if name == "production_action_requested":
            active = production_action_requested
        elif name == "production_executed_true_count_nonzero":
            active = production_executed_true_count != 0
        elif name in _MARKER_TO_RULE.values():
            active = name in missing
        results.append(
            BlockingRuleResult(name=name, severity=r.get("severity", "hard"), active=active)
        )
    return results


def required_markers() -> tuple[str, ...]:
    return REQUIRED_MARKERS
