#!/usr/bin/env python3
"""Step 66C.4-BE2 -- reminder/expiry poller and transactional outbox relay verifier.

Static/structural + git-diff checks that the two workers implement the canonical lifecycle
transitions and outbox relay, keep state+outbox atomic, use persisted retry/dead/replay semantics,
expose metrics/health, claim at-least-once (never exactly-once), reuse canonical dotted event
names, and add NO migration, NO existing-producer cutover, NO shared-runtime activation, NO
deployment, and NO resume/dispatch/external notification.

Marker: STEP66C4_BE2_REMINDER_EXPIRY_OUTBOX_RELAY_VERIFY: PASS | FAIL
This marker is self-verification only; it is NOT an independent technical PASS.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
POLLER = ROOT / "shared" / "sdk" / "tasks" / "lifecycle_poller.py"
RELAY = ROOT / "shared" / "sdk" / "tasks" / "outbox_relay.py"
METRICS = ROOT / "shared" / "sdk" / "tasks" / "lifecycle_metrics.py"
POLLER_MAIN = ROOT / "apps" / "clarification-lifecycle-worker" / "src" / "main.py"
RELAY_MAIN = ROOT / "apps" / "clarification-outbox-relay" / "src" / "main.py"
TESTS = ROOT / "tests" / "test_step66c4_be2_reminder_expiry_outbox_relay.py"
PROGRESS = ROOT / "source" / "progress.md"

CONTRACT_DIR = ROOT / "docs" / "contracts" / "66c4-reminder-expiry-controlled-resume"
RECORDS = {
    "impl": CONTRACT_DIR / "be2-implementation-record.md",
    "poller": CONTRACT_DIR / "be2-lifecycle-poller-record.md",
    "relay": CONTRACT_DIR / "be2-outbox-relay-record.md",
    "retry": CONTRACT_DIR / "be2-retry-dlq-replay-record.md",
    "obs": CONTRACT_DIR / "be2-observability-record.md",
    "safety": CONTRACT_DIR / "be2-safety-and-nonactivation-record.md",
    "handoff": ROOT
    / "docs"
    / "handoffs"
    / "66c4-reminder-expiry-controlled-resume"
    / "be2-independent-review-handoff.md",
    "test-record": ROOT / "docs" / "test" / "step66c4-be2-reminder-expiry-outbox-relay-record.md",
}
STAGE_DIR = ROOT / "docs" / "stages" / "66c4-be2-reminder-expiry-outbox-relay"
STAGE_DOCS = {
    "manifest": STAGE_DIR / "stage-manifest.yaml",
    "receipt": STAGE_DIR / "context-receipt.md",
    "gate": STAGE_DIR / "stage-gate-report.md",
}

MARKER = "STEP66C4_BE2_REMINDER_EXPIRY_OUTBOX_RELAY_VERIFY"

# Forbidden path prefixes that must have zero changes in this branch.
FORBIDDEN_CHANGED_PATHS = (
    "frontend/",
    "infra/",
    "helm/",
    "k8s/",
    ".github/workflows/",
    "apps/communication-gateway/",
    "migrations/",
)
# Existing transport that must remain unchanged.
TRANSPORT_UNCHANGED_PATHS = (
    "shared/sdk/audit/",
    "shared/sdk/event_bus/",
    "apps/retry-scheduler/",
    "apps/notification-worker/",
    "apps/audit-worker/",
)

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


def main() -> int:
    for name, p in {**RECORDS, **STAGE_DOCS}.items():
        if not p.is_file():
            bad(f"missing doc: {p} ({name})")
    for p in (POLLER, RELAY, METRICS, POLLER_MAIN, RELAY_MAIN, TESTS, PROGRESS):
        if not p.is_file():
            bad(f"missing source file: {p}")
    if failures:
        print(f"{MARKER}: FAIL")
        return 1

    poller = POLLER.read_text(encoding="utf-8")
    relay = RELAY.read_text(encoding="utf-8")
    metrics = METRICS.read_text(encoding="utf-8")
    tests = TESTS.read_text(encoding="utf-8")
    progress_low = re.sub(r"\s+", " ", PROGRESS.read_text(encoding="utf-8").lower())

    # 1-2. Reminder + expiry pollers implemented with canonical predicates.
    if (
        "reminder_at <= statement_timestamp()" not in poller
        or "due_at > statement_timestamp()" not in poller
    ):
        bad("check1: reminder poller predicate not canonical")
    if "reminder_sent_at IS NULL" not in poller:
        bad("check1: reminder poller does not guard reminder_sent_at")
    if "due_at <= statement_timestamp()" not in poller:
        bad("check2: expiry poller predicate not canonical")

    # 3. Lifecycle state + outbox atomic (single transaction, outbox via BE1 repo).
    if "insert_lifecycle_outbox_event" not in poller:
        bad("check3: poller does not use the BE1 transaction-aware outbox insert")
    if "FOR UPDATE SKIP LOCKED" not in poller:
        bad("check3: poller does not claim with FOR UPDATE SKIP LOCKED")

    # 4-5. Task reuses clarification_expired; no new global task status.
    if "status='clarification_expired'" not in poller:
        bad("check4: expiry does not reuse the clarification_expired task status")
    if re.search(r"status\s*=\s*'clarification_(?!expired|needed)", poller):
        bad("check5: expiry appears to introduce a new task/clarification status value")

    # 6. Relay implemented with the canonical claim + single durable destination.
    if "FOR UPDATE SKIP LOCKED" not in relay:
        bad("check6: relay does not claim with FOR UPDATE SKIP LOCKED")
    if "publish_audit_event" not in relay:
        bad("check6: relay does not publish via the existing audit SDK entry point")

    # 7. Persisted retry/backoff.
    if "plan_retry_state" not in relay or "available_at=statement_timestamp() + (" not in relay:
        bad("check7: relay does not persist a backoff schedule in available_at")

    # 8. Dead terminal state.
    if "status='dead'" not in relay or "dead_at=statement_timestamp()" not in relay:
        bad("check8: relay does not implement the terminal dead state")

    # 9. Replay foundation without a public endpoint.
    if "plan_replay_state" not in relay or "def replay_dead" not in relay:
        bad("check9: relay replay foundation missing")
    for base in (ROOT / "apps" / "orchestrator", ROOT / "apps" / "admin-console"):
        for path in base.rglob("*.py") if base.exists() else []:
            txt = path.read_text(encoding="utf-8", errors="ignore")
            if "replay_dead" in txt or "outbox_relay" in txt:
                bad(f"check9: replay/relay wired into an API surface: {path.relative_to(ROOT)}")

    # 10. Metrics + health.
    for metric in (
        "POLL_CYCLES_TOTAL",
        "OUTBOX_PUBLISH_SUCCESS_TOTAL",
        "OUTBOX_DEAD_TOTAL",
        "OUTBOX_PENDING_COUNT",
        "LAST_SUCCESSFUL_PUBLISH_TIMESTAMP",
    ):
        if metric not in metrics:
            bad(f"check10: metric missing: {metric}")
    if '"/health"' not in POLLER_MAIN.read_text(
        encoding="utf-8"
    ) or '"/health"' not in RELAY_MAIN.read_text(encoding="utf-8"):
        bad("check10: worker entrypoints do not expose /health")

    # 11-12. at-least-once explicit; exactly-once NOT claimed.
    if "AT-LEAST-ONCE" not in relay:
        bad("check11: at-least-once delivery not stated")
    if "EXACTLY-ONCE is NOT claimed" not in relay:
        bad("check12: exactly-once must be explicitly disclaimed")
    if re.search(r"exactly[- ]once", relay, re.IGNORECASE) and "NOT" not in relay:
        bad("check12: exactly-once appears to be claimed")

    # 13. Canonical dotted event names.
    if "clarification.reminder_recorded" not in poller or "clarification.expired" not in poller:
        bad("check13: canonical dotted event names not used")
    # Legacy underscore EVENT names (not the legitimate clarification_expired task STATUS) must
    # not be used as an event_type.
    if re.search(r"event_type\s*=\s*[\"']clarification_", poller):
        bad("check13: legacy underscore event name used as event_type")

    # 14. Positive payload allowlist still in effect (BE1), payload minimal.
    if 'payload={"reason"' not in poller:
        bad("check14: poller does not send a minimal safe payload")

    changed = _changed_files()

    # 15. No migration/schema change.
    if any(f.startswith("migrations/") for f in changed):
        bad("check15: a migration was added/modified")

    # 16. No existing producer cutover / transport change.
    for prefix in TRANSPORT_UNCHANGED_PATHS:
        touched = [f for f in changed if f.startswith(prefix)]
        if touched:
            bad(f"check16: existing transport/producer changed: {touched}")

    # 17. No shared runtime activation: workers not referenced in any compose/k8s/helm/workflow.
    for prefix in ("infra/", "helm/", "k8s/", ".github/workflows/"):
        for f in changed:
            if f.startswith(prefix):
                bad(f"check17/18: forbidden deployment path changed: {f}")
    # And the orchestrator must not import/activate the workers.
    for path in (ROOT / "apps" / "orchestrator").rglob("*.py"):
        txt = path.read_text(encoding="utf-8", errors="ignore")
        if "lifecycle_poller" in txt or "outbox_relay" in txt:
            bad(f"check17: orchestrator activates a BE2 worker: {path.relative_to(ROOT)}")

    # 18. No deployment / forbidden path.
    for f in changed:
        for prefix in FORBIDDEN_CHANGED_PATHS:
            if f.startswith(prefix):
                bad(f"check18: forbidden path changed: {f}")

    # 19. No resume/dispatch implemented.
    for banned in (
        "resume_dispatch",
        "def request_resume",
        "def authorize_resume",
        "workflow_resume",
    ):
        if banned in poller or banned in relay:
            bad(f"check19: resume/dispatch behavior added: {banned}")

    # 20. No external notification.
    if re.search(
        r"(discord|slack|telegram|smtp|send_notification|external_send)",
        poller + relay,
        re.IGNORECASE,
    ):
        bad("check20: external notification added")

    # 21. Mandatory tests exist for the required behaviors.
    for needle in (
        "def test_pg_reminder_due_records_state_and_outbox_atomically",
        "def test_pg_expiry_transitions_clarification_task_and_outbox_atomically",
        "def test_pg_two_workers_reminder_exactly_one_claim",
        "def test_pg_reminder_rollback_leaves_no_state_or_outbox",
        "def test_pg_expiry_task_update_failure_rolls_back_clarification_and_outbox",
        "def test_pg_relay_transient_failure_schedules_backoff_without_exhausting",
        "def test_pg_relay_exhausts_to_dead_after_bounded_attempts",
        "def test_pg_relay_crash_before_commit_leaves_row_recoverable",
        "def test_pg_operator_replay_foundation_dead_to_pending",
    ):
        if needle not in tests:
            bad(f"check21: mandatory test missing: {needle}")

    # 22. Records state BE3/Codex/Claude Design posture + independent review required.
    impl_text = " ".join(
        RECORDS[k].read_text(encoding="utf-8").lower() for k in ("impl", "handoff", "safety")
    )
    if "be3" not in impl_text or "not authorized" not in impl_text:
        bad("check22: BE3 not-authorized posture not recorded")
    if "independent review" not in impl_text:
        bad("check22: independent review requirement not recorded")

    # 23. progress.md updated.
    if "66c.4-be2" not in progress_low:
        bad("check23: source/progress.md does not reference Stage 66C.4-BE2")

    if MARKER not in RECORDS["test-record"].read_text(encoding="utf-8"):
        bad("marker missing from test record")

    if failures:
        print(f"{MARKER}: FAIL")
        return 1

    print("  [OK] Reminder + expiry pollers with canonical statement_timestamp() predicates; state")
    print(
        "       + outbox atomic via the BE1 transaction-aware insert under FOR UPDATE SKIP LOCKED;"
    )
    print("       clarification_expired task status reused, no new status; relay publishes to the")
    print("       single canonical audit destination with persisted backoff, terminal dead, and an")
    print("       internal-only replay foundation; metrics/health present; at-least-once stated,")
    print("       exactly-once disclaimed; canonical dotted event names; no migration, no producer")
    print("       cutover, no transport change, no shared activation, no deployment, no")
    print("       resume/dispatch, no external notification; mandatory tests present; BE3/Codex/")
    print("       Claude Design unauthorized; independent review required; progress.md updated.")
    print(f"{MARKER}: PASS")
    print("  NOTE: self-verification only; BE2 technical closure requires the independent")
    print("        Step 66C.4-BE2-R reviewer.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
