"""Step 52.2 -- no secret/token-shaped value in the OIDC surface.

Also a positive control: the detector must flag a runtime-assembled token shape.
"""

from __future__ import annotations

from pathlib import Path

from shared.sdk.identity import contains_secret_like, find_secret_like

ROOT = Path(__file__).resolve().parents[1]
IDENT = ROOT / "infra" / "identity"
SDK_DIR = ROOT / "shared" / "sdk" / "identity"


def test_oidc_yaml_files_have_no_secret_like_value() -> None:
    for p in sorted(IDENT.glob("oidc-*.yaml")) + [IDENT / "production-oidc-disabled-config.yaml"]:
        assert find_secret_like(p.read_text(encoding="utf-8")) == [], p.name


def test_sdk_files_have_no_secret_like_value() -> None:
    for p in SDK_DIR.glob("*.py"):
        if p.name == "oidc_redaction.py":  # detector holds pattern fragments
            continue
        assert find_secret_like(p.read_text(encoding="utf-8")) == [], p.name


def test_detector_positive_control() -> None:
    jwt = "eyJ" + "a" * 20 + "." + "b" * 20 + "." + "c" * 20
    assert contains_secret_like(jwt) is True
    assert contains_secret_like("client_secret: " + "Z" * 24) is True


def test_detector_allows_placeholders() -> None:
    assert contains_secret_like('clientSecret:\n  name: ""\n  key: ""') is False
    assert contains_secret_like("issuer: <placeholder>") is False
    assert contains_secret_like("contact: ops@example.com") is False
