"""Step 51.2C2 -- per-environment batch job render rules."""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
CHART = ROOT / "infra" / "kubernetes" / "charts" / "ai-agents-platform"


def _merged(env_file: str) -> dict:
    base = yaml.safe_load((CHART / "values.yaml").read_text(encoding="utf-8"))
    over = yaml.safe_load((CHART / env_file).read_text(encoding="utf-8"))

    def merge(a: dict, b: dict) -> dict:
        out = dict(a)
        for k, v in (b or {}).items():
            out[k] = merge(a[k], v) if isinstance(v, dict) and isinstance(a.get(k), dict) else v
        return out

    return merge(base, over)


def test_dev_test_render_migration_backup_not_restore() -> None:
    for f in ("values-dev.yaml", "values-test.yaml"):
        bj = _merged(f)["batchJobs"]
        assert bj["migration"]["renderTemplate"] is True
        assert bj["backup"]["renderTemplate"] is True
        assert bj["restore"]["renderTemplate"] is False
        assert bj["migration"]["executionEnabled"] is False
        assert bj["backup"]["scheduleEnabled"] is False


def test_staging_prod_all_disabled() -> None:
    for f in ("values-staging-placeholder.yaml", "values-prod-placeholder.yaml"):
        bj = _merged(f)["batchJobs"]
        assert bj["migration"]["renderTemplate"] is False
        assert bj["backup"]["renderTemplate"] is False
        assert bj["restore"]["renderTemplate"] is False
        assert bj["migration"]["executionEnabled"] is False
        assert bj["backup"]["scheduleEnabled"] is False
        assert bj["restore"]["executionEnabled"] is False
