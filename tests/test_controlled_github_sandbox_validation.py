"""Step 65D -- Controlled GitHub sandbox validation (docs + posture)."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STAGING = ROOT / "docs" / "staging"
REPORT = STAGING / "controlled-github-sandbox-validation-report.md"
EVIDENCE = STAGING / "controlled-github-sandbox-validation-evidence.md"
SAFETY = STAGING / "controlled-github-sandbox-safety-record.md"
GAPS = STAGING / "controlled-github-sandbox-known-gaps.md"
PROGRESS = ROOT / "source" / "progress.md"

DOCS = (REPORT, EVIDENCE, SAFETY, GAPS)


def test_docs_exist() -> None:
    for p in DOCS:
        assert p.is_file(), p.name


def test_real_draft_pr_recorded() -> None:
    low = REPORT.read_text(encoding="utf-8").lower()
    assert "pr #15" in low or "pull/15" in low
    assert "draft" in low and "created" in low


def test_sandbox_repo_named() -> None:
    low = "".join(p.read_text(encoding="utf-8") for p in DOCS).lower()
    assert "ai-agents-swd-sandbox" in low


def test_flow_fix_and_reset_documented() -> None:
    low = "".join(p.read_text(encoding="utf-8") for p in DOCS).lower()
    assert "no commits" in low and "evidence" in low
    assert "reset" in low and "sandbox_github_live=false" in low


def test_no_merge_no_production_action() -> None:
    low = "".join(p.read_text(encoding="utf-8") for p in DOCS).lower()
    assert "no merge" in low
    for p in DOCS:
        pl = p.read_text(encoding="utf-8").lower()
        assert "no production action" in pl, p.name
        assert "production_executed_true_count=0" in pl, p.name


def test_safety_flags_present() -> None:
    for p in DOCS:
        text = p.read_text(encoding="utf-8")
        assert "production-action=false" in text
        assert "github-merge=false" in text
        assert "image-push=false" in text
        assert "production-action=true" not in text
        assert "github-merge=true" not in text


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


def test_step65d_documented_in_progress() -> None:
    text = PROGRESS.read_text(encoding="utf-8")
    assert "65D" in text
    assert "CONTROLLED_GITHUB_SANDBOX_VALIDATION_VERIFY" in text
