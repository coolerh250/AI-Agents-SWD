"""Step 51.2B -- per-source egress policy generation (source-level)."""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
CHART = ROOT / "infra" / "kubernetes" / "charts" / "ai-agents-platform"


def _values() -> dict:
    return yaml.safe_load((CHART / "values.yaml").read_text(encoding="utf-8"))


def test_template_generates_per_source_egress() -> None:
    tpl = (CHART / "templates" / "networkpolicies.yaml").read_text(encoding="utf-8")
    assert "egress-{{ $source }}" in tpl
    assert "app.kubernetes.io/name: {{ $e.target }}" in tpl


def test_every_edge_source_is_known_component() -> None:
    v = _values()
    comps = set(v["components"])
    for e in v["networkPolicy"]["internalEdges"]:
        assert e["source"] in comps, e["source"]


def test_edges_have_explicit_tcp_port() -> None:
    for e in _values()["networkPolicy"]["internalEdges"]:
        assert e["protocol"] == "TCP", e
        assert 1 <= int(e["port"]) <= 65535, e
