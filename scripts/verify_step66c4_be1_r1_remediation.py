#!/usr/bin/env python3
"""Step 66C.4-BE1-R1 -- deadline / outbox durability / payload safety remediation verifier.

Confirms the two blocking findings and the medium finding from the Step 66C.4-BE1-R independent
review are remediated: the canonical time semantics are corrected and the deadline predicate and
answered_at use statement_timestamp(); the outbox carries a persisted retry schedule, a terminal
death timestamp and a bounded failure reason; and the payload guard is a positive allowlist.

Static/structural + git-diff checks only; it touches no runtime and no remote host.

TWO SEPARATE RESULTS -- never conflate them:
  STEP66C4_BE1_R1_REMEDIATION_VERIFY -- static remediation artifacts and self-verification.
  STEP66C4_BE1_R1_PG_EVIDENCE        -- whether the MANDATORY real-PostgreSQL suite actually ran
                                        with zero skips. A static PASS is NOT technical closure.

Neither marker is a technical verdict. Final technical closure for BE1 must be declared by a new
independent reviewer (Step 66C.4-BE1-R1-R), not by this verifier and not by the remediation session.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIG_UP = ROOT / "migrations" / "031_clarification_lifecycle_outbox_foundation.sql"
MIG_DOWN = ROOT / "migrations" / "031_clarification_lifecycle_outbox_foundation_down.sql"
STORE = ROOT / "shared" / "sdk" / "tasks" / "workroom_store.py"
OUTBOX = ROOT / "shared" / "sdk" / "tasks" / "lifecycle_outbox.py"
GUARD = ROOT / "tests" / "step66c4_pg_safety.py"
R1_TESTS = ROOT / "tests" / "test_step66c4_be1_r1_remediation.py"
BE1_TESTS = ROOT / "tests" / "test_step66c4_be1_data_model_deadline_outbox.py"
PROGRESS = ROOT / "source" / "progress.md"

CONTRACT_DIR = ROOT / "docs" / "contracts" / "66c4-reminder-expiry-controlled-resume"
LIFECYCLE = CONTRACT_DIR / "lifecycle-and-time-contract.md"
DATA_MODEL = CONTRACT_DIR / "data-model-contract.md"

RECORDS = {
    "remediation": CONTRACT_DIR / "be1-r1-remediation-record.md",
    "deadline": CONTRACT_DIR / "be1-r1-deadline-remediation-record.md",
    "outbox": CONTRACT_DIR / "be1-r1-outbox-durability-remediation-record.md",
    "payload": CONTRACT_DIR / "be1-r1-payload-safety-remediation-record.md",
    "deferred": CONTRACT_DIR / "be1-deferred-low-findings.md",
    "handoff": ROOT
    / "docs"
    / "handoffs"
    / "66c4-reminder-expiry-controlled-resume"
    / "be1-r1-closure-review-handoff.md",
    "test-record": ROOT / "docs" / "test" / "step66c4-be1-r1-remediation-record.md",
}
STAGE_DIR = ROOT / "docs" / "stages" / "66c4-be1-r1-remediation"
STAGE_DOCS = {
    "manifest": STAGE_DIR / "stage-manifest.yaml",
    "receipt": STAGE_DIR / "context-receipt.md",
    "gate": STAGE_DIR / "stage-gate-report.md",
}

MARKER = "STEP66C4_BE1_R1_REMEDIATION_VERIFY"
PG_MARKER = "STEP66C4_BE1_R1_PG_EVIDENCE"

DURABILITY_COLUMNS = ("available_at", "dead_at", "last_error")

TRANSPORT_UNCHANGED_PATHS = (
    "shared/sdk/audit",
    "shared/sdk/event_bus",
    "apps/retry-scheduler",
    "apps/communication-gateway",
    "frontend/",
    "infra/",
    "helm/",
    "k8s/",
    ".github/workflows/",
)

failures: list[str] = []


def bad(m: str) -> None:
    failures.append(m)
    print(f"  [FAIL] {m}")


def _changed_files() -> list[str]:
    out = subprocess.run(
        ["git", "diff", "--name-only", "origin/main"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    files = [f.strip() for f in out.stdout.splitlines() if f.strip()]
    untracked = subprocess.run(
        ["git", "ls-files", "--others", "--exclude-standard"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    files += [f.strip() for f in untracked.stdout.splitlines() if f.strip()]
    return files


def main() -> int:
    for name, p in {**RECORDS, **STAGE_DOCS}.items():
        if not p.is_file():
            bad(f"missing doc: {p} ({name})")
    for p in (MIG_UP, MIG_DOWN, STORE, OUTBOX, GUARD, R1_TESTS, BE1_TESTS, PROGRESS):
        if not p.is_file():
            bad(f"missing source file: {p}")
    if failures:
        print(f"{MARKER}: FAIL")
        return 1

    up = MIG_UP.read_text(encoding="utf-8")
    store = STORE.read_text(encoding="utf-8")
    outbox = OUTBOX.read_text(encoding="utf-8")
    guard = GUARD.read_text(encoding="utf-8")
    r1_tests = R1_TESTS.read_text(encoding="utf-8")
    lifecycle = LIFECYCLE.read_text(encoding="utf-8")
    data_model = DATA_MODEL.read_text(encoding="utf-8")
    test_record = RECORDS["test-record"].read_text(encoding="utf-8")
    handoff = RECORDS["handoff"].read_text(encoding="utf-8")
    manifest = STAGE_DOCS["manifest"].read_text(encoding="utf-8")
    progress_low = re.sub(r"\s+", " ", PROGRESS.read_text(encoding="utf-8").lower())

    # 1. Canonical now() semantics corrected.
    if "now() is evaluated per statement" in lifecycle.lower():
        bad("check1: the refuted 'now() is evaluated per statement' claim is still in the contract")
    if "transaction_timestamp()" not in lifecycle or "statement_timestamp()" not in lifecycle:
        bad("check1: the contract does not state the corrected PostgreSQL time semantics")
    if (
        "transaction start" not in lifecycle.lower()
        and "transaction started" not in lifecycle.lower()
    ):
        bad("check1: the contract does not record that now() is the transaction start time")

    # 2. Deadline predicate uses statement_timestamp().
    if "due_at > statement_timestamp()" not in store:
        bad("check2: the answer CAS does not use due_at > statement_timestamp()")
    if "due_at > now()" in store or "due_at > transaction_timestamp()" in store:
        bad("check2: the answer CAS still uses a transaction-time deadline predicate")
    if "due_at > statement_timestamp()" not in lifecycle:
        bad("check2: the binding contract predicate is not statement_timestamp()")

    # 3. answered_at uses statement_timestamp().
    if "answered_at=statement_timestamp()" not in store:
        bad("check3: answered_at is not stamped with statement_timestamp()")
    if "answered_at=now()" in store or "answered_at=transaction_timestamp()" in store:
        bad("check3: answered_at still uses transaction time")

    # 4-6. Mandatory deadline tests exist.
    if "def test_pg_transaction_crossing_deadline_is_rejected" not in r1_tests:
        bad("check4: the transaction-crossing-deadline test does not exist")
    if "def test_pg_strict_boundary_equality_is_rejected" not in r1_tests:
        bad("check5: the strict-boundary equality test does not exist")
    if "def test_pg_due_at_remains_not_null" not in r1_tests:
        bad("check6: the due_at NOT NULL regression test does not exist")

    # 7-9. Migration carries the durability columns.
    for col in DURABILITY_COLUMNS:
        if col not in up:
            bad(f"check7/8/9: migration 031 does not define {col}")
    if "available_at      TIMESTAMPTZ NOT NULL" not in up:
        bad("check7: available_at is not NOT NULL")
    if "chk_clo_last_error_bounded" not in up:
        bad("check9: last_error has no DB-enforced bound")
    if "chk_clo_status_timestamps" not in up:
        bad("check9: no status/timestamp coherence constraint")
    for banned in ("DROP TABLE", "DROP COLUMN", "ALTER COLUMN", "TRUNCATE", "DELETE FROM"):
        if banned in up:
            bad(f"check7-9: up migration is no longer additive: {banned}")

    # 10. Retry / dead / replay semantics documented as binding.
    for heading in ("Retry semantics", "Operator replay semantics", "Status semantics"):
        if heading not in data_model:
            bad(f"check10: data-model contract lacks the binding section: {heading}")
    if "available_at <= statement_timestamp()" not in data_model:
        bad("check10: the relay claim-eligibility rule is not recorded")

    # 11-13. Payload positive allowlist.
    if "ALLOWED_PAYLOAD_KEYS_BY_EVENT_TYPE" not in outbox:
        bad("check11: no positive payload allowlist")
    if "PROHIBITED_PAYLOAD_KEYS" in outbox:
        bad("check11: the bypassable deny list is still the guard")
    if "must be a bounded scalar" not in outbox:
        bad("check12: nested/non-scalar payload values are not rejected")
    if "def test_payload_allowlist_rejects_bypass_attempts" not in r1_tests:
        bad("check12: nested-payload bypass tests do not exist")
    for probe in ('{"meta": {"answer"', '{"items": [{"token"', '"answer_body"', '"question_text"'):
        if probe not in r1_tests:
            bad(f"check12: missing bypass probe: {probe}")
    if "unknown lifecycle outbox event_type" not in outbox:
        bad("check13: unknown event types are not rejected")
    if "is not allowed for" not in outbox:
        bad("check13: unknown payload keys are not rejected")

    # 14. Destructive fixture guard is fail-closed.
    if "STEP66C4_ALLOW_DESTRUCTIVE_PG_TESTS" not in guard:
        bad("check14: no explicit destructive-test opt-in")
    if "FORBIDDEN_DB_NAMES" not in guard or "ALLOWED_DB_NAME_PATTERNS" not in guard:
        bad("check14: no database-name protection")
    for f in (R1_TESTS, BE1_TESTS):
        if "destructive_pg_refusal_reason" not in f.read_text(encoding="utf-8"):
            bad(f"check14: destructive fixtures in {f.name} are not gated by the guard")

    # 15. Mandatory PostgreSQL evidence is recorded, not silently skipped.
    pg_evidence_ok = bool(
        re.search(r"mandatory postgresql tests[^\n]*0 skipped", test_record, re.IGNORECASE)
    ) and bool(re.search(r"0 failed", test_record, re.IGNORECASE))
    if not pg_evidence_ok:
        bad("check15: the test record does not evidence a mandatory PostgreSQL run with 0 skipped")

    # 16. Concurrency barrier test exists.
    if "asyncio.Barrier" not in r1_tests:
        bad("check16: the concurrency test does not use a barrier")
    if "def test_pg_loser_blocks_until_winner_commits" not in r1_tests:
        bad("check16: no lock-blocking concurrency test")

    # 17-18. No scheduler / relay / live producer added.
    for banned in ("while True", "asyncio.sleep", "create_task(", "XREADGROUP", "FOR UPDATE"):
        if banned in outbox:
            bad(f"check17: outbox module contains a relay/scheduler construct: {banned}")
    offenders = []
    for base in (ROOT / "apps", ROOT / "shared"):
        for path in base.rglob("*.py"):
            if path == OUTBOX or "__pycache__" in str(path):
                continue
            txt = path.read_text(encoding="utf-8", errors="ignore")
            if "lifecycle_outbox" in txt or "clarification_lifecycle_outbox" in txt:
                offenders.append(str(path.relative_to(ROOT)))
    if offenders:
        bad(f"check18: live runtime references to the outbox: {offenders}")

    changed = _changed_files()

    # 19. Audit/event transport and forbidden paths unchanged.
    for prefix in TRANSPORT_UNCHANGED_PATHS:
        touched = [f for f in changed if f.startswith(prefix)]
        if touched:
            bad(f"check19: forbidden/unchanged path modified: {touched}")

    # 20. No resume/dispatch added.
    api_diff = subprocess.run(
        ["git", "diff", "origin/main", "--", "apps/orchestrator/src/workroom_api.py"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    ).stdout
    added = "\n".join(
        ln for ln in api_diff.splitlines() if ln.startswith("+") and not ln.startswith("+++")
    )
    for banned in ("resume-request", "def request_resume", "def resume", "resume_dispatch("):
        if banned in added:
            bad(f"check20: resume/dispatch behavior added to the API: {banned}")
    if re.search(r"@router\.\w+\([^)]*resume", added):
        bad("check20: a resume route was added")

    # 21-23. Posture recorded.
    posture = " ".join(
        [
            handoff.lower(),
            manifest.lower(),
            RECORDS["remediation"].read_text(encoding="utf-8").lower(),
        ]
    )
    if "draft" not in posture or "merge_allowed: false" not in manifest.lower():
        bad("check21: PR #17 draft/unmerged posture not recorded")
    if "be2_authorized: false" not in manifest.lower():
        bad("check22: BE2 is not recorded as unauthorized")
    if "independent_closure_review_required: true" not in manifest.lower():
        bad("check23: the independent closure review is not recorded as required")
    if "remediation_session_may_approve_merge: false" not in manifest.lower():
        bad("check23: the no-self-approval rule is not recorded")

    # 24. progress.md updated.
    if "66c.4-be1-r1" not in progress_low:
        bad("check24: source/progress.md does not reference Stage 66C.4-BE1-R1")

    # The deferred LOW finding must be recorded, not silently fixed.
    deferred = RECORDS["deferred"].read_text(encoding="utf-8").lower()
    if "already answered" not in deferred:
        bad("deferred: the deleted-clarification LOW finding is not recorded")

    if failures:
        print(f"{MARKER}: FAIL")
        print(f"{PG_MARKER}: {'PASS' if pg_evidence_ok else 'UNAVAILABLE'}")
        return 1

    print("  [OK] Canonical time semantics corrected; deadline predicate and answered_at use")
    print("       statement_timestamp(); transaction-crossing / strict-boundary / due_at NOT NULL")
    print("       tests exist; migration 031 carries available_at/dead_at/bounded last_error with")
    print("       status-coherence constraints; retry/dead/replay semantics are binding; payload")
    print("       guard is a positive allowlist with bypass probes; destructive PG fixtures are")
    print("       fail-closed; concurrency barrier test exists; no scheduler/relay/live producer;")
    print("       audit/event transport and frontend/infra unchanged; no resume/dispatch; PR #17")
    print("       stays Draft; BE2 unauthorized; independent closure review required.")
    print(f"{MARKER}: PASS")
    print(f"{PG_MARKER}: {'PASS' if pg_evidence_ok else 'UNAVAILABLE'}")
    print("  NOTE: neither marker is a technical verdict. BE1 technical closure must be declared")
    print("        by the independent Step 66C.4-BE1-R1-R reviewer.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
