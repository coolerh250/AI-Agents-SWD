"""Stage 52 -- CSRF token bound to session; invalid/cross-session rejected."""

from __future__ import annotations

from shared.sdk.operator_actions.csrf import issue_csrf, verify_csrf


def test_valid_csrf() -> None:
    sh = "a" * 64
    t = issue_csrf(sh, now=1000, env={})
    assert verify_csrf(t, sh, now=1100, env={}) is True


def test_cross_session_csrf_rejected() -> None:
    t = issue_csrf("a" * 64, now=1000, env={})
    assert verify_csrf(t, "b" * 64, now=1100, env={}) is False


def test_missing_or_garbage_csrf_rejected() -> None:
    sh = "c" * 64
    assert verify_csrf("", sh, env={}) is False
    assert verify_csrf("nope", sh, env={}) is False


def test_expired_csrf_rejected() -> None:
    sh = "d" * 64
    t = issue_csrf(sh, now=1000, env={})
    assert verify_csrf(t, sh, now=1000 + 99999, ttl=1800, env={}) is False
