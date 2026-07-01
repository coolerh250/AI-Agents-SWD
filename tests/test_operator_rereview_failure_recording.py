"""Step 64E.2 -- operator re-review failure recording (docs, non-production only)."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STAGING = ROOT / "docs" / "staging"
RESULT = STAGING / "operator-rereview-result-after-react-bundle-remediation.md"
BLOCKER = STAGING / "admin-console-demo-evidence-ui-blocker.md"
STATUS = STAGING / "step64e-current-blocker-status.md"
PROGRESS = ROOT / "source" / "progress.md"

DOCS = (RESULT, BLOCKER, STATUS)


def test_rereview_failure_docs_exist() -> None:
    for p in DOCS:
        assert p.is_file(), p.name


def test_not_usable_verdict_documented() -> None:
    low = "".join(p.read_text(encoding="utf-8") for p in DOCS).lower()
    assert "not_usable" in low or "not usable" in low


def test_five_missing_visibility_items_documented() -> None:
    low = RESULT.read_text(encoding="utf-8").lower()
    assert "wi-0001" in low
    for term in ("agent execution", "workflow", "qa", "audit"):
        assert term in low, term
    assert low.count("no") >= 5


def test_step64e_failed_documented() -> None:
    low = "".join(p.read_text(encoding="utf-8") for p in DOCS).lower()
    assert "failed_operator_validation" in low


def test_step64f_blocked_documented() -> None:
    low = "".join(p.read_text(encoding="utf-8") for p in DOCS).lower()
    assert "step 64f" in low
    assert "block" in low


def test_next_remediation_documented() -> None:
    low = "".join(p.read_text(encoding="utf-8") for p in DOCS).lower()
    assert "demo evidence ui" in low or "demo-evidence ui" in low


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


def test_step64e2_documented_in_progress() -> None:
    text = PROGRESS.read_text(encoding="utf-8")
    assert "64E.2" in text
    assert "OPERATOR_REREVIEW_FAILURE_RECORDING_VERIFY" in text
