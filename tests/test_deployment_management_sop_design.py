"""Step 64F.1 -- Staging deployment management SOP design (docs + guardrails)."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STAGING = ROOT / "docs" / "staging"
SOP = STAGING / "deployment-management-sop.md"
CHECKLIST = STAGING / "deployment-management-operator-checklist.md"
COMMANDS = STAGING / "deployment-management-command-reference.md"
AUTHZ = STAGING / "deployment-management-authorization-matrix.md"
TROUBLE = STAGING / "deployment-management-troubleshooting-guide.md"
VALIDATION = STAGING / "deployment-management-validation-plan.md"
RISKS = STAGING / "deployment-management-known-risks.md"
PROGRESS = ROOT / "source" / "progress.md"

DOCS = (SOP, CHECKLIST, COMMANDS, AUTHZ, TROUBLE, VALIDATION, RISKS)
PROCEDURES = (
    "start procedure",
    "stop procedure",
    "restart procedure",
    "redeploy",
    "upgrade procedure",
    "rollback procedure",
    "teardown procedure",
    "restore procedure",
    "health and safety validation",
    "troubleshooting",
    "authorization matrix",
)


def test_sop_docs_exist() -> None:
    for p in DOCS:
        assert p.is_file(), p.name


def test_sop_documents_all_procedures() -> None:
    low = SOP.read_text(encoding="utf-8").lower()
    for proc in PROCEDURES:
        assert proc in low, proc


def test_authorization_matrix_and_troubleshooting_present() -> None:
    assert "authorization" in AUTHZ.read_text(encoding="utf-8").lower()
    assert "troubleshoot" in TROUBLE.read_text(encoding="utf-8").lower()


def test_destructive_requires_explicit_authorization() -> None:
    low = "".join(p.read_text(encoding="utf-8") for p in DOCS).lower()
    assert "destructive" in low
    assert "explicit" in low and "authorization" in low


def test_status_recorded() -> None:
    low = "".join(p.read_text(encoding="utf-8") for p in DOCS).lower()
    assert "step 64e" in low and "pass" in low
    assert "sop_design_completed" in low or "in_progress" in low


def test_design_only_no_runtime_change() -> None:
    low = "".join(p.read_text(encoding="utf-8") for p in DOCS).lower()
    assert "no runtime change" in low
    assert "not production readiness" in low


def test_no_production_action_and_prod_exec_zero() -> None:
    for p in DOCS:
        low = p.read_text(encoding="utf-8").lower()
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


def test_step64f1_documented_in_progress() -> None:
    text = PROGRESS.read_text(encoding="utf-8")
    assert "64F.1" in text
    assert "DEPLOYMENT_MANAGEMENT_SOP_DESIGN_VERIFY" in text
