"""Step 51.2C2 -- no batch job is executed (gated entrypoints, disabled values)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
CHART = ROOT / "infra" / "kubernetes" / "charts" / "ai-agents-platform"
SCRIPTS = ROOT / "scripts"
WRAPPERS = ["k8s_apply_migrations.py", "k8s_encrypted_backup.py", "k8s_restore_drill.py"]


def _v() -> dict:
    return yaml.safe_load((CHART / "values.yaml").read_text(encoding="utf-8"))


def test_all_execution_flags_false() -> None:
    bj = _v()["batchJobs"]
    assert bj["migration"]["executionEnabled"] is False
    assert bj["backup"]["scheduleEnabled"] is False
    assert bj["restore"]["executionEnabled"] is False


def test_wrappers_gate_on_execute_env() -> None:
    for w in WRAPPERS:
        src = (SCRIPTS / w).read_text(encoding="utf-8")
        assert "AIAGENTS_BATCH_EXECUTE" in src, w


def test_wrappers_baseline_run_no_db(tmp_path: Path) -> None:
    # gate off (default) -> wrappers print a plan and exit 0 without DB work
    for w in WRAPPERS:
        res = subprocess.run(
            [sys.executable, str(SCRIPTS / w)],
            capture_output=True,
            text=True,
            cwd=str(ROOT),
        )
        assert res.returncode == 0, f"{w}: {res.stderr}"
        assert "baseline" in res.stdout.lower() or "no " in res.stdout.lower(), w
