"""Step 51.2A -- writable path / emptyDir model safety."""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
CHART = ROOT / "infra" / "kubernetes" / "charts" / "ai-agents-platform"

FORBIDDEN_MOUNTS = {"/", "/app", "/etc"}


def _values() -> dict:
    return yaml.safe_load((CHART / "values.yaml").read_text(encoding="utf-8"))


def test_writable_paths_safe_and_sized() -> None:
    comps = _values()["components"]
    for n, c in comps.items():
        for w in (c.get("security", {}) or {}).get("writablePaths", []) or []:
            assert w["mountPath"].startswith("/"), n
            assert w["mountPath"] not in FORBIDDEN_MOUNTS, f"{n}: {w['mountPath']}"
            assert "docker.sock" not in w["mountPath"], n
            assert w.get("sizeLimit"), f"{n} writable path missing sizeLimit"
            assert w.get("name"), n


def test_no_hostpath_anywhere_in_values() -> None:
    raw = (CHART / "values.yaml").read_text(encoding="utf-8")
    assert "hostPath" not in raw


def test_workspace_agents_have_writable_tmp() -> None:
    comps = _values()["components"]
    for n in (
        "development-agent",
        "qa-agent",
        "workspace-operator-agent",
        "mini-delivery-pilot-agent",
    ):
        paths = {w["mountPath"] for w in comps[n]["security"]["writablePaths"]}
        assert "/tmp" in paths, n


def test_template_default_writable_is_tmp() -> None:
    tpl = (CHART / "templates" / "deployments.yaml").read_text(encoding="utf-8")
    # components without explicit writablePaths default to an /tmp emptyDir
    assert '"mountPath" "/tmp"' in tpl
    assert "emptyDir:" in tpl
    assert "sizeLimit:" in tpl


def test_deferred_persistent_storage_recorded() -> None:
    inv = yaml.safe_load(
        (ROOT / "infra" / "kubernetes" / "workload-security-inventory.yaml").read_text(
            encoding="utf-8"
        )
    )
    deferred = inv["deferred"]["persistentStorage"]["components"]
    assert "postgres" in deferred
    # postgres PGDATA is deferred, NOT faked as emptyDir
    pg = inv["components"]["postgres"]["writablePaths"]
    assert any(w.get("type") == "deferred_to_51_2C" for w in pg)
