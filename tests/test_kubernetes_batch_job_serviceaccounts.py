"""Step 51.2C2 -- batch job ServiceAccounts (token off, no RBAC)."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHART = ROOT / "infra" / "kubernetes" / "charts" / "ai-agents-platform"
SA_TPL = CHART / "templates" / "serviceaccounts.yaml"
TEMPLATES = CHART / "templates"


def test_batch_sa_created_token_off() -> None:
    t = SA_TPL.read_text(encoding="utf-8")
    assert "-{{ $job }}-job" in t
    assert "automountServiceAccountToken: false" in t


def test_batch_sa_gated_dev_test() -> None:
    t = SA_TPL.read_text(encoding="utf-8")
    assert 'has $env (list "dev" "test")' in t
    assert "$bj.serviceAccounts.create" in t


def test_no_rbac_objects_in_chart() -> None:
    for p in TEMPLATES.glob("*.yaml"):
        raw = p.read_text(encoding="utf-8")
        for kind in (
            "kind: Role",
            "kind: ClusterRole",
            "kind: RoleBinding",
            "kind: ClusterRoleBinding",
        ):
            assert kind not in raw, f"{p.name}: {kind}"


def test_jobs_reference_dedicated_sa() -> None:
    for name, job in (
        ("migration-job.yaml", "migration"),
        ("backup-cronjob.yaml", "backup"),
        ("restore-job.yaml", "restore"),
    ):
        t = (TEMPLATES / name).read_text(encoding="utf-8")
        assert f"-{job}-job" in t, name
