"""Stage 52 -- one-time confirmation nonce validation."""

from __future__ import annotations

from shared.sdk.operator_actions.confirmation import (
    confirmation_valid,
    expiry_ts,
    generate_nonce,
    nonce_hash,
)


def test_valid_confirmation() -> None:
    nonce = generate_nonce()
    ok, reason = confirmation_valid(
        provided_nonce=nonce,
        stored_hash=nonce_hash(nonce),
        used=False,
        expires_ts=expiry_ts(now=1000),
        same_identity=True,
        now=1100,
    )
    assert ok is True and reason == "ok"


def test_used_confirmation_rejected() -> None:
    nonce = generate_nonce()
    ok, reason = confirmation_valid(
        provided_nonce=nonce,
        stored_hash=nonce_hash(nonce),
        used=True,
        expires_ts=expiry_ts(now=1000),
        same_identity=True,
        now=1100,
    )
    assert ok is False and reason == "confirmation_already_used"


def test_expired_confirmation_rejected() -> None:
    nonce = generate_nonce()
    ok, reason = confirmation_valid(
        provided_nonce=nonce,
        stored_hash=nonce_hash(nonce),
        used=False,
        expires_ts=expiry_ts(now=1000, ttl=300),
        same_identity=True,
        now=99999,
    )
    assert ok is False and reason == "confirmation_expired"


def test_identity_mismatch_rejected() -> None:
    nonce = generate_nonce()
    ok, reason = confirmation_valid(
        provided_nonce=nonce,
        stored_hash=nonce_hash(nonce),
        used=False,
        expires_ts=expiry_ts(now=1000),
        same_identity=False,
        now=1100,
    )
    assert ok is False and reason == "confirmation_identity_mismatch"


def test_wrong_nonce_rejected() -> None:
    ok, reason = confirmation_valid(
        provided_nonce="wrong",
        stored_hash=nonce_hash(generate_nonce()),
        used=False,
        expires_ts=expiry_ts(now=1000),
        same_identity=True,
        now=1100,
    )
    assert ok is False and reason == "confirmation_invalid"


def test_nonce_hash_not_raw() -> None:
    n = generate_nonce()
    assert nonce_hash(n) != n and len(nonce_hash(n)) == 64
