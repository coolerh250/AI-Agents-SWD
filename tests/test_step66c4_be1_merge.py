"""Step 66C.4-BE1-M -- merge and technical-closure record tests.

Static tests over committed merge artifacts and the post-merge repository state. No DB, no network,
no shared runtime. They assert the merge was a non-squash merge commit, that both technical verdicts
are preserved and kept separate from review process markers, and that no runtime activation or
deployment was introduced.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
CONTRACT = REPO / "docs" / "contracts" / "66c4-reminder-expiry-controlled-resume"

MERGE_REC = CONTRACT / "be1-merge-record.md"
CLOSURE_REC = CONTRACT / "be1-technical-closure-record.md"
SOT_REC = CONTRACT / "be1-source-of-truth-record.md"
DEFERRED = CONTRACT / "be1-deferred-low-findings.md"

REVIEWED_HEAD = "0bb9944"
PRE_MERGE_MAIN = "e03c22d"
MERGE_COMMIT = "8080141"


def _git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=REPO, capture_output=True, text=True).stdout.strip()


def test_merge_record_records_all_commits_and_non_squash() -> None:
    t = MERGE_REC.read_text(encoding="utf-8")
    for c in (REVIEWED_HEAD, PRE_MERGE_MAIN, MERGE_COMMIT, "d2467f5", "f5417f4", "2e1c369"):
        assert c in t, c
    assert "non-squash" in t.lower()


def test_merge_commit_is_two_parent_merge_of_main_and_reviewed_head() -> None:
    parents = _git("rev-list", "--parents", "-n", "1", MERGE_COMMIT).split()
    assert len(parents) == 3, parents
    assert parents[1].startswith(PRE_MERGE_MAIN)
    assert parents[2].startswith(REVIEWED_HEAD)


def test_both_verdicts_preserved_and_separate() -> None:
    closure = CLOSURE_REC.read_text(encoding="utf-8")
    assert "BE1_TECHNICAL_VERDICT: REMEDIATION_REQUIRED" in closure
    assert "BE1_TECHNICAL_VERDICT: PASS" in closure
    merge = MERGE_REC.read_text(encoding="utf-8")
    # A review PROCESS marker is recorded, not conflated with a technical verdict.
    assert "STEP66C4_BE1_INDEPENDENT_REVIEW_VERIFY: PASS" in merge
    assert "STEP66C4_BE1_R1_INDEPENDENT_CLOSURE_REVIEW_VERIFY: PASS" in merge


def test_deferred_low_finding_not_lost() -> None:
    closure = CLOSURE_REC.read_text(encoding="utf-8").lower()
    assert "deferred" in closure and "already answered" in closure
    assert DEFERRED.is_file()


def test_source_of_truth_states_runtime_not_deployed() -> None:
    t = SOT_REC.read_text(encoding="utf-8")
    assert "due_at > statement_timestamp()" in t
    assert "NOT DEPLOYED" in t and "NOT RUNTIME VALIDATED" in t
    for col in ("available_at", "dead_at", "last_error"):
        assert col in t, col


def test_be1_implementation_present_on_main() -> None:
    head = _git("rev-parse", "HEAD")
    for f in (
        "migrations/031_clarification_lifecycle_outbox_foundation.sql",
        "shared/sdk/tasks/lifecycle_outbox.py",
    ):
        assert _git("cat-file", "-t", f"{head}:{f}") == "blob", f


def test_merge_introduced_no_deployment_change() -> None:
    changed = _git(
        "diff",
        "--name-only",
        f"{PRE_MERGE_MAIN}..{MERGE_COMMIT}",
        "--",
        "infra",
        "helm",
        "k8s",
        ".github/workflows",
    )
    assert changed == "", changed


def test_deadline_predicate_on_main_is_statement_time() -> None:
    store = (REPO / "shared" / "sdk" / "tasks" / "workroom_store.py").read_text(encoding="utf-8")
    assert "due_at > statement_timestamp()" in store
    assert "due_at > now()" not in store
    assert "answered_at=statement_timestamp()" in store


def test_no_live_outbox_producer_on_main() -> None:
    outbox_path = REPO / "shared" / "sdk" / "tasks" / "lifecycle_outbox.py"
    offenders = []
    for base in (REPO / "apps", REPO / "shared"):
        for path in base.rglob("*.py"):
            if path == outbox_path or "__pycache__" in str(path):
                continue
            txt = path.read_text(encoding="utf-8", errors="ignore")
            if "lifecycle_outbox" in txt or "clarification_lifecycle_outbox" in txt:
                offenders.append(str(path.relative_to(REPO)))
    assert offenders == [], offenders


def test_review_evidence_branches_preserved() -> None:
    for br in (
        "review/66c4-be1-technical-security-migration",
        "review/66c4-be1-r1-remediation-closure",
    ):
        assert _git("rev-parse", "--verify", f"origin/{br}"), br
