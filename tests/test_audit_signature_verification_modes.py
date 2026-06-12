"""Stage 39 -- signature verification modes (permissive/strict/chain_only)."""

from __future__ import annotations

from shared.sdk.audit_integrity import (
    VERIFY_MODE_CHAIN_ONLY,
    VERIFY_MODE_PERMISSIVE,
    VERIFY_MODE_STRICT,
    resolve_verify_mode,
)
from shared.sdk.audit_integrity.verifier import _allow_unsigned_legacy


def test_resolve_verify_mode_explicit_wins():
    assert resolve_verify_mode("strict") == VERIFY_MODE_STRICT
    assert resolve_verify_mode("chain_only") == VERIFY_MODE_CHAIN_ONLY
    assert resolve_verify_mode("permissive") == VERIFY_MODE_PERMISSIVE


def test_resolve_verify_mode_defaults_to_permissive_for_unknown():
    assert resolve_verify_mode("garbage") == VERIFY_MODE_PERMISSIVE
    assert resolve_verify_mode(None) == VERIFY_MODE_PERMISSIVE
    assert resolve_verify_mode("") == VERIFY_MODE_PERMISSIVE


def test_resolve_verify_mode_normalises_case():
    assert resolve_verify_mode("STRICT") == VERIFY_MODE_STRICT
    assert resolve_verify_mode("Chain_Only") == VERIFY_MODE_CHAIN_ONLY


def test_resolve_verify_mode_uses_env_when_caller_doesnt_pass(monkeypatch):
    monkeypatch.setenv("AUDIT_VERIFY_SIGNATURE_MODE", "strict")
    assert resolve_verify_mode(None) == VERIFY_MODE_STRICT


def test_allow_unsigned_legacy_off_by_default(monkeypatch):
    monkeypatch.delenv("AUDIT_VERIFY_ALLOW_UNSIGNED_LEGACY", raising=False)
    assert _allow_unsigned_legacy() is False


def test_allow_unsigned_legacy_recognises_truthy(monkeypatch):
    for value in ("1", "true", "yes", "TRUE", "Yes"):
        monkeypatch.setenv("AUDIT_VERIFY_ALLOW_UNSIGNED_LEGACY", value)
        assert _allow_unsigned_legacy() is True


def test_verification_result_to_dict_contains_stage39_fields():
    from shared.sdk.audit_integrity.verifier import VerificationResult

    result = VerificationResult(
        status="passed",
        chain_version=1,
        total_records=2,
        verified_records=2,
        failed_records=0,
        mode=VERIFY_MODE_STRICT,
        keyring_mode="multi_keyring",
        active_signing_key_id="kid-active",
        known_key_ids=["kid-old", "kid-active"],
        signed_records=2,
        unsigned_records=0,
        key_missing_records=0,
        signature_failed_records=0,
    )
    body = result.to_dict()
    for field in (
        "mode",
        "keyring_mode",
        "active_signing_key_id",
        "known_key_ids",
        "signed_records",
        "unsigned_records",
        "key_missing_records",
        "signature_failed_records",
        "warnings",
    ):
        assert field in body, f"missing field: {field}"
    assert body["mode"] == VERIFY_MODE_STRICT
    assert body["active_signing_key_id"] == "kid-active"
