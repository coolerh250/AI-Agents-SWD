"""Step 52.4 -- combined identity foundation verifier wiring (source-level)."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMBINED = ROOT / "scripts" / "verify_identity_foundation_baseline.sh"


def test_combined_chains_all_step52_baselines() -> None:
    src = COMBINED.read_text(encoding="utf-8")
    for chained in (
        "verify_identity_auth_boundary_baseline.sh",
        "verify_oidc_disabled_production_baseline.sh",
        "verify_session_role_mapping_baseline.sh",
        "verify_identity_operations_visibility.py",
        "verify_admin_console_identity_posture.py",
        "verify_identity_safety_fields.py",
    ):
        assert chained in src


def test_combined_emits_final_marker() -> None:
    src = COMBINED.read_text(encoding="utf-8")
    assert "IDENTITY_FOUNDATION_BASELINE_VERIFY: PASS" in src
    assert "IDENTITY_FOUNDATION_BASELINE_VERIFY: FAIL" in src


def test_combined_checks_no_http_and_production_executed_zero() -> None:
    src = COMBINED.read_text(encoding="utf-8")
    assert "production_executed_true_count" in src
    assert "requests|httpx|aiohttp" in src


def test_all_three_verifier_scripts_exist() -> None:
    for name in (
        "verify_identity_operations_visibility.py",
        "verify_admin_console_identity_posture.py",
        "verify_identity_safety_fields.py",
    ):
        assert (ROOT / "scripts" / name).is_file()
