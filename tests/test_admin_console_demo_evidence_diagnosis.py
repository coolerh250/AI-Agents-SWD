"""Step 64E.3A -- Admin Console demo-evidence UI/API diagnosis (docs, read-only)."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STAGING = ROOT / "docs" / "staging"
DIAGNOSIS = STAGING / "admin-console-demo-evidence-ui-api-diagnosis.md"
ENDPOINTS = STAGING / "admin-console-demo-evidence-endpoint-map.md"
ROUTES = STAGING / "admin-console-demo-evidence-frontend-route-map.md"
MISMATCH = STAGING / "admin-console-demo-evidence-ui-api-mismatch-report.md"
PLAN = STAGING / "admin-console-demo-evidence-remediation-plan.md"
PROGRESS = ROOT / "source" / "progress.md"

DOCS = (DIAGNOSIS, ENDPOINTS, ROUTES, MISMATCH, PLAN)
ITEMS = ("wi-0001", "agent execution", "workflow", "qa", "audit")


def test_diagnosis_docs_exist() -> None:
    for p in DOCS:
        assert p.is_file(), p.name


def test_all_five_items_diagnosed() -> None:
    low = DIAGNOSIS.read_text(encoding="utf-8").lower()
    for term in ITEMS:
        assert term in low, term
    assert low.count("recommended fix") >= 5


def test_endpoint_and_route_maps_exist() -> None:
    assert ENDPOINTS.is_file()
    assert ROUTES.is_file()
    assert "/operations/" in ENDPOINTS.read_text(encoding="utf-8")


def test_mismatch_report_exists() -> None:
    low = MISMATCH.read_text(encoding="utf-8").lower()
    for term in ITEMS:
        assert term in low, term


def test_remediation_plan_exists() -> None:
    low = PLAN.read_text(encoding="utf-8").lower()
    assert "frontend changes" in low
    assert "operator re-review" in low


def test_step64e_failed_documented() -> None:
    low = "".join(p.read_text(encoding="utf-8") for p in DOCS).lower()
    assert "failed_operator_validation" in low


def test_step64f_blocked_documented() -> None:
    low = "".join(p.read_text(encoding="utf-8") for p in DOCS).lower()
    assert "step 64f" in low and "block" in low


def test_no_code_remediation_claimed() -> None:
    low = "".join(p.read_text(encoding="utf-8") for p in DOCS).lower()
    assert "no remediation implemented" in low or "no code change" in low


def test_no_production_action_allowed() -> None:
    for p in DOCS:
        text = p.read_text(encoding="utf-8")
        assert "production-action=false" in text
        assert "production-ready=false" in text
        assert "production-action=true" not in text


def test_no_secret_values_stored() -> None:
    for p in DOCS:
        text = p.read_text(encoding="utf-8")
        assert "-----BEGIN" not in text
        assert "p@ssw0rd" not in text
        assert not re.search(r"password\s*[:=]\s*\S", text, re.IGNORECASE)


def test_step64e3a_documented_in_progress() -> None:
    text = PROGRESS.read_text(encoding="utf-8")
    assert "64E.3A" in text
    assert "ADMIN_CONSOLE_DEMO_EVIDENCE_DIAGNOSIS_VERIFY" in text
