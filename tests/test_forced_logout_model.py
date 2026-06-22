"""Step 52.3 -- forced logout model."""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
F = ROOT / "infra" / "identity" / "forced-logout-model.yaml"


def _f() -> dict:
    return yaml.safe_load(F.read_text(encoding="utf-8"))["forcedLogout"]


def test_session_revoke_server_authoritative() -> None:
    r = _f()["sessionLevelRevoke"]
    assert r["supported"] is True
    assert r["serverAuthoritative"] is True
    assert r["frontendOnlyLogout"] is False


def test_role_change_forced_logout_required() -> None:
    assert _f()["roleChangeForcedLogout"]["required"] is True


def test_audit_required_no_raw_token() -> None:
    a = _f()["audit"]
    assert a["required"] is True
    assert a["rawTokenRecorded"] is False


def test_not_production_ready() -> None:
    s = yaml.safe_load(F.read_text(encoding="utf-8"))["status"]
    assert s["productionReady"] is False
