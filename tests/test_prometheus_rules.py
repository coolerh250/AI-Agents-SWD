from pathlib import Path

import yaml

_REPO_ROOT = Path(__file__).resolve().parents[1]
_RULES_PATH = _REPO_ROOT / "infra" / "observability" / "prometheus" / "rules" / "aiagents.rules.yml"
_PROMETHEUS_YML = _REPO_ROOT / "infra" / "observability" / "prometheus.yml"

REQUIRED_ALERTS = (
    "AIWorkflowFailuresHigh",
    "AIWorkflowLatencyP95High",
    "AIAgentExecutionFailuresHigh",
    "AIDeadletterIncreasing",
    "AIRetrySpike",
    "AIServiceDown",
    "AIPrometheusTargetDown",
    "AIApprovalPendingTooLong",
)


def _load_rules() -> dict:
    return yaml.safe_load(_RULES_PATH.read_text(encoding="utf-8"))


def _flatten_alert_rules() -> list[dict]:
    config = _load_rules()
    rules: list[dict] = []
    for group in config.get("groups", []):
        for rule in group.get("rules", []):
            if "alert" in rule:
                rules.append(rule)
    return rules


def test_rules_file_exists():
    assert _RULES_PATH.exists(), f"missing {_RULES_PATH}"


def test_rules_yaml_is_valid_and_has_groups():
    config = _load_rules()
    assert isinstance(config, dict)
    assert isinstance(config.get("groups"), list)
    assert config["groups"], "rules file must declare at least one group"


def test_every_required_alert_is_present():
    alerts_by_name = {rule["alert"] for rule in _flatten_alert_rules()}
    for name in REQUIRED_ALERTS:
        assert name in alerts_by_name, f"alert {name!r} not found in rules file"


def test_every_alert_has_required_labels():
    for rule in _flatten_alert_rules():
        labels = rule.get("labels") or {}
        assert "severity" in labels, f"{rule['alert']} is missing label severity"
        assert "component" in labels, f"{rule['alert']} is missing label component"
        assert labels["severity"] in ("critical", "warning", "info"), rule["alert"]


def test_every_alert_has_required_annotations():
    for rule in _flatten_alert_rules():
        annotations = rule.get("annotations") or {}
        for key in ("summary", "description", "runbook_url"):
            assert key in annotations, f"{rule['alert']} is missing annotation {key}"


def test_every_alert_has_an_expression():
    for rule in _flatten_alert_rules():
        assert rule.get("expr"), f"{rule['alert']} is missing expr"


def test_prometheus_yml_loads_rules_and_targets_alertmanager():
    config = yaml.safe_load(_PROMETHEUS_YML.read_text(encoding="utf-8"))
    rule_files = config.get("rule_files") or []
    assert rule_files, "prometheus.yml must declare rule_files"
    assert any("rules" in str(p) for p in rule_files), rule_files
    alerting = config.get("alerting") or {}
    alertmanagers = alerting.get("alertmanagers") or []
    assert alertmanagers, "prometheus.yml must declare alerting.alertmanagers"
    targets = []
    for am in alertmanagers:
        for sc in am.get("static_configs", []):
            targets.extend(sc.get("targets", []))
    assert any("alertmanager:9093" in t for t in targets), targets
