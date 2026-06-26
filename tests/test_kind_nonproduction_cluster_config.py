"""Step 55.1 -- kind non-production cluster definition."""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
CFG = ROOT / "infra" / "kubernetes" / "kind" / "nonproduction-kind-cluster.yaml"


def test_cluster_name_is_non_production() -> None:
    cfg = yaml.safe_load(CFG.read_text(encoding="utf-8"))
    assert cfg["name"] == "aiagents-smoke"
    assert "prod" not in cfg["name"].lower()


def test_local_only_no_public_exposure() -> None:
    raw = CFG.read_text(encoding="utf-8")
    # No host port mappings / ingress-ready / LoadBalancer: local-only smoke.
    assert "extraPortMappings" not in raw
    assert "ingress-ready" not in raw
    assert "LoadBalancer" not in raw


def test_single_control_plane_node() -> None:
    cfg = yaml.safe_load(CFG.read_text(encoding="utf-8"))
    assert [n["role"] for n in cfg["nodes"]] == ["control-plane"]
