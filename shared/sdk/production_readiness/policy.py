"""Step 62 -- production readiness gate policy loading.

Policy values read straight from the committed YAML so the dangerous toggles (production
deploy / sync / restore / failover / merge / image push / auto-promotion) and
productionReady / currentStageAllowsProductionAction cannot silently drift true in code.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[3]
POLICY_YAML = ROOT / "infra" / "readiness" / "production-readiness-gate-policy.yaml"


@lru_cache(maxsize=1)
def load_policy() -> dict[str, Any]:
    data = yaml.safe_load(POLICY_YAML.read_text(encoding="utf-8")) or {}
    return data.get("productionReadinessGate", {}) or {}


def allows_production_action() -> bool:
    return bool(load_policy().get("currentStageAllowsProductionAction", False))
