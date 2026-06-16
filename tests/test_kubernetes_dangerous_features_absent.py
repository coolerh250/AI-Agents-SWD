"""Step 51.2A -- dangerous workload features absent from chart sources."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHART = ROOT / "infra" / "kubernetes" / "charts" / "ai-agents-platform"


# validate-values.yaml names the forbidden tokens in its fail-closed guards;
# it is policy logic, not a manifest, so it is excluded from the literal scan.
EXCLUDE = {"validate-values.yaml"}


def _chart_text() -> str:
    parts = []
    for ext in ("*.yaml", "*.yml", "*.tpl", "*.json"):
        for p in CHART.rglob(ext):
            if p.name in EXCLUDE:
                continue
            parts.append(p.read_text(encoding="utf-8"))
    return "\n".join(parts)


def test_no_hostpath() -> None:
    assert "hostPath" not in _chart_text()


def test_no_docker_socket() -> None:
    assert "docker.sock" not in _chart_text()


def test_no_host_namespaces_true() -> None:
    text = _chart_text()
    for field in ("hostNetwork", "hostPID", "hostIPC"):
        assert not re.search(rf"{field}:\s*true", text), field


def test_no_privileged_true_or_privesc_true() -> None:
    text = _chart_text()
    assert not re.search(r"privileged:\s*true", text)
    assert not re.search(r"allowPrivilegeEscalation:\s*true", text)


def test_no_unconfined_seccomp() -> None:
    assert "Unconfined" not in _chart_text()


def test_no_capability_add_in_helper_or_values() -> None:
    # the security helper only drops; never adds
    tpl = (CHART / "templates" / "_security_helpers.tpl").read_text(encoding="utf-8")
    assert "add:" not in tpl
    assert "drop:" in tpl


def test_validate_values_enforces_dangerous_feature_fail_closed() -> None:
    v = (CHART / "templates" / "validate-values.yaml").read_text(encoding="utf-8")
    for needle in (
        "runAsNonRoot must be true",
        "must not be 0",
        "allowPrivilegeEscalation must be false",
        "privileged must be false",
        "RuntimeDefault",
        "dropCapabilities must include ALL",
        "must not use hostPath",
        "docker socket",
        "must not mount writable /app",
    ):
        assert needle in v, needle
