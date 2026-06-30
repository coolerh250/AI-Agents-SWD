"""Step 62 -- operator review package builder.

Assembles a redacted package for a human operator. It is NOT a production approval and
authorizes NO production action. No secret / token / kubeconfig / chain-of-thought / raw
dump ever appears.
"""

from __future__ import annotations

from typing import Any

from .redaction import redact


def build_operator_review_package(
    *,
    readiness_decision: dict[str, Any],
    evidence_inventory: list[dict[str, Any]],
    blocking_results: list[dict[str, Any]],
    missing_prerequisites: list[str],
    known_limitations: list[str] | None = None,
) -> dict[str, Any]:
    package = {
        "readiness_summary": {
            "decision": readiness_decision.get("decision"),
            "production_ready": False,
            "production_approved": False,
            "production_action_allowed": False,
        },
        "evidence_inventory": evidence_inventory,
        "blocking_rules_result": blocking_results,
        "known_limitations": known_limitations or [],
        "missing_prerequisites": missing_prerequisites,
        "required_operator_decisions": [
            "review readiness evidence and limitations",
            "decide whether a future explicit production rollout phase should be planned",
        ],
        "production_action_blocking_status": {
            "production_deploy_blocked": True,
            "production_sync_blocked": True,
            "production_restore_blocked": True,
            "production_failover_blocked": True,
            "github_merge_blocked": True,
            "image_push_blocked": True,
        },
        "production_ready": False,
        "production_approval": False,
        "production_action_allowed": False,
    }
    return redact(package)
