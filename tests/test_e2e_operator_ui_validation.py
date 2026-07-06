"""Step 65G.2-V -- E2E operator UI validation record (docs + posture)."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STAGING = ROOT / "docs" / "staging"
RECORD = STAGING / "e2e-staging-operator-ui-validation-record.md"
PROGRESS = ROOT / "source" / "progress.md"


def _low() -> str:
    return RECORD.read_text(encoding="utf-8").lower()


def test_record_exists() -> None:
    assert RECORD.is_file()


def test_visible_documented() -> None:
    assert re.search(r"operator response:\s*\**\s*visible", _low())


def test_step_65g2_pass_documented() -> None:
    low = _low()
    assert "step 65g.2 final status: pass" in low or "step 65g.2: **pass**" in low


def test_formal_evidence_path_documented() -> None:
    low = _low()
    assert "operator_visible" in low
    assert "not used as the acceptance path" in low or "demo evidence was not used" in low


def test_no_new_external_actions_claimed() -> None:
    low = _low()
    assert "no new external action" in low
    for phrase in ("no workflow execution", "no github write", "no discord send", "no llm call"):
        assert phrase in low, phrase


def test_no_production_action() -> None:
    assert "no production action" in _low()


def test_fresh_e2e_resolved() -> None:
    low = _low()
    assert "fresh e2e" in low
    assert "resolved" in low or "validated" in low


def test_no_secret_values_stored() -> None:
    text = RECORD.read_text(encoding="utf-8")
    shapes = re.compile(
        r"(-----BEGIN|ghp_[A-Za-z0-9]{20,}|xoxb-[A-Za-z0-9-]{10,}|sk-ant-[A-Za-z0-9_-]{20,})"
    )
    tok = re.compile(r"(token|api[_-]?key|secret|webhook)\s*[:=]\s*[\"']?[A-Za-z0-9/+]{16,}", re.I)
    assert not shapes.search(text)
    assert not tok.search(text)
    assert not re.search(r"password\s*[:=]\s*\S", text, re.IGNORECASE)


def test_prod_exec_zero_documented() -> None:
    low = _low()
    assert "production_executed_true_count=0" in low
    assert not re.search(r"production_executed_true_count\s*[`]*\s*[:=]?\s*[`]*\s*[1-9]", low)


def test_progress_documents_stage() -> None:
    text = PROGRESS.read_text(encoding="utf-8")
    assert "65G.2-V" in text
    assert "E2E_OPERATOR_UI_VALIDATION_VERIFY" in text
