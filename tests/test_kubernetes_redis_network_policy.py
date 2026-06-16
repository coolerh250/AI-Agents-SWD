"""Step 51.2B -- Redis connectivity isolation."""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
CHART = ROOT / "infra" / "kubernetes" / "charts" / "ai-agents-platform"
CATALOG = ROOT / "infra" / "kubernetes" / "network-connectivity-catalog.yaml"


def _values() -> dict:
    return yaml.safe_load((CHART / "values.yaml").read_text(encoding="utf-8"))


def _cat() -> dict:
    return yaml.safe_load(CATALOG.read_text(encoding="utf-8"))


def test_redis_allowed_sources_exact() -> None:
    edges = _values()["networkPolicy"]["internalEdges"]
    want = sorted({e["source"] for e in edges if e["target"] == "redis"})
    got = sorted(_cat()["infrastructure"]["redis"]["allowedSources"])
    assert want == got
    assert len(got) == 19, len(got)


def test_redis_port_and_no_external_exposure() -> None:
    rd = _cat()["infrastructure"]["redis"]
    assert rd["port"] == 6379
    assert rd["externalExposureAllowed"] is False


def test_redis_service_is_clusterip() -> None:
    comp = _values()["components"]["redis"]
    assert comp["service"]["port"] == 6379


def test_redis_edges_are_infra_dev_test_only() -> None:
    for e in _cat()["internalEdges"]:
        if e["target"] == "redis":
            assert e["infra"] is True
            assert set(e["environments"]) == {"dev", "test"}


def test_external_redis_disabled_no_cidr() -> None:
    rd = _values()["externalDataServices"]["redis"]
    assert rd["enabled"] is False
    assert rd["cidrs"] == []
