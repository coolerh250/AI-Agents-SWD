"""Step 60 -- release evidence package builder."""

from __future__ import annotations

from shared.sdk.release_governance import build_evidence_summary


def test_empty_evidence_incomplete() -> None:
    s = build_evidence_summary({})
    assert s["complete"] is False
    assert s["production_ready"] is False
    assert s["production_approved"] is False
    assert s["missing_required"]


def test_full_evidence_complete() -> None:
    s = build_evidence_summary(
        {
            "security_readiness": "pass",
            "rollback_plan": {"rollback_owner": "ops"},
            "audit_events": ["e1"],
        }
    )
    assert s["complete"] is True
    assert s["production_approved"] is False


def test_secret_shaped_value_redacted() -> None:
    s = build_evidence_summary(
        {
            "security_readiness": "-----BEGIN PRIVATE KEY-----",
            "rollback_plan": {"o": 1},
            "audit_events": ["e"],
        }
    )
    assert s["evidence"]["security_readiness"] == "[redacted]"
