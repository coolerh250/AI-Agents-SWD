"""Step 66UI.2-FE.1-FIX1-R -- Delivery Package placement remediation review (docs-only checks).

Review/validation stage: no runtime code change by this file, no backend, no
database, no workflow, no production action, no PR merge, no further Codex
authorization. Reads the reviewed frontend branch via `git show <ref>:<path>`
/ `git diff --name-only` (never checking it out or merging it) and confirms
the remediation, scope boundary, shared artifacts, review documents, and the
absence of sensitive identifiers / forbidden capability claims.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
FE_BRANCH_REF = "origin/frontend/66ui2-navigation-grouping"
FE_BRANCH_NAME = "frontend/66ui2-navigation-grouping"
EXPECTED_COMMITS = ("8fd406a", "469b980", "ce8ab2f")
FIX1_COMMIT = "ce8ab2f"
PRE_FIX1_COMMIT = "469b980"

FE_SHARED_ARTIFACTS = (
    "docs/frontend/66ui2-navigation-ia/fe1-navigation-grouping-implementation-report.md",
    "docs/frontend/66ui2-navigation-ia/fe1-open-questions-and-gaps.md",
    "docs/handoffs/66ui2-navigation-ia/codex-to-claude-code-handoff.md",
    "docs/test/step66ui2-fe1-navigation-grouping-test-report.md",
)

REVIEW_DOCS = {
    "claude-code-fe1-fix1-review": ROOT
    / "docs"
    / "frontend"
    / "66ui2-navigation-ia"
    / "claude-code-fe1-fix1-review.md",
    "fe1-fix1-review": ROOT / "docs" / "test" / "step66ui2-fe1-fix1-review.md",
}

ALLOWED_PREFIXES = (
    "apps/admin-console/",
    "docs/frontend/66ui2-navigation-ia/",
    "docs/handoffs/66ui2-navigation-ia/",
    "docs/test/step66ui2-fe1-navigation-grouping-test-report.md",
    "docs/test/step66ui2-fe1-fix1-review.md",
    "scripts/verify_step66ui2_fe1_navigation_grouping.py",
    "scripts/verify_step66ui2_fe1_fix1_review.py",
    "tests/test_step66ui2_fe1_navigation_grouping.py",
    "tests/test_step66ui2_fe1_fix1_review.py",
    "source/progress.md",
)


def _git(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args], cwd=ROOT, capture_output=True, text=True, encoding="utf-8"
    )


def _branch_available() -> bool:
    if _git("cat-file", "-e", FE_BRANCH_REF).returncode == 0:
        return True
    _git("fetch", "origin", FE_BRANCH_NAME)
    return _git("cat-file", "-e", FE_BRANCH_REF).returncode == 0


requires_fe_branch = pytest.mark.skipif(
    not _branch_available(),
    reason=f"{FE_BRANCH_REF} not resolvable locally -- run 'git fetch origin {FE_BRANCH_NAME}' first",
)


def _show(path: str) -> str:
    res = _git("show", f"{FE_BRANCH_REF}:{path}")
    assert res.returncode == 0, path
    return res.stdout


def _all_branch_shared_text() -> str:
    return "\n".join(_show(p) for p in FE_SHARED_ARTIFACTS)


def _all_review_text() -> str:
    return "\n".join(p.read_text(encoding="utf-8") for p in REVIEW_DOCS.values())


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower())


def test_review_docs_exist() -> None:
    for name, p in REVIEW_DOCS.items():
        assert p.is_file(), name


@requires_fe_branch
def test_expected_commits_present() -> None:
    for commit in EXPECTED_COMMITS:
        assert _git("cat-file", "-e", commit).returncode == 0, commit


@requires_fe_branch
def test_branch_not_merged_into_main() -> None:
    res = _git("merge-base", "--is-ancestor", FE_BRANCH_REF, "origin/main")
    assert res.returncode != 0, "frontend branch must not be merged into main before review"


@requires_fe_branch
def test_delivery_package_removed_from_deliveries_group() -> None:
    nav = _show("apps/admin-console/src/components/Nav.tsx")
    section = re.search(r'id: "deliveries".*?id: "operator-center"', nav, re.DOTALL)
    assert section is not None
    assert 'to: "/delivery-package"' not in section.group(0)
    assert 'to: "/delivery-inbox"' in section.group(0)
    assert 'to: "/delivery-detail"' in section.group(0)


@requires_fe_branch
def test_delivery_package_present_under_platform_ops() -> None:
    nav = _show("apps/admin-console/src/components/Nav.tsx")
    section = re.search(r'id: "platform-ops".*?id: "settings"', nav, re.DOTALL)
    assert section is not None
    assert 'to: "/delivery-package"' in section.group(0)


@requires_fe_branch
def test_delivery_package_route_unchanged() -> None:
    app_tsx = _show("apps/admin-console/src/App.tsx")
    assert 'path="/delivery-package"' in app_tsx


@requires_fe_branch
def test_fix1_commit_touches_no_backend_or_shared_paths() -> None:
    diff = _git("diff", "--name-only", f"{PRE_FIX1_COMMIT}..{FIX1_COMMIT}")
    changed = [line for line in diff.stdout.splitlines() if line.strip()]
    assert changed, "expected the FIX1 commit to change at least one file"
    for f in changed:
        assert not f.startswith("shared/"), f
        assert not f.startswith("migrations/"), f


@requires_fe_branch
def test_diff_stays_within_expected_scope() -> None:
    diff = _git("diff", "--name-only", f"origin/main...{FE_BRANCH_REF}")
    assert diff.returncode == 0
    changed = [line for line in diff.stdout.splitlines() if line.strip()]
    assert changed
    for f in changed:
        assert any(f.startswith(p) for p in ALLOWED_PREFIXES), f


@requires_fe_branch
def test_fe1_shared_artifacts_present_and_reference_fix1() -> None:
    for path in FE_SHARED_ARTIFACTS:
        text = _norm(_show(path))
        assert "fix1" in text, path


@requires_fe_branch
def test_untracked_proposal_file_confirmed_absent() -> None:
    diff = _git("diff", "--name-only", f"origin/main...{FE_BRANCH_REF}")
    changed = diff.stdout.splitlines()
    assert not any("platform-progress-admin-console-proposal" in f for f in changed)


@requires_fe_branch
def test_no_drag_and_drop_or_workflow_claims() -> None:
    text = _norm(_all_branch_shared_text() + _all_review_text())
    assert "dragging is allowed" not in text
    assert "workflow dispatch is enabled" not in text
    assert "workflow resume is enabled" not in text


@requires_fe_branch
def test_no_sensitive_identifiers() -> None:
    combined = _all_branch_shared_text() + _all_review_text()
    for forbidden in ("10.0.1.31", "aiagent-swd", "itadmin"):
        assert forbidden not in combined.lower()


def test_no_secret_shapes_in_review_docs() -> None:
    shapes = re.compile(
        r"(-----BEGIN [A-Z ]*PRIVATE KEY|ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|"
        r"AKIA[0-9A-Z]{16}|xoxb-[A-Za-z0-9-]{10,}|sk-ant-[A-Za-z0-9_-]{20,})"
    )
    for name, p in REVIEW_DOCS.items():
        assert not shapes.search(p.read_text(encoding="utf-8")), name


def test_review_docs_state_scope_control() -> None:
    for name, p in REVIEW_DOCS.items():
        text_low = _norm(p.read_text(encoding="utf-8"))
        assert "backend changed" in text_low, name
        assert "codex" in text_low, name


def test_review_docs_state_pr_not_merged() -> None:
    for name, p in REVIEW_DOCS.items():
        text_low = _norm(p.read_text(encoding="utf-8"))
        assert "not merged" in text_low, name


def test_review_docs_state_blocking_gap_closed() -> None:
    combined = _norm(_all_review_text())
    assert "closed" in combined


def test_marker_pass_present() -> None:
    text = REVIEW_DOCS["fe1-fix1-review"].read_text(encoding="utf-8")
    assert "STEP66UI2_FE1_FIX1_REVIEW_VERIFY: PASS" in text
