"""Step 66UI.4-FE.1C-R -- Overview Attention-first design review (docs-only checks).

This file changes no runtime code. It confirms the architecture review,
frontend implementation boundary, Codex readiness boundary, and review
record exist and state the required facts: PR #8/branch/commit, Codex
remaining unauthorized, the existing-data-only boundary, no backend/API/
database/workflow/production/external requirement, 66D/66C.4 placeholders,
no fake controls/new endpoints, the FE.1B reuse+merge-order precondition,
the /tasks usage recommendation, the agent-execution status mapping
recommendation, no runtime files changed, and a stated review result.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

REVIEW_DOCS = {
    "claude-code-architecture-review": ROOT
    / "docs"
    / "design"
    / "66ui4-fe1c-overview-attention-first"
    / "claude-code-architecture-review.md",
    "frontend-implementation-boundary": ROOT
    / "docs"
    / "contracts"
    / "66ui4-fe1c-overview-attention-first"
    / "frontend-implementation-boundary.md",
    "codex-readiness-boundary": ROOT
    / "docs"
    / "frontend"
    / "66ui4-fe1c-overview-attention-first"
    / "codex-readiness-boundary.md",
    "design-review-record": ROOT / "docs" / "test" / "step66ui4-fe1c-design-review-record.md",
}

PROGRESS = ROOT / "source" / "progress.md"


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower())


def _all_text() -> str:
    return "\n".join(p.read_text(encoding="utf-8") for p in REVIEW_DOCS.values())


def test_review_docs_exist() -> None:
    for name, p in REVIEW_DOCS.items():
        assert p.is_file(), name


def test_pr_branch_commit_referenced() -> None:
    text = _norm(_all_text())
    assert "pr #8" in text
    assert "design/66ui4-fe1c-overview-attention-first" in text
    assert "0c7762e" in text


def test_progress_references_stage() -> None:
    text = _norm(PROGRESS.read_text(encoding="utf-8"))
    assert "66ui.4-fe.1c-r" in text


def test_marker_verbatim() -> None:
    assert "STEP66UI4_FE1C_DESIGN_REVIEW_VERIFY" in _all_text()


def test_codex_unauthorized() -> None:
    text = _norm(_all_text())
    assert "codex" in text
    assert "unauthorized" in text or "not authorized" in text


def test_existing_data_only_boundary() -> None:
    text = _norm(_all_text())
    assert "existing-data-only" in text or "existing data only" in text


def test_no_backend_api_database_workflow_required() -> None:
    text = _norm(_all_text())
    for term in ("backend", "api", "database", "workflow"):
        assert re.search(rf"no [\w/]*{term}", text), term


def test_no_production_or_external_action_required() -> None:
    text = _norm(_all_text())
    assert re.search(r"no [\w/]*production action", text)
    assert re.search(r"no [\w/]*external action", text)


def test_66d_66c4_placeholders() -> None:
    text = _norm(_all_text())
    assert "66d" in text
    assert "66c.4" in text
    assert "placeholder" in text


def test_no_fake_controls_no_new_endpoints() -> None:
    text = _norm(_all_text())
    assert "no fake" in text or "fake control" in text
    assert "no new endpoint" in text or "new endpoint" in text


def test_fe1b_reuse_and_merge_order_precondition() -> None:
    text = _norm(_all_text())
    assert "fe.1b" in text
    assert "reuse" in text
    assert "merged to `main`" in text or "merged to main" in text


def test_tasks_usage_recommendation() -> None:
    text = _norm(_all_text())
    assert "/tasks" in text


def test_agent_execution_status_mapping_recommendation() -> None:
    text = _norm(_all_text())
    assert "agent-execution" in text or "agent_executions" in text
    assert "not reported" in text


def test_no_runtime_files_changed() -> None:
    result = subprocess.run(
        ["git", "diff", "--name-only", "HEAD"],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    cached = subprocess.run(
        ["git", "diff", "--name-only", "--cached"],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    changed = {
        line.strip().replace("\\", "/")
        for line in (result.stdout.splitlines() + cached.stdout.splitlines())
        if line.strip()
    }
    forbidden_prefixes = ("apps/", "services/", "infra/", "migrations/", "database/")
    forbidden = [p for p in changed if any(p.startswith(prefix) for prefix in forbidden_prefixes)]
    assert not forbidden, forbidden


def test_review_result_stated() -> None:
    text = _norm(_all_text())
    assert any(v in text for v in ("pass_with_gaps", "**pass.**", "verdict: **pass", "pass."))


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


def test_marker_pass_present() -> None:
    text = REVIEW_DOCS["design-review-record"].read_text(encoding="utf-8")
    assert "STEP66UI4_FE1C_DESIGN_REVIEW_VERIFY: PASS" in text
