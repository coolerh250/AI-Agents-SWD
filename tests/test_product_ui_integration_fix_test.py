"""Step 64E.4B -- Product UI integration fix in test/QA (docs + code-backed)."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STAGING = ROOT / "docs" / "staging"
REPORT = STAGING / "product-ui-integration-fix-test-report.md"
MATRIX = STAGING / "product-ui-formal-page-validation-matrix.md"
EVIDENCE = STAGING / "product-ui-test-qa-evidence.md"
GAPS = STAGING / "product-ui-known-gaps-before-staging-redeploy.md"
PROGRESS = ROOT / "source" / "progress.md"

APP = ROOT / "apps" / "admin-console" / "src" / "App.tsx"
NAV = ROOT / "apps" / "admin-console" / "src" / "components" / "Nav.tsx"
PAGES = ROOT / "apps" / "admin-console" / "src" / "pages"
AGENT = PAGES / "AgentExecutions.tsx"
QACODE = PAGES / "QaCode.tsx"
AUDIT = PAGES / "AuditEvidence.tsx"
TASKGRAPH = PAGES / "TaskGraph.tsx"
SAFETY = PAGES / "SafetyCenter.tsx"

DOCS = (REPORT, MATRIX, EVIDENCE, GAPS)
ITEMS = ("wi-0001", "agent execution", "workflow", "qa", "audit", "safety")


def test_docs_exist() -> None:
    for p in DOCS:
        assert p.is_file(), p.name


def test_formal_pages_addressed_in_matrix() -> None:
    low = MATRIX.read_text(encoding="utf-8").lower()
    for term in ITEMS:
        assert term in low, term


def test_formal_pages_are_code_backed() -> None:
    assert AGENT.is_file() and QACODE.is_file() and AUDIT.is_file()
    app = APP.read_text(encoding="utf-8")
    for route in ("/agent-executions", "/qa-code", "/audit-evidence"):
        assert route in app, route
    assert "getAgentExecutions" in AGENT.read_text(encoding="utf-8")
    qac = QACODE.read_text(encoding="utf-8")
    assert "getQaRuns" in qac and "getCodeWorkspaces" in qac
    assert "getDeliveryWorkItemEvents" in AUDIT.read_text(encoding="utf-8")
    assert "getWorkflows" in TASKGRAPH.read_text(encoding="utf-8")
    assert "production_executed_true_count" in SAFETY.read_text(encoding="utf-8")


def test_demo_evidence_diagnostic_only_in_nav() -> None:
    nav = NAV.read_text(encoding="utf-8")
    demo_lines = [ln for ln in nav.splitlines() if "/demo-evidence" in ln]
    assert demo_lines and "diagnostic" in demo_lines[0].lower()
    routes = re.findall(r'to:\s*"([^"]+)"', nav)
    assert routes[-1] == "/demo-evidence"


def test_step64e_failed_step64f_blocked() -> None:
    low = "".join(p.read_text(encoding="utf-8") for p in DOCS).lower()
    assert "failed_staging_representativeness" in low or "failed_operator_validation" in low
    assert "step 64f" in low and "block" in low


def test_no_staging_redeploy_or_production_action_claimed() -> None:
    for p in DOCS:
        low = p.read_text(encoding="utf-8").lower()
        assert "no staging redeploy" in low, p.name
        assert "no image rebuild" in low, p.name
        assert "no container restart" in low, p.name
        assert "no production action" in low, p.name
        assert "production_executed_true_count=0" in low, p.name


def test_safety_flags_present() -> None:
    for p in DOCS:
        text = p.read_text(encoding="utf-8")
        assert "production-action=false" in text
        assert "image-push=false" in text
        assert "production-action=true" not in text


def test_no_secret_values_stored() -> None:
    for p in DOCS:
        text = p.read_text(encoding="utf-8")
        assert "-----BEGIN" not in text
        assert not re.search(r"password\s*[:=]\s*\S", text, re.IGNORECASE)


def test_step64e4b_documented_in_progress() -> None:
    text = PROGRESS.read_text(encoding="utf-8")
    assert "64E.4B" in text
    assert "PRODUCT_UI_INTEGRATION_FIX_TEST_VERIFY" in text
