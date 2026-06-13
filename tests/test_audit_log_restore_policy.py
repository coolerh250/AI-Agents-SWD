"""Stage 43 -- restore policy doc + precheck-as-policy gating (pure)."""

from __future__ import annotations

from pathlib import Path

from shared.sdk.audit_integrity.log_restore import (
    RESTORE_TYPE_TEST_TAMPER_RESIDUE,
    RestorePrecheck,
)

POLICY_DOC = Path("docs/operations/audit-log-restore-exception-policy.md")


def test_policy_doc_exists():
    assert POLICY_DOC.is_file(), "audit-log-restore-exception-policy.md must exist"


def test_policy_doc_states_key_constraints():
    text = POLICY_DOC.read_text(encoding="utf-8").lower()
    for needle in [
        "test_tamper_not_restored",
        "audit_log_restore_approved",
        "audit_integrity_records",
        "production_executed",
        "dry-run",
    ]:
        assert needle in text, f"policy doc must mention {needle!r}"


def test_restore_type_constant():
    assert RESTORE_TYPE_TEST_TAMPER_RESIDUE == "test_tamper_residue"


def test_precheck_dict_is_redacted():
    pc = RestorePrecheck(
        ok=True,
        affected_audit_log_id="abc",
        affected_sequence_number=265288,
        root_cause="test_tamper_not_restored",
        before_summary_hash="h1",
        after_summary_hash="h2",
    )
    d = pc.to_dict()
    # Precheck dict exposes hashes + ids, never the raw summary text.
    assert "summary" not in {k for k in d if k in ("summary", "_current_summary")}
    assert d["before_summary_hash"] == "h1"
    assert d["affected_sequence_number"] == 265288
