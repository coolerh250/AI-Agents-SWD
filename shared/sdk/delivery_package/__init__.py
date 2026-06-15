"""Stage 49 -- Delivery Package & Acceptance Gate SDK (controlled-only)."""

from __future__ import annotations

from shared.sdk.delivery_package.acceptance_gate import evaluate_acceptance_gate
from shared.sdk.delivery_package.artifact_collector import build_package_artifacts
from shared.sdk.delivery_package.audit_events import (
    DELIVERY_PACKAGE_DECISION_TYPES,
    safe_package_artifact_refs,
)
from shared.sdk.delivery_package.checklist_builder import build_acceptance_checklist
from shared.sdk.delivery_package.events import (
    DELIVERY_PACKAGE_NOTIFICATION_EVENTS,
    EVENT_DELIVERY_PACKAGE_BUILD_FAILED,
    EVENT_DELIVERY_PACKAGE_READY_FOR_REVIEW,
    EVENT_PROJECT_DELIVERY_PACKAGE_REQUESTED,
    STREAM_DELIVERY_PACKAGE,
    STREAM_DELIVERY_PACKAGE_EVENTS,
)
from shared.sdk.delivery_package.export_metadata import build_export_metadata, render_markdown
from shared.sdk.delivery_package.handoff_builder import build_handoff_summaries
from shared.sdk.delivery_package.models import (
    AcceptanceGateCheckResult,
    AcceptanceGateRun,
    DeliveryPackage,
    DeliveryPackageArtifact,
    DeliveryPackageRequest,
    DeliveryPackageResult,
    DeliveryPackageSection,
    DeliveryReadinessSnapshot,
    HandoffSummary,
    OperatorAcceptanceReview,
)
from shared.sdk.delivery_package.package_builder import (
    PACKAGE_AGENT,
    gather_evidence,
    run_delivery_package_build,
)
from shared.sdk.delivery_package.readiness_snapshot import build_readiness_snapshot
from shared.sdk.delivery_package.report_builder import build_delivery_package_report
from shared.sdk.delivery_package.safety import delivery_package_safety_flags
from shared.sdk.delivery_package.section_builder import build_sections
from shared.sdk.delivery_package.store import DeliveryPackageStore

__all__ = [
    "DeliveryPackage",
    "DeliveryPackageSection",
    "DeliveryPackageArtifact",
    "AcceptanceGateRun",
    "AcceptanceGateCheckResult",
    "OperatorAcceptanceReview",
    "HandoffSummary",
    "DeliveryReadinessSnapshot",
    "DeliveryPackageRequest",
    "DeliveryPackageResult",
    "run_delivery_package_build",
    "gather_evidence",
    "PACKAGE_AGENT",
    "evaluate_acceptance_gate",
    "build_package_artifacts",
    "build_acceptance_checklist",
    "build_sections",
    "build_readiness_snapshot",
    "build_handoff_summaries",
    "build_delivery_package_report",
    "build_export_metadata",
    "render_markdown",
    "delivery_package_safety_flags",
    "DeliveryPackageStore",
    "DELIVERY_PACKAGE_DECISION_TYPES",
    "safe_package_artifact_refs",
    "DELIVERY_PACKAGE_NOTIFICATION_EVENTS",
    "STREAM_DELIVERY_PACKAGE",
    "STREAM_DELIVERY_PACKAGE_EVENTS",
    "EVENT_DELIVERY_PACKAGE_READY_FOR_REVIEW",
    "EVENT_DELIVERY_PACKAGE_BUILD_FAILED",
    "EVENT_PROJECT_DELIVERY_PACKAGE_REQUESTED",
]
