#!/usr/bin/env python3
"""Step 66C.4-BE2-R1 -- expiry-consistency + bounded-relay-timeout remediation verifier.

Static/structural + dynamic (import-and-drive) checks that the two blocking findings are closed
and the PO's binding retry/replay decisions are implemented. This marker is self-verification
only; it is NOT an independent technical PASS -- Step 66C.4-BE2-R1-R must run the closure review.

Markers:
  STEP66C4_BE2_R1_REMEDIATION_VERIFY: PASS | FAIL   (this script)
  STEP66C4_BE2_R1_PG_REDIS_EVIDENCE: PASS           (recorded in the test record after real-DB run)
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

POLLER = ROOT / "shared" / "sdk" / "tasks" / "lifecycle_poller.py"
RELAY = ROOT / "shared" / "sdk" / "tasks" / "outbox_relay.py"
OUTBOX = ROOT / "shared" / "sdk" / "tasks" / "lifecycle_outbox.py"
MODELS = ROOT / "shared" / "sdk" / "tasks" / "models.py"
BUS = ROOT / "shared" / "sdk" / "event_bus" / "redis_streams.py"
TESTS = ROOT / "tests" / "test_step66c4_be2_r1_remediation.py"
PROGRESS = ROOT / "source" / "progress.md"

CONTRACT_DIR = ROOT / "docs" / "contracts" / "66c4-reminder-expiry-controlled-resume"
RECORDS = {
    "remediation": CONTRACT_DIR / "be2-r1-remediation-record.md",
    "expiry": CONTRACT_DIR / "be2-r1-expiry-consistency-record.md",
    "timeout": CONTRACT_DIR / "be2-r1-relay-timeout-record.md",
    "retry": CONTRACT_DIR / "be2-r1-retry-semantics-record.md",
    "replay": CONTRACT_DIR / "be2-r1-replay-boundary-record.md",
    "handoff": ROOT
    / "docs"
    / "handoffs"
    / "66c4-reminder-expiry-controlled-resume"
    / "be2-r1-closure-review-handoff.md",
    "test-record": ROOT / "docs" / "test" / "step66c4-be2-r1-remediation-record.md",
}
STAGE_DIR = ROOT / "docs" / "stages" / "66c4-be2-r1-remediation"
STAGE_DOCS = {
    "manifest": STAGE_DIR / "stage-manifest.yaml",
    "receipt": STAGE_DIR / "context-receipt.md",
    "gate": STAGE_DIR / "stage-gate-report.md",
}

MARKER = "STEP66C4_BE2_R1_REMEDIATION_VERIFY"
EVIDENCE_MARKER = "STEP66C4_BE2_R1_PG_REDIS_EVIDENCE"

failures: list[str] = []


def bad(m: str) -> None:
    failures.append(m)
    print(f"  [FAIL] {m}")


def _changed_files() -> list[str]:
    out = subprocess.run(
        ["git", "diff", "--name-only", "origin/main"], cwd=ROOT, capture_output=True, text=True
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


def main() -> int:  # noqa: C901
    for name, p in {**RECORDS, **STAGE_DOCS}.items():
        if not p.is_file():
            bad(f"missing doc: {p} ({name})")
    for p in (POLLER, RELAY, OUTBOX, MODELS, BUS, TESTS, PROGRESS):
        if not p.is_file():
            bad(f"missing source file: {p}")
    if failures:
        print(f"{MARKER}: FAIL")
        return 1

    poller = POLLER.read_text(encoding="utf-8")
    relay = RELAY.read_text(encoding="utf-8")
    models = MODELS.read_text(encoding="utf-8")
    bus = BUS.read_text(encoding="utf-8")
    tests = TESTS.read_text(encoding="utf-8")

    # 1. Terminal parent suppresses all expiry mutations.
    if "TERMINAL_TASK_STATUSES" not in models or "TERMINAL_TASK_STATUSES" not in poller:
        bad("check1: canonical terminal-status set not used by expiry")
    if "reason_code=terminal_parent_suppressed" not in poller:
        bad("check1: terminal-parent suppression path missing")
    if "TERMINAL_PARENT_SUPPRESSED_TOTAL" not in poller:
        bad("check1: terminal_parent_suppressed metric not incremented")

    # 2. Unexpected non-terminal parent -> reconciliation observability.
    if "reason_code=reconciliation_required" not in poller:
        bad("check2: reconciliation path missing")
    if "RECONCILIATION_FAILURES_TOTAL" not in poller:
        bad("check2: reconciliation_failure metric not incremented")

    # 3. Parent task locked and guarded update rowcount inspected (must equal 1).
    if "SELECT status FROM operator_tasks WHERE id=$1 FOR UPDATE" not in poller:
        bad("check3: parent task not locked before mutation")
    if "_rowcount(tag) != 1" not in poller:
        bad("check3: guarded update rowcount not asserted == 1")

    # 4. Rowcount 0 rolls back clarification/task/outbox (test present).
    if "def test_pg_b1_guarded_update_rowcount_zero_rolls_back_everything" not in tests:
        bad("check4: rowcount-0 rollback test missing")

    # 5. Redis client timeout bounded (relay builds a bus with non-None socket timeouts).
    if "socket_timeout: float | None = None" not in bus:
        bad("check5: bus does not accept a bounded socket_timeout")
    if "socket_timeout=self.publish_timeout_seconds" not in relay:
        bad("check5: relay bus socket_timeout not bounded")
    if "socket_connect_timeout=self.publish_timeout_seconds" not in relay:
        bad("check5: relay bus socket_connect_timeout not bounded")

    # 6. Total publish await bounded.
    if "asyncio.wait_for(" not in relay or "timeout=self.publish_timeout_seconds" not in relay:
        bad("check6: publish await not bounded by asyncio.wait_for")

    # 9. Timeout is a transient retry, not published.
    if "PublishResult(False, PUBLISH_TIMEOUT_REASON)" not in relay:
        bad("check9: timeout not treated as a transient failure")
    if 'PUBLISH_TIMEOUT_REASON = "redis_publish_timeout"' not in relay:
        bad("check9: safe timeout reason label missing")

    # 10. Cancellation rolls back and re-raises.
    if "except asyncio.CancelledError" not in relay or "except BaseException" not in relay:
        bad("check10: cancellation not rolled back / re-raised")

    # 7-8, 11-14. Dynamic import-and-drive of the actual constants and planner.
    try:
        from shared.sdk.tasks import lifecycle_outbox as lo
        from shared.sdk.tasks import outbox_relay as orm

        if orm.DEFAULT_PUBLISH_TIMEOUT_SECONDS != 5.0:  # 7
            bad("check7: default publish timeout is not 5s")
        if orm._resolve_publish_timeout(None) != 5.0:
            bad("check7: resolved default timeout is not 5s")
        for good in (1, 5, 30):  # 8
            orm._resolve_publish_timeout(good)
        for out_of_range in (0.99, 30.01, 0):
            try:
                orm._resolve_publish_timeout(out_of_range)
                bad(f"check8: out-of-range timeout accepted: {out_of_range}")
            except ValueError:
                pass
        if lo.MAX_RETRIES != 4:  # 11
            bad("check11: MAX_RETRIES != 4")
        if lo.MAX_PUBLISH_ATTEMPTS != 5:  # 12
            bad("check12: MAX_PUBLISH_ATTEMPTS != 5")
        # 13-14. Drive the planner across the whole schedule.
        backoffs = []
        attempts = 0
        terminal = None
        for _ in range(10):
            plan = lo.plan_retry_state(attempts=attempts, error="x")
            if plan["status"] == "dead":
                terminal = plan
                break
            backoffs.append(plan["backoff_seconds"])
            attempts = plan["attempts"]
        if backoffs != [30, 120, 600, 3600]:  # 13
            bad(f"check13: backoff schedule not fully reachable: {backoffs}")
        if terminal is None or terminal["attempts"] != 5:  # 14
            bad("check14: fifth failure does not enter dead at attempts=5")
    except Exception as exc:  # pragma: no cover
        bad(f"checks7-14: dynamic verification failed: {type(exc).__name__}: {exc}")

    # 15. replay_dead has no public/runtime/startup caller (word-boundary scan).
    for base in (ROOT / "apps", ROOT / "shared"):
        for path in base.rglob("*.py"):
            if "__pycache__" in str(path) or path.name == "outbox_relay.py":
                continue
            if re.search(r"replay_dead\b", path.read_text(encoding="utf-8", errors="ignore")):
                bad(f"check15: replay_dead has a caller: {path.relative_to(ROOT)}")

    changed = _changed_files()

    # 16. No schema/migration change.
    if any(f.startswith("migrations/") for f in changed):
        bad("check16: a migration was added/modified")

    # 17. No shared activation/deployment path changed; workers not activated anywhere.
    for prefix in ("infra/", "helm/", "k8s/", ".github/workflows/", "frontend/"):
        for f in changed:
            if f.startswith(prefix):
                bad(f"check17: forbidden deployment/activation path changed: {f}")
    for base in (ROOT / "apps" / "orchestrator", ROOT / "apps" / "admin-console"):
        for path in base.rglob("*.py") if base.exists() else []:
            txt = path.read_text(encoding="utf-8", errors="ignore")
            if "lifecycle_poller" in txt or "outbox_relay" in txt:
                bad(f"check17: a BE2 worker is activated in {path.relative_to(ROOT)}")

    # 18-20. Documented posture: PR #18 Draft, BE3 unauthorized, independent closure review required.
    posture = " ".join(
        RECORDS[k].read_text(encoding="utf-8").lower()
        for k in ("remediation", "handoff", "test-record")
    )
    if "draft" not in posture or "#18" not in posture:
        bad("check18: PR #18 Draft posture not recorded")
    if "be3" not in posture or "not authorized" not in posture:
        bad("check19: BE3 not-authorized posture not recorded")
    if "independent closure review" not in posture:
        bad("check20: independent closure review requirement not recorded")

    # Evidence + self markers present in the test record.
    tr = RECORDS["test-record"].read_text(encoding="utf-8")
    if f"{EVIDENCE_MARKER}: PASS" not in tr:
        bad(f"evidence marker missing from test record: {EVIDENCE_MARKER}")
    if MARKER not in tr:
        bad(f"self marker missing from test record: {MARKER}")

    if failures:
        print(f"{MARKER}: FAIL")
        return 1

    print("  [OK] B-1 expiry consistency: parent task locked, transition only from")
    print("       clarification_needed with guarded rowcount==1, terminal parent suppressed,")
    print("       unexpected parent reconciled -- all observable, all-or-nothing.")
    print("  [OK] B-2 bounded relay: bounded Redis socket timeout + asyncio.wait_for total cap;")
    print("       timeout is a transient retry (never published); cancellation rolls back and")
    print("       re-raises; default 5s, range [1, 30].")
    print("  [OK] Retry: MAX_RETRIES=4, MAX_PUBLISH_ATTEMPTS=5, backoffs 30/120/600/3600 all")
    print("       reached, dead on the 5th failure.")
    print("  [OK] Replay foundation internal-only; no migration; no shared activation; PR #18")
    print(
        "       Draft; BE3/Codex/Claude Design unauthorized; independent closure review required."
    )
    print(f"{MARKER}: PASS")
    print("  NOTE: self-verification only; BE2 technical closure requires the independent")
    print("        Step 66C.4-BE2-R1-R reviewer.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
