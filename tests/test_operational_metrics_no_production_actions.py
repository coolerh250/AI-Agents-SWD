"""Step 58 -- operational metrics expose no production action / mutation surface."""

from __future__ import annotations

from pathlib import Path

from shared.sdk.operations_metrics import operational_metrics_safety_fields

ROOT = Path(__file__).resolve().parents[1]
API = ROOT / "apps" / "orchestrator" / "src" / "operational_metrics_api.py"
AGG = ROOT / "shared" / "sdk" / "operations_metrics" / "aggregator.py"
COLLECTORS = ROOT / "shared" / "sdk" / "operations_metrics" / "collectors.py"


def test_safety_fields_no_production_action() -> None:
    f = operational_metrics_safety_fields()
    assert f["operational_metrics_production_action_enabled"] is False
    assert f["operational_metrics_production_ready"] is False


def test_api_has_no_mutation_surface() -> None:
    src = API.read_text(encoding="utf-8")
    for verb in ("@router.post", "@router.put", "@router.patch", "@router.delete"):
        assert verb not in src


def test_aggregator_collectors_do_not_mutate_or_sync() -> None:
    agg = AGG.read_text(encoding="utf-8")
    col = COLLECTORS.read_text(encoding="utf-8")
    for forbidden in (
        "kubectl",
        "helm ",
        "argocd app sync",
        "git push",
        "INSERT ",
        "UPDATE ",
        "DELETE ",
    ):
        assert forbidden not in agg, forbidden
        assert forbidden not in col, forbidden
