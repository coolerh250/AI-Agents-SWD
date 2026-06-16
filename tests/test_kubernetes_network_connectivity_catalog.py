"""Step 51.2B -- connectivity catalog completeness + matrix consistency."""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
MATRIX = ROOT / "infra" / "kubernetes" / "runtime-dependency-matrix.yaml"
CATALOG = ROOT / "infra" / "kubernetes" / "network-connectivity-catalog.yaml"

OBS_T = {"tempo", "prometheus", "grafana", "alertmanager"}
OBS_S = {"prometheus", "grafana", "alertmanager"}


def _load(p: Path) -> dict:
    return yaml.safe_load(p.read_text(encoding="utf-8"))


def _internal(deps: list[dict]) -> list[dict]:
    return [e for e in deps if e["target"] not in OBS_T and e["source"] not in OBS_S]


def test_catalog_matches_matrix_internal_edges() -> None:
    matrix = _load(MATRIX)["dependencies"]
    internal = _internal(matrix)
    cat = _load(CATALOG)["internalEdges"]
    mk = {(e["source"], e["target"], e["port"]) for e in internal}
    ck = {(e["source"], e["target"], e["port"]) for e in cat}
    assert mk == ck, mk ^ ck
    assert len(cat) == 49, len(cat)


def test_external_dependencies_all_disabled() -> None:
    for d in _load(CATALOG)["externalDependencies"]:
        assert d["enabled"] is False, d
        assert d["policyGenerated"] is False, d


def test_infra_allowed_sources_match_matrix() -> None:
    matrix = _internal(_load(MATRIX)["dependencies"])
    cat = _load(CATALOG)["infrastructure"]
    for infra in ("postgres", "redis"):
        want = sorted({e["source"] for e in matrix if e["target"] == infra})
        assert sorted(cat[infra]["allowedSources"]) == want, infra
        assert cat[infra]["externalExposureAllowed"] is False


def test_catalog_has_no_real_endpoint() -> None:
    raw = CATALOG.read_text(encoding="utf-8")
    for pat in ("0.0.0.0/0", "::/0", "https://", "http://", "amazonaws", "googleapis"):
        assert pat not in raw, pat


def test_observability_deferred() -> None:
    obs = _load(CATALOG)["deferred"]["observability"]
    assert obs["prometheusScrape"] is False
    assert obs["otlpExport"] is False
