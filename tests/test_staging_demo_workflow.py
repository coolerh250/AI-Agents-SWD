"""Step 64D -- staging demo workflow (docs, non-production only)."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STAGING = ROOT / "docs" / "staging"
REPORT = STAGING / "staging-demo-workflow-execution-report.md"
SEED = STAGING / "staging-demo-seed-data.md"
CONSOLE = STAGING / "staging-demo-admin-console-evidence.md"
AUDIT = STAGING / "staging-demo-audit-evidence.md"
DELIVERY = STAGING / "staging-demo-delivery-evidence.md"
GAPS = STAGING / "staging-demo-known-gaps.md"
PROGRESS = ROOT / "source" / "progress.md"

DOCS = (REPORT, SEED, CONSOLE, AUDIT, DELIVERY, GAPS)


def test_demo_docs_exist() -> None:
    for p in DOCS:
        assert p.is_file(), p.name


def test_demo_project_documented() -> None:
    both = "".join(p.read_text(encoding="utf-8") for p in DOCS)
    assert "SaaS User Management Module" in both


def test_demo_work_item_documented() -> None:
    both = "".join(p.read_text(encoding="utf-8") for p in DOCS)
    assert "Create user CRUD API" in both


def test_admin_console_evidence_documented() -> None:
    text = CONSOLE.read_text(encoding="utf-8").lower()
    assert "admin console" in text
    assert "/operations/" in CONSOLE.read_text(encoding="utf-8")


def test_audit_evidence_documented() -> None:
    assert "work_item_created" in AUDIT.read_text(encoding="utf-8")


def test_delivery_evidence_or_gap_documented() -> None:
    text = DELIVERY.read_text(encoding="utf-8").lower()
    assert "delivery" in text
    assert "gap" in text or "gated" in text or "package" in text


def test_live_integrations_disabled() -> None:
    for p in DOCS:
        assert "live-integrations=disabled" in p.read_text(encoding="utf-8")


def test_no_production_action_allowed() -> None:
    for p in DOCS:
        text = p.read_text(encoding="utf-8")
        assert "production-action=false" in text
        assert "production-ready=false" in text
        assert "production-action=true" not in text
        assert "production-ready=true" not in text


def test_no_secret_values_stored() -> None:
    for p in DOCS:
        text = p.read_text(encoding="utf-8")
        assert "-----BEGIN" not in text
        assert "p@ssw0rd" not in text
        assert not re.search(r"password\s*[:=]\s*\S", text, re.IGNORECASE)


def test_step64d_documented_in_progress() -> None:
    text = PROGRESS.read_text(encoding="utf-8")
    assert "64D" in text
    assert "STAGING_DEMO_WORKFLOW_VERIFY" in text
