"""Stage 34 -- operations endpoints + safety fields for audit integrity."""

from __future__ import annotations

from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]


def _read_operations() -> str:
    return (_REPO_ROOT / "apps" / "orchestrator" / "src" / "operations.py").read_text(
        encoding="utf-8"
    )


def test_integrity_routes_registered():
    src = _read_operations()
    for path in (
        '@router.get("/audit/integrity")',
        '@router.post("/audit/verify-chain")',
        '@router.get("/audit/verify-chain/latest")',
        '@router.get("/audit/receipt/{audit_log_id}")',
    ):
        assert path in src, f"missing route: {path}"


def test_safety_carries_stage34_fields():
    src = _read_operations()
    for field in (
        '"audit_integrity_enabled"',
        '"audit_chain_latest_status"',
        '"audit_integrity_degraded"',
        '"audit_hmac_enabled"',
        '"audit_last_verification_at"',
        '"audit_missing_integrity_records"',
        '"audit_tamper_detected"',
    ):
        assert field in src, f"missing safety field: {field}"


def test_summary_carries_audit_integrity_summary():
    src = _read_operations()
    assert "audit_integrity_summary" in src
    assert "_audit_integrity_summary" in src


def test_receipt_response_does_not_expose_full_signature_by_default():
    """The receipt endpoint exposes hmac_signature_present + preview only.

    Stage 39 added rotation-aware verification on the receipt path; the
    handler may now read ``record.hmac_signature`` server-side to call
    ``signer.verify_with(...)``, but the *response body* still only
    contains ``hmac_signature_present`` + ``hmac_signature_preview``
    from ``to_safe_dict``.
    """
    src = _read_operations()
    models_src = (_REPO_ROOT / "shared" / "sdk" / "audit_integrity" / "models.py").read_text(
        encoding="utf-8"
    )
    assert "hmac_signature_present" in models_src
    assert "hmac_signature_preview" in models_src
    # The orchestrator endpoint MUST go through to_safe_dict to build
    # the response body.
    assert "record.to_safe_dict" in src
    # The response must not assign the bare hmac_signature into the body.
    assert 'body["hmac_signature"]' not in src
    assert "'hmac_signature'" not in src
