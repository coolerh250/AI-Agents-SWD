"""Step 62 -- production environment prerequisite loading.

The production environment does not exist yet; prerequisites are missing / not_configured.
A kind non-production cluster is never substituted for production.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[3]
MODEL_YAML = ROOT / "infra" / "readiness" / "production-environment-prerequisite-model.yaml"

_SATISFIED = {"configured", "defined", "assigned", "tested", "ready", "available"}


@lru_cache(maxsize=1)
def _model() -> dict[str, Any]:
    data = yaml.safe_load(MODEL_YAML.read_text(encoding="utf-8")) or {}
    return data.get("productionEnvironmentPrerequisites", {}) or {}


def load_prerequisites() -> list[dict[str, Any]]:
    return _model().get("prerequisites", []) or []


def missing_prerequisites() -> list[str]:
    return [p["name"] for p in load_prerequisites() if p.get("status") not in _SATISFIED]


def production_environment_exists() -> bool:
    return bool(_model().get("productionEnvironmentExists", False))
