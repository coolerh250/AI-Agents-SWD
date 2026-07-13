"""Step 66UI.1-R -- Claude Design Full UI/UX Redesign Options review (docs-only checks).

Review/architecture stage: no runtime code, no backend, no frontend
implementation change, no design PR merge. This file follows the repo's
tests/test_stepNN_*.py convention. It reads the reviewed design branch via
`git show <ref>:<path>` (never checking it out or merging it) and confirms
the required decisions, the 3 review documents, and the absence of
sensitive identifiers / forbidden capability claims.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DESIGN_BRANCH_REF = "origin/design/66ui-full-redesign-options"
DESIGN_BRANCH_NAME = "design/66ui-full-redesign-options"
DESIGN_DOC_DIR = "docs/design/66ui-full-redesign-options"
EXPECTED_COMMITS = ("bc6c5b3", "00d1191")

DESIGN_FILES = (
    "design-objective.md",
    "feature-categorization.md",
    "layout-comparison.md",
    "layout-option-1-operations-command-center.md",
    "layout-option-2-task-workspace.md",
    "layout-option-3-lifecycle-pipeline.md",
    "product-owner-decision-summary.md",
    "product-owner-discussion-guide.md",
    "recommendation.md",
    "user-role-journey-map.md",
)

REVIEW_DOCS = {
    "architecture-review": ROOT / DESIGN_DOC_DIR / "claude-code-architecture-review.md",
    "frontend-implementation-boundary": ROOT
    / "docs"
    / "contracts"
    / "66ui-full-redesign-options"
    / "frontend-implementation-boundary.md",
    "codex-readiness-boundary": ROOT
    / "docs"
    / "frontend"
    / "66ui-full-redesign-options"
    / "codex-readiness-boundary.md",
}


def _git(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args], cwd=ROOT, capture_output=True, text=True, encoding="utf-8"
    )


def _branch_available() -> bool:
    if _git("cat-file", "-e", DESIGN_BRANCH_REF).returncode == 0:
        return True
    _git("fetch", "origin", DESIGN_BRANCH_NAME)
    return _git("cat-file", "-e", DESIGN_BRANCH_REF).returncode == 0


requires_design_branch = pytest.mark.skipif(
    not _branch_available(),
    reason=f"{DESIGN_BRANCH_REF} not resolvable locally -- run "
    f"'git fetch origin {DESIGN_BRANCH_NAME}' first",
)


def _show(path: str) -> str:
    res = _git("show", f"{DESIGN_BRANCH_REF}:{DESIGN_DOC_DIR}/{path}")
    assert res.returncode == 0, path
    return res.stdout


def _all_design_text() -> str:
    return "\n".join(_show(name) for name in DESIGN_FILES)


def _all_review_text() -> str:
    return "\n".join(p.read_text(encoding="utf-8") for p in REVIEW_DOCS.values())


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower())


def test_review_docs_exist() -> None:
    for name, p in REVIEW_DOCS.items():
        assert p.is_file(), name


@requires_design_branch
def test_all_10_design_files_present() -> None:
    for name in DESIGN_FILES:
        _show(name)  # asserts inside _show


@requires_design_branch
def test_hybrid_decision_recorded() -> None:
    assert "hybrid" in _norm(_show("product-owner-decision-summary.md"))
    assert "hybrid" in _norm(_show("product-owner-discussion-guide.md"))


@requires_design_branch
def test_category_h_included_as_platform_ops_grouping_only() -> None:
    text = _norm(_show("product-owner-decision-summary.md"))
    assert "category h" in text
    assert "platform ops" in text
    assert "grouping only" in text


@requires_design_branch
def test_delivery_deferred_to_66d() -> None:
    text = _norm(_show("product-owner-decision-summary.md"))
    assert "not merged yet" in text or "not merged" in text
    assert "66d" in text


@requires_design_branch
def test_pipeline_is_read_only_and_deferred() -> None:
    text = _norm(_show("product-owner-decision-summary.md"))
    assert "read-only" in text
    assert "drag" in text


@requires_design_branch
def test_no_drag_and_drop_state_mutation_claimed() -> None:
    text = _norm(_all_design_text())
    assert "dragging is allowed" not in text
    assert "drag and drop is enabled" not in text


@requires_design_branch
def test_design_branch_touches_no_runtime_path() -> None:
    diff = _git("diff", "--name-only", f"{EXPECTED_COMMITS[0]}~1", EXPECTED_COMMITS[1])
    assert diff.returncode == 0
    changed = [line for line in diff.stdout.splitlines() if line.strip()]
    assert changed, "expected at least one changed file"
    for f in changed:
        assert f.startswith(f"{DESIGN_DOC_DIR}/"), f


@requires_design_branch
def test_no_sensitive_identifiers_in_reviewed_content() -> None:
    combined = _all_design_text() + _all_review_text()
    for forbidden in ("10.0.1.31", "aiagent-swd", "itadmin"):
        assert forbidden not in combined.lower()


def test_no_secret_shapes_in_review_docs() -> None:
    shapes = re.compile(
        r"(-----BEGIN [A-Z ]*PRIVATE KEY|ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|"
        r"AKIA[0-9A-Z]{16}|xoxb-[A-Za-z0-9-]{10,}|sk-ant-[A-Za-z0-9_-]{20,})"
    )
    for name, p in REVIEW_DOCS.items():
        assert not shapes.search(p.read_text(encoding="utf-8")), name


def test_review_docs_state_no_runtime_code_changed() -> None:
    for name, p in REVIEW_DOCS.items():
        assert "no runtime code changed" in _norm(p.read_text(encoding="utf-8")), name


def test_review_docs_reference_codex_authorization_boundary() -> None:
    for name, p in REVIEW_DOCS.items():
        assert "codex" in p.read_text(encoding="utf-8").lower(), name


def test_architecture_review_pass_verdict() -> None:
    text = REVIEW_DOCS["architecture-review"].read_text(encoding="utf-8")
    assert "PASS" in text
