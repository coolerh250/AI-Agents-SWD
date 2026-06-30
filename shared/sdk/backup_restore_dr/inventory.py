"""Step 61 -- backup target inventory loading.

Reads the committed backup target inventory -- declarative, secret-free governance metadata
(names / classifications / boolean handling flags). Every target reports
restore_allowed_production=false. The inventory carries no secret, token, kubeconfig, raw
dump, or customer data, so it is returned as-is (the handling flags such as
``contains_secret`` are intentionally preserved, not redacted away).
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[3]
INVENTORY_YAML = ROOT / "infra" / "dr" / "backup-target-inventory.yaml"


@lru_cache(maxsize=1)
def load_targets() -> list[dict[str, Any]]:
    data = yaml.safe_load(INVENTORY_YAML.read_text(encoding="utf-8")) or {}
    return list(data.get("backupTargets", []) or [])


def production_restore_allowed_count() -> int:
    return sum(1 for t in load_targets() if t.get("restore_allowed_production"))


def secret_bearing_backup_count() -> int:
    """Targets flagged contains_secret AND backup_allowed (must be 0)."""
    return sum(1 for t in load_targets() if t.get("contains_secret") and t.get("backup_allowed"))
