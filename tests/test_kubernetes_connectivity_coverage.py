"""Step 51.2B -- structural connectivity pairing (source-level).

The rendered ingress/egress pairing + missing/unexpected detection is enforced
by scripts/verify_kubernetes_service_connectivity.py against real manifests.
This test checks the structural invariants that guarantee pairing.
"""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
CHART = ROOT / "infra" / "kubernetes" / "charts" / "ai-agents-platform"


def _values() -> dict:
    return yaml.safe_load((CHART / "values.yaml").read_text(encoding="utf-8"))


def test_no_self_edges_and_no_duplicates() -> None:
    edges = _values()["networkPolicy"]["internalEdges"]
    keys = [(e["source"], e["target"], e["port"]) for e in edges]
    assert len(keys) == len(set(keys)), "duplicate edges"
    assert all(e["source"] != e["target"] for e in edges), "self-edge"


def test_template_iterates_edges_for_both_directions() -> None:
    tpl = (CHART / "templates" / "networkpolicies.yaml").read_text(encoding="utf-8")
    # one ingress map keyed by target, one egress map keyed by source
    assert "$ingressByTarget" in tpl
    assert "$egressBySource" in tpl
    # both endpoints checked for enablement so no dangling allow rule renders
    assert "$targetEnabled" in tpl
    assert "$sourceEnabled" in tpl


def test_infra_edges_flagged() -> None:
    edges = _values()["networkPolicy"]["internalEdges"]
    for e in edges:
        if e["target"] in ("postgres", "redis"):
            assert e["infra"] is True, e
        else:
            assert e["infra"] is False, e
