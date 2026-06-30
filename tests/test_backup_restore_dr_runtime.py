"""Step 61 -- backup / restore / DR runtime generators (offline, no deletion)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / ".runtime" / "backup-dr"


def _run(script: str) -> None:
    subprocess.run([sys.executable, str(ROOT / "scripts" / script)], check=True, cwd=ROOT)


def test_generators_produce_safe_artifacts() -> None:
    _run("generate_backup_dr_runtime_inventory.py")
    _run("generate_controlled_cleanup_review.py")

    inv = json.loads((BASE / "backup-dr-runtime-inventory.json").read_text(encoding="utf-8"))
    assert inv["contains_secret"] is False
    assert inv["contains_raw_dump_body"] is False
    assert inv["production_executed"] is False

    cln = json.loads((BASE / "controlled-cleanup-review.json").read_text(encoding="utf-8"))
    assert cln["cleanup_executed"] is False


def test_restore_validation_no_active_mutation() -> None:
    _run("run_nonproduction_restore_validation.py")
    val = json.loads(
        (BASE / "nonproduction-restore-validation-result.json").read_text(encoding="utf-8")
    )
    for k in (
        "active_database_overwritten",
        "active_redis_overwritten",
        "argocd_sync_performed",
        "kind_cluster_mutated",
        "production_executed",
    ):
        assert val[k] is False
