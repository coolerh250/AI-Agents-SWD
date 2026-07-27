# Step 66C.4-BE3-B-C1 — Policy Authority and Command Routing Alignment

> **Targeted alignment of BE3-B (same implementation session, no subagent). NOT FOR MERGE (Draft PR
> #20). No BE3-C, no merge, no deployment, no shared migration, no real resume/replay execution.**

Two independent gaps were confirmed and closed.

## 1. Policy authority authentication boundary

**Before:** `_policy_authority` accepted ANY authenticated actor (whatever `X-Task-Actor`/`X-Task-Role`
the caller sent) as long as they presented the correct `X-Resume-Policy-Authority` header value,
compared with plain `!=`. A plain Operator who learned or guessed the capability could add the
header themselves and become the policy authority.

**Now:** resolving the policy authority requires BOTH:

```text
1. authenticated actor id (X-Task-Actor) == a server-configured TRUSTED PRINCIPAL id
   (BE3_RESUME_POLICY_AUTHORITY_PRINCIPAL_ID) -- an internal service account, never an
   Operator's own actor id, even if they add the header themselves.
2. the presented capability (current OR previous, for rotation:
   BE3_RESUME_POLICY_AUTHORITY_CAPABILITY[_PREVIOUS]) matches via hmac.compare_digest
   (constant-time; never `==`/`!=` on the secret).
```

Both checks always run (no short-circuit), so failure timing cannot distinguish "wrong principal"
from "wrong/missing capability" from "not configured" — every failure raises the identical
`403 policy_authority_required`. The presented value is never interpolated into a log, audit
payload, exception detail, or response body (proven by
`test_api_capability_never_leaks_into_response_or_audit`). An oversized (>256 chars) or empty
presented value is rejected outright, before any comparison. The whole router's feature gate
(`_require_api_enabled`) still runs BEFORE the policy-authority resolver, so a disabled API never
performs a credential comparison or a DB operation (proven by
`test_api_feature_gate_off_never_compares_capability`, which makes the comparison function raise if
called). An unauthenticated caller (no `X-Task-Actor`/`X-Task-Role`) is rejected by the existing
fail-closed test auth before the capability is ever inspected.

The resolved Actor carries a fixed role label, `_POLICY_AUTHORITY_ROLE = "policy_authority"` — not
one of the six `TASK_ROLES` and never the caller's own `X-Task-Role` — and `is_policy_authority=True`,
which `authorization_policy.evaluate` (unchanged from BE3-A-C1) restricts to ONLY
`authorize_resume`/`reject_resume`: the policy authority can never request, cancel, or consume, and
the independent production-approval gate (delegated to `authorization_service.consume`) is untouched.

**Rotation:** current + previous dual-value smoothing (`BE3_RESUME_POLICY_AUTHORITY_CAPABILITY` +
`_CAPABILITY_PREVIOUS`) — an operator sets a new value while keeping the old one valid, then clears
`_PREVIOUS` once every internal caller has switched. No second parallel authentication framework was
introduced; the constant-time-comparison idiom (`hmac.compare_digest`) reuses the codebase's existing
`alert_receiver.py` precedent rather than inventing a new one.

## 2. Command outbox destination compatibility

**Findings:**
- **A.** `resume.execution_requested`'s durable destination is a `clarification_lifecycle_outbox` row
  classified `DESTINATION_ORCHESTRATOR_COMMAND` — the SAME table as audit evidence, discriminated
  by an explicit `event_type -> destination` classification (`EVENT_DESTINATIONS`), never guessed.
- **B.** No relay/consumer is responsible for it yet. A dedicated orchestrator-command consumer is a
  SEPARATE, not-yet-built component (out of scope for BE3-B/B-C1).
- **C.** The existing BE2 audit relay (`ClarificationOutboxRelay`) does NOT claim it: its claim query
  now filters `event_type = ANY($1)` against `audit_relay_claimable_event_types()`, which is derived
  from `EVENT_DESTINATIONS` and structurally excludes every `DESTINATION_ORCHESTRATOR_COMMAND` type.
- **D.** N/A — never claimed, so never published anywhere.
- **E.** In the current disabled posture (`BE3_RESUME_COMMAND_ENABLED` defaults false), zero command
  rows are ever created, so there is no accumulation today. Once the gate is enabled in a future,
  separately-authorized activation, a command consumer + retry/DLQ + metrics/health + a verified
  rollback + a runtime E2E + explicit PO activation authorization are ALL required first
  (be3-runtime-activation-gate.md, unchanged) — this stage builds none of them.

**Model chosen:** a variant of Option A (single transactional outbox, explicit per-event-type
destination classification) rather than a second dedicated command table — `EVENT_DESTINATIONS` is
the single source of truth; `set(EVENT_DESTINATIONS) == ALLOWED_EVENT_TYPES` is asserted at import
time, so a new event type added without a destination fails the module import outright. There is no
"guess by event_type but every relay claims it" ambiguity: `destination_for_event_type` raises for
anything unclassified, and the relay's claim set is built FROM the classification (fail-closed by
construction, not a denylist that must be kept in sync).

**Changes (both already-merged BE2 files, extended — not replaced — per the allowed scope):**
- `shared/sdk/tasks/lifecycle_outbox.py`: `DESTINATION_AUDIT` / `DESTINATION_ORCHESTRATOR_COMMAND`,
  `EVENT_DESTINATIONS`, `destination_for_event_type`, `audit_relay_claimable_event_types`,
  `count_pending_by_destination` (read-only visibility helper; not a consumer).
- `shared/sdk/tasks/outbox_relay.py`: the claim query (`publish_one`) and the backlog sampler
  (`_sample_backlog`) are now scoped to `audit_relay_claimable_event_types()`. Fully backward
  compatible: every pre-existing (audit) event type is still claimed/published exactly as before;
  only the new orchestrator-command type is excluded.

## Verification

```text
STEP66C4_BE3_B_AUTHORITY_ROUTING_ALIGNMENT_VERIFY: PASS
Tests: see docs/test/step66c4-be3-b-c1-authority-routing-alignment-record.md (isolated ephemeral
PostgreSQL 16; 0 failed / 0 skipped). ruff / black / mypy clean. No orchestrator call, no resume
execution, no replay_dead, no BE3-C, no shared migration/deployment, no worker/relay activation.
production_executed_true_count = 0.
```

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
