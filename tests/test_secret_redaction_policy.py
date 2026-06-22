"""Step 53 -- secret redaction policy + helper."""

from __future__ import annotations

from pathlib import Path

import yaml

from shared.sdk.secrets_foundation import contains_committed_secret, redact

ROOT = Path(__file__).resolve().parents[1]
F = ROOT / "infra" / "secrets" / "secret-redaction-policy.yaml"


def test_policy_enabled_lists_substrings() -> None:
    d = yaml.safe_load(F.read_text(encoding="utf-8"))
    assert d["status"] == "enabled"
    for sub in ("secret", "token", "password", "key", "private", "credential", "jwt"):
        assert sub in d["redactKeySubstrings"]


def test_redact_secret_keyed_value() -> None:
    out = redact({"client_secret": "hunter2supersecret", "issuer": "https://idp.example.com"})
    assert out["client_secret"] == "***REDACTED***"
    assert out["issuer"] == "https://idp.example.com"


def test_redact_token_string_value() -> None:
    jwt = "eyJ" + "a" * 20 + "." + "b" * 20 + "." + "c" * 20
    assert redact({"blob": jwt})["blob"] == "***REDACTED***"


def test_redact_nested() -> None:
    out = redact({"a": {"password": "x" * 12}, "b": ["ok", {"token": "y" * 12}]})
    assert out["a"]["password"] == "***REDACTED***"
    assert out["b"][1]["token"] == "***REDACTED***"


def test_detector_positive_control() -> None:
    assert contains_committed_secret("-----BEGIN " + "PRIVATE KEY-----") is True
