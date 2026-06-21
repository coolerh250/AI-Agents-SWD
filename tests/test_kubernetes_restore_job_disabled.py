"""Step 51.2C2 -- restore Job disabled in all standard environments."""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
CHART = ROOT / "infra" / "kubernetes" / "charts" / "ai-agents-platform"

ENV_FILES = [
    "values.yaml",
    "values-dev.yaml",
    "values-test.yaml",
    "values-staging-placeholder.yaml",
    "values-prod-placeholder.yaml",
]


def _restore(name: str) -> dict | None:
    data = yaml.safe_load((CHART / name).read_text(encoding="utf-8")) or {}
    return (data.get("batchJobs") or {}).get("restore")


def test_restore_not_rendered_in_standard_values() -> None:
    for f in ENV_FILES:
        r = _restore(f)
        if r is not None and "renderTemplate" in r:
            assert r["renderTemplate"] is False, f


def test_restore_execution_disabled() -> None:
    for f in ENV_FILES:
        r = _restore(f)
        if r is not None and "executionEnabled" in r:
            assert r["executionEnabled"] is False, f


def test_only_fixture_enables_render() -> None:
    fix = yaml.safe_load(
        (
            ROOT / "infra" / "kubernetes" / "fixtures" / "batch-restore-scaffold-fixture.yaml"
        ).read_text("utf-8")
    )
    assert fix["batchJobs"]["restore"]["renderTemplate"] is True
    assert fix["batchJobs"]["restore"]["executionEnabled"] is False
