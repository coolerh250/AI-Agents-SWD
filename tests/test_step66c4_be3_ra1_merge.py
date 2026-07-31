"""Step 66C.4-BE3-RA-1M -- RA-1 migration-readiness-foundation merge verification tests.

Independently re-derives the merge-shape, ancestry, and safety-posture claims for the controlled
merge of Draft PR #21 into canonical main -- git/gh state only, no shared database, no deployment,
no runtime service. Complements (does not merely invoke) scripts/verify_step66c4_be3_ra1_merge.py.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

SOT = (
    ROOT
    / "docs"
    / "contracts"
    / "66c4-reminder-expiry-controlled-resume"
    / "be3-ra1-merge-source-of-truth.md"
)
EVIDENCE = ROOT / "docs" / "test" / "step66c4-be3-ra1-merge-evidence.md"
RESUME_MODEL = ROOT / "shared" / "sdk" / "tasks" / "resume_request_model.py"
REPLAY_MODEL = ROOT / "shared" / "sdk" / "tasks" / "replay_request_model.py"
MIGRATIONS = ROOT / "migrations"
VERIFY_SCRIPT = ROOT / "scripts" / "verify_step66c4_be3_ra1_merge.py"

PRE_MERGE_MAIN = "18f11fe"
FEATURE_HEAD = "97e56d4"
REVIEW_HEAD = "1f3a66f"
MERGE_COMMIT = "48004e3"
EVIDENCE_COMMITS = ("352d546", "9cd841f", "800035b", "1f3a66f")
INTEGRATION_ONLY_COMMITS = ("19cff82", "07f839f", "7c6b830")


def _git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True)


def _is_ancestor(commit: str, ref: str) -> bool:
    return _git("merge-base", "--is-ancestor", commit, ref).returncode == 0


@pytest.fixture(scope="module")
def sot_text() -> str:
    return SOT.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def evidence_text() -> str:
    return EVIDENCE.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def progress_text() -> str:
    return (ROOT / "source" / "progress.md").read_text(encoding="utf-8")


def test_merge_commit_has_two_parents_in_order() -> None:
    result = _git("show", "--no-patch", "--format=%P", MERGE_COMMIT)
    assert result.returncode == 0, result.stderr
    parents = result.stdout.strip().split()
    assert len(parents) == 2, f"expected exactly two parents, got {parents}"
    assert parents[0].startswith(PRE_MERGE_MAIN), parents[0]
    assert parents[1].startswith(FEATURE_HEAD), parents[1]


def test_feature_head_is_main_ancestor() -> None:
    assert _is_ancestor(FEATURE_HEAD, "origin/main")


def test_review_head_not_main_ancestor() -> None:
    assert not _is_ancestor(REVIEW_HEAD, "origin/main")


@pytest.mark.parametrize("commit", INTEGRATION_ONLY_COMMITS)
def test_integration_only_commits_not_main_ancestors(commit: str) -> None:
    assert not _is_ancestor(commit, "origin/main")


@pytest.mark.parametrize("commit", EVIDENCE_COMMITS)
def test_evidence_commits_exist(commit: str) -> None:
    result = _git("cat-file", "-e", f"{commit}^{{commit}}")
    assert result.returncode == 0, f"{commit} does not exist"


def test_pr21_state_merged_with_matching_commit() -> None:
    result = subprocess.run(
        ["gh", "pr", "view", "21", "--json", "state,mergeCommit,headRefOid"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        pytest.skip("gh CLI unavailable or unauthenticated in this environment")
    payload = json.loads(result.stdout)
    assert payload["state"] == "MERGED"
    assert payload["mergeCommit"]["oid"].startswith(MERGE_COMMIT)
    assert payload["headRefOid"].startswith(FEATURE_HEAD)


def test_source_of_truth_records_final_verdict_pass(sot_text: str) -> None:
    assert "RA1_TECHNICAL_VERDICT: PASS" in sot_text


@pytest.mark.parametrize("finding", ["H-1", "M-1", "M-2A", "M-2B", "M-3A", "M-3B"])
def test_source_of_truth_records_finding_closed(sot_text: str, finding: str) -> None:
    assert re.search(rf"{re.escape(finding)}\s+CLOSED", sot_text)


@pytest.mark.parametrize("version", ["031", "032", "033", "034", "035"])
def test_migration_file_present_on_main(version: str) -> None:
    assert list(MIGRATIONS.glob(f"{version}_*.sql")), f"migration {version} not found"


def test_source_of_truth_states_migrations_not_applied(sot_text: str) -> None:
    assert "NOT APPLIED" in sot_text


def test_resume_feature_gates_default_false() -> None:
    src = RESUME_MODEL.read_text(encoding="utf-8")
    assert 'os.environ.get("BE3_RESUME_API_ENABLED", "false")' in src
    assert 'os.environ.get("BE3_RESUME_COMMAND_ENABLED", "false")' in src


def test_replay_feature_gates_default_false() -> None:
    src = REPLAY_MODEL.read_text(encoding="utf-8")
    assert 'os.environ.get("BE3_REPLAY_API_ENABLED", "false")' in src
    assert 'os.environ.get("BE3_REPLAY_EXECUTION_ENABLED", "false")' in src


def test_source_of_truth_states_not_deployed_not_activated(sot_text: str) -> None:
    assert "NOT DEPLOYED" in sot_text
    assert "NOT ACTIVATED" in sot_text


def test_no_worker_relay_consumer_started(sot_text: str) -> None:
    assert "none started" in sot_text.lower()


def test_no_runtime_resume_replay_dispatch_executed(sot_text: str) -> None:
    assert "none executed" in sot_text.lower()


@pytest.mark.parametrize("gate", ["Gate 1", "Gate 2", "Gate 6"])
def test_gates_pending_runtime_shared_execution(sot_text: str, gate: str) -> None:
    assert f"{gate} -- PENDING RUNTIME/SHARED EXECUTION" in sot_text


def test_ra2_not_authorized(sot_text: str) -> None:
    assert "RA-2: NOT AUTHORIZED" in sot_text


def test_production_executed_true_count_zero(sot_text: str, progress_text: str) -> None:
    assert "production_executed_true_count:      0" in sot_text or (
        "production_executed_true_count: 0" in sot_text
    )
    assert "production_executed_true_count: 0" in progress_text


def test_verifier_script_passes() -> None:
    result = subprocess.run(
        [sys.executable, str(VERIFY_SCRIPT)], cwd=ROOT, capture_output=True, text=True
    )
    assert "STEP66C4_BE3_RA1_MERGE_VERIFY: PASS" in result.stdout, result.stdout + result.stderr
    assert result.returncode == 0
