"""Stage 39 -- HMAC keyring loader tests (no DB)."""

from __future__ import annotations

import json

from shared.sdk.audit_integrity import (
    KEYRING_MODE_INVALID,
    KEYRING_MODE_LEGACY_SINGLE_KEY,
    KEYRING_MODE_MULTI_KEYRING,
    KEYRING_MODE_NONE,
    AuditHmacKeyring,
    AuditSigner,
)
from shared.sdk.audit_integrity.keyring import (
    KEY_SOURCE_KEYRING_ENV,
    KEY_SOURCE_LEGACY_ENV,
)


def test_keyring_mode_none_when_no_env_vars_set():
    kr = AuditHmacKeyring(env={})
    assert kr.mode == KEYRING_MODE_NONE
    assert kr.configured is False
    assert kr.valid is True
    assert kr.active_key_id is None
    assert kr.known_key_ids == []


def test_legacy_single_key_loads_with_default_id():
    kr = AuditHmacKeyring(env={"AUDIT_HMAC_KEY": "secret-bytes"})
    assert kr.mode == KEYRING_MODE_LEGACY_SINGLE_KEY
    assert kr.configured is True
    assert kr.active_key_id == "legacy-single-key"
    assert kr.known_key_ids == ["legacy-single-key"]
    assert kr.source == KEY_SOURCE_LEGACY_ENV


def test_legacy_single_key_respects_explicit_id():
    kr = AuditHmacKeyring(env={"AUDIT_HMAC_KEY": "secret-bytes", "AUDIT_HMAC_KEY_ID": "kid-alpha"})
    assert kr.active_key_id == "kid-alpha"
    assert kr.has_key("kid-alpha")


def test_multi_keyring_loads_and_picks_declared_active():
    payload = {
        "active_key_id": "kid-2",
        "keys": {"kid-1": "old-secret", "kid-2": "new-secret"},
    }
    kr = AuditHmacKeyring(env={"AUDIT_HMAC_KEYRING_JSON": json.dumps(payload)})
    assert kr.mode == KEYRING_MODE_MULTI_KEYRING
    assert kr.active_key_id == "kid-2"
    assert set(kr.known_key_ids) == {"kid-1", "kid-2"}
    assert kr.source == KEY_SOURCE_KEYRING_ENV


def test_multi_keyring_active_override_via_env():
    payload = {
        "active_key_id": "kid-2",
        "keys": {"kid-1": "old", "kid-2": "new"},
    }
    kr = AuditHmacKeyring(
        env={
            "AUDIT_HMAC_KEYRING_JSON": json.dumps(payload),
            "AUDIT_HMAC_ACTIVE_KEY_ID": "kid-1",
        }
    )
    assert kr.active_key_id == "kid-1"


def test_invalid_keyring_when_json_malformed():
    kr = AuditHmacKeyring(env={"AUDIT_HMAC_KEYRING_JSON": "not json"})
    assert kr.mode == KEYRING_MODE_INVALID
    assert kr.valid is False
    assert kr.configured is False
    assert kr.invalid_reason and "JSON" in kr.invalid_reason


def test_invalid_keyring_when_active_not_in_keys():
    payload = {"active_key_id": "missing", "keys": {"kid-1": "secret"}}
    kr = AuditHmacKeyring(env={"AUDIT_HMAC_KEYRING_JSON": json.dumps(payload)})
    assert kr.mode == KEYRING_MODE_INVALID
    assert "active_key_id" in (kr.invalid_reason or "")


def test_invalid_keyring_when_keys_empty():
    payload = {"active_key_id": "k", "keys": {}}
    kr = AuditHmacKeyring(env={"AUDIT_HMAC_KEYRING_JSON": json.dumps(payload)})
    assert kr.mode == KEYRING_MODE_INVALID


def test_invalid_keyring_when_value_empty():
    payload = {"active_key_id": "k", "keys": {"k": ""}}
    kr = AuditHmacKeyring(env={"AUDIT_HMAC_KEYRING_JSON": json.dumps(payload)})
    assert kr.mode == KEYRING_MODE_INVALID


def test_keyring_snapshot_excludes_key_value():
    kr = AuditHmacKeyring(
        env={
            "AUDIT_HMAC_KEYRING_JSON": json.dumps(
                {"active_key_id": "kid-1", "keys": {"kid-1": "very-secret-value-XYZ"}}
            )
        }
    )
    snap = kr.snapshot().to_safe_dict()
    flat = json.dumps(snap)
    assert "very-secret-value-XYZ" not in flat


def test_signer_uses_keyring_active_key():
    kr = AuditHmacKeyring(
        env={
            "AUDIT_HMAC_KEYRING_JSON": json.dumps(
                {
                    "active_key_id": "kid-active",
                    "keys": {"kid-old": "old", "kid-active": "new"},
                }
            )
        }
    )
    signer = AuditSigner(keyring=kr)
    sig, status, key_id = signer.sign("deadbeef")
    assert key_id == "kid-active"
    assert status == "signed"
    assert sig is not None and len(sig) == 64


def test_signer_refuses_to_sign_when_keyring_invalid():
    kr = AuditHmacKeyring(env={"AUDIT_HMAC_KEYRING_JSON": "{broken"})
    signer = AuditSigner(keyring=kr)
    sig, status, key_id = signer.sign("deadbeef")
    assert sig is None
    assert status == "signing_key_not_configured"
    assert key_id == "unsigned"
