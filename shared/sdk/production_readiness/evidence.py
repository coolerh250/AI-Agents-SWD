"""Step 62 -- readiness evidence inventory loading.

Reads the committed evidence inventory. Every item is non-production scope at this stage;
the inventory carries no secret. Missing evidence is never reported as clean.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[3]
INVENTORY_YAML = ROOT / "infra" / "readiness" / "readiness-evidence-inventory.yaml"


@lru_cache(maxsize=1)
def load_evidence() -> list[dict[str, Any]]:
    data = yaml.safe_load(INVENTORY_YAML.read_text(encoding="utf-8")) or {}
    return data.get("readinessEvidence", {}).get("items", []) or []


def production_scope_count() -> int:
    """Evidence items claiming production scope (must be 0 this stage)."""
    return sum(1 for e in load_evidence() if e.get("production_scope"))
