"""Stage 34 -- HMAC signer tests."""

from __future__ import annotations

from shared.sdk.audit_integrity import AuditSigner
from shared.sdk.audit_integrity.models import (
    SIGNATURE_STATUS_NOT_CONFIGURED,
    SIGNATURE_STATUS_SIGNED,
)


def test_signer_returns_not_configured_when_key_missing():
    signer = AuditSigner(env={})
    sig, status, key_id = signer.sign("0" * 64)
    assert sig is None
    assert status == SIGNATURE_STATUS_NOT_CONFIGURED
    assert key_id == "unsigned"
    assert signer.configured is False


def test_signer_signs_when_key_present_and_returns_hex_digest():
    signer = AuditSigner(env={"AUDIT_HMAC_KEY": "test-key", "AUDIT_HMAC_KEY_ID": "kid-1"})
    sig, status, key_id = signer.sign("deadbeef")
    assert status == SIGNATURE_STATUS_SIGNED
    assert key_id == "kid-1"
    assert sig is not None and len(sig) == 64  # SHA-256 hex digest
    assert signer.configured is True


def test_signer_verify_round_trip():
    signer = AuditSigner(env={"AUDIT_HMAC_KEY": "k"})
    sig, _, _ = signer.sign("abc")
    assert signer.verify("abc", sig) is True
    assert signer.verify("abd", sig) is False
    assert signer.verify("abc", "") is False


def test_signer_verify_returns_false_when_key_missing():
    signer = AuditSigner(env={})
    # Even with a signature value, an unconfigured signer cannot verify.
    assert signer.verify("anything", "garbage") is False


def test_signer_repr_does_not_leak_key():
    signer = AuditSigner(env={"AUDIT_HMAC_KEY": "super-secret-value-xyz"})
    text = repr(signer)
    assert "super-secret-value-xyz" not in text
    # The default repr exposes only the class + id; the key is held
    # privately. This test pins that behavior.
    assert "AuditSigner" in text


def test_signer_default_key_id_when_key_present_no_explicit_id():
    signer = AuditSigner(env={"AUDIT_HMAC_KEY": "k"})
    assert signer.key_id == "default-test-key-id"
