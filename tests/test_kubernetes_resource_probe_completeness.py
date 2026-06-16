"""Step 51.2A -- resource + probe completeness for first-party components."""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
CHART = ROOT / "infra" / "kubernetes" / "charts" / "ai-agents-platform"

FIRST_PARTY = {"application", "governance", "communication", "worker", "agent"}


def _values() -> dict:
    return yaml.safe_load((CHART / "values.yaml").read_text(encoding="utf-8"))


def test_first_party_resources_complete() -> None:
    comps = _values()["components"]
    for n, c in comps.items():
        if c["type"] not in FIRST_PARTY:
            continue
        res = c["resources"]
        assert res["requests"]["cpu"], n
        assert res["requests"]["memory"], n
        assert res["limits"]["cpu"], n
        assert res["limits"]["memory"], n


def test_first_party_health_probe_http() -> None:
    comps = _values()["components"]
    for n, c in comps.items():
        if c["type"] not in FIRST_PARTY:
            continue
        h = c["health"]
        assert h["enabled"] is True, n
        assert h["type"] == "httpGet", n
        assert h["path"] == "/health", n


def test_service_port_matches_container_port() -> None:
    comps = _values()["components"]
    for n, c in comps.items():
        if c.get("service", {}).get("enabled"):
            assert c["service"]["port"] == c["containerPort"], n


def test_deployment_template_renders_probes() -> None:
    tpl = (CHART / "templates" / "deployments.yaml").read_text(encoding="utf-8")
    assert "livenessProbe:" in tpl
    assert "readinessProbe:" in tpl
    assert "terminationGracePeriodSeconds:" in tpl
