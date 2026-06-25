"""Step 54.4 -- release risk summary generator."""

from __future__ import annotations

import json

from scripts.generate_release_risk_summary import build_release_risk_summary

ALLOWED = {"not_ready", "ready_for_non_production_review", "ready_for_operator_review", "blocked"}


def test_status_within_allowed_enum() -> None:
    summ = build_release_risk_summary()
    assert summ["status"] in ALLOWED
    assert summ["status"] not in ("production_ready", "production_approved")


def test_no_production_or_deployment_approval() -> None:
    summ = build_release_risk_summary()
    assert summ["productionReady"] is False
    assert summ["productionApproval"] is False
    assert summ["deploymentApproval"] is False
    assert summ["scoreIsNotApproval"] is True


def test_missing_evidence_forces_not_ready_or_blocked() -> None:
    summ = build_release_risk_summary()
    if summ["missingEvidence"]:
        assert summ["status"] in ("not_ready", "blocked")
    assert summ["blockers"]


def test_no_approval_language() -> None:
    blob = json.dumps(build_release_risk_summary()).lower()
    assert "production_ready" not in blob
    assert "production_approved" not in blob
