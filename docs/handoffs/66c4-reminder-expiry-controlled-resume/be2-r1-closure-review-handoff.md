# Step 66C.4-BE2-R1 → Independent Closure Review Handoff

> **Handoff. PR #18 is Draft / NOT FOR MERGE. The remediation session does NOT review its own work,
> does NOT approve a merge, does NOT deploy, and does NOT start BE3. Only the independent
> Step 66C.4-BE2-R1-R reviewer may set `BE2_TECHNICAL_VERDICT`.**

## What the reviewer reviews

```text
Branch:            feature/66c4-be2-reminder-expiry-outbox-relay
Base:              origin/main @ ab3c6cc (BE1 merged)
Prior review:      review/66c4-be2-poller-relay-transaction-recovery @ c70f205
                   (BE2_TECHNICAL_VERDICT: REMEDIATION_REQUIRED -- the two findings closed here)
BE1 outbox schema: migration 031 (on main), UNCHANGED by BE2 and BE2-R1.
```

Executed by Step 66C.4-BE2-R1-R: a FRESH Claude Code review subagent, independent session,
independent worktree. Judge only from the canonical contract, PO decisions, the exact commit, the
committed records, the code, and the tests; do NOT fix anything, merge, deploy, or start BE3.

## Markers (never conflate)

```text
STEP66C4_BE2_R1_REMEDIATION_VERIFY: PASS   -- the remediation session's self-verification.
STEP66C4_BE2_R1_PG_REDIS_EVIDENCE: PASS    -- the remediation session's real-DB test evidence.
BE2_TECHNICAL_VERDICT (PASS | REMEDIATION_REQUIRED) -- only the independent reviewer may set this.
```

## What must be independently re-verified

```text
B-1 (blocking, now claimed closed):
  1. Expiry locks the parent task and reads its status BEFORE any mutation.
  2. Transition happens ONLY from clarification_needed; the guarded task UPDATE rowcount is
     asserted == 1; a 0-row result rolls back clarification + task + outbox (independently
     reproduce a rowcount-0 race).
  3. A terminal parent (accepted/rejected/canceled/archived/failed/completed/aborted) is
     suppressed: no clarification/task/outbox mutation, terminal_parent_suppressed metric, safe
     diagnostic, no clarification.expired event.
  4. A non-terminal, non-clarification_needed parent (e.g. running) is a reconciliation failure:
     no mutation, reconciliation_failure metric, safe diagnostic; not a silent unobservable retry.
  5. Lock ordering (clarification-then-task) introduces no deadlock vs the answer/task-update paths.

B-2 (blocking, now claimed closed):
  6. The Redis client has non-None socket_timeout and socket_connect_timeout.
  7. The publish await is bounded by asyncio.wait_for (default 5s, range [1,30], out-of-range
     rejected at construction, not clamped). Independently reproduce a broker hang and confirm the
     DB transaction / row lock is released, the row is a persisted retry (attempts+1, future
     available_at, last_error='redis_publish_timeout'), and it is NOT marked published.
  8. asyncio.CancelledError rolls back and re-raises; the row stays pending, attempts unchanged.

Retry (PO 1.2):
  9. MAX_RETRIES=4, MAX_PUBLISH_ATTEMPTS=5; backoffs 30/120/600/3600 all reached; dead on the 5th
     failure; the 3600 branch is actually exercised.

Replay (PO 1.4):
  10. replay_dead has zero public/runtime/startup callers and no automatic loop.

Cross-cutting:
  11. last_error and logs carry no raw payload/secret/DSN.
  12. No migration/schema change; BE1 031 unchanged. The ONLY event_bus change is the additive
      bounded socket timeout (default None). No existing-producer cutover. No shared-runtime
      activation. No deployment. No resume/dispatch. No external notification.
  13. Mandatory PostgreSQL 16 suites run 0 skipped / 0 failed on isolated ephemeral containers; the
      reviewer should re-run them on its own ephemeral containers.
```

## Disclosed test changes (review directly)

Three previously-committed assertions encoded the OLD (pre-decision) behavior and were updated
MINIMALLY; see be2-r1-remediation-record.md "Disclosed changes to previously-committed tests":
the terminal-parent expiry test (now asserts suppression), the dead-attempts count (4 -> 5), and
the BE1-R1 retry-plan threshold (MAX_PUBLISH_ATTEMPTS-1). No previously-committed independent review
finding or verdict was modified, and the zero-caller/non-activation allowlist was NOT broadened.

## Posture

```text
PR #18:            Draft / NOT FOR MERGE.
Step 66C.4-BE3:    NOT authorized, NOT started.
Codex / Claude Design: NOT authorized.
Deployment / shared migration / producer cutover: NOT performed, NOT authorized.
```

## Statement

Handoff only. No deployment. No shared-runtime activation. No shared migration. No producer cutover.
No dispatch/resume. No external notification. No merge. No production or external action.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
