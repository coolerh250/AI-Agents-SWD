"""Step 51.2A -- ServiceAccount hardening (token automount disabled)."""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
CHART = ROOT / "infra" / "kubernetes" / "charts" / "ai-agents-platform"


def _values() -> dict:
    return yaml.safe_load((CHART / "values.yaml").read_text(encoding="utf-8"))


def test_serviceaccount_create_and_automount_false() -> None:
    v = _values()
    assert v["serviceAccount"]["create"] is True
    assert v["serviceAccount"]["automountServiceAccountToken"] is False
    assert v["global"]["workloadSecurity"]["automountServiceAccountToken"] is False


def test_serviceaccount_template_sets_automount_false() -> None:
    tpl = (CHART / "templates" / "serviceaccounts.yaml").read_text(encoding="utf-8")
    assert "automountServiceAccountToken:" in tpl


def test_pod_spec_sets_automount_false() -> None:
    tpl = (CHART / "templates" / "deployments.yaml").read_text(encoding="utf-8")
    assert "automountServiceAccountToken:" in tpl


def test_no_role_objects_in_templates() -> None:
    text = "\n".join(p.read_text(encoding="utf-8") for p in (CHART / "templates").glob("*.yaml"))
    import re

    for kind in ("Role", "RoleBinding", "ClusterRole", "ClusterRoleBinding"):
        assert not re.search(rf"kind:\s*{kind}\b", text), kind
