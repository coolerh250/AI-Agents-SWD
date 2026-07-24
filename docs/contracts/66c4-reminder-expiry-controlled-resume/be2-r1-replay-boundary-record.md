# Step 66C.4-BE2-R1 — Replay Authorization Boundary Record (PO decision 1.4)

> **Remediation record. NOT deployed. NOT runtime validated.**

## Finding (independent review, MEDIUM — future-tied)

`replay_dead` (dead -> pending) has no authorization boundary. It is safe while unexposed, but a
future stage that wires replay to an operator control must add RBAC and human authorization.

## Decision (PO 1.4)

`replay_dead` remains internal-only for BE2-R1:

```text
- no public API / endpoint
- no Admin Console caller
- no startup caller
- no automatic replay loop
```

No RBAC or endpoint is added in this stage. Instead, a defense-line test asserts the boundary, and
this record binds the BE3 prerequisites.

## Defense-line test

`tests/test_step66c4_be2_r1_remediation.py::test_replay_dead_has_no_public_or_runtime_or_startup_caller`
scans `apps/**` and `shared/**` (excluding the definition site `outbox_relay.py`) with a
word-boundary match for `replay_dead` and asserts ZERO callers. (The unrelated retry-scheduler
`replay_deadletter` is excluded by the word boundary.)

## BE3 prerequisites (BINDING for any future replay control)

```text
- Team/operator RBAC on the replay action.
- Explicit human authorization before a dead row is replayed.
- Replay audit evidence (who authorized, when, which event_id).
- Authorization-outcome persistence.
```

Until all four exist, replay stays an internal foundation with no operator-facing surface.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
