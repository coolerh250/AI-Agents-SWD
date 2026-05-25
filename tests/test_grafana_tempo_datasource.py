from pathlib import Path

import pytest
import yaml

_REPO_ROOT = Path(__file__).resolve().parents[1]
_DS_DIR = _REPO_ROOT / "infra" / "observability" / "grafana" / "provisioning" / "datasources"
_TEMPO_DS = _DS_DIR / "tempo.yml"
_PROM_DS = _DS_DIR / "prometheus.yml"


def _load(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def test_tempo_datasource_file_exists():
    assert _TEMPO_DS.exists(), f"missing {_TEMPO_DS}"


def test_tempo_datasource_is_tempo_type_pointing_at_tempo_3200():
    config = _load(_TEMPO_DS)
    datasources = config["datasources"]
    tempo = next((d for d in datasources if d["type"] == "tempo"), None)
    assert tempo is not None, "no tempo datasource declared"
    assert tempo["name"] == "Tempo"
    assert tempo["url"] == "http://tempo:3200"
    assert tempo["access"] == "proxy"


def test_tempo_datasource_links_service_map_to_prometheus():
    config = _load(_TEMPO_DS)
    tempo = next(d for d in config["datasources"] if d["type"] == "tempo")
    json_data = tempo.get("jsonData") or {}
    service_map = json_data.get("serviceMap") or {}
    assert service_map.get("datasourceUid") == "prometheus"


def test_prometheus_datasource_uid_is_prometheus():
    # The Tempo datasource references the Prometheus datasource by UID for the
    # service map; the Prometheus provisioning must declare that uid.
    config = _load(_PROM_DS)
    prometheus = next(d for d in config["datasources"] if d["type"] == "prometheus")
    assert prometheus["uid"] == "prometheus"


def _grafana_up() -> bool:
    import httpx

    try:
        return httpx.get("http://localhost:3000/api/health", timeout=3).status_code == 200
    except Exception:
        return False


requires_grafana = pytest.mark.skipif(
    not _grafana_up(), reason="grafana not reachable on localhost:3000"
)


@requires_grafana
def test_grafana_serves_tempo_datasource_via_api():
    import httpx

    response = httpx.get("http://localhost:3000/api/datasources", timeout=5)
    assert response.status_code == 200
    datasources = response.json()
    tempo = next((d for d in datasources if d.get("type") == "tempo"), None)
    assert tempo is not None, "grafana did not provision the Tempo datasource"
    assert tempo["url"] == "http://tempo:3200"
