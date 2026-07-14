"""Step 66UI.4-R -- Phase 1 Product Visual Language design review (docs-only checks).

Review stage: this file itself changes no runtime code. It confirms the four
required review docs exist and state the required facts: the Product Owner
Hybrid decision, Delivery Package placement, Codex authorization status, and
absence of any runtime/backend/API/database/workflow/production/external
claim.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

REVIEW_DOCS = {
    "architecture-review": ROOT
    / "docs"
    / "design"
    / "66ui4-phase1-product-visual-language"
    / "claude-code-architecture-review.md",
    "frontend-implementation-boundary": ROOT
    / "docs"
    / "contracts"
    / "66ui4-phase1-product-visual-language"
    / "frontend-implementation-boundary.md",
    "codex-readiness-boundary": ROOT
    / "docs"
    / "frontend"
    / "66ui4-phase1-product-visual-language"
    / "codex-readiness-boundary.md",
    "design-pr-source-of-truth-review": ROOT
    / "docs"
    / "design"
    / "66ui4-phase1-product-visual-language"
    / "design-pr-source-of-truth-review.md",
}


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower())


def _all_text() -> str:
    return "\n".join(p.read_text(encoding="utf-8") for p in REVIEW_DOCS.values())


def test_review_docs_exist() -> None:
    for name, p in REVIEW_DOCS.items():
        assert p.is_file(), name


def test_hybrid_decision_recorded() -> None:
    text = _norm(_all_text())
    assert "hybrid" in text
    assert "direction a" in text
    assert "direction b" in text


def test_delivery_package_under_platform_ops() -> None:
    text = _norm(_all_text())
    assert "delivery package" in text
    assert "platform ops" in text


def test_codex_not_yet_authorized() -> None:
    text = _norm(_all_text())
    assert "not authorized" in text or "not yet authorized" in text
    assert "66d" in text


def test_no_runtime_or_backend_change_claimed() -> None:
    for name, p in REVIEW_DOCS.items():
        if name == "design-pr-source-of-truth-review":
            continue
        text = _norm(p.read_text(encoding="utf-8"))
        assert "no runtime code" in text
        assert "no backend" in text or "backend impact: none" in text


def test_no_production_or_external_action_claimed() -> None:
    text = _norm(_all_text())
    assert "no production action" in text
    assert "external action" in text


def test_no_pr_merged() -> None:
    text = _norm(_all_text())
    assert "no pr merged" in text or "not merged" in text


def test_frontend_only_scoping() -> None:
    text = _norm(_all_text())
    assert "frontend-only" in text


def test_source_of_truth_recommendations_present() -> None:
    text = _norm(REVIEW_DOCS["design-pr-source-of-truth-review"].read_text(encoding="utf-8"))
    assert "pr #1" in text
    assert "pr #2" in text
    assert "pr #4" in text
    assert "pr #5" in text
    assert "superseded" in text


def test_no_secret_shapes() -> None:
    shapes = re.compile(
        r"(-----BEGIN [A-Z ]*PRIVATE KEY|ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|"
        r"AKIA[0-9A-Z]{16}|xoxb-[A-Za-z0-9-]{10,}|sk-ant-[A-Za-z0-9_-]{20,})"
    )
    for name, p in REVIEW_DOCS.items():
        assert not shapes.search(p.read_text(encoding="utf-8")), name


def test_no_sensitive_identifiers() -> None:
    text = _all_text().lower()
    for forbidden in ("10.0.1.31", "aiagent-swd", "itadmin"):
        assert forbidden not in text


def test_verdict_pass_present() -> None:
    text = REVIEW_DOCS["architecture-review"].read_text(encoding="utf-8")
    assert "**PASS.**" in text or "PASS." in text
