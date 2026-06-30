"""Step 63A -- controlled rollout review YAML loaders + missing-item counts.

Reads the committed review policy + models from infra/readiness/. Values come straight from
YAML so the dangerous toggles (production deploy / sync / restore / failover / action) and
recommendation-is-approval cannot drift true in code. No production action is ever taken.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[3]
DIR = ROOT / "infra" / "readiness"

_FILES = {
    "policy": (
        "controlled-production-rollout-pilot-review-policy.yaml",
        "controlledProductionRolloutPilotReview",
    ),
    "criteria": ("controlled-rollout-go-no-go-criteria.yaml", "controlledRolloutGoNoGoCriteria"),
    "target": ("production-target-assessment-model.yaml", "productionTargetAssessment"),
    "credentials": ("production-credential-readiness-model.yaml", "productionCredentialReadiness"),
    "gitops": ("production-gitops-readiness-model.yaml", "productionGitopsReadiness"),
    "approval_channel": (
        "production-approval-channel-readiness-model.yaml",
        "productionApprovalChannelReadiness",
    ),
    "rollback_dr": ("rollback-dr-pilot-readiness-model.yaml", "rollbackDrPilotReadiness"),
    "scope": ("controlled-rollout-pilot-scope-model.yaml", "controlledRolloutPilotScope"),
    "risk_register": (
        "controlled-rollout-pilot-risk-register.yaml",
        "controlledRolloutPilotRiskRegister",
    ),
    "decision_package": (
        "controlled-rollout-operator-decision-package-model.yaml",
        "controlledRolloutOperatorDecisionPackage",
    ),
    "recommendation": (
        "controlled-rollout-pilot-recommendation-model.yaml",
        "controlledRolloutPilotRecommendation",
    ),
    "audit": ("controlled-rollout-review-audit-mapping.yaml", "controlledRolloutReviewAudit"),
}

# Statuses that count as satisfied (everything else is a gap).
_SATISFIED = {"met", "configured", "defined", "ready", "available", "validated", "tested"}


@lru_cache(maxsize=None)
def load(section: str) -> dict[str, Any]:
    fname, key = _FILES[section]
    data = yaml.safe_load((DIR / fname).read_text(encoding="utf-8")) or {}
    return data.get(key, {}) or {}


def _missing(items: list[dict[str, Any]], status_key: str = "status") -> list[str]:
    out = []
    for it in items:
        val = it.get(status_key)
        if isinstance(val, bool):
            if not val:
                out.append(it.get("name", "?"))
        elif val not in _SATISFIED:
            out.append(it.get("name", "?"))
    return out


def missing_target_items() -> list[str]:
    return _missing(load("target").get("items", []))


def missing_credential_refs() -> list[str]:
    return [r["name"] for r in load("credentials").get("references", []) if not r.get("configured")]


def missing_gitops_items() -> list[str]:
    return _missing(load("gitops").get("items", []))


def missing_approval_items() -> list[str]:
    return _missing(load("approval_channel").get("items", []))


def rollback_dr_incomplete() -> bool:
    return load("rollback_dr").get("status") not in _SATISFIED
