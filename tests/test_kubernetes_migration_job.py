"""Step 51.2C2 -- migration Job template + values."""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
CHART = ROOT / "infra" / "kubernetes" / "charts" / "ai-agents-platform"
TPL = CHART / "templates" / "migration-job.yaml"


def _v() -> dict:
    return yaml.safe_load((CHART / "values.yaml").read_text(encoding="utf-8"))


def _t() -> str:
    return TPL.read_text(encoding="utf-8")


def test_render_gated_dev_test() -> None:
    t = _t()
    assert "$m.renderTemplate" in t
    assert 'has $env (list "dev" "test")' in t


def test_fixed_command_via_helper() -> None:
    assert 'aiagents.batch.command" (dict "root" $root "commandKey" $m.commandKey)' in _t()
    assert _v()["batchCommands"]["migration"]["args"] == ["scripts/k8s_apply_migrations.py"]


def test_values_baseline() -> None:
    m = _v()["batchJobs"]["migration"]
    assert m["renderTemplate"] is True
    assert m["executionEnabled"] is False
    assert m["backoffLimit"] == 0
    assert m["activeDeadlineSeconds"] >= 1
    assert m["ttlSecondsAfterFinished"] >= 1
    assert m["commandKey"] == "migration"


def test_database_url_secret_keyref_only() -> None:
    t = _t()
    assert "secretKeyRef" in t
    assert "valueFrom" in t
    # no inline DATABASE_URL value assignment
    assert "DATABASE_URL: postgresql://" not in t


def test_restart_policy_never_and_automount_off() -> None:
    t = _t()
    assert "restartPolicy: Never" in t
    assert "automountServiceAccountToken: false" in t
