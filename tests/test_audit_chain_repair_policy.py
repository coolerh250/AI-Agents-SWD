"""Stage 42 -- repair plan + policy gating (pure, no DB)."""

from __future__ import annotations

from shared.sdk.audit_integrity import build_canonical_payload, compute_payload_hash
from shared.sdk.audit_integrity.forensics import (
    ROOT_CAUSE_AUDIT_LOG_MUTATED,
    ROOT_CAUSE_TEST_TAMPER_NOT_RESTORED,
    ROOT_CAUSE_UNKNOWN,
    analyse_record,
)
from shared.sdk.audit_integrity.repair import plan_repair


def _tamper_record(seq: int):
    base = {
        "task_id": "smoke",
        "agent": "github-automation",
        "decision_type": "github_real_test_blocked",
        "summary": "blocked: missing_github_token",
        "result": "blocked",
        "artifact_refs": {"production_executed": False},
        "created_at": "2026-06-13T05:57:57+00:00",
    }
    stored = compute_payload_hash(build_canonical_payload({"audit_log_id": str(seq), **base}))
    tampered = dict(base, summary=base["summary"] + " [TAMPER-SIMULATION]")
    return analyse_record(
        sequence_number=seq,
        audit_log_id=str(seq),
        audit_log_row=tampered,
        stored_canonical_payload_hash=stored,
        stored_row_hash="rr",
        stored_prev_hash="pp",
        signature_status="signing_key_not_configured",
        expected_prev_record_hash="pp",
    )


def test_plan_affects_first_failed_to_tail():
    failed = [_tamper_record(100)]
    plan = plan_repair(
        failed=failed,
        root_cause=ROOT_CAUSE_TEST_TAMPER_NOT_RESTORED,
        repair_allowed=True,
        repair_risk="low",
        chain_tail_sequence=105,
    )
    assert plan.first_failed_sequence == 100
    assert plan.affected_sequences == [100, 101, 102, 103, 104, 105]
    assert plan.changed_records_count == 6
    assert plan.repair_allowed is True


def test_plan_blocks_unknown_root_cause():
    failed = [_tamper_record(100)]
    plan = plan_repair(
        failed=failed,
        root_cause=ROOT_CAUSE_UNKNOWN,
        repair_allowed=True,  # forensics said allowed, but unknown is not repairable
        repair_risk="high",
        chain_tail_sequence=105,
    )
    assert plan.repair_allowed is False


def test_plan_blocks_non_repairable_root_cause():
    failed = [_tamper_record(100)]
    plan = plan_repair(
        failed=failed,
        root_cause=ROOT_CAUSE_AUDIT_LOG_MUTATED,
        repair_allowed=False,
        repair_risk="high",
        chain_tail_sequence=105,
    )
    assert plan.repair_allowed is False


def test_plan_empty_when_no_failures():
    plan = plan_repair(
        failed=[],
        root_cause=ROOT_CAUSE_TEST_TAMPER_NOT_RESTORED,
        repair_allowed=True,
        repair_risk="low",
        chain_tail_sequence=None,
    )
    assert plan.affected_sequences == []
    assert plan.repair_allowed is False


def test_plan_to_dict_redacts_large_sample():
    failed = [_tamper_record(1)]
    plan = plan_repair(
        failed=failed,
        root_cause=ROOT_CAUSE_TEST_TAMPER_NOT_RESTORED,
        repair_allowed=True,
        repair_risk="medium",
        chain_tail_sequence=1000,
    )
    d = plan.to_dict()
    assert d["affected_sequences_count"] == 1000
    assert len(d["affected_sequences_sample"]) <= 25
    assert d["affected_sequence_range"] == [1, 1000]
