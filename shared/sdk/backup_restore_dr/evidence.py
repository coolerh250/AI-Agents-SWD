"""Step 61 -- recovery evidence package builder.

Assembles a redacted recovery evidence package referencing existing platform evidence.
Missing required evidence is reported (and blocks DR readiness). The package never contains
a secret / raw DB dump / raw Redis dump / kubeconfig / token / chain-of-thought, and
production_ready / production_restore_ready are always false.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from .redaction import redact

ROOT = Path(__file__).resolve().parents[3]
MODEL_YAML = ROOT / "infra" / "dr" / "recovery-evidence-package-model.yaml"


@lru_cache(maxsize=1)
def _model() -> dict[str, Any]:
    data = yaml.safe_load(MODEL_YAML.read_text(encoding="utf-8")) or {}
    return data.get("recoveryEvidencePackage", {}) or {}


def required_for_readiness() -> list[str]:
    return list(_model().get("requiredForReadiness", []) or [])


def build_recovery_evidence(evidence: dict[str, Any] | None = None) -> dict[str, Any]:
    """Build a redacted recovery evidence package + list of missing required references."""
    evidence = evidence or {}
    refs = _model().get("references", []) or []
    summary: dict[str, Any] = {ref: evidence.get(ref) for ref in refs}
    missing = [ref for ref in required_for_readiness() if not evidence.get(ref)]
    return {
        "production_ready": False,
        "production_restore_ready": False,
        "evidence": redact(summary),
        "missing_required": missing,
        "complete": not missing,
        "production_blocking_status": {
            "production_restore_blocked": True,
            "production_failover_blocked": True,
        },
    }
