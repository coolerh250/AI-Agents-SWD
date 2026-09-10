# AT-D38 — AT-M3.6B.2 Runtime Image Redeploy Evidence Reconciliation

> **Product Owner decision record. Does NOT authorize, execute, or repeat a redeploy. It
> independently re-verifies, from the currently running non-production test runtime, that a
> runtime image redeploy reported from a prior execution session actually occurred and actually
> carries the AT-D37 Sonnet 5 request-contract remediation, and writes that verified state back to
> canonical PM/source-of-truth. Authorizes NO Anthropic call, NO live-gate enablement, NO
> budget-policy mutation, NO credential access, NO rebuild, NO further redeploy, and NO application
> code change. `production_executed_true_count: 0`.**

```text
AT-D38:                      RESOLVED / BINDING
Recorded_on:                 2026-09-10
Recorded_by:                 Product Owner
Canonical_main:               4282cda794be55203be6b65a47d43a18bdf93e76 (unchanged by this record)
Depends_on:                  AT-D32, AT-D33, AT-D34, AT-D35, AT-D36, AT-D37
Scope:                        Independent read-only runtime re-verification + docs-only
                               reconciliation. No implementation, no runtime mutation.

AT-M3.6B.2 RUNTIME IMAGE:    REDEPLOYED / VERIFIED / CLOSED
AT-M3.6B.2 LIVE VALIDATION:  AUTHORIZED / READY_FOR_COMBINED_EXECUTION
AT-D32 real requests:        1 of 12 CONSUMED (unchanged; independently reconfirmed)
AT-D32 requests remaining:   11
Retained unresolved reservation: US$0.016086 (unchanged; independently reconfirmed)
Budget policy (d29ad073-9f7c-48b4-876d-cd3cb1343b40): INACTIVE (independently reconfirmed)
LIVE_NETWORK_GATE:           DEFAULT FALSE (independently reconfirmed)
Real Anthropic calls (this reconciliation):        0
Diagnostic Anthropic calls (this reconciliation):  0
AT-M4:                       NOT AUTHORIZED
Production:                  NOT GRANTED
production_executed_true_count: 0
```

## 1. What this record does

A runtime image rebuild/redeploy of the internal non-production test orchestrator — the action
`NEXT_PERMITTED_STAGE` named after AT-D37 — was carried out in a prior execution session. That
session's result had not yet been durably reconciled into canonical PM state or
`source/progress.md`; `AI_AGENTS_PM_STATE.md` still read `AT_M3_6B_2_RUNTIME_IMAGE:
REDEPLOY_REQUIRED` as of the AT-D37 canonicalization commit.

Per the execution standard, an implementation report is a CLAIM and independently reproduced
evidence is PROOF. This record does not trust the prior report's claims on their own; it
independently re-derives each one directly from the running system and only then reconciles.

## 2. Independent runtime evidence, reproduced this session

All checks below were run read-only against the live `aiagents-test` stack on the internal
non-production test host. No rebuild, redeploy, restart, application code change, database
mutation, migration, budget-policy mutation, live-gate enablement, or Anthropic call (real or
diagnostic) was performed to produce any of them.

```text
1. Orchestrator health
   aiagents-test-orchestrator-1   Up (healthy)   created 2026-09-10T04:01:49Z
   /health -> {"service":"orchestrator","status":"ok"}

2. Deployed source vs canonical main
   Test-runtime checkout HEAD:     4282cda794be55203be6b65a47d43a18bdf93e76
     (a descendant of the AT-D37-accepted implementation d1deae9; includes it in full)
   `git diff 4282cda -- shared/ apps/ agents/ migrations/ infra/ scripts/ tests/` -> empty
   `git status --short` in the checkout -> clean
   sha256(shared/sdk/agent_reasoning/anthropic_provider.py) checkout == running container, both
     973ac599ed31c5c4a4136b560b8af6cb1c07bcf83fa6d8b8e9af08b0ecfea655
   sha256(shared/sdk/agent_reasoning/live_config.py) checkout == running container, both
     bf2b99f97557d69972728c2f8dc4d4c0268d3cb4221de2e0f7f429a2a529adcb

3. Old defective request path (158c8a8) no longer served
   Running container source contains no `"temperature"` / `temperature=` / `top_p` / `top_k`
   assignment anywhere in build_request()'s return payload -- only an explanatory comment
   referencing why they were removed. 158c8a8 is independently confirmed (section 2 above) to be
   an ancestor state the running checkout has moved past, not the running checkout.

4. build_request() zero-network verification, executed inside the running container
   (PYTHONPATH=/app, in-process, no HTTP client constructed -- build_request() is a pure
   dict-building method with no I/O, confirmed by direct source read before execution)
   propose             -> keys={max_tokens,messages,model,system}  temperature=false top_p=false
                           top_k=false  model=claude-sonnet-5
   critique             -> same shape, same result
   summarize_decision   -> same shape, same result
   decompose_plan       -> same shape, same result
   Verification script copied into the container via `docker cp`, executed, then deleted from
   both the container and the host afterward.

5. Live-network gate
   REASONING_LIVE_NETWORK_ENABLED=false (container environment, read directly)
   /operations/safety -> "reasoning_live_enabled": false

6. AT-D33 budget policy status
   Postgres SELECT (read-only) on llm_budget_policies WHERE
     policy_id='d29ad073-9f7c-48b4-876d-cd3cb1343b40':
     status=inactive, scope_type=provider, provider=anthropic, enforcement_mode=block,
     max_cost_per_day_usd=5.000000, max_cost_per_month_usd=5.000000
   /operations/safety -> "llm_budget_policy_active": false

7. AT-D32 historical evidence, preserved and independently reconfirmed
   Exactly ONE `reserved_usage` budget-ledger event exists for provider=anthropic against this
   policy, ever:
     budget_event_id 7dae4765-bda6-4de7-890c-45cc3abd2420, estimated_cost_usd=0.016086,
     reservation_key=75795266-bd86-4760-b2df-b119266402f4:1, created_at 2026-09-09 09:32:14 UTC
   Tied invocation 75795266-bd86-4760-b2df-b119266402f4: reasoning_verb=propose,
     provider_mode=live, model_name=claude-sonnet-5, status=failed,
     failure_category=provider_unauthorized, latency_ms=796. No `actual_cost_usd` and no
     `released_reservation` event exist for this key -- the reservation remains retained and
     unresolved, exactly as previously recorded. No `reserved_usage` or `preflight` event for
     provider=anthropic exists after this one. No such event exists after 2026-09-09
     12:00:00 UTC, i.e. none occurred during today's redeploy or during this reconciliation.

8. Postgres schema alignment (migrations 039-045)
   `reasoning_invocations.artifact_type` column present, with the exact per-verb CHECK constraint
   tying it to reasoning_verb. `provider_mode` CHECK admits 'live'. `reasoning_verb` CHECK admits
   'decompose_plan'. All independently read directly from `\d reasoning_invocations`, not assumed.

9. Vault
   `vault status` inside aiagents-test-vault-1: Initialized=true, Sealed=false, Seal Type=shamir
   /operations/safety -> "vault_reachable": true, "vault_configured": true

10. SecretProvider
    Container env: SECRET_PROVIDER=vault. `shared/sdk/secrets/provider.py`'s factory resolves
    `SECRET_PROVIDER=vault` to `VaultKvSecretProvider`.
    /operations/safety -> "secret_provider": "vault", "secret_provider_status": "vault",
      "mock_vault_enabled": false

11. Credential exposure
    `ANTHROPIC_API_KEY` absent from the container's long-lived environment -- the only
    Anthropic-related env var present is `REASONING_PROVIDER=anthropic` (a provider selector, not
    a credential). No secret value was read, rendered, hashed, or measured at any point in this
    reconciliation.

12. Anthropic real calls during this reconciliation: 0
13. Anthropic diagnostic calls during this reconciliation: 0
    (both established by item 7's ledger query -- zero anthropic-provider budget events of any
    kind since the single historical reservation, and this session issued none)

14. production_executed_true_count
    /operations/safety -> "production_executed_true_count": 0
```

No runtime proof contradicted the prior redeploy report on the specific claims it made about the
redeployed image's content, the request contract, the live-gate posture, the budget-policy state,
or the AT-D32 historical evidence. This record therefore reconciles the redeploy as **CLOSED /
CANONICAL** rather than issuing `REDEPLOY_REQUIRED`.

## 3. Disclosed observation — not a blocker

Independent inspection of `reasoning_invocations` in the runtime's own `aiagents` database (the
database `DATABASE_URL` on the running orchestrator actually points at) found roughly thirty
additional rows with `provider_mode='live'`, dated 2026-09-09, distinct from the one row named in
section 2 item 7. They carry consistent markers of the injected in-process test transport the
adapter's own module docstring describes ("every test in this slice drives the adapter through an
injected in-process transport"): uniform `input_tokens=400` / `output_tokens=300`, single-digit-
to-low-double-digit millisecond latencies inconsistent with a real network round trip, and mostly
NULL `project_id` / `requested_by_principal_id`. None of them has a matching `llm_budget_events`
row of any kind for the AT-D33/AT-D35 policy -- and the adapter's own enforced ordering (budget
reservation strictly precedes the wire) means a `reasoning_invocations` row with no matching
reservation never reached the wire. Cross-checked against the complete budget ledger (section 2
item 7), exactly one `reserved_usage` event for provider=anthropic exists in this database's
history, full stop -- confirming AT-D32's "1 of 12 consumed" figure is exact and these extra rows
carry no real spend and represent no additional external call.

This reads as test-suite output that landed in the shared runtime database rather than an
isolated per-run database -- a test-hygiene gap, not a budget, authorization, or external-call
integrity failure. It is recorded here for transparency rather than left undisclosed. It maps to
the already-deferred "P2 test-DB isolation cleanup" item named in
`AI_AGENTS_PM_STATE.md` `NEXT_PRODUCT_STAGE`, and this record does not create new debt for it --
it confirms the existing deferral is still accurate and still non-blocking (no P0/P1 risk named:
not a production action, not an authorization bypass, not a secrets exposure, not a budget-
integrity break).

## 4. What this record does NOT do

```text
Does NOT perform, repeat, or authorize a redeploy -- the redeploy already happened in a prior
   session; this record only verifies and reconciles its result
Does NOT rebuild or restart any container
Does NOT change any application code
Does NOT mutate the database in any way -- every Postgres access in this record was SELECT-only
Does NOT activate, deactivate, or otherwise mutate the AT-D33/AT-D35 budget policy -- confirmed
   inactive, left exactly as found
Does NOT enable REASONING_LIVE_NETWORK_ENABLED, not even briefly
Does NOT read, render, hash, measure, rotate, or otherwise access the value of ANTHROPIC_API_KEY
   or any other credential
Does NOT make a real or diagnostic Anthropic call of any kind
Does NOT authorize AT-M3.6B.2 Live Validation execution, budget-policy reactivation, or any part
   of the combined live-execution stage named next below -- that stage must create its own
   separate AT-D before any budget-policy activation or Anthropic call, exactly as its own prior
   authorization already required
Does NOT authorize AT-M4 or any real work execution
Does NOT grant production authorization -- NOT GRANTED, unchanged
Does NOT amend AT-D32, AT-D33, AT-D34, AT-D35, AT-D36, or AT-D37
```

## 5. Next decision

`AT-M3.6B.2 LIVE VALIDATION EXECUTION — Combined Budget Activation and Terminal Cleanup`. The
Product Owner authorization previously granted in principle for that combined execution remains
conceptually valid, but that execution must still create its own next durable AT-D (expected
AT-D39, to be confirmed from repository truth at that time, not assumed here) before any
budget-policy activation or Anthropic call. This record's AT-D38 is the redeploy-reconciliation
decision only and is not combined with that next one.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
