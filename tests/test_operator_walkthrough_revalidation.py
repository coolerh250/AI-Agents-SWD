"""Step 64E-R -- operator walkthrough revalidation / status correction (docs)."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STAGING = ROOT / "docs" / "staging"
REPORT = STAGING / "operator-walkthrough-validation-report.md"
FORM = STAGING / "operator-walkthrough-confirmation-form.md"
NOTES = STAGING / "operator-walkthrough-revalidation-notes.md"
ROADMAP = STAGING / "staging-step64-roadmap.md"
PROGRESS = ROOT / "source" / "progress.md"

DOCS = (REPORT, FORM, NOTES)
CORRECTED = "PASS_WITH_OPERATOR_VALIDATION_PENDING"


def test_revalidation_docs_exist() -> None:
    for p in DOCS:
        assert p.is_file(), p.name


def test_operator_confirmation_form_exists() -> None:
    assert FORM.is_file()
    assert "Confirmed: yes / no / not checked" in FORM.read_text(encoding="utf-8")


def test_step64e_corrected_status() -> None:
    assert CORRECTED in REPORT.read_text(encoding="utf-8")


def test_operator_validation_remains_pending() -> None:
    low = REPORT.read_text(encoding="utf-8").lower()
    assert "pending" in low
    assert "document completeness" in low and "pass" in low


def test_step64f_paused_pending_operator_validation() -> None:
    low = "".join(p.read_text(encoding="utf-8") for p in DOCS).lower()
    assert "step 64f" in low
    assert "pause" in low or "paused" in low or "should not proceed" in low


def test_self_confirmation_forbidden() -> None:
    low = "".join(p.read_text(encoding="utf-8") for p in DOCS).lower()
    assert "cannot self-confirm" in low or "cannot self confirm" in low


def test_no_doc_marks_step64e_full_pass() -> None:
    for p in DOCS:
        for line in p.read_text(encoding="utf-8").splitlines():
            ll = line.lower()
            if "overall" in ll and "step 64e" in ll and "pass" in ll:
                negation = " not " in ll or "not full" in ll or "must not" in ll
                if not negation:
                    assert "pass_with_operator_validation_pending" in ll, line


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


def test_step64er_documented() -> None:
    assert "64E-R" in ROADMAP.read_text(encoding="utf-8")
    prog = PROGRESS.read_text(encoding="utf-8")
    assert "64E-R" in prog
    assert "OPERATOR_WALKTHROUGH_REVALIDATION_VERIFY" in prog
