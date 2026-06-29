"""Step 60 (Stage 62A) -- release & deployment governance SDK.

Integrates delivery / work-item / sandbox-draft-PR / runtime / GitOps / security /
approval evidence into a NON-PRODUCTION release governance decision. It does NOT deploy,
sync, merge, push, or release. Production stays blocked; production_ready is always false.
"""

from __future__ import annotations

from .audit import EVENTS, build_audit_metadata
from .candidates import CandidateError, build_candidate
from .deployment_intent import build_intent
from .evidence import build_evidence_summary
from .models import (
    ALLOWED_ACTIONS,
    ALLOWED_ENVIRONMENTS,
    FORBIDDEN_ACTIONS,
    FORBIDDEN_ENVIRONMENTS,
    DeploymentIntent,
    ReadinessResult,
    ReleaseCandidate,
)
from .readiness import evaluate
from .rollback import validate_rollback
from .safety import release_governance_safety_fields
from .store import ReleaseGovernanceStore

__all__ = [
    "ALLOWED_ACTIONS",
    "ALLOWED_ENVIRONMENTS",
    "FORBIDDEN_ACTIONS",
    "FORBIDDEN_ENVIRONMENTS",
    "DeploymentIntent",
    "ReadinessResult",
    "ReleaseCandidate",
    "CandidateError",
    "build_candidate",
    "build_intent",
    "build_evidence_summary",
    "evaluate",
    "validate_rollback",
    "build_audit_metadata",
    "EVENTS",
    "release_governance_safety_fields",
    "ReleaseGovernanceStore",
]
