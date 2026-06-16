"""Step 51.2B -- default-deny ingress + egress baseline."""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
CHART = ROOT / "infra" / "kubernetes" / "charts" / "ai-agents-platform"


def _np() -> dict:
    return yaml.safe_load((CHART / "values.yaml").read_text(encoding="utf-8"))["networkPolicy"]


def test_network_policy_enabled_default_deny() -> None:
    np = _np()
    assert np["enabled"] is True
    assert np["defaultDenyIngress"] is True
    assert np["defaultDenyEgress"] is True


def test_template_renders_default_deny() -> None:
    tpl = (CHART / "templates" / "networkpolicies.yaml").read_text(encoding="utf-8")
    assert "default-deny-ingress" in tpl
    assert "default-deny-egress" in tpl
    assert "podSelector: {}" in tpl


def test_empty_pod_selector_only_on_default_deny() -> None:
    tpl = (CHART / "templates" / "networkpolicies.yaml").read_text(encoding="utf-8")
    # the only literal empty podSelector is the default-deny block
    assert tpl.count("podSelector: {}") == 2  # ingress + egress default-deny
