"""Stage 39 -- HMAC key rotation: sign with new key, verify old rows with old key."""

from __future__ import annotations

import json

from shared.sdk.audit_integrity import (
    AuditHmacKeyring,
    AuditSigner,
    VERIFY_OUTCOME_KEY_MISSING,
    VERIFY_OUTCOME_OK,
    VERIFY_OUTCOME_SIGNATURE_FAILED,
)


def _multi_keyring(active: str, keys: dict[str, str]) -> AuditHmacKeyring:
    return AuditHmacKeyring(
        env={"AUDIT_HMAC_KEYRING_JSON": json.dumps({"active_key_id": active, "keys": keys})}
    )


def test_active_key_signs_new_rows():
    keyring = _multi_keyring("kid-new", {"kid-old": "old", "kid-new": "new"})
    signer = AuditSigner(keyring=keyring)
    sig, status, kid = signer.sign("row-hash-abc")
    assert kid == "kid-new"
    assert status == "signed"
    assert sig is not None


def test_old_row_verifies_with_its_original_key():
    keyring_old = _multi_keyring("kid-old", {"kid-old": "old-secret"})
    sig_old, _, kid_old = AuditSigner(keyring=keyring_old).sign("row-1")

    # Rotate to a new active key, BUT keep the old key in the keyring.
    keyring_after = _multi_keyring("kid-new", {"kid-old": "old-secret", "kid-new": "new-secret"})
    verifier = AuditSigner(keyring=keyring_after)
    ok, outcome = verifier.verify_with(row_hash="row-1", signature=sig_old, signing_key_id=kid_old)
    assert ok is True
    assert outcome == VERIFY_OUTCOME_OK


def test_new_row_verifies_with_active_key():
    keyring = _multi_keyring("kid-new", {"kid-old": "old", "kid-new": "new"})
    signer = AuditSigner(keyring=keyring)
    sig, _, kid = signer.sign("row-new")
    ok, outcome = signer.verify_with(row_hash="row-new", signature=sig, signing_key_id=kid)
    assert ok is True
    assert outcome == VERIFY_OUTCOME_OK


def test_old_row_fails_when_old_key_dropped_from_keyring():
    keyring_old = _multi_keyring("kid-old", {"kid-old": "old-secret"})
    sig_old, _, kid_old = AuditSigner(keyring=keyring_old).sign("row-1")

    # Drop old key — only new key remains.
    keyring_after = _multi_keyring("kid-new", {"kid-new": "new-secret"})
    verifier = AuditSigner(keyring=keyring_after)
    ok, outcome = verifier.verify_with(row_hash="row-1", signature=sig_old, signing_key_id=kid_old)
    assert ok is False
    assert outcome == VERIFY_OUTCOME_KEY_MISSING


def test_signature_failure_distinguishes_from_key_missing():
    keyring = _multi_keyring("kid-1", {"kid-1": "secret"})
    signer = AuditSigner(keyring=keyring)
    # tampered signature, key IS present:
    ok, outcome = signer.verify_with(row_hash="row-1", signature="0" * 64, signing_key_id="kid-1")
    assert ok is False
    assert outcome == VERIFY_OUTCOME_SIGNATURE_FAILED


def test_key_rotation_does_not_change_history_signatures():
    keyring_v1 = _multi_keyring("kid-v1", {"kid-v1": "first-secret"})
    sig_v1, _, kid_v1 = AuditSigner(keyring=keyring_v1).sign("row-1")

    # Add a new key, rotate active. The historical row stays bound to
    # ``kid-v1`` -- the verifier MUST use the row's signing_key_id, not
    # the current active key.
    keyring_v2 = _multi_keyring("kid-v2", {"kid-v1": "first-secret", "kid-v2": "second-secret"})
    signer_v2 = AuditSigner(keyring=keyring_v2)
    ok, outcome = signer_v2.verify_with(row_hash="row-1", signature=sig_v1, signing_key_id=kid_v1)
    assert ok is True
    assert outcome == VERIFY_OUTCOME_OK
