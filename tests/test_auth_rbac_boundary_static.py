"""Step 52.1 -- static auth/RBAC boundary over actual code."""

from __future__ import annotations

from pathlib import Path

from shared.sdk.operator_actions.action_catalog import ENABLED_ACTIONS
from shared.sdk.operator_actions.auth import resolve_auth_config
from shared.sdk.operator_actions.rbac import ROLE_RANK, role_can

ROOT = Path(__file__).resolve().parents[1]
RUNTIME_API = ROOT / "apps" / "orchestrator" / "src" / "runtime_baseline_api.py"


def test_default_auth_disabled() -> None:
    cfg = resolve_auth_config({})
    assert cfg.auth_mode == "disabled"
    assert cfg.operator_actions_enabled is False


def test_test_local_requires_full_gate() -> None:
    cfg = resolve_auth_config(
        {
            "ADMIN_CONSOLE_AUTH_MODE": "test_local_signed_session",
            "ADMIN_CONSOLE_TEST_AUTH_ENABLED": "true",
            "ENABLE_ADMIN_CONSOLE_OPERATOR_ACTIONS": "true",
        }
    )
    assert cfg.operator_actions_enabled is True
    # production flag forces it off
    cfg2 = resolve_auth_config(
        {
            "ADMIN_CONSOLE_AUTH_MODE": "test_local_signed_session",
            "ADMIN_CONSOLE_TEST_AUTH_ENABLED": "true",
            "ADMIN_CONSOLE_PRODUCTION_AUTH_ENABLED": "true",
            "ENABLE_ADMIN_CONSOLE_OPERATOR_ACTIONS": "true",
        }
    )
    assert cfg2.operator_actions_enabled is False


def test_platform_admin_equals_operator_rank() -> None:
    assert ROLE_RANK["platform_admin"] == ROLE_RANK["operator"]


def test_no_enabled_action_is_infrastructure() -> None:
    for a in ENABLED_ACTIONS:
        assert not any(s in a for s in ("deploy", "github", "argocd", "kubernetes", "merge"))
        # viewer can never perform it
        assert role_can("viewer", a) is False


def test_runtime_api_read_only() -> None:
    src = RUNTIME_API.read_text(encoding="utf-8")
    for verb in ("@router.post", "@router.put", "@router.patch", "@router.delete"):
        assert verb not in src
