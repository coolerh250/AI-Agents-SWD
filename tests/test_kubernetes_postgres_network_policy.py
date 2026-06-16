"""Step 51.2B -- Postgres connectivity isolation."""

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


def test_postgres_allowed_sources_exact() -> None:
    edges = _values()["networkPolicy"]["internalEdges"]
    want = sorted({e["source"] for e in edges if e["target"] == "postgres"})
    got = sorted(_cat()["infrastructure"]["postgres"]["allowedSources"])
    assert want == got
    assert len(got) == 18, len(got)


def test_postgres_port_and_no_external_exposure() -> None:
    pg = _cat()["infrastructure"]["postgres"]
    assert pg["port"] == 5432
    assert pg["externalExposureAllowed"] is False


def test_postgres_service_is_clusterip() -> None:
    comp = _values()["components"]["postgres"]
    assert comp["service"]["port"] == 5432
    # services template renders ClusterIP only (asserted in services-internal test)


def test_postgres_edges_are_infra_dev_test_only() -> None:
    cat = _cat()["internalEdges"]
    for e in cat:
        if e["target"] == "postgres":
            assert e["infra"] is True
            assert set(e["environments"]) == {"dev", "test"}


def test_external_postgres_disabled_no_cidr() -> None:
    pg = _values()["externalDataServices"]["postgres"]
    assert pg["enabled"] is False
    assert pg["cidrs"] == []
