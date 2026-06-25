"""Step 54.4 -- threat category taxonomy."""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SEC = ROOT / "infra" / "security"

REQUIRED = {
    "spoofing",
    "tampering",
    "repudiation",
    "information_disclosure",
    "denial_of_service",
    "elevation_of_privilege",
    "prompt_injection",
    "tool_misuse",
    "agent_goal_drift",
    "supply_chain_compromise",
    "secret_leakage",
    "deployment_boundary_bypass",
    "audit_integrity_failure",
    "human_approval_bypass",
}


def _cats() -> list[dict]:
    data = yaml.safe_load((SEC / "threat-category-taxonomy.yaml").read_text(encoding="utf-8")) or {}
    return data["threatCategories"]["categories"]


def test_all_required_categories_present() -> None:
    ids = {c["id"] for c in _cats()}
    assert REQUIRED <= ids


def test_each_category_fully_specified() -> None:
    for c in _cats():
        for field in (
            "description",
            "affectedSurfaces",
            "defaultSeverity",
            "requiredMitigations",
            "productionBlocker",
            "evidenceRequirement",
        ):
            assert field in c, f"{c.get('id')} missing {field}"
        assert isinstance(c["productionBlocker"], bool)
