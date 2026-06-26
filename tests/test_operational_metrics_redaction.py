"""Step 58 -- operational metrics redaction."""

from __future__ import annotations

from shared.sdk.operations_metrics.redaction import redact


def test_redacts_secret_shapes() -> None:
    out = redact({"x": "ghp_" + "a" * 30, "ok": "running"})
    assert out["x"] == "[redacted]"
    assert out["ok"] == "running"


def test_redacts_forbidden_keys() -> None:
    out = redact({"token": "abc", "password": "p", "kubeconfig": "k", "count": 5})
    assert out["token"] == "[redacted]"
    assert out["password"] == "[redacted]"
    assert out["kubeconfig"] == "[redacted]"
    assert out["count"] == 5


def test_recurses_nested() -> None:
    out = redact({"a": {"secret": "x", "n": 1}, "b": ["running", "BEGIN RSA PRIVATE KEY"]})
    assert out["a"]["secret"] == "[redacted]"
    assert out["a"]["n"] == 1
    assert out["b"][0] == "running"
    assert out["b"][1] == "[redacted]"
