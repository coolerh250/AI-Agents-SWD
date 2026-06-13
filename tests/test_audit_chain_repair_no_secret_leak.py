"""Stage 42 -- forensic/repair surfaces never leak secrets or raw payload."""

from __future__ import annotations

import json

from shared.sdk.audit_integrity import build_canonical_payload, compute_payload_hash
from shared.sdk.audit_integrity.forensics import analyse_record, redact_summary
from shared.sdk.audit_integrity.repair import RepairPlan

SECRET_TOKENS = [
    "ghp_abcdefgh12345678ijklmnop",
    "sk-abcdefgh12345678ijklmnop",
    "xoxb-1111-2222-aaaaaaaaaaaa",
]


def test_redact_summary_scrubs_tokens():
    for tok in SECRET_TOKENS:
        out = redact_summary(f"leaked {tok} here")
        assert tok not in out
        assert "[REDACTED]" in out


def test_redact_summary_truncates_long_text():
    out = redact_summary("x" * 500)
    assert len(out) <= 200
    assert out.endswith("[truncated]")


def test_record_to_dict_has_no_raw_token():
    base = {
        "task_id": "T",
        "agent": "x",
        "decision_type": "d",
        "summary": "blocked ghp_abcdefgh12345678ijklmnop trailing",
        "result": "ok",
        "artifact_refs": {"production_executed": False},
        "created_at": "2026-06-01T00:00:00+00:00",
    }
    stored = compute_payload_hash(build_canonical_payload({"audit_log_id": "id", **base}))
    a = analyse_record(
        sequence_number=1,
        audit_log_id="id",
        audit_log_row=base,
        stored_canonical_payload_hash=stored,
        stored_row_hash="r",
        stored_prev_hash=None,
        signature_status="signing_key_not_configured",
        expected_prev_record_hash=None,
    )
    blob = json.dumps(a.to_dict())
    assert "ghp_" not in blob


def test_plan_dict_carries_no_payload():
    plan = RepairPlan(
        root_cause="test_tamper_not_restored",
        repair_allowed=True,
        repair_risk="low",
        first_failed_sequence=1,
        affected_sequences=[1, 2, 3],
        reason="synthetic",
    )
    blob = json.dumps(plan.to_dict())
    # Plan exposes hashes/sequences, never summary or artifact_refs content.
    assert "summary" not in blob
    assert "artifact_refs" not in blob


def test_forensics_module_never_reads_key_material():
    import shared.sdk.audit_integrity.forensics as f

    src = open(f.__file__, encoding="utf-8").read()
    # The analyzer must never read an HMAC key env var or select the
    # hmac_signature column (it works from signature_status only).
    assert "AUDIT_HMAC_KEY" not in src
    assert "r.hmac_signature" not in src
