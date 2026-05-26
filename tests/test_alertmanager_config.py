from pathlib import Path

import yaml

_REPO_ROOT = Path(__file__).resolve().parents[1]
_AM_YML = _REPO_ROOT / "infra" / "observability" / "alertmanager" / "alertmanager.yml"
_COMPOSE_YML = _REPO_ROOT / "infra" / "docker-compose" / "docker-compose.yml"

# Off-host notifier blocks an Alertmanager receiver MUST NOT contain in the
# local/test environment — the platform routes to a null receiver only.
FORBIDDEN_NOTIFIER_KEYS = (
    "slack_configs",
    "discord_configs",
    "telegram_configs",
    "pagerduty_configs",
    "opsgenie_configs",
    "webhook_configs",
    "email_configs",
)


def _load_alertmanager() -> dict:
    return yaml.safe_load(_AM_YML.read_text(encoding="utf-8"))


def _load_compose() -> dict:
    return yaml.safe_load(_COMPOSE_YML.read_text(encoding="utf-8"))


def test_alertmanager_yml_exists():
    assert _AM_YML.exists(), f"missing {_AM_YML}"


def test_alertmanager_yml_is_valid_yaml_and_has_required_top_level():
    config = _load_alertmanager()
    assert isinstance(config, dict)
    assert "route" in config, "alertmanager.yml must declare a route block"
    assert "receivers" in config, "alertmanager.yml must declare receivers"
    receivers = config["receivers"]
    assert isinstance(receivers, list) and receivers, "receivers must be a non-empty list"


def test_default_route_points_at_existing_receiver():
    config = _load_alertmanager()
    route = config["route"]
    default_receiver = route.get("receiver")
    assert default_receiver, "route.receiver must be set"
    receiver_names = {r["name"] for r in config["receivers"]}
    assert default_receiver in receiver_names, (default_receiver, receiver_names)
    # subroutes must also point at known receivers
    for sub in route.get("routes", []) or []:
        target = sub.get("receiver")
        if target is not None:
            assert target in receiver_names, target


def test_no_offhost_notifier_is_configured():
    """The local/test environment must never publish a real Slack / Discord /
    Telegram / PagerDuty / OpsGenie / webhook / email alert. Every receiver
    must be the null receiver (no notifier blocks)."""
    config = _load_alertmanager()
    for receiver in config["receivers"]:
        for key in FORBIDDEN_NOTIFIER_KEYS:
            assert (
                key not in receiver
            ), f"receiver {receiver.get('name')!r} declares forbidden notifier {key!r}"


def test_compose_includes_alertmanager_service_bound_to_localhost():
    config = _load_compose()
    services = config["services"]
    assert "alertmanager" in services, "docker-compose must define alertmanager"
    am = services["alertmanager"]
    assert am["image"].startswith("prom/alertmanager"), am["image"]
    ports = [str(p) for p in am.get("ports", [])]
    assert any("127.0.0.1:9093:9093" in p for p in ports), ports


def test_compose_prometheus_depends_on_alertmanager_and_mounts_rules():
    config = _load_compose()
    prometheus = config["services"]["prometheus"]
    depends_on = prometheus.get("depends_on") or []
    if isinstance(depends_on, dict):
        depends_on = list(depends_on.keys())
    assert "alertmanager" in depends_on, depends_on
    volumes = [str(v) for v in prometheus.get("volumes", [])]
    assert any("prometheus/rules" in v and "/etc/prometheus/rules" in v for v in volumes), volumes
