"""Step 54.4 -- threat model baseline."""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SEC = ROOT / "infra" / "security"


def _load(name: str) -> dict:
    return yaml.safe_load((SEC / name).read_text(encoding="utf-8")) or {}


def _tm() -> dict:
    return _load("threat-model-baseline.yaml")["threatModel"]


def test_status_not_production_enforced() -> None:
    tm = _tm()
    assert tm["status"] == "modeled_not_production_enforced"
    assert tm["productionReady"] is False


def test_methodology_covers_stride_agentic_supply() -> None:
    method = set(_tm()["methodology"])
    assert {"stride_inspired", "agentic_ai_specific", "supply_chain_specific"} <= method


def test_required_assets_and_flows_present() -> None:
    tm = _tm()
    assets = {a["id"] for a in tm["assets"]}
    for required in (
        "admin_console",
        "operator_actions",
        "identity_oidc",
        "secret_management",
        "audit_integrity",
        "workspace_operator",
        "agent_execution_pipeline",
        "future_production_deployment",
        "llm_integration",
    ):
        assert required in assets
    for field in ("trustBoundaries", "entrypoints", "dataFlows", "mitigations", "blockers"):
        assert tm[field]


def test_threats_reference_taxonomy_categories() -> None:
    cats = {
        c["id"] for c in _load("threat-category-taxonomy.yaml")["threatCategories"]["categories"]
    }
    threats = _tm()["threats"]
    assert threats
    assert all(t["category"] in cats for t in threats)


def test_no_production_approval_language() -> None:
    blob = str(_tm()).lower()
    assert "production_ready" not in blob
    assert "production_approved" not in blob
