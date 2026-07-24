# Step 66C.4-BE2-R1-R — Historical Tests / Verifiers Closure Review

> Independent review record. Not deployed. Not a merge authorization. No shared activation.

## Scope

Three historical assertions changed in `319123b..c2677f7`, plus the BE2 verifier's narrowed
transport check. Confirming they only remove PO-overturned old behaviour, do not weaken other
safety invariants, do not rewrite the `c70f205` findings/verdict, and do not broaden the
zero-caller / non-activation allowlist.

## The three modified assertions

```text
1. tests/test_step66c4_be2_reminder_expiry_outbox_relay.py
   test_pg_expiry_..._protects_terminal_task -> renamed ..._suppresses_terminal_parent.
   OLD behaviour asserted (expired + emitted, task guard-protected) was the B-1 bug. NEW asserts
   PO 1.1 suppression: clarification stays 'open', task stays terminal, 0 outbox rows, cycle == 0.
   The 'answered is skipped' invariant is RETAINED. The dropped 'canceled clarification skipped'
   assertion is still covered by the claim guard (status='open' AND answered_at IS NULL) — not a
   safety-invariant loss.

2. same file, test_pg_relay_exhausts_to_dead_after_bounded_attempts
   attempts 4 -> 5 (MAX_PUBLISH_ATTEMPTS, PO 1.2). Still asserts dead_at set, published_at NULL,
   and NO 'redis' substring in last_error (secret-free). Only the PO-overturned count changed.

3. tests/test_step66c4_be1_r1_remediation.py, test_retry_plan_persists_backoff_then_dies
   MAX_DELIVERY_ATTEMPTS-1 -> MAX_PUBLISH_ATTEMPTS-1 (the off-by-one that never reached 3600).
   Terminal assertions (status dead, set_dead_at True, backoff None) unchanged.
```

All three remove only PO-overturned old behaviour. None rewrites the `c70f205` review docs (which
live on a separate branch and are untouched by the feature diff) or its verdict.

## Verifier integrity

```text
scripts/verify_step66c4_be2_reminder_expiry_outbox_relay.py:
  - shared/sdk/event_bus/ removed from TRANSPORT_UNCHANGED_PATHS, REPLACED by a PRECISE POSITIVE
    check16b asserting the exact backward-compatible signature
    ('socket_timeout: float | None = None' AND 'socket_connect_timeout: float | None = None').
    Not a bare deletion — a positive guard on the additive change.
  - check16 still forbids changes to shared/sdk/audit/, retry-scheduler, notification-worker,
    audit-worker; check17 still forbids infra/helm/k8s/workflow activation.
scripts/verify_step66c4_be2_r1_remediation.py (new): check15 word-boundary replay_dead zero-caller
  scan; retry constants exact; timeout range fail-closed; wait_for + cancellation present.
```

The zero-caller / non-activation allowlist is NOT broadened: a 3rd runtime caller of `replay_dead`,
or a shared compose/startup registration of either worker, would still fail
`test_indep_replay_dead_has_no_runtime_or_startup_caller`, the BE2-R1 verifier check15, and the BE2
verifier check17. Independently re-confirmed by re-running both verifiers (both `PASS`) and this
reviewer's own tests.

## Verdict

**Historical safeguards: INTACT.**

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
