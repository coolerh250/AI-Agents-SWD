# Step 66C.4-BE2-R1-R — Replay Boundary Closure Review

> Independent review record. Not deployed. Not a merge authorization. No shared activation.

## Original finding (c70f205, MEDIUM future-tied)

`replay_dead` (dead -> pending foundation) has no authorization boundary — safe only because it is
unexposed. BE3 must add RBAC when wiring an operator replay control.

## What the code does now (`shared/sdk/tasks/outbox_relay.py`, `replay_dead`)

An internal async method that returns one `dead` row to `pending` (preserving `event_id` and
`idempotency_key`, NOT resetting `attempts`, resetting `available_at`, clearing `dead_at`/
`last_error` per `plan_replay_state`). It performs NO live publication of its own and carries a
docstring stating it is NOT a public endpoint and NOT wired to any API or Admin Console control.

## Independent verification — zero runtime callers

Word-boundary scan (`replay_dead\b`, so the unrelated retry-scheduler `replay_deadletter` is not a
false positive) across `apps/**` and `shared/**` excluding the definition site:

```text
callers found: []   (only the definition, the two verifiers, and tests reference the name)
```

No HTTP/API route, no Admin Console control, no orchestrator/worker-startup, no automatic loop
invokes `replay_dead`. Confirmed by this reviewer's own test
(`test_indep_replay_dead_has_no_runtime_or_startup_caller`) and independently by the BE2 and BE2-R1
verifiers.

## BE3 prerequisites (binding)

The remediation record binds, as BE3 prerequisites before any operator replay control is wired:
RBAC, human authorization, replay audit evidence, and authorization-outcome persistence. This is
carried forward openly; it is NOT a closure blocker because nothing is exposed or activated at BE2.

## Verdict

**Replay boundary: INTERNAL-ONLY and SAFE.** Non-blocking, future-tied to BE3.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
