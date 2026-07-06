"""Step 65D-C -- 65C / 65D integration status consolidation (docs + posture)."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STAGING = ROOT / "docs" / "staging"
CONSOLIDATION = STAGING / "step65c-65d-integration-status-consolidation.md"
GAP_MAP = STAGING / "step65c-65d-gap-closure-map.md"
SAFETY = STAGING / "step65c-65d-current-safety-posture.md"
NEXT_GATES = STAGING / "step65c-65d-next-gates.md"
PROGRESS = ROOT / "source" / "progress.md"

DOCS = (CONSOLIDATION, GAP_MAP, SAFETY, NEXT_GATES)


def _all_low() -> str:
    return "\n".join(p.read_text(encoding="utf-8") for p in DOCS).lower()


def test_docs_exist() -> None:
    for p in DOCS:
        assert p.is_file(), p.name


def test_statuses_recorded() -> None:
    low = _all_low()
    assert "step 65c: pass_with_gaps" in low
    assert "step 65d: pass" in low


def test_github_validated_recorded() -> None:
    low = _all_low()
    assert "github sandbox integration: validated" in low
    assert "github sandbox token gap: resolved_by_65d" in low
    assert "pr #15" in low or "pull/15" in low


def test_notification_and_llm_pending() -> None:
    low = _all_low()
    assert "notification integration: pending_65e" in low
    assert "llm integration: pending_65f" in low
    assert "configured reference present / not yet validated" in low


def test_no_full_65dr_required() -> None:
    assert "no full 65d-r" in _all_low()


def test_no_new_external_write_claimed() -> None:
    low = _all_low()
    assert "no new external write" in low
    assert "no notification send" in low
    assert "no llm call" in low
    assert "no production action" in low
    assert "no workflow execution" in low


def test_prod_exec_zero_documented() -> None:
    low = _all_low()
    assert "production_executed_true_count=0" in low
    assert not re.search(r"production_executed_true_count\s*[`]*\s*[:=]?\s*[`]*\s*[1-9]", low)


def test_no_secret_values_stored() -> None:
    shapes = re.compile(
        r"(-----BEGIN|ghp_[A-Za-z0-9]{20,}|xoxb-[A-Za-z0-9-]{10,}|sk-ant-[A-Za-z0-9_-]{20,})"
    )
    tok = re.compile(r"(token|api[_-]?key|secret|webhook)\s*[:=]\s*[\"']?[A-Za-z0-9/+]{16,}", re.I)
    for p in DOCS:
        text = p.read_text(encoding="utf-8")
        assert not shapes.search(text), p.name
        assert not tok.search(text), p.name
        assert not re.search(r"password\s*[:=]\s*\S", text, re.IGNORECASE), p.name


def test_progress_documents_stage() -> None:
    text = PROGRESS.read_text(encoding="utf-8")
    assert "65D-C" in text
    assert "STEP65C_65D_CONSOLIDATION_VERIFY" in text
