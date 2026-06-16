"""Step 51.2B -- observability network policies deferred (not generated)."""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
CHART = ROOT / "infra" / "kubernetes" / "charts" / "ai-agents-platform"
CATALOG = ROOT / "infra" / "kubernetes" / "network-connectivity-catalog.yaml"


def test_observability_flags_disabled() -> None:
    obs = yaml.safe_load((CHART / "values.yaml").read_text(encoding="utf-8"))["networkPolicy"][
        "observability"
    ]
    assert obs["prometheusScrape"]["enabled"] is False
    assert obs["otlpExport"]["enabled"] is False


def test_catalog_marks_otlp_deferred() -> None:
    obs = yaml.safe_load(CATALOG.read_text(encoding="utf-8"))["deferred"]["observability"]
    assert obs["otlpExport"] is False
    assert obs["prometheusScrape"] is False


def test_template_has_no_prometheus_or_otlp_policy() -> None:
    tpl = (CHART / "templates" / "networkpolicies.yaml").read_text(encoding="utf-8")
    assert "prometheus" not in tpl.lower()
    assert "otlp" not in tpl.lower()
    assert "4317" not in tpl
