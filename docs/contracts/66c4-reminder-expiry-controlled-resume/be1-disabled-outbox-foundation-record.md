# Step 66C.4-BE1 — Disabled Transactional-Outbox Foundation Record

> **The outbox is a DISABLED-BY-DEFAULT foundation. No relay, no scheduler, no live producer, no
> unconsumed accumulation. Producer cutover is gated by the BE1 Runtime Compatibility Gate.**

## Repository / model added

```text
shared/sdk/tasks/lifecycle_outbox.py (NEW):
  - insert_lifecycle_outbox_event(conn, *, clarification_id, task_id, event_type,
    idempotency_key, payload) -- transaction-aware INSERT using the CALLER'S connection.
  - assert_safe_outbox_payload(payload) -- rejects prohibited keys (question/answer/body/token/
    secret/password/credential/...) and oversize payloads (> 2000 bytes).
  - ALLOWED_EVENT_TYPES allowlist (reminder_sent/expired/resume_eligible/requested/authorized).
  - Read-only helpers get_lifecycle_outbox_event / list_pending_lifecycle_outbox_events (no
    claim/mutation -- there is no relay in BE1).
```

## Transaction-aware semantics

```text
insert_lifecycle_outbox_event takes an asyncpg connection owned by the caller. It NEVER opens its
own connection, NEVER begins/commits/rolls back, and NEVER closes the connection. A lifecycle state
mutation and its outbox insert can therefore commit atomically (both or neither) inside the caller's
transaction. Verified by test_pg_outbox_transaction_atomicity_and_idempotency: a rolled-back
transaction leaves zero outbox rows; a committed one persists exactly one; a duplicate
idempotency_key raises asyncpg.UniqueViolationError.
```

## Disabled-foundation gate (proven)

```text
1. No active outbox relay exists.                         -- no relay module/loop added.
2. No scheduler exists.                                    -- no poller/cron/background task added.
3. Existing producers remain on current audit/event paths. -- shared/sdk/audit/** and
     shared/sdk/event_bus/** are UNCHANGED (verified by the BE1 verifier's transport-unchanged
     git-diff check).
4. No runtime path inserts lifecycle outbox events.        -- only lifecycle_outbox.py and tests
     reference the module/table (static scan of apps/** and shared/** finds no other caller).
5. No lifecycle event can accumulate without a consumer.   -- no producer writes to the outbox, so
     nothing accumulates.
6. New outbox repository code is unreachable from live runtime flow. -- no import from any runtime
     module; test_outbox_module_has_no_live_producer_import + verifier check 13 enforce this.
7. No application-startup registration activates it.        -- nothing added to any service startup.
8. No compose/service/deployment definition adds a worker.  -- no infra/helm/k8s/compose change.
```

## Payload safety

```text
Prohibited keys rejected: question, answer, body, message, content, text, token, secret, password,
  credential(s), api_key, apikey, authorization, access_token, refresh_token, private_key.
Bounded size: <= 2000 bytes JSON. No raw clarification body, no secret, no full external payload
  can be stored. DB-layer defense-in-depth: chk_clo_event_type_nonempty /
  chk_clo_idempotency_key_nonempty CHECK constraints; SQL uses parameters (no string concatenation
  of user input).
```

## Contract-refinement note (forward, non-blocking)

```text
The outbox table implements EXACTLY the canonical data-model-contract.md columns (id,
clarification_id, task_id, event_type, idempotency_key, payload, status, attempts, created_at,
published_at + UNIQUE(idempotency_key)). Basic durable-retry state is carried by attempts + status
IN ('pending','published','dead').

BE1 did NOT self-expand the schema (per the stage's hard constraint). A future relay (BE2) will
likely want additional durable-retry columns that the canonical contract does not currently define
-- e.g. a next-attempt/backoff timestamp (available_at), a terminal-dead timestamp (dead_at), and
bounded last_error text. Per the stage rule "if the contract lacks durable-retry fields, report the
gap; do not self-expand", these are RECORDED HERE as a forward contract-refinement item for the
independent review (66C.4-BE1-R) and for BE2 to resolve via a contract update BEFORE the relay is
built. Their absence blocks nothing in BE1 (no relay exists; the outbox is disabled).
```

## Statement

Disabled outbox foundation record. No relay activated. No scheduler activated. No live producer
writes to the outbox. Existing audit/event transport unchanged. No dispatch/resume. No external
notification. No deployment.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
