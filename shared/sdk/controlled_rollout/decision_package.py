"""Step 63A -- controlled rollout operator decision package builder.

Assembles a redacted package for a human operator: readiness gate result, go/no-go
criteria, production target / credential / GitOps / approval-channel / rollback-DR
assessments, pilot scope, risk register, missing items, required operator decisions, and
the recommendation. The recommendation is NOT an approval. No secret / token / kubeconfig /
chain-of-thought ever appears.
"""

from __future__ import annotations

from typing import Any

from . import loaders, recommendation
from .redaction import redact


def build(readiness_gate_result: dict[str, Any] | None = None) -> dict[str, Any]:
    rec = recommendation.evaluate()
    missing_items = {
        "production_target": loaders.missing_target_items(),
        "production_credentials": loaders.missing_credential_refs(),
        "production_gitops": loaders.missing_gitops_items(),
        "production_approval_channel": loaders.missing_approval_items(),
    }
    package = {
        "summary": {
            "recommendation": rec["recommendation"],
            "recommendation_is_approval": False,
            "production_ready": False,
            "production_approved": False,
            "production_action_allowed": False,
        },
        "readiness_gate_result": readiness_gate_result
        or {"decision": "ready_for_operator_review", "production_ready": False},
        "go_no_go_criteria": loaders.load("criteria").get("criteria", []),
        "production_target_assessment": loaders.load("target"),
        "credential_readiness": loaders.load("credentials"),
        "gitops_readiness": loaders.load("gitops"),
        "approval_channel_readiness": loaders.load("approval_channel"),
        "rollback_dr_readiness": loaders.load("rollback_dr"),
        "pilot_scope": loaders.load("scope"),
        "risk_register": loaders.load("risk_register").get("risks", []),
        "missing_items": missing_items,
        "required_operator_decisions": [
            "review the go/no-go recommendation and gaps",
            "decide whether to provision a real production target (separate stage)",
            "explicitly approve any future controlled rollout pilot in a separate stage",
        ],
        "recommendation": rec,
        "production_ready": False,
        "production_approval": False,
        "production_action_allowed": False,
    }
    return redact(package)
