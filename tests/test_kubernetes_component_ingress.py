"""Step 51.2B -- per-target ingress policy generation (source-level)."""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
CHART = ROOT / "infra" / "kubernetes" / "charts" / "ai-agents-platform"


def _values() -> dict:
    return yaml.safe_load((CHART / "values.yaml").read_text(encoding="utf-8"))


def test_template_generates_per_target_ingress() -> None:
    tpl = (CHART / "templates" / "networkpolicies.yaml").read_text(encoding="utf-8")
    assert "ingress-{{ $target }}" in tpl
    assert "policyTypes:" in tpl
    assert "app.kubernetes.io/instance" in tpl


def test_every_edge_target_is_known_component() -> None:
    v = _values()
    comps = set(v["components"])
    for e in v["networkPolicy"]["internalEdges"]:
        assert e["target"] in comps, e["target"]


def test_ingress_uses_explicit_source_selectors() -> None:
    tpl = (CHART / "templates" / "networkpolicies.yaml").read_text(encoding="utf-8")
    # ingress 'from' is built from explicit per-source podSelectors, never empty
    assert "from:" in tpl
    assert "app.kubernetes.io/name: {{ $e.source }}" in tpl
