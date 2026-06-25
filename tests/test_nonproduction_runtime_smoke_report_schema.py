"""Step 55 -- runtime smoke report schema."""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "infra" / "kubernetes" / "nonproduction-runtime-smoke-report-schema.yaml"


def _schema() -> dict:
    return (yaml.safe_load(SCHEMA.read_text(encoding="utf-8")) or {})[
        "nonProductionRuntimeSmokeReportSchema"
    ]


def test_not_production_ready_not_committed() -> None:
    s = _schema()
    assert s["productionReady"] is False
    assert s["committedRuntimeReportAllowed"] is False


def test_redaction_rules() -> None:
    red = _schema()["redaction"]
    for k in ("noKubeconfig", "noToken", "noCert", "noSecret", "noRenderedManifest"):
        assert red[k] is True


def test_report_fields_present() -> None:
    fields = _schema()["fields"]
    for k in (
        "podStatus",
        "serviceHealth",
        "connectivity",
        "networkPolicy",
        "pvc",
        "securityContext",
        "batchJobs",
        "clusterContextHash",
    ):
        assert k in fields
    assert fields["productionReady"] is False
