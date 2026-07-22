"""Step 66C.4-BE1-R -- independent review regression tests.

Two layers:
  * Review-completeness tests: the required review artifacts exist, the review-process marker and
    the technical verdict are recorded SEPARATELY, and the review modified no implementation path.
  * Findings-regression tests: each blocking finding this review recorded is pinned to a check that
    will FLIP once the finding is remediated, so the remediation stage (66C.4-BE1-R1) cannot close
    a finding without this suite noticing.

These tests describe the REVIEW. They deliberately do not assert that BE1 is correct -- the whole
point of the review is that it is not yet.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
CONTRACT_DIR = REPO / "docs" / "contracts" / "66c4-reminder-expiry-controlled-resume"
STAGE_DIR = REPO / "docs" / "stages" / "66c4-be1-independent-review"

REVIEW_ARTIFACTS = (
    CONTRACT_DIR / "be1-independent-review.md",
    CONTRACT_DIR / "be1-deadline-semantics-review.md",
    CONTRACT_DIR / "be1-outbox-foundation-sufficiency-review.md",
    CONTRACT_DIR / "be1-security-review.md",
    CONTRACT_DIR / "be1-migration-review.md",
    CONTRACT_DIR / "be1-test-quality-review.md",
    REPO
    / "docs"
    / "handoffs"
    / "66c4-reminder-expiry-controlled-resume"
    / "be1-review-result-handoff.md",
    REPO / "docs" / "test" / "step66c4-be1-independent-review-record.md",
    STAGE_DIR / "stage-manifest.yaml",
    STAGE_DIR / "context-receipt.md",
    STAGE_DIR / "stage-gate-report.md",
)

PROCESS_MARKER = "STEP66C4_BE1_INDEPENDENT_REVIEW_VERIFY"
TECHNICAL_MARKER = "BE1_TECHNICAL_VERDICT"

STORE = REPO / "shared" / "sdk" / "tasks" / "workroom_store.py"
OUTBOX = REPO / "shared" / "sdk" / "tasks" / "lifecycle_outbox.py"
MIGRATION = REPO / "migrations" / "031_clarification_lifecycle_outbox_foundation.sql"


# ---------------------------------------------------------------------------------------
# Review completeness
# ---------------------------------------------------------------------------------------


@pytest.mark.parametrize("path", REVIEW_ARTIFACTS, ids=lambda p: p.name)
def test_review_artifact_exists_and_is_substantive(path: Path) -> None:
    assert path.is_file(), f"missing review artifact: {path}"
    assert len(path.read_text(encoding="utf-8").strip()) > 400


def test_process_marker_and_technical_verdict_are_separate() -> None:
    master = (CONTRACT_DIR / "be1-independent-review.md").read_text(encoding="utf-8")
    assert f"{PROCESS_MARKER}: PASS" in master
    assert f"{TECHNICAL_MARKER}: REMEDIATION_REQUIRED" in master
    # The two must never be conflated onto a single line in any artifact.
    for path in REVIEW_ARTIFACTS:
        for line in path.read_text(encoding="utf-8").splitlines():
            assert not (PROCESS_MARKER in line and TECHNICAL_MARKER in line), path.name


def test_handoff_carries_the_same_technical_verdict() -> None:
    handoff = (
        REPO
        / "docs"
        / "handoffs"
        / "66c4-reminder-expiry-controlled-resume"
        / "be1-review-result-handoff.md"
    ).read_text(encoding="utf-8")
    assert f"{TECHNICAL_MARKER}: REMEDIATION_REQUIRED" in handoff
    assert "NOT recommended for merge" in handoff


def test_review_modified_no_implementation_path() -> None:
    out = subprocess.run(
        [
            "git",
            "diff",
            "--name-only",
            "origin/feature/66c4-be1-lifecycle-outbox-foundation...HEAD",
        ],
        cwd=REPO,
        capture_output=True,
        text=True,
    )
    changed = [line.strip() for line in out.stdout.splitlines() if line.strip()]
    forbidden = [
        path
        for path in changed
        if path.startswith(
            (
                "migrations/",
                "shared/sdk/",
                "apps/",
                "services/",
                "infra/",
                "helm/",
                "k8s/",
                "frontend/",
                ".github/workflows/",
            )
        )
    ]
    assert forbidden == [], f"the review modified implementation paths: {forbidden}"


def test_review_artifacts_respect_the_masking_rule() -> None:
    for path in REVIEW_ARTIFACTS:
        content = path.read_text(encoding="utf-8")
        for pattern in ("10.0.1.31", "10.0.1.32", "aiagent-swd", "itadmin", "stpadmin"):
            assert pattern not in content, f"unmasked identifier {pattern} in {path.name}"


# ---------------------------------------------------------------------------------------
# Findings regression -- these pin the reviewed state so remediation is visible
# ---------------------------------------------------------------------------------------


def test_finding_b1_deadline_predicate_still_uses_transaction_time() -> None:
    """B-1: the CAS uses now() (== transaction_timestamp), frozen at BEGIN.

    When 66C.4-BE1-R1 switches the predicate to statement_timestamp()/clock_timestamp(), this test
    fails and must be updated together with the review's verdict -- that is the point.
    """
    src = STORE.read_text(encoding="utf-8")
    assert "due_at > now()" in src, "predicate changed -- re-evaluate finding B-1 and the verdict"
    assert "due_at > statement_timestamp()" not in src
    assert "due_at > clock_timestamp()" not in src


def test_finding_b2_outbox_lacks_durability_columns() -> None:
    """B-2: available_at/next_attempt_at, dead_at and last_error are absent from migration 031."""
    sql = MIGRATION.read_text(encoding="utf-8")
    create = sql[sql.index("CREATE TABLE IF NOT EXISTS clarification_lifecycle_outbox") :]
    create = create[: create.index(");")]
    for missing in ("available_at", "next_attempt_at", "dead_at", "last_error"):
        assert (
            missing not in create
        ), f"{missing} was added -- re-evaluate finding B-2 and the foundation verdict"
    # The columns that ARE present stay present.
    for present in ("idempotency_key", "attempts", "status", "published_at", "created_at"):
        assert present in create


def test_finding_m1_payload_guard_inspects_only_top_level_keys() -> None:
    """M-1: nested prohibited keys are not detected by the payload-safety guard."""
    from shared.sdk.tasks import lifecycle_outbox

    # Top-level and case-folded keys ARE caught (the guard works as far as it goes).
    with pytest.raises(ValueError):
        lifecycle_outbox.assert_safe_outbox_payload({"answer": "x"})
    with pytest.raises(ValueError):
        lifecycle_outbox.assert_safe_outbox_payload({"ANSWER": "x"})
    # Nested and near-miss keys are NOT caught -- this is the finding.
    assert lifecycle_outbox.assert_safe_outbox_payload({"meta": {"answer": "raw body"}})
    assert lifecycle_outbox.assert_safe_outbox_payload({"items": [{"token": "value"}]})
    assert lifecycle_outbox.assert_safe_outbox_payload({"answer_body": "raw body"})


def test_reviewed_facts_that_must_not_regress() -> None:
    """Facts this review verified as CORRECT; a change here invalidates the review."""
    src = OUTBOX.read_text(encoding="utf-8")
    # The outbox module opens/commits/closes nothing (caller-owned transaction).
    for banned in ("conn.transaction()", "await conn.close()", "asyncpg.connect("):
        assert banned not in src, f"outbox module gained connection ownership: {banned}"
    # No relay or scheduler construct.
    for banned in ("XREADGROUP", "asyncio.sleep", "while True", "create_task("):
        assert banned not in src, f"outbox module gained a relay/scheduler construct: {banned}"
    # due_at remains NOT NULL in the table's defining migration (finding 5.2 depends on it).
    base = (REPO / "migrations" / "030_workroom_clarification_foundation.sql").read_text(
        encoding="utf-8"
    )
    assert "due_at                TIMESTAMPTZ NOT NULL" in base
