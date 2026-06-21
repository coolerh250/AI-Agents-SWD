"""Step 51.2C2 -- backup CronJob template + values."""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
CHART = ROOT / "infra" / "kubernetes" / "charts" / "ai-agents-platform"
TPL = CHART / "templates" / "backup-cronjob.yaml"


def _v() -> dict:
    return yaml.safe_load((CHART / "values.yaml").read_text(encoding="utf-8"))


def test_backup_disabled_and_suspended() -> None:
    b = _v()["batchJobs"]["backup"]
    assert b["renderTemplate"] is True
    assert b["scheduleEnabled"] is False
    assert b["suspend"] is True
    assert b["concurrencyPolicy"] == "Forbid"


def test_backup_history_and_deadlines() -> None:
    b = _v()["batchJobs"]["backup"]
    assert b["backoffLimit"] == 0
    assert b["activeDeadlineSeconds"] >= 1
    assert b["ttlSecondsAfterFinished"] >= 1
    assert b["successfulJobsHistoryLimit"] >= 0
    assert b["failedJobsHistoryLimit"] >= 0
    assert b["startingDeadlineSeconds"] >= 1


def test_template_suspend_and_concurrency() -> None:
    t = TPL.read_text(encoding="utf-8")
    assert "suspend: {{ $b.suspend }}" in t
    assert "concurrencyPolicy: {{ $b.concurrencyPolicy }}" in t


def test_render_gated_dev_test() -> None:
    t = TPL.read_text(encoding="utf-8")
    assert "$b.renderTemplate" in t
    assert 'has $env (list "dev" "test")' in t
