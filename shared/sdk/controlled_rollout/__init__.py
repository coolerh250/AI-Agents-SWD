"""Step 63A (Stage 65A) -- controlled production rollout pilot go/no-go REVIEW SDK.

The go/no-go review (NOT the Step 63 rollout pilot itself): collects the Step 62 readiness
evidence, assesses the production rollout pilot prerequisites (target / credentials / GitOps
/ approval channel / rollback-DR), bounds the pilot scope, registers risks, builds an
operator decision package, and produces a go / conditional_go / no_go recommendation. It
does NOT deploy, sync, merge, push, restore, or fail over. A Go / Conditional Go
recommendation is NOT an approval and authorizes NO production action.
"""

from __future__ import annotations

from . import loaders, recommendation
from .audit import EVENTS, build_audit_metadata
from .decision_package import build as build_operator_decision_package
from .models import RECOMMENDATIONS, REC_CONDITIONAL_GO, REC_GO, REC_NO_GO
from .safety import controlled_rollout_safety_fields

__all__ = [
    "loaders",
    "recommendation",
    "build_operator_decision_package",
    "build_audit_metadata",
    "EVENTS",
    "RECOMMENDATIONS",
    "REC_GO",
    "REC_CONDITIONAL_GO",
    "REC_NO_GO",
    "controlled_rollout_safety_fields",
]
