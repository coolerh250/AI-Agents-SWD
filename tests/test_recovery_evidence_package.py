"""Step 61 -- recovery evidence package."""

from __future__ import annotations

from shared.sdk.backup_restore_dr import build_recovery_evidence


def test_empty_evidence_incomplete_and_not_ready() -> None:
    ev = build_recovery_evidence({})
    assert ev["complete"] is False
    assert ev["missing_required"]
    assert ev["production_ready"] is False
    assert ev["production_restore_ready"] is False


def test_forbidden_keys_redacted() -> None:
    ev = build_recovery_evidence(
        {
            "backup_inventory": {"ok": 1},
            "operator_decisions": {"token": "x", "kubeconfig": "y", "raw_db_dump": "z"},
        }
    )
    od = ev["evidence"]["operator_decisions"]
    assert od["token"] == "[redacted]"
    assert od["kubeconfig"] == "[redacted]"
    assert od["raw_db_dump"] == "[redacted]"


def test_production_blocking_status_explicit() -> None:
    ev = build_recovery_evidence({"backup_inventory": 1})
    pb = ev["production_blocking_status"]
    assert pb["production_restore_blocked"] is True
    assert pb["production_failover_blocked"] is True
