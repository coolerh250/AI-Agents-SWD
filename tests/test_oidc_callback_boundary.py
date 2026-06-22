"""Step 52.2 -- OIDC callback boundary: callback disabled, no code handling."""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
F = ROOT / "infra" / "identity" / "oidc-callback-boundary.yaml"


def _d() -> dict:
    return yaml.safe_load(F.read_text(encoding="utf-8"))


def test_callback_disabled() -> None:
    cb = _d()["callback"]
    assert cb["enabled"] is False
    assert cb["authorizationCodeExchange"] is False
    assert cb["createsSession"] is False
    assert cb["assignsRole"] is False
    assert _d()["status"] == "disabled"


def test_reject_and_mustnot_rules() -> None:
    d = _d()
    for r in (
        "provider_disabled",
        "missing_state",
        "invalid_nonce",
        "missing_code",
        "tokens_in_url_fragment",
    ):
        assert r in d["mustReject"]
    for r in ("log_authorization_code", "log_token", "create_session_before_token_validation"):
        assert r in d["mustNot"]


def test_only_readonly_status_route_allowed() -> None:
    d = _d()
    allowed = d["allowedRoutes"]
    assert all(r["method"] == "GET" and r["handlesCode"] is False for r in allowed)
    forbidden_paths = {r["path"] for r in d["forbiddenRoutes"]}
    assert "/auth/oidc/callback" in forbidden_paths


def test_audit_no_raw_token() -> None:
    a = _d()["auditing"]
    assert a["rawTokenRecorded"] is False
    assert a["rawCodeRecorded"] is False
