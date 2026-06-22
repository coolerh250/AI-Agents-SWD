"""Step 53 -- secret access boundary model."""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
F = ROOT / "infra" / "secrets" / "secret-access-boundary.yaml"


def _b() -> dict:
    return yaml.safe_load(F.read_text(encoding="utf-8"))["accessBoundary"]


def test_no_frontend_or_console_access() -> None:
    b = _b()
    assert b["frontendCanAccessSecret"] is False
    assert b["adminConsoleCanDisplaySecret"] is False
    assert b["backendMayReferenceMetadataOnly"] is True


def test_value_access_disabled() -> None:
    assert _b()["secretValueAccessEnabled"] is False
    assert _b()["productionSecretReadRequiresStoreProvider"] is True


def test_operators_and_platform_admin_and_break_glass_cannot_read() -> None:
    b = _b()
    assert b["operatorsCanViewSecretValues"] is False
    assert b["platformAdminCanReadSecretValues"] is False
    assert b["breakGlassRevealsSecretValues"] is False
