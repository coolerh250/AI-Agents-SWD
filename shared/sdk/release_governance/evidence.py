"""Step 60 -- release evidence package builder.

Assembles a redacted evidence summary referencing existing platform evidence. Missing
required evidence is reported (and blocks readiness). The package never contains a
secret / token / chain-of-thought, and never marks "production approved".
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from .redaction import redact

ROOT = Path(__file__).resolve().parents[3]
MODEL_YAML = ROOT / "infra" / "release" / "release-evidence-package-model.yaml"


@lru_cache(maxsize=1)
def _model() -> dict[str, Any]:
    data = yaml.safe_load(MODEL_YAML.read_text(encoding="utf-8")) or {}
    return data.get("releaseEvidencePackage", {}) or {}


def required_for_readiness() -> list[str]:
    return list(_model().get("requiredForReadiness", []) or [])


def build_evidence_summary(evidence: dict[str, Any] | None = None) -> dict[str, Any]:
    """Build a redacted evidence summary + list of missing required references."""
    evidence = evidence or {}
    refs = _model().get("references", []) or []
    summary: dict[str, Any] = {ref: evidence.get(ref) for ref in refs}
    missing = [ref for ref in required_for_readiness() if not evidence.get(ref)]
    return {
        "production_ready": False,
        "production_approved": False,
        "evidence": redact(summary),
        "missing_required": missing,
        "complete": not missing,
    }
