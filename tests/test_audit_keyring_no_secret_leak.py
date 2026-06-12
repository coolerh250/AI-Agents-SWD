"""Stage 39 -- ensure no key value leaks via any Stage 39 surface."""

from __future__ import annotations

import json
from pathlib import Path

from shared.sdk.audit_integrity import (
    AuditHmacKeyring,
    AuditSigner,
)
from shared.sdk.audit_integrity.audit_events import safe_keyring_artifact_refs

_SECRET_MARKER = "this-must-never-appear-in-output-zz0117"


def _build_keyring() -> AuditHmacKeyring:
    return AuditHmacKeyring(
        env={
            "AUDIT_HMAC_KEYRING_JSON": json.dumps(
                {
                    "active_key_id": "kid-1",
                    "keys": {"kid-1": _SECRET_MARKER},
                }
            )
        }
    )


def test_keyring_snapshot_to_dict_does_not_contain_key_value():
    snap = _build_keyring().snapshot()
    body = json.dumps(snap.to_safe_dict())
    assert _SECRET_MARKER not in body


def test_signer_signature_is_not_the_key_value():
    signer = AuditSigner(keyring=_build_keyring())
    sig, _, _ = signer.sign("row-hash-abc")
    assert sig is not None
    assert _SECRET_MARKER not in sig


def test_artifact_refs_helper_drops_key_value():
    refs = safe_keyring_artifact_refs(
        keyring_mode="multi_keyring",
        active_key_id="kid-1",
        known_key_ids=["kid-1"],
        valid=True,
        verification_mode="permissive",
        signature_status="signed",
    )
    flat = json.dumps(refs)
    assert _SECRET_MARKER not in flat
    assert "key_id" in refs
    assert refs["production_executed"] is False


def test_signer_repr_does_not_leak_key():
    signer = AuditSigner(keyring=_build_keyring())
    text = repr(signer)
    assert _SECRET_MARKER not in text


def test_keyring_repr_does_not_leak_key():
    keyring = _build_keyring()
    text = repr(keyring)
    assert _SECRET_MARKER not in text


def test_audit_integrity_sdk_does_not_log_key():
    """The SDK source files must not echo or log AUDIT_HMAC_KEY content."""

    sdk_dir = Path(__file__).resolve().parents[1] / "shared" / "sdk" / "audit_integrity"
    forbidden_patterns = (
        "print(AUDIT_HMAC_KEY",
        "logger.info(AUDIT_HMAC_KEY",
        "logger.debug(AUDIT_HMAC_KEY",
        "logging.info(AUDIT_HMAC_KEY",
    )
    for py_file in sdk_dir.glob("*.py"):
        src = py_file.read_text(encoding="utf-8")
        for pattern in forbidden_patterns:
            assert pattern not in src, f"{py_file.name} must not log the key value"
