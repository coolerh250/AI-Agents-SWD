"""Step 52.3 -- no secret/token-shaped value + no real group IDs in the surface."""

from __future__ import annotations

import re
from pathlib import Path

from shared.sdk.identity import find_secret_like

ROOT = Path(__file__).resolve().parents[1]
IDENT = ROOT / "infra" / "identity"
SDK_DIR = ROOT / "shared" / "sdk" / "identity"

_STEP_523_YAML = [
    "session-hardening-catalog.yaml",
    "session-concurrency-policy.yaml",
    "forced-logout-model.yaml",
    "session-key-rotation-model.yaml",
    "role-mapping-policy.yaml",
    "unknown-user-policy.yaml",
    "break-glass-model.yaml",
    "identity-authorization-decision-model.yaml",
    "test-fixtures/role-mapping-safe-fixture.yaml",
]
# 8-4-4-4-12 hex GUID (Entra tenant / group object ID shape).
_GUID = re.compile(
    r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"
)


def test_step_523_yaml_no_secret_like() -> None:
    for rel in _STEP_523_YAML:
        text = (IDENT / rel).read_text(encoding="utf-8")
        assert find_secret_like(text) == [], rel


def test_new_sdk_modules_no_secret_like() -> None:
    for name in (
        "role_mapping.py",
        "role_mapping_models.py",
        "session_cleanup.py",
        "identity_runtime_config.py",
    ):
        text = (SDK_DIR / name).read_text(encoding="utf-8")
        assert find_secret_like(text) == [], name


def test_no_real_group_ids_in_fixture() -> None:
    text = (IDENT / "test-fixtures" / "role-mapping-safe-fixture.yaml").read_text(encoding="utf-8")
    assert _GUID.search(text) is None
    # every group is a documented placeholder
    for line in text.splitlines():
        if "matchGroup" in line:
            assert "placeholder" in line
