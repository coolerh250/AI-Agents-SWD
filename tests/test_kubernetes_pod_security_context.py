"""Step 51.2A -- pod-level security context baseline (values + helper)."""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
CHART = ROOT / "infra" / "kubernetes" / "charts" / "ai-agents-platform"


def _ws() -> dict:
    return yaml.safe_load((CHART / "values.yaml").read_text(encoding="utf-8"))["global"][
        "workloadSecurity"
    ]


def test_run_as_non_root_and_nonzero_uid() -> None:
    ws = _ws()
    assert ws["enabled"] is True
    assert ws["runAsNonRoot"] is True
    assert ws["runAsUser"] == 10001 and ws["runAsUser"] != 0
    assert ws["runAsGroup"] == 10001
    assert ws["fsGroup"] == 10001


def test_seccomp_runtime_default() -> None:
    assert _ws()["seccompProfile"]["type"] == "RuntimeDefault"


def test_helper_renders_pod_security_context() -> None:
    tpl = (CHART / "templates" / "_security_helpers.tpl").read_text(encoding="utf-8")
    assert 'define "aiagents.podSecurityContext"' in tpl
    assert "runAsNonRoot:" in tpl
    assert "seccompProfile:" in tpl
    assert "fsGroup:" in tpl


def test_infra_uid_overrides_are_nonzero() -> None:
    comps = yaml.safe_load((CHART / "values.yaml").read_text(encoding="utf-8"))["components"]
    for n in ("postgres", "redis", "vault"):
        sec = comps[n]["security"]
        assert sec["runAsUser"] != 0, n
