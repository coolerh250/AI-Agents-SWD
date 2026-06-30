"""Step 62 -- production readiness checklist loading.

Reads the committed checklist model. No category may ever produce a production approval
(production_ready_claim_allowed is false everywhere).
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[3]
MODEL_YAML = ROOT / "infra" / "readiness" / "production-readiness-checklist-model.yaml"


@lru_cache(maxsize=1)
def load_categories() -> list[dict[str, Any]]:
    data = yaml.safe_load(MODEL_YAML.read_text(encoding="utf-8")) or {}
    return data.get("productionReadinessChecklist", {}).get("categories", []) or []


def production_ready_claim_count() -> int:
    """Categories that (wrongly) allow a production-ready claim (must be 0)."""
    return sum(1 for c in load_categories() if c.get("production_ready_claim_allowed"))


def required_categories() -> list[dict[str, Any]]:
    return [c for c in load_categories() if c.get("required")]
