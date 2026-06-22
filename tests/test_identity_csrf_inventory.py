"""Step 52.1 -- CSRF inventory."""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
F = ROOT / "infra" / "identity" / "csrf-inventory.yaml"


def _c() -> dict:
    return yaml.safe_load(F.read_text(encoding="utf-8"))["csrf"]


def test_enabled_and_methods() -> None:
    c = _c()
    assert c["enabled"] is True
    assert set(c["protectedMethods"]) == {"POST", "PUT", "PATCH", "DELETE"}
    assert "GET" in c["unprotectedMethods"]


def test_header_and_binding() -> None:
    c = _c()
    assert c["headerName"] == "X-CSRF-Token"
    assert c["boundToSession"] is True


def test_failure_rejects() -> None:
    c = _c()
    assert c["missingTokenBehavior"] == "reject_403"
    assert c["invalidTokenBehavior"] == "reject_403"


def test_token_not_in_url_or_audit() -> None:
    c = _c()
    assert c["tokenInUrl"] is False
    assert c["tokenAuditedOrLogged"] is False
