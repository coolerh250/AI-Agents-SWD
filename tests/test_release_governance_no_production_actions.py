"""Step 60 -- release governance performs no production / deploy / sync / merge action."""

from __future__ import annotations

from pathlib import Path

from shared.sdk.release_governance import release_governance_safety_fields

ROOT = Path(__file__).resolve().parents[1]
SDK = ROOT / "shared" / "sdk" / "release_governance"
API = (ROOT / "apps" / "orchestrator" / "src" / "release_governance_api.py").read_text(
    encoding="utf-8"
)
SDK_SRC = "\n".join(p.read_text(encoding="utf-8") for p in SDK.glob("*.py"))


def test_sdk_and_api_have_no_deploy_or_cluster_calls() -> None:
    # Real execution paths only. Safety field NAMES (argocd/production) and the read-only
    # ``WHERE production_executed=true`` count guard legitimately assert the action did
    # NOT happen, so they are not flagged here -- only an actual *set to True* would be.
    for blob in (SDK_SRC, API):
        for forbidden in (
            "kubectl ",
            "helm install",
            "argocd app sync",
            "subprocess",
            "docker push",
        ):
            assert forbidden not in blob
        assert '"production_executed": True' not in blob
        assert "production_executed=True" not in blob


def test_safety_posture_production_blocked() -> None:
    f = release_governance_safety_fields()
    assert f["release_governance_production_ready"] is False
    assert f["release_governance_allow_production_deploy"] is False
    assert f["deployment_intent_production_executed_count"] == 0
