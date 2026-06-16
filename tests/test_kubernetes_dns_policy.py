"""Step 51.2B -- DNS egress policy (TCP/UDP 53 only, scoped)."""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
CHART = ROOT / "infra" / "kubernetes" / "charts" / "ai-agents-platform"


def _dns() -> dict:
    return yaml.safe_load((CHART / "values.yaml").read_text(encoding="utf-8"))["networkPolicy"][
        "dns"
    ]


def test_dns_enabled_and_scoped() -> None:
    dns = _dns()
    assert dns["enabled"] is True
    assert dns["namespaceSelector"], "namespace selector must not be empty"
    assert dns["podSelector"], "pod selector must not be empty"


def test_dns_ports_are_53_only() -> None:
    ports = _dns()["ports"]
    assert {p["port"] for p in ports} == {53}
    assert {p["protocol"] for p in ports} == {"TCP", "UDP"}


def test_template_renders_dns_policy() -> None:
    tpl = (CHART / "templates" / "networkpolicies.yaml").read_text(encoding="utf-8")
    assert "allow-dns" in tpl
    assert "kube-dns" not in tpl  # selector comes from values, not hardcoded
