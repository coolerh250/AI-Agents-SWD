"""Stage 52 -- idempotency key validation."""

from __future__ import annotations

from shared.sdk.operator_actions.idempotency import is_valid_key, normalize_key


def test_valid_keys() -> None:
    assert is_valid_key("idem-abc12345") is True
    assert is_valid_key("a" * 32) is True


def test_invalid_keys() -> None:
    assert is_valid_key(None) is False
    assert is_valid_key("") is False
    assert is_valid_key("short") is False
    assert is_valid_key("has space here!!") is False
    assert is_valid_key("x" * 200) is False


def test_normalize() -> None:
    assert normalize_key("  k  ") == "k"
    assert normalize_key("") is None
    assert normalize_key(None) is None
