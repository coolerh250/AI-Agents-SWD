"""Step 63A -- controlled rollout risk register."""

from __future__ import annotations

from shared.sdk.controlled_rollout import loaders


def test_required_risks_present() -> None:
    names = {r["name"] for r in loaders.load("risk_register").get("risks", [])}
    for required in (
        "production_target_absent",
        "production_credentials_absent",
        "production_gitops_absent",
        "operator_approval_missing",
    ):
        assert required in names


def test_each_risk_has_required_fields() -> None:
    fields = {"severity", "likelihood", "mitigation", "decision_impact"}
    for r in loaders.load("risk_register").get("risks", []):
        assert fields <= set(r.keys())
        assert r["decision_impact"] in ("go", "conditional_go", "no_go")


def test_has_no_go_risk() -> None:
    risks = loaders.load("risk_register").get("risks", [])
    assert any(r["decision_impact"] == "no_go" for r in risks)
