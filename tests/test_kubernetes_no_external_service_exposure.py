"""Step 51.2B -- no NodePort/LoadBalancer; Postgres/Redis stay ClusterIP."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHART = ROOT / "infra" / "kubernetes" / "charts" / "ai-agents-platform"
TEMPLATES = CHART / "templates"


def _template_text() -> str:
    return "\n".join(p.read_text(encoding="utf-8") for p in TEMPLATES.glob("*.yaml"))


def test_services_clusterip_only() -> None:
    svc = (TEMPLATES / "services.yaml").read_text(encoding="utf-8")
    assert "type: ClusterIP" in svc


def test_no_nodeport_or_loadbalancer() -> None:
    text = _template_text()
    assert not re.search(r"type:\s*NodePort", text)
    assert not re.search(r"type:\s*LoadBalancer", text)


def test_no_host_network_or_host_port() -> None:
    text = _template_text()
    assert not re.search(r"hostNetwork:\s*true", text)
    assert "hostPort" not in text


def test_no_externalname_service() -> None:
    text = _template_text()
    assert not re.search(r"type:\s*ExternalName", text)
