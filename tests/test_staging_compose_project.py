"""Stage 25 expanded staging compose checks.

These pin the contract the staging stack must honour to coexist with
the local/test stack on the same host:

* compose project name = ``aiagents-staging`` (distinct from
  ``aiagents-test``);
* every host port binding offset by +10000 from the local file;
* every Postgres consumer reads ``DATABASE_URL`` with a password;
* every volume name carries a ``-staging`` suffix.
"""

from __future__ import annotations

from pathlib import Path

import pytest

try:
    import yaml as _yaml
except ImportError:  # pragma: no cover
    _yaml = None  # type: ignore[assignment]

_REPO_ROOT = Path(__file__).resolve().parents[1]
_STAGING = _REPO_ROOT / "infra" / "docker-compose" / "docker-compose.staging.yml"
_LOCAL = _REPO_ROOT / "infra" / "docker-compose" / "docker-compose.yml"


def _load(path: Path) -> dict:
    if _yaml is None:
        pytest.skip("PyYAML not installed")
    return _yaml.safe_load(path.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def staging_doc():
    return _load(_STAGING)


@pytest.fixture(scope="module")
def local_doc():
    return _load(_LOCAL)


def test_staging_project_name_distinct(staging_doc, local_doc):
    assert staging_doc.get("name") == "aiagents-staging"
    assert local_doc.get("name") == "aiagents-test"
    assert staging_doc.get("name") != local_doc.get("name")


def test_staging_includes_full_service_set(staging_doc):
    """Step 24 spec requires the staging stack to ship at least the
    core 22-service set so an operator can run a full e2e workflow.
    """
    services = set(staging_doc.get("services") or {})
    required = {
        "postgres",
        "redis",
        "orchestrator",
        "communication-gateway",
        "discord-gateway",
        "github-automation",
        "audit-service",
        "audit-worker",
        "notification-worker",
        "intake-agent",
        "requirement-agent",
        "development-agent",
        "qa-agent",
        "devops-agent",
        "retry-scheduler",
        "prometheus",
        "grafana",
        "tempo",
        "alertmanager",
    }
    missing = required - services
    assert not missing, f"staging compose missing required services: {missing}"


def _host_port(svc_block: dict) -> list[int]:
    ports = svc_block.get("ports") or []
    out: list[int] = []
    for p in ports:
        # forms: "127.0.0.1:18000:8000" or "127.0.0.1:18000:8000/tcp"
        host = p.split(":", 2)[1] if p.count(":") >= 2 else None
        if host:
            out.append(int(host.split("/")[0]))
    return out


def test_staging_host_ports_offset_by_10000(staging_doc, local_doc):
    """Every service that exposes a host port in BOTH files must have
    the staging host port offset by +10000.
    """
    s_services = staging_doc.get("services") or {}
    l_services = local_doc.get("services") or {}
    for name, l_block in l_services.items():
        if name not in s_services:
            continue
        l_ports = _host_port(l_block)
        s_ports = _host_port(s_services[name])
        if not l_ports or not s_ports:
            continue
        # Every host port in the local block must have +10000 sibling in staging.
        for l_port in l_ports:
            assert (
                l_port + 10000 in s_ports
            ), f"service {name} local host port {l_port} has no staging sibling at {l_port + 10000}"


def test_staging_no_host_port_collides_with_local(staging_doc, local_doc):
    s_services = staging_doc.get("services") or {}
    l_services = local_doc.get("services") or {}
    s_all: set[int] = set()
    for block in s_services.values():
        s_all.update(_host_port(block))
    l_all: set[int] = set()
    for block in l_services.values():
        l_all.update(_host_port(block))
    overlap = s_all & l_all
    assert not overlap, f"staging + local host ports collide: {overlap}"


def test_staging_postgres_requires_password(staging_doc):
    block = staging_doc["services"]["postgres"]
    env = block.get("environment") or {}
    val = env.get("POSTGRES_PASSWORD", "")
    # Must use the ${VAR:?} required form so compose refuses to start
    # without a password.
    assert "${POSTGRES_PASSWORD:?" in str(val)


def test_staging_postgres_no_trust_auth(staging_doc):
    block = staging_doc["services"]["postgres"]
    env = block.get("environment") or {}
    assert "POSTGRES_HOST_AUTH_METHOD" not in env
    text = _STAGING.read_text(encoding="utf-8")
    assert "POSTGRES_HOST_AUTH_METHOD: trust" not in text


def test_staging_database_urls_carry_password(staging_doc):
    """Every service whose env contains ``DATABASE_URL`` must
    interpolate ``${POSTGRES_PASSWORD}`` so the staging Postgres
    accepts the connection.
    """
    services = staging_doc.get("services") or {}
    expected = {
        "approval-engine",
        "audit-service",
        "audit-worker",
        "notification-worker",
        "discord-gateway",
        "orchestrator",
        "communication-gateway",
        "intake-agent",
        "requirement-agent",
        "development-agent",
        "qa-agent",
        "devops-agent",
        "retry-scheduler",
    }
    for name in expected:
        env = (services.get(name) or {}).get("environment") or {}
        url = str(env.get("DATABASE_URL", ""))
        assert "${POSTGRES_PASSWORD}" in url, f"{name} DATABASE_URL missing password placeholder"


def test_staging_volumes_have_staging_suffix(staging_doc):
    volumes = staging_doc.get("volumes") or {}
    for vol in volumes:
        assert "staging" in vol, f"volume {vol!r} missing staging suffix"
    # The local volume names must NOT appear in the staging template.
    local_names = {
        "postgres-data",
        "prometheus-data",
        "grafana-data",
        "tempo-data",
        "alertmanager-data",
    }
    assert local_names.isdisjoint(volumes)


def test_local_compose_unchanged_by_staging_work(local_doc):
    """Stage 25 is additive — the local/test compose keeps its trust
    auth + dev-mode Vault + null-receiver posture."""
    pg = local_doc["services"]["postgres"]
    assert pg["environment"]["POSTGRES_HOST_AUTH_METHOD"] == "trust"
    vault = local_doc["services"]["vault"]
    assert "server -dev" in str(vault.get("command", ""))
