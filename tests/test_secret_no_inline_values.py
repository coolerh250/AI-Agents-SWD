"""Step 53 -- no inline secret values in the secret-management surface."""

from __future__ import annotations

from pathlib import Path

from shared.sdk.secrets_foundation import contains_committed_secret, find_committed_secret

ROOT = Path(__file__).resolve().parents[1]
SECRETS = ROOT / "infra" / "secrets"
SDK = ROOT / "shared" / "sdk" / "secrets_foundation"


def test_infra_secrets_have_no_inline_value() -> None:
    for p in sorted(SECRETS.glob("*.yaml")):
        assert find_committed_secret(p.read_text(encoding="utf-8")) == [], p.name


def test_sdk_modules_have_no_inline_value() -> None:
    for p in SDK.glob("*.py"):
        # detector modules legitimately hold pattern fragments
        if p.name in ("secret_redaction.py", "secret_ref.py"):
            continue
        assert find_committed_secret(p.read_text(encoding="utf-8")) == [], p.name


def test_detector_positive_control() -> None:
    jwt = "eyJ" + "a" * 20 + "." + "b" * 20 + "." + "c" * 20
    assert contains_committed_secret(jwt) is True
    assert contains_committed_secret("-----BEGIN " + "PRIVATE KEY-----") is True
    assert contains_committed_secret("ghp_" + "A" * 30) is True


def test_detector_allows_placeholders() -> None:
    assert contains_committed_secret('name: ""\nkey: ""') is False
    assert contains_committed_secret("issuer: https://idp.example.com") is False
    assert contains_committed_secret("postgresql://postgres@localhost:5432/aiagents") is False
