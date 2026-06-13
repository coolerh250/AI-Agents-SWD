"""Stage 42 -- root cause classification (pure, no DB)."""

from __future__ import annotations

from shared.sdk.audit_integrity import build_canonical_payload, compute_payload_hash
from shared.sdk.audit_integrity.forensics import (
    FAILURE_SIGNING_KEY_MISSING,
    ROOT_CAUSE_CANONICALIZATION_VERSION_DRIFT,
    ROOT_CAUSE_HMAC_KEY_MISSING_ONLY,
    ROOT_CAUSE_TEST_TAMPER_NOT_RESTORED,
    ROOT_CAUSE_UNKNOWN,
    FailedRecordAnalysis,
    analyse_record,
    classify_chain_root_cause,
)


def _synthetic_tamper_record(seq: int) -> FailedRecordAnalysis:
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


def test_empty_failed_list_is_clean():
    out = classify_chain_root_cause([])
    assert out["root_cause_classification"] is None
    assert out["repair_allowed"] is False


def test_single_test_tamper_not_restored_allows_repair():
    out = classify_chain_root_cause([_synthetic_tamper_record(265288)])
    assert out["root_cause_classification"] == ROOT_CAUSE_TEST_TAMPER_NOT_RESTORED
    assert out["repair_allowed"] is True
    assert out["confidence"] == "high"
    assert out["production_executed_involved"] is False


def test_signature_only_failure_not_repairable():
    a = FailedRecordAnalysis(
        sequence_number=1,
        audit_log_id="id",
        decision_type="d",
        task_id="T",
        created_at="2026-06-01T00:00:00+00:00",
        stored_canonical_payload_hash="h",
        recomputed_canonical_payload_hash="h",
        stored_row_hash="r",
        recomputed_row_hash="r",
        stored_prev_record_hash="p",
        expected_prev_record_hash="p",
        signature_status="signed",
        signature_verification_status=FAILURE_SIGNING_KEY_MISSING,
        failure_types=[FAILURE_SIGNING_KEY_MISSING],
    )
    # analyse_record classifies; here we re-run classify by constructing
    # via analyse_record to exercise the real path.
    rec = analyse_record(
        sequence_number=1,
        audit_log_id="id",
        audit_log_row={
            "task_id": "T",
            "agent": "x",
            "decision_type": "d",
            "summary": "ok",
            "result": "ok",
            "artifact_refs": {},
            "created_at": "2026-06-01T00:00:00+00:00",
        },
        stored_canonical_payload_hash=compute_payload_hash(
            build_canonical_payload(
                {
                    "audit_log_id": "id",
                    "task_id": "T",
                    "agent": "x",
                    "decision_type": "d",
                    "summary": "ok",
                    "result": "ok",
                    "artifact_refs": {},
                    "created_at": "2026-06-01T00:00:00+00:00",
                }
            )
        ),
        stored_row_hash="will_not_match",
        stored_prev_hash=None,
        signature_status="signed",
        expected_prev_record_hash=None,
        signature_verification_status="key_missing",
    )
    # canonical OK + row mismatch (stored_row bogus) -> not signature-only.
    # Build a clean signature-only case directly instead:
    assert a.signature_verification_status == FAILURE_SIGNING_KEY_MISSING
    out = classify_chain_root_cause([_signature_only_record()])
    assert out["root_cause_classification"] == ROOT_CAUSE_HMAC_KEY_MISSING_ONLY
    assert out["repair_allowed"] is False
    assert rec is not None


def _signature_only_record() -> FailedRecordAnalysis:
    base = {
        "task_id": "T",
        "agent": "x",
        "decision_type": "d",
        "summary": "ok",
        "result": "ok",
        "artifact_refs": {},
        "created_at": "2026-06-01T00:00:00+00:00",
    }
    stored_canonical = compute_payload_hash(build_canonical_payload({"audit_log_id": "id", **base}))
    from shared.sdk.audit_integrity import compute_row_hash

    stored_row = compute_row_hash(
        chain_version=1,
        sequence_number=1,
        audit_log_id="id",
        prev_hash=None,
        canonical_payload_hash=stored_canonical,
    )
    return analyse_record(
        sequence_number=1,
        audit_log_id="id",
        audit_log_row=base,
        stored_canonical_payload_hash=stored_canonical,
        stored_row_hash=stored_row,
        stored_prev_hash=None,
        signature_status="signed",
        expected_prev_record_hash=None,
        signature_verification_status="signature_failed",
    )


def test_canonicalization_drift_cluster():
    # >=3 records, same decision_type, canonical mismatch, no markers.
    recs = []
    for seq in (10, 11, 12, 13):
        recs.append(
            analyse_record(
                sequence_number=seq,
                audit_log_id=str(seq),
                audit_log_row={
                    "task_id": f"T{seq}",
                    "agent": "x",
                    "decision_type": "uniform_type",
                    "summary": f"row {seq}",
                    "result": "ok",
                    "artifact_refs": {"production_executed": False},
                    "created_at": "2026-06-01T00:00:00+00:00",
                },
                stored_canonical_payload_hash="mismatch_hash",
                stored_row_hash="rr",
                stored_prev_hash="pp",
                signature_status="signing_key_not_configured",
                expected_prev_record_hash="pp",
            )
        )
    out = classify_chain_root_cause(recs)
    assert out["root_cause_classification"] == ROOT_CAUSE_CANONICALIZATION_VERSION_DRIFT
    assert out["repair_allowed"] is True
    assert out["affected_decision_types"] == ["uniform_type"]


def test_mixed_causes_force_unknown():
    tamper = _synthetic_tamper_record(5)
    mutated = analyse_record(
        sequence_number=6,
        audit_log_id="6",
        audit_log_row={
            "task_id": "T",
            "agent": "x",
            "decision_type": "d",
            "summary": "real mutation no marker",
            "result": "ok",
            "artifact_refs": {"production_executed": False},
            "created_at": "2026-06-01T00:00:00+00:00",
        },
        stored_canonical_payload_hash="bogus",
        stored_row_hash="rr",
        stored_prev_hash="pp",
        signature_status="signing_key_not_configured",
        expected_prev_record_hash="pp",
    )
    out = classify_chain_root_cause([tamper, mutated])
    assert out["root_cause_classification"] == ROOT_CAUSE_UNKNOWN
    assert out["repair_allowed"] is False


def test_production_executed_blocks_repair():
    base = {
        "task_id": "smoke",
        "agent": "x",
        "decision_type": "github_real_test_blocked",
        "summary": "blocked",
        "result": "blocked",
        "artifact_refs": {"production_executed": True},
        "created_at": "2026-06-13T00:00:00+00:00",
    }
    stored = compute_payload_hash(build_canonical_payload({"audit_log_id": "p", **base}))
    tampered = dict(base, summary=base["summary"] + " [TAMPER-SIMULATION]")
    rec = analyse_record(
        sequence_number=9,
        audit_log_id="p",
        audit_log_row=tampered,
        stored_canonical_payload_hash=stored,
        stored_row_hash="rr",
        stored_prev_hash="pp",
        signature_status="signing_key_not_configured",
        expected_prev_record_hash="pp",
    )
    # production_executed True -> record is not classified test_tamper.
    out = classify_chain_root_cause([rec])
    assert out["repair_allowed"] is False
