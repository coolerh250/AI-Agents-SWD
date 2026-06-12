"""Stage 39 -- structural assertions on the orchestrator keyring/audit endpoints."""

from __future__ import annotations

from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]


def _read_operations() -> str:
    return (_REPO_ROOT / "apps" / "orchestrator" / "src" / "operations.py").read_text(
        encoding="utf-8"
    )


def test_keyring_endpoint_registered():
    src = _read_operations()
    assert '@router.get("/audit/keyring")' in src
    assert "operations_audit_keyring" in src


def test_verify_chain_accepts_mode_argument():
    src = _read_operations()
    assert "resolve_verify_mode" in src
    # The verify-chain handler must build a verifier with the resolved mode.
    assert "AuditChainVerifier(mode=" in src
    # The verifier module is where the three modes live.
    verifier_src = (_REPO_ROOT / "shared" / "sdk" / "audit_integrity" / "verifier.py").read_text(
        encoding="utf-8"
    )
    for marker in ("VERIFY_MODE_STRICT", "VERIFY_MODE_PERMISSIVE", "VERIFY_MODE_CHAIN_ONLY"):
        assert marker in verifier_src, f"verifier module missing {marker}"


def test_safety_carries_stage39_audit_fields():
    src = _read_operations()
    for field in (
        '"audit_hmac_keyring_configured"',
        '"audit_hmac_keyring_valid"',
        '"audit_hmac_keyring_mode"',
        '"audit_hmac_active_signing_key_id"',
        '"audit_hmac_rotation_supported": True',
        '"audit_direct_post_integrity_enabled"',
        '"audit_direct_post_integrity_gap_closed"',
        '"audit_integrity_concurrency_lock_enabled"',
        '"audit_integrity_strict_verify_ready"',
        '"audit_signature_key_missing_count"',
    ):
        assert field in src, f"missing safety field: {field}"


def test_integrity_summary_exposes_stage39_counts():
    src = _read_operations()
    for field in (
        '"hmac_keyring_configured"',
        '"hmac_keyring_mode"',
        '"hmac_keyring_valid"',
        '"active_signing_key_id"',
        '"known_key_ids"',
        '"signed_records"',
        '"unsigned_records"',
        '"key_missing_records"',
        '"signature_failed_records"',
        '"latest_verification_mode"',
        '"direct_post_integrity_enabled"',
        '"direct_post_missing_integrity_records"',
        '"audit_integrity_writer_locking_enabled"',
    ):
        assert field in src, f"missing audit integrity summary field: {field}"


def test_receipt_endpoint_exposes_rotation_aware_fields():
    src = _read_operations()
    assert '"key_available"' in src
    assert '"signature_verification_status"' in src
    assert '"keyring_mode"' in src


def test_no_secret_in_audit_handlers():
    """Stage 39 audit handlers must never read the HMAC key value."""

    src = _read_operations()
    marker = "Stage 39 -- Audit Integrity Remediation operations view"
    assert marker in src
    block = src[src.index(marker) :]
    forbidden = (
        'os.environ.get("AUDIT_HMAC_KEY"',
        'os.environ["AUDIT_HMAC_KEY"',
        'os.environ.get("AUDIT_HMAC_KEYRING_JSON"',
    )
    for needle in forbidden:
        assert needle not in block, f"Stage 39 routing handlers must not read {needle}"
