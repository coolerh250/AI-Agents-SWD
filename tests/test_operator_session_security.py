"""Stage 52 -- session token signing / verification / expiry / tamper."""

from __future__ import annotations

from shared.sdk.operator_actions.session import issue_session, session_hash, verify_session


def test_valid_session_roundtrip() -> None:
    tok, issued, expires = issue_session("operator-test", ttl_seconds=1800, now=1000, env={})
    claims = verify_session(tok, now=1100, env={})
    assert claims and claims["identity_key"] == "operator-test"
    assert claims["expires_at"] == expires


def test_expired_session_rejected() -> None:
    tok, _i, _e = issue_session("operator-test", ttl_seconds=10, now=1000, env={})
    assert verify_session(tok, now=2000, env={}) is None


def test_tampered_token_rejected() -> None:
    tok, _i, _e = issue_session("operator-test", now=1000, env={})
    assert verify_session(tok + "x", now=1100, env={}) is None
    payload, sig = tok.split(".", 1)
    assert verify_session(payload + ".AAAA", now=1100, env={}) is None


def test_session_hash_not_token() -> None:
    tok, _i, _e = issue_session("operator-test", now=1000, env={})
    h = session_hash(tok)
    assert h != tok and len(h) == 64


def test_no_session_returns_none() -> None:
    assert verify_session("", now=1, env={}) is None
    assert verify_session("garbage", now=1, env={}) is None
