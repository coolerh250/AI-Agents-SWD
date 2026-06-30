"""Step 61 -- backup artifact classification loading.

Reads the committed artifact classification. Exposes per-class retention / cleanup /
commit / secret-scan flags. database_dump and redis_snapshot are never commit-allowed.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[3]
CLASSIFICATION_YAML = ROOT / "infra" / "dr" / "backup-artifact-classification.yaml"


@lru_cache(maxsize=1)
def load_classes() -> dict[str, dict[str, Any]]:
    data = yaml.safe_load(CLASSIFICATION_YAML.read_text(encoding="utf-8")) or {}
    return data.get("backupArtifactClassification", {}).get("classes", {}) or {}


def get_class(classification: str) -> dict[str, Any]:
    return load_classes().get(classification, {})


def commit_allowed(classification: str) -> bool:
    return bool(get_class(classification).get("commit_allowed", False))


def committable_dump_count() -> int:
    """database_dump / redis_snapshot classes that are (wrongly) commit-allowed (must be 0)."""
    classes = load_classes()
    return sum(
        1
        for name in ("database_dump", "redis_snapshot")
        if classes.get(name, {}).get("commit_allowed", False)
    )
