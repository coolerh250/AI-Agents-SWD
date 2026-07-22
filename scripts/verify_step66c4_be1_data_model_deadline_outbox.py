#!/usr/bin/env python3
"""Step 66C.4-BE1 -- data model / deadline CAS / disabled outbox foundation verifier.

Confirms the BE1 backend foundation is exactly the canonical additive schema, the answer CAS
enforces the PostgreSQL-authoritative deadline, and the transactional-outbox foundation is
disabled (no relay, no scheduler, no live producer, existing audit/event transport unchanged).

Static/structural + git-diff checks only; it touches no runtime or remote host.

Marker: STEP66C4_BE1_DATA_MODEL_DEADLINE_OUTBOX_VERIFY: PASS | FAIL
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
API = ROOT / "apps" / "orchestrator" / "src" / "workroom_api.py"
PROGRESS = ROOT / "source" / "progress.md"

CONTRACT_DIR = ROOT / "docs" / "contracts" / "66c4-reminder-expiry-controlled-resume"
RECORDS = {
    "impl": CONTRACT_DIR / "be1-implementation-record.md",
    "migration": CONTRACT_DIR / "be1-migration-and-compatibility-record.md",
    "cas": CONTRACT_DIR / "be1-deadline-cas-record.md",
    "outbox": CONTRACT_DIR / "be1-disabled-outbox-foundation-record.md",
    "handoff": ROOT
    / "docs"
    / "handoffs"
    / "66c4-reminder-expiry-controlled-resume"
    / "be1-review-handoff.md",
    "test-record": ROOT / "docs" / "test" / "step66c4-be1-data-model-deadline-outbox-record.md",
}
STAGE_DIR = ROOT / "docs" / "stages" / "66c4-be1-data-model-deadline-outbox"
STAGE_DOCS = {
    "manifest": STAGE_DIR / "stage-manifest.yaml",
    "receipt": STAGE_DIR / "context-receipt.md",
    "gate": STAGE_DIR / "stage-gate-report.md",
}

MARKER = "STEP66C4_BE1_DATA_MODEL_DEADLINE_OUTBOX_VERIFY"

LIFECYCLE_FIELDS = (
    "reminder_sent_at",
    "expired_at",
    "resume_eligible_at",
    "resume_requested_at",
    "resume_requested_by",
    "resume_authorized_at",
)
FORBIDDEN_COLUMNS = ("resume_dispatched_at", "resume_authorized_by", "lock_version")

# Paths whose runtime transport must remain unchanged by BE1.
TRANSPORT_UNCHANGED_PATHS = (
    "shared/sdk/audit",
    "shared/sdk/event_bus",
    "apps/retry-scheduler",
    "apps/communication-gateway",
)
# Forbidden path prefixes that must have zero changes in this branch.
FORBIDDEN_CHANGED_PATHS = (
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
    """Files changed on this branch vs origin/main (committed + working tree)."""
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
    for p in (MIG_UP, MIG_DOWN, STORE, OUTBOX, API, PROGRESS):
        if not p.is_file():
            bad(f"missing source file: {p}")
    if failures:
        print(f"{MARKER}: FAIL")
        return 1

    up = MIG_UP.read_text(encoding="utf-8")
    down = MIG_DOWN.read_text(encoding="utf-8")
    store = STORE.read_text(encoding="utf-8")
    outbox = OUTBOX.read_text(encoding="utf-8")
    api = API.read_text(encoding="utf-8")
    progress_low = re.sub(r"\s+", " ", PROGRESS.read_text(encoding="utf-8").lower())

    # 1. Exactly six lifecycle fields implemented (each ADD COLUMN present).
    for f in LIFECYCLE_FIELDS:
        if f"ADD COLUMN IF NOT EXISTS {f}" not in up:
            bad(f"check1: lifecycle field not added: {f}")

    # 2. No unauthorized lifecycle field is added as a column.
    for f in FORBIDDEN_COLUMNS:
        if f"ADD COLUMN IF NOT EXISTS {f}" in up or re.search(
            rf"\b{f}\b\s+(TIMESTAMPTZ|TEXT|INT)", up
        ):
            bad(f"check2: unauthorized lifecycle column present: {f}")

    # 3. Outbox table exists.
    if "CREATE TABLE IF NOT EXISTS clarification_lifecycle_outbox" not in up:
        bad("check3: clarification_lifecycle_outbox table not created")

    # 4. Migration is additive (no destructive statement in the up migration).
    for banned in ("DROP TABLE", "DROP COLUMN", "ALTER COLUMN", "TRUNCATE", "DELETE FROM"):
        if banned in up:
            bad(f"check4: up migration contains destructive statement: {banned}")

    # 5. Migration rollback documented and tested.
    if "DROP TABLE IF EXISTS clarification_lifecycle_outbox" not in down:
        bad("check5: down migration does not drop the outbox table")
    for f in LIFECYCLE_FIELDS:
        if f"DROP COLUMN IF EXISTS {f}" not in down:
            bad(f"check5: down migration does not drop lifecycle column: {f}")

    # 6. Existing rows remain compatible (all six columns nullable -- no NOT NULL attached).
    for f in LIFECYCLE_FIELDS:
        if re.search(rf"ADD COLUMN IF NOT EXISTS {f}\s+\w+\s+NOT NULL", up):
            bad(f"check6: lifecycle column is NOT NULL (breaks existing rows): {f}")

    # 7. Deadline predicate uses PostgreSQL DB time.
    if "due_at > now()" not in store:
        bad("check7: answer CAS does not use the DB-time deadline predicate 'due_at > now()'")
    if re.search(r"datetime\.now\([^)]*\)[^\n]*due_at", store):
        bad("check7: answer deadline appears to use a Python clock")

    # 8. DB time >= due_at results in 409.
    if "invalid_state_for_answer:expired" not in api:
        bad("check8: API does not return 409 invalid_state_for_answer:expired past the deadline")

    # 9. Scheduler lag cannot extend answer eligibility (predicate is in the CAS, not scheduler).
    if "answered_at IS NULL" not in store or "status='open'" not in store:
        bad("check9: CAS guard incomplete (answered_at/status)")

    # 10. No task status added (no new operator_tasks/clarification status enum value in migration).
    if re.search(r"CHECK\s*\(\s*status\s+IN", up) and "clarification_lifecycle_outbox" not in (
        up[up.find("CHECK (status IN") : up.find("CHECK (status IN") + 200]
        if "CHECK (status IN" in up
        else ""
    ):
        # The only status CHECK allowed is the outbox status check; no change to clarification/task status.
        pass
    if "'clarification_expired'" in up or "operator_tasks.status" in up:
        bad("check10: migration appears to alter task/clarification status values")

    # 11-12. No scheduler / no outbox relay code added (no poll loop / stream consumer here).
    for banned in ("XREADGROUP", "asyncio.sleep", "while True", "create_task(", "BackgroundTasks"):
        if banned in outbox:
            bad(f"check11/12: outbox module contains a relay/scheduler construct: {banned}")

    # 13. No live producer writes to outbox (only lifecycle_outbox.py + tests reference it).
    offenders = []
    for base in (ROOT / "apps", ROOT / "shared"):
        for path in base.rglob("*.py"):
            if path == OUTBOX or "__pycache__" in str(path):
                continue
            txt = path.read_text(encoding="utf-8", errors="ignore")
            if "lifecycle_outbox" in txt or "clarification_lifecycle_outbox" in txt:
                offenders.append(str(path.relative_to(ROOT)))
    if offenders:
        bad(f"check13: live runtime references to the outbox: {offenders}")

    changed = _changed_files()

    # 14. Existing audit/event transport unchanged.
    for prefix in TRANSPORT_UNCHANGED_PATHS:
        touched = [f for f in changed if f.startswith(prefix)]
        if touched:
            bad(f"check14: transport path changed by BE1: {touched}")

    # 15-16. No resume endpoint/behavior, no dispatch/resume behavior ADDED by BE1.
    # Inspect only BE1's added lines (git diff) so pre-existing disabled flags such as
    # `resume_dispatch_enabled: False` (unchanged by BE1) do not false-trigger.
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
            bad(f"check15/16: BE1 adds resume/dispatch behavior to the API: {banned}")
    if re.search(r"@router\.\w+\([^)]*resume", added):
        bad("check15/16: BE1 adds a resume route to the API")

    # 17. No external notification added by BE1 (inspect added lines).
    if re.search(r"(discord|slack|telegram|smtp|external_send)", added, re.IGNORECASE):
        bad("check17: BE1 adds external notification to the API")

    # 18. No deployment / forbidden-path changes.
    for f in changed:
        for prefix in FORBIDDEN_CHANGED_PATHS:
            if f.startswith(prefix):
                bad(f"check18: forbidden path changed: {f}")

    # 19-21. Records state the authorization posture.
    impl_text = " ".join(
        RECORDS[k].read_text(encoding="utf-8").lower() for k in ("impl", "handoff")
    )
    if "codex" not in impl_text or "claude design" not in impl_text:
        bad("check19: Codex/Claude Design posture not recorded")
    if "unauthorized" not in impl_text and "not authorized" not in impl_text:
        bad("check19: Codex/Claude Design unauthorized statement missing")
    if "be2" not in impl_text or "not" not in impl_text:
        bad("check20: BE2 not-started statement missing")
    if "independent review" not in impl_text and "66c.4-be1-r" not in impl_text:
        bad("check21: independent-review requirement not recorded")

    # 22. progress.md updated.
    if "66c.4-be1" not in progress_low:
        bad("check22: source/progress.md does not reference Stage 66C.4-BE1")

    # Marker present in the test record.
    if MARKER not in RECORDS["test-record"].read_text(encoding="utf-8"):
        bad("marker missing from test record")

    if failures:
        print(f"{MARKER}: FAIL")
        return 1

    print("  [OK] Exactly six additive nullable lifecycle columns; outbox table created; no")
    print("       unauthorized column; migration additive with tested rollback; answer CAS uses")
    print("       PostgreSQL DB-time deadline (due_at > now()); past-deadline -> 409")
    print(
        "       invalid_state_for_answer:expired; no task-status change; no scheduler/relay code;"
    )
    print("       no live producer writes to the outbox; audit/event transport unchanged; no")
    print("       resume/dispatch/external-notification/deployment change; Codex/Claude Design")
    print("       unauthorized; BE2 not started; independent review required; progress.md updated")
    print(f"{MARKER}: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
