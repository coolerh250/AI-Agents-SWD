"""Step 51.1 -- Service template is internal-only; no RBAC/Ingress objects."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHART = ROOT / "infra" / "kubernetes" / "charts" / "ai-agents-platform"
TEMPLATES = CHART / "templates"


def _all_template_text() -> str:
    return "\n".join(p.read_text(encoding="utf-8") for p in TEMPLATES.rglob("*.yaml"))


def test_services_are_clusterip() -> None:
    svc = (TEMPLATES / "services.yaml").read_text(encoding="utf-8")
    assert "type: ClusterIP" in svc


def test_no_nodeport_or_loadbalancer() -> None:
    text = _all_template_text()
    assert not re.search(r"type:\s*NodePort", text)
    assert not re.search(r"type:\s*LoadBalancer", text)


def test_no_ingress() -> None:
    text = _all_template_text()
    assert not re.search(r"kind:\s*Ingress\b", text)


def test_no_rbac_objects() -> None:
    text = _all_template_text()
    for kind in ("ClusterRole", "ClusterRoleBinding", "Role", "RoleBinding"):
        assert not re.search(rf"kind:\s*{kind}\b", text), kind


def test_serviceaccount_token_not_automounted() -> None:
    values = (CHART / "values.yaml").read_text(encoding="utf-8")
    assert "automountServiceAccountToken: false" in values
