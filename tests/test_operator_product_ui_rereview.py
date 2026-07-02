"""Step 64E.4D -- Operator product UI re-review recording (docs + posture)."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STAGING = ROOT / "docs" / "staging"
RESULT = STAGING / "operator-product-ui-rereview-result.md"
RECORD = STAGING / "product-ui-staging-operator-acceptance-record.md"
GAPS = STAGING / "product-ui-accepted-gaps.md"
PROGRESS = ROOT / "source" / "progress.md"

DOCS = (RESULT, RECORD, GAPS)
OPERATOR_STATEMENT = "正式頁面都能呈現必要 evidence"
PAGES = (
    "projects / work items",
    "agent executions",
    "workflows / task graph",
    "qa / code",
    "audit / evidence",
    "safety center",
)


def test_docs_exist() -> None:
    for p in DOCS:
        assert p.is_file(), p.name


def test_operator_verdict_pass_recorded() -> None:
    low = "".join(p.read_text(encoding="utf-8") for p in DOCS).lower()
    assert "operator verdict: pass" in low


def test_acceptance_tied_to_operator_statement() -> None:
    both = "".join(p.read_text(encoding="utf-8") for p in DOCS)
    assert OPERATOR_STATEMENT in both


def test_formal_page_checklist_all_pass() -> None:
    lines = [ln.lower() for ln in RECORD.read_text(encoding="utf-8").splitlines()]
    for page in PAGES:
        assert any(page in ln and "pass" in ln for ln in lines), page


def test_diagnostics_not_acceptance_path() -> None:
    low = "".join(p.read_text(encoding="utf-8") for p in DOCS).lower()
    assert "not used as" in low or "not an acceptance path" in low
    assert "diagnostic" in low


def test_status_transition_recorded() -> None:
    low = "".join(p.read_text(encoding="utf-8") for p in DOCS).lower()
    assert "step 64e: pass" in low or "step 64e result: pass" in low
    assert "ready_to_resume" in low
    assert "production_executed_true_count=0" in low


def test_no_production_action_or_image_push() -> None:
    combined = "".join(p.read_text(encoding="utf-8") for p in DOCS).lower()
    assert "no image push" in combined
    for p in DOCS:
        assert "no production action" in p.read_text(encoding="utf-8").lower(), p.name


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


def test_step64e4d_documented_in_progress() -> None:
    text = PROGRESS.read_text(encoding="utf-8")
    assert "64E.4D" in text
    assert "OPERATOR_PRODUCT_UI_REREVIEW_VERIFY" in text
