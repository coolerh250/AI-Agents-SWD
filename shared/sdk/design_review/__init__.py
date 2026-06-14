"""Stage 46 -- Design Review SDK."""

from __future__ import annotations

from shared.sdk.design_review.acceptance_coverage import (
    AcceptanceCoverage,
    compute_acceptance_coverage,
    review_acceptance_coverage,
)
from shared.sdk.design_review.audit_events import (
    DESIGN_REVIEW_DECISION_TYPES,
    safe_review_artifact_refs,
)
from shared.sdk.design_review.events import (
    DESIGN_REVIEW_NOTIFICATION_EVENTS,
    EVENT_DESIGN_REVIEW_COMPLETED,
    EVENT_DESIGN_REVIEW_STARTED,
    EVENT_PROJECT_DESIGN_REVIEW_REQUESTED,
    STREAM_DESIGN_REVIEW,
    STREAM_DESIGN_REVIEW_EVENTS,
)
from shared.sdk.design_review.gate_evaluator import (
    build_decisions,
    decide_go_no_go,
    evaluate_gates,
)
from shared.sdk.design_review.models import (
    DesignReviewDecision,
    DesignReviewFinding,
    DesignReviewOutput,
    DesignReviewSession,
    GoNoGoSummary,
    ProjectReviewGate,
    ReviewContext,
)
from shared.sdk.design_review.report_builder import build_review_summary
from shared.sdk.design_review.review_builder import ReviewResult, build_review
from shared.sdk.design_review.runner import (
    REVIEW_AGENT,
    load_review_context,
    run_design_review,
)
from shared.sdk.design_review.store import DesignReviewStore

__all__ = [
    "ReviewContext",
    "DesignReviewSession",
    "DesignReviewFinding",
    "DesignReviewDecision",
    "ProjectReviewGate",
    "DesignReviewOutput",
    "GoNoGoSummary",
    "ReviewResult",
    "build_review",
    "build_review_summary",
    "evaluate_gates",
    "decide_go_no_go",
    "build_decisions",
    "AcceptanceCoverage",
    "compute_acceptance_coverage",
    "review_acceptance_coverage",
    "DesignReviewStore",
    "run_design_review",
    "load_review_context",
    "REVIEW_AGENT",
    "STREAM_DESIGN_REVIEW",
    "STREAM_DESIGN_REVIEW_EVENTS",
    "EVENT_DESIGN_REVIEW_STARTED",
    "EVENT_DESIGN_REVIEW_COMPLETED",
    "EVENT_PROJECT_DESIGN_REVIEW_REQUESTED",
    "DESIGN_REVIEW_NOTIFICATION_EVENTS",
    "DESIGN_REVIEW_DECISION_TYPES",
    "safe_review_artifact_refs",
]
