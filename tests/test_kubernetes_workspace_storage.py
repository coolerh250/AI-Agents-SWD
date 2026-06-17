"""Step 51.2C1 -- workspace storage model (ephemeral, not faked durable)."""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
CHART = ROOT / "infra" / "kubernetes" / "charts" / "ai-agents-platform"
CAT = ROOT / "infra" / "kubernetes" / "storage-ownership-catalog.yaml"

WORKSPACE_AGENTS = (
    "development-agent",
    "qa-agent",
    "workspace-operator-agent",
    "mini-delivery-pilot-agent",
)


def _v(name: str = "values.yaml") -> dict:
    return yaml.safe_load((CHART / name).read_text(encoding="utf-8"))


def _store() -> dict:
    return yaml.safe_load(CAT.read_text(encoding="utf-8"))["stores"]["workspace-scratch"]


def test_workspace_values_ephemeral() -> None:
    ws = _v()["storage"]["workspace"]
    assert ws["strategy"] == "ephemeralEmptyDir"
    assert ws["persistenceEnabled"] is False
    assert ws["existingClaim"] == ""
    assert ws["productionConfigured"] is False


def test_workspace_not_shared_filesystem() -> None:
    s = _store()
    assert s["sharedFilesystem"] is False
    assert s["multiWriter"] is False
    assert s["persistenceSolved"] is False


def test_workspace_agents_keep_ephemeral_tmp() -> None:
    comps = _v()["components"]
    for n in WORKSPACE_AGENTS:
        paths = {w["mountPath"] for w in comps[n]["security"]["writablePaths"]}
        assert "/tmp" in paths, n


def test_workspace_persistence_disabled_all_envs() -> None:
    for f in ("values-staging-placeholder.yaml", "values-prod-placeholder.yaml"):
        ws = _v(f)["storage"]["workspace"]
        assert ws["strategy"] == "ephemeralEmptyDir"
        assert ws["persistenceEnabled"] is False
        assert ws["productionConfigured"] is False
