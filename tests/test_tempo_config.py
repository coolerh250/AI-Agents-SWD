from pathlib import Path

import yaml

_REPO_ROOT = Path(__file__).resolve().parents[1]
_TEMPO_YML = _REPO_ROOT / "infra" / "observability" / "tempo" / "tempo.yml"
_COMPOSE_YML = _REPO_ROOT / "infra" / "docker-compose" / "docker-compose.yml"

_OTEL_SERVICES = (
    "policy-engine",
    "approval-engine",
    "audit-service",
    "orchestrator",
    "communication-gateway",
    "intake-agent",
    "requirement-agent",
    "development-agent",
    "qa-agent",
    "devops-agent",
    "retry-scheduler",
)


def _load_tempo() -> dict:
    return yaml.safe_load(_TEMPO_YML.read_text(encoding="utf-8"))


def _load_compose() -> dict:
    return yaml.safe_load(_COMPOSE_YML.read_text(encoding="utf-8"))


def test_tempo_config_exists():
    assert _TEMPO_YML.exists(), f"missing {_TEMPO_YML}"


def test_tempo_http_listen_port_is_3200():
    config = _load_tempo()
    assert config["server"]["http_listen_port"] == 3200


def test_tempo_accepts_otlp_grpc_on_4317():
    config = _load_tempo()
    protocols = config["distributor"]["receivers"]["otlp"]["protocols"]
    assert protocols["grpc"]["endpoint"].endswith(":4317")


def test_tempo_accepts_otlp_http_on_4318():
    config = _load_tempo()
    protocols = config["distributor"]["receivers"]["otlp"]["protocols"]
    assert protocols["http"]["endpoint"].endswith(":4318")


def test_tempo_storage_is_local_filesystem():
    config = _load_tempo()
    trace_storage = config["storage"]["trace"]
    assert trace_storage["backend"] == "local"
    assert trace_storage["local"]["path"].startswith("/var/tempo")
    assert trace_storage["wal"]["path"].startswith("/var/tempo")


def test_tempo_usage_report_is_disabled():
    # local/test runtime must not phone home to grafana.com
    config = _load_tempo()
    assert config["usage_report"]["reporting_enabled"] is False


def test_compose_includes_tempo_service():
    config = _load_compose()
    services = config["services"]
    assert "tempo" in services
    tempo = services["tempo"]
    assert tempo["image"].startswith("grafana/tempo")
    ports = [str(p) for p in tempo["ports"]]
    assert any("127.0.0.1:3200:3200" in p for p in ports)
    assert any("127.0.0.1:4317:4317" in p for p in ports)
    assert any("127.0.0.1:4318:4318" in p for p in ports)


def test_compose_grafana_depends_on_tempo():
    config = _load_compose()
    grafana_deps = config["services"]["grafana"]["depends_on"]
    if isinstance(grafana_deps, dict):
        assert "tempo" in grafana_deps
    else:
        assert "tempo" in grafana_deps


def test_every_service_sets_otlp_env_pointing_at_tempo():
    config = _load_compose()
    services = config["services"]
    for name in _OTEL_SERVICES:
        env = services[name]["environment"]
        assert env["OTEL_EXPORTER_OTLP_ENDPOINT"] == "http://tempo:4317", name
        assert env["OTEL_EXPORTER_OTLP_PROTOCOL"] == "grpc", name
        assert env["OTEL_SERVICE_NAME"] == name, name
