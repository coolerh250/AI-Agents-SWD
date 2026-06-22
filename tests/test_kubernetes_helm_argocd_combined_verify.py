"""Step 51.4 -- combined Step 51 verification script wiring."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMBINED = ROOT / "scripts" / "verify_kubernetes_helm_argocd_baseline.sh"


def _t() -> str:
    return COMBINED.read_text(encoding="utf-8")


def test_combined_script_exists() -> None:
    assert COMBINED.is_file()


def test_chains_gitops_baseline_and_runtime_verifiers() -> None:
    t = _t()
    assert "verify_gitops_argocd_baseline.sh" in t
    assert "verify_runtime_operations_visibility.py" in t
    assert "verify_runtime_safety_fields.py" in t
    assert "verify_admin_console_runtime_baseline.py" in t


def test_final_marker_and_no_mutation() -> None:
    t = _t()
    assert "KUBERNETES_HELM_ARGOCD_BASELINE_VERIFY: PASS" in t
    assert "production_executed_true_count" in t


def test_referenced_verifiers_exist() -> None:
    for s in (
        "verify_gitops_argocd_baseline.sh",
        "verify_runtime_operations_visibility.py",
        "verify_runtime_safety_fields.py",
        "verify_admin_console_runtime_baseline.py",
    ):
        assert (ROOT / "scripts" / s).is_file(), s
