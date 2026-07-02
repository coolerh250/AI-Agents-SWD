"""Step 64E.4C -- Product UI staging redeploy (docs + posture)."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STAGING = ROOT / "docs" / "staging"
REPORT = STAGING / "product-ui-staging-redeploy-report.md"
TECH = STAGING / "product-ui-staging-technical-validation.md"
EVIDENCE = STAGING / "product-ui-formal-page-staging-evidence.md"
INSTRUCTIONS = STAGING / "product-ui-operator-rereview-instructions.md"
GAPS = STAGING / "product-ui-staging-known-gaps.md"
PROGRESS = ROOT / "source" / "progress.md"

DOCS = (REPORT, TECH, EVIDENCE, INSTRUCTIONS, GAPS)
ITEMS = ("wi-0001", "agent execution", "workflow", "qa", "audit", "safety")


def test_redeploy_docs_exist() -> None:
    for p in DOCS:
        assert p.is_file(), p.name


def test_technical_validation_recorded() -> None:
    low = TECH.read_text(encoding="utf-8").lower()
    assert "/health" in low and "/admin" in low and "/operations/safety" in low


def test_formal_page_staging_evidence_addresses_all_types() -> None:
    low = EVIDENCE.read_text(encoding="utf-8").lower()
    for term in ITEMS:
        assert term in low, term


def test_operator_rereview_instructions_present() -> None:
    low = INSTRUCTIONS.read_text(encoding="utf-8").lower()
    assert "re-review" in low
    assert "/admin" in low


def test_step64e_not_marked_pass() -> None:
    for p in DOCS:
        for line in p.read_text(encoding="utf-8").splitlines():
            ll = line.lower()
            if "step 64e" in ll and "overall" in ll and "pass" in ll and "step 64e.4" not in ll:
                assert "failed" in ll or " not " in ll or "pending" in ll, line


def test_step64f_blocked() -> None:
    low = "".join(p.read_text(encoding="utf-8") for p in DOCS).lower()
    assert "step 64f" in low and "block" in low


def test_demo_evidence_diagnostic_only() -> None:
    low = "".join(p.read_text(encoding="utf-8") for p in DOCS).lower()
    assert "diagnostic" in low
    assert "not an acceptance path" in low


def test_no_production_action_image_push_or_volume_deletion() -> None:
    combined = "".join(p.read_text(encoding="utf-8") for p in DOCS).lower()
    assert "no image push" in combined
    assert "no volume deletion" in combined or "no volume delete" in combined
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


def test_step64e4c_documented_in_progress() -> None:
    text = PROGRESS.read_text(encoding="utf-8")
    assert "64E.4C" in text
    assert "PRODUCT_UI_STAGING_REDEPLOY_VERIFY" in text
