"""Step 55 -- non-production runtime smoke /operations/safety fields (SDK level)."""

from __future__ import annotations

from pathlib import Path

from shared.sdk.runtime_smoke import nonprod_runtime_safety_fields

ROOT = Path(__file__).resolve().parents[1]

EXPECT_FALSE = [
    "nonprod_cluster_access_detected",
    "nonprod_cluster_context_safe",
    "nonprod_helm_install_attempted",
    "nonprod_helm_install_succeeded",
    "nonprod_pods_running",
    "nonprod_service_health_passed",
    "nonprod_connectivity_passed",
    "nonprod_networkpolicy_passed",
    "nonprod_storage_passed",
    "nonprod_securitycontext_passed",
    "nonprod_batch_job_smoke_passed",
    "nonprod_runtime_smoke_report_generated",
    "nonprod_runtime_smoke_production_ready",
    "kubernetes_production_deploy_performed",
    "argocd_sync_performed",
]


def _f(tmp_path) -> dict:
    empty = tmp_path / "k"
    empty.mkdir()
    return nonprod_runtime_safety_fields(ROOT, runtime_dir=empty)


def test_smoke_enabled_true(tmp_path) -> None:
    assert _f(tmp_path)["nonprod_kubernetes_smoke_enabled"] is True


def test_blocked_defaults_all_false(tmp_path) -> None:
    f = _f(tmp_path)
    for k in EXPECT_FALSE:
        assert f[k] is False, k


def test_namespace_non_production(tmp_path) -> None:
    assert "prod" not in str(_f(tmp_path)["nonprod_namespace"]).lower()
