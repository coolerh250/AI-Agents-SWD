"""Step 51.2A -- container-level security context baseline."""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
CHART = ROOT / "infra" / "kubernetes" / "charts" / "ai-agents-platform"


def _ws() -> dict:
    return yaml.safe_load((CHART / "values.yaml").read_text(encoding="utf-8"))["global"][
        "workloadSecurity"
    ]


def test_no_privilege_escalation_or_privileged() -> None:
    ws = _ws()
    assert ws["allowPrivilegeEscalation"] is False
    assert ws["privileged"] is False


def test_drop_all_capabilities_no_add() -> None:
    ws = _ws()
    assert ws["dropCapabilities"] == ["ALL"]
    # no component is allowed to add capabilities (schema forbids the key)
    comps = yaml.safe_load((CHART / "values.yaml").read_text(encoding="utf-8"))["components"]
    for n, c in comps.items():
        sec = c.get("security", {}) or {}
        assert "capabilities" not in sec, n


def test_helper_renders_container_security_context() -> None:
    tpl = (CHART / "templates" / "_security_helpers.tpl").read_text(encoding="utf-8")
    assert 'define "aiagents.containerSecurityContext"' in tpl
    assert "allowPrivilegeEscalation:" in tpl
    assert "privileged:" in tpl
    assert "readOnlyRootFilesystem:" in tpl
    assert "drop:" in tpl


def test_schema_forbids_capability_add_via_additional_properties() -> None:
    import json

    schema = json.loads((CHART / "values.schema.json").read_text(encoding="utf-8"))
    sec = schema["properties"]["components"]["additionalProperties"]["properties"]["security"]
    assert sec["additionalProperties"] is False
    assert "capabilities" not in sec["properties"]
