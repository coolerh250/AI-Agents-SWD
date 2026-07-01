"""Step 64E -- operator walkthrough SOP (docs, non-production only)."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STAGING = ROOT / "docs" / "staging"

SOP = STAGING / "operator-walkthrough-sop.md"
NAV = STAGING / "operator-admin-console-navigation-guide.md"
DEMO = STAGING / "operator-demo-workflow-review-guide.md"
SAFETY = STAGING / "operator-safety-check-guide.md"
GAPS = STAGING / "operator-known-gaps-and-limitations.md"
DONOT = STAGING / "operator-do-not-execute-list.md"
TROUBLE = STAGING / "operator-access-troubleshooting.md"
ACCEPT = STAGING / "operator-acceptance-checklist.md"
PROGRESS = ROOT / "source" / "progress.md"

DOCS = (SOP, NAV, DEMO, SAFETY, GAPS, DONOT, TROUBLE, ACCEPT)


def test_operator_sop_docs_exist() -> None:
    for p in DOCS:
        assert p.is_file(), p.name


def test_ssh_tunnel_documented() -> None:
    both = "".join(p.read_text(encoding="utf-8") for p in DOCS)
    assert "-L 18000:127.0.0.1:18000" in both


def test_operator_url_documented() -> None:
    both = "".join(p.read_text(encoding="utf-8") for p in DOCS).lower()
    assert "localhost:18000/admin" in both


def test_admin_console_navigation_documented() -> None:
    assert "admin console" in NAV.read_text(encoding="utf-8").lower()


def test_demo_workflow_review_documented() -> None:
    both = "".join(p.read_text(encoding="utf-8") for p in DOCS)
    assert "SaaS User Management Module" in both
    assert "Create user CRUD API" in both


def test_safety_check_documented() -> None:
    assert "production_executed_true_count" in SAFETY.read_text(encoding="utf-8")


def test_known_gaps_documented() -> None:
    low = GAPS.read_text(encoding="utf-8").lower()
    assert "yaml" in low
    assert "gated" in low or "operator auth" in low


def test_do_not_execute_list_documented() -> None:
    low = DONOT.read_text(encoding="utf-8").lower()
    assert "production deploy" in low
    assert "down -v" in low


def test_acceptance_checklist_documented() -> None:
    assert "- [ ]" in ACCEPT.read_text(encoding="utf-8")


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


def test_step64e_documented_in_progress() -> None:
    text = PROGRESS.read_text(encoding="utf-8")
    assert "64E" in text
    assert "OPERATOR_WALKTHROUGH_SOP_VERIFY" in text
