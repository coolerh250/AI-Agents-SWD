"""Step 64E.3B -- Admin Console demo-evidence UI remediation (docs + code-backed)."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STAGING = ROOT / "docs" / "staging"
REPORT = STAGING / "admin-console-demo-evidence-ui-remediation-report.md"
VALIDATION = STAGING / "admin-console-demo-evidence-ui-validation.md"
CHECKLIST = STAGING / "admin-console-demo-evidence-operator-rereview-checklist.md"
GAPS = STAGING / "admin-console-demo-evidence-known-gaps-after-remediation.md"
PAGE = ROOT / "apps" / "admin-console" / "src" / "pages" / "DemoEvidence.tsx"
APP = ROOT / "apps" / "admin-console" / "src" / "App.tsx"
NAV = ROOT / "apps" / "admin-console" / "src" / "components" / "Nav.tsx"
OPS = ROOT / "apps" / "orchestrator" / "src" / "operations.py"
PROGRESS = ROOT / "source" / "progress.md"

DOCS = (REPORT, VALIDATION, CHECKLIST, GAPS)
ITEMS = ("wi-0001", "agent execution", "workflow", "qa", "audit")


def test_remediation_docs_exist() -> None:
    for p in DOCS:
        assert p.is_file(), p.name


def test_all_five_evidence_types_addressed() -> None:
    low = REPORT.read_text(encoding="utf-8").lower()
    for term in ITEMS:
        assert term in low, term


def test_demo_evidence_page_and_route_exist() -> None:
    assert PAGE.is_file()
    assert "/demo-evidence" in APP.read_text(encoding="utf-8")
    assert "Demo Evidence" in NAV.read_text(encoding="utf-8")


def test_backend_endpoints_present() -> None:
    ops = OPS.read_text(encoding="utf-8")
    assert "/agent-executions" in ops
    assert '@router.get("/workflows")' in ops


def test_page_uses_evidence_getters() -> None:
    page = PAGE.read_text(encoding="utf-8")
    for getter in ("getAgentExecutions", "getWorkflows", "getQaRuns", "getCodeWorkspaces"):
        assert getter in page, getter


def test_operator_rereview_required() -> None:
    low = "".join(p.read_text(encoding="utf-8") for p in DOCS).lower()
    assert "re-review" in low or "rereview" in low


def test_step64e_not_marked_pass() -> None:
    for p in DOCS:
        for line in p.read_text(encoding="utf-8").splitlines():
            ll = line.lower()
            if "step 64e" in ll and "overall" in ll and "pass" in ll and "step 64e.3" not in ll:
                assert "failed" in ll or " not " in ll or "pass_with_gaps" in ll, line


def test_step64f_blocked() -> None:
    low = "".join(p.read_text(encoding="utf-8") for p in DOCS).lower()
    assert "step 64f" in low and "block" in low


def test_no_production_action_allowed() -> None:
    for p in DOCS:
        text = p.read_text(encoding="utf-8")
        assert "production-action=false" in text
        assert "image-push=false" in text
        assert "production-action=true" not in text


def test_no_secret_values_stored() -> None:
    for p in DOCS:
        text = p.read_text(encoding="utf-8")
        assert "-----BEGIN" not in text
        assert "p@ssw0rd" not in text
        assert not re.search(r"password\s*[:=]\s*\S", text, re.IGNORECASE)


def test_step64e3b_documented_in_progress() -> None:
    text = PROGRESS.read_text(encoding="utf-8")
    assert "64E.3B" in text
    assert "ADMIN_CONSOLE_DEMO_EVIDENCE_UI_REMEDIATION_VERIFY" in text
