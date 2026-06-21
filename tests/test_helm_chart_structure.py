"""Step 51.1 -- Helm chart structure + Chart.yaml metadata."""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
CHART = ROOT / "infra" / "kubernetes" / "charts" / "ai-agents-platform"

REQUIRED = [
    "Chart.yaml",
    "values.yaml",
    "values.schema.json",
    "values-dev.yaml",
    "values-test.yaml",
    "values-staging-placeholder.yaml",
    "values-prod-placeholder.yaml",
    "component-catalog.yaml",
    "templates/_helpers.tpl",
    "templates/deployments.yaml",
    "templates/services.yaml",
    "templates/configmaps.yaml",
    "templates/serviceaccounts.yaml",
    "templates/validate-values.yaml",
    "templates/NOTES.txt",
    # Step 51.2A / 51.2B additions
    "templates/_security_helpers.tpl",
    "templates/networkpolicies.yaml",
    # Step 51.2C1 addition
    "templates/persistentvolumeclaims.yaml",
    # Step 51.2C2 additions
    "templates/_batch_helpers.tpl",
    "templates/migration-job.yaml",
    "templates/backup-cronjob.yaml",
    "templates/restore-job.yaml",
]

# Step 51.3+ templates that MUST NOT exist yet.
FORBIDDEN = [
    "templates/horizontalpodautoscalers.yaml",
    "templates/poddisruptionbudgets.yaml",
]


def test_required_files_present() -> None:
    for rel in REQUIRED:
        assert (CHART / rel).is_file(), rel


def test_forbidden_files_absent() -> None:
    for rel in FORBIDDEN:
        assert not (CHART / rel).exists(), rel
    assert not (ROOT / "infra" / "kubernetes" / "argocd").exists()


def test_chart_metadata() -> None:
    chart = yaml.safe_load((CHART / "Chart.yaml").read_text(encoding="utf-8"))
    assert chart["apiVersion"] == "v2"
    assert chart["name"] == "ai-agents-platform"
    assert chart["type"] == "application"
    assert chart["version"] == "0.1.0"
    assert str(chart["appVersion"]).startswith("step-51")
    assert chart["description"]
    assert chart["annotations"]["ai-agents-swd/production-ready"] == "false"
