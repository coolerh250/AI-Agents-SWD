"""Step 51.2C2 -- backup artifact target isolation (no active-storage reuse)."""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
CHART = ROOT / "infra" / "kubernetes" / "charts" / "ai-agents-platform"
VALIDATE = CHART / "templates" / "validate-values.yaml"


def _v() -> dict:
    return yaml.safe_load((CHART / "values.yaml").read_text(encoding="utf-8"))


def test_target_disabled_placeholder() -> None:
    t = _v()["batchJobs"]["backup"]["target"]
    assert t["strategy"] == "disabled"
    assert t["existingClaim"] == ""
    assert t["externalObjectStoreEnabled"] is False


def test_target_not_active_datastore_pvc() -> None:
    t = _v()["batchJobs"]["backup"]["target"]
    assert t["existingClaim"] not in ("postgres-data", "redis-data")


def test_validate_blocks_active_pvc_reuse() -> None:
    raw = VALIDATE.read_text(encoding="utf-8")
    assert "backup target must not reuse an active datastore PVC" in raw


def test_validate_blocks_schedule_without_target() -> None:
    raw = VALIDATE.read_text(encoding="utf-8")
    assert "backup schedule cannot be enabled while the artifact target is disabled" in raw
