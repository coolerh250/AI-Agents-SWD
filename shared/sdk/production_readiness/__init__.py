"""Step 62 (Stage 64A) -- production deployment readiness gate SDK.

Integrates the completed identity / secret / security / runtime / GitOps / delivery /
metrics / sandbox-GitHub / release-governance / backup-restore-DR evidence into a readiness
GATE: checklist, evidence inventory, blocking rules, production prerequisites, deployment
authorization boundary, operator review package, readiness decision, rollout preflight,
audit. It does NOT deploy, sync, merge, push, restore, or fail over. Production stays
blocked; production_ready / production_approved / production_action_allowed are always
false; the gate never approves production.
"""

from __future__ import annotations

from . import (
    authorization,
    blocking_rules,
    checklist,
    decision,
    evidence,
    policy,
    prerequisites,
    preflight,
)
from .audit import EVENTS, build_audit_metadata
from .models import (
    DECISION_STATUSES,
    REQUIRED_MARKERS,
    BlockingRuleResult,
    ReadinessDecision,
)
from .operator_review import build_operator_review_package
from .safety import production_readiness_safety_fields
from .store import ProductionReadinessStore

__all__ = [
    "authorization",
    "blocking_rules",
    "checklist",
    "decision",
    "evidence",
    "policy",
    "prerequisites",
    "preflight",
    "DECISION_STATUSES",
    "REQUIRED_MARKERS",
    "BlockingRuleResult",
    "ReadinessDecision",
    "build_operator_review_package",
    "build_audit_metadata",
    "EVENTS",
    "production_readiness_safety_fields",
    "ProductionReadinessStore",
]
