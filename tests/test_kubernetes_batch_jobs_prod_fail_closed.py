"""Step 51.2C2 -- production/staging batch fail-closed enforcement."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VALIDATE = (
    ROOT
    / "infra"
    / "kubernetes"
    / "charts"
    / "ai-agents-platform"
    / "templates"
    / "validate-values.yaml"
)


def _t() -> str:
    return VALIDATE.read_text(encoding="utf-8")


def test_blocks_render_in_staging_prod() -> None:
    t = _t()
    assert "must not render a migration Job" in t
    assert "must not render a backup CronJob" in t
    assert "must not render a restore Job" in t


def test_blocks_execution_gates() -> None:
    t = _t()
    assert "migration.executionEnabled must be false" in t
    assert "backup.scheduleEnabled must be false" in t
    assert "backup CronJob must be suspended" in t
    assert "restore.executionEnabled must be false" in t


def test_blocks_concurrency_and_backoff() -> None:
    t = _t()
    assert "backup concurrencyPolicy must be Forbid" in t
    assert "backoffLimit must be 0" in t


def test_blocks_shell_constructs() -> None:
    t = _t()
    assert "args must not contain shell constructs" in t
    assert "shell must be false" in t
