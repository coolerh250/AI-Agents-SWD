"""Step 55 -- Helm smoke runner + values guardrails."""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "scripts" / "run_nonproduction_helm_smoke.sh"
VALUES = (
    ROOT / "infra" / "kubernetes" / "charts" / "ai-agents-platform" / "values-nonprod-smoke.yaml"
)


def test_runner_has_guardrails() -> None:
    src = RUNNER.read_text(encoding="utf-8")
    for needle in (
        "--dry-run-only",
        "--namespace",
        "BLOCKED_NO_SAFE_CLUSTER",
        "forbidden namespace",
        "production substring",
        "Ingress",
        "LoadBalancer",
    ):
        assert needle in src, needle
    assert "argocd" in src.lower()


def test_values_disable_production() -> None:
    v = yaml.safe_load(VALUES.read_text(encoding="utf-8")) or {}
    assert v["global"]["production"] is False
    assert v["global"]["realDeployEnabled"] is False
    ac = v["platform"]["adminConsole"]
    assert ac["productionAuthEnabled"] is False
    assert ac["oidcEnabled"] is False
    integ = v["platform"]["integrations"]
    for k in ("githubWrite", "prCreation", "deployment", "realLlm", "externalDelivery"):
        assert integ[k] is False
