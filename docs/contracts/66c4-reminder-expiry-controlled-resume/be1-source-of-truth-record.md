# Step 66C.4-BE1 Source-of-Truth Record

> **Source-of-truth record. The canonical BE1 foundation is now on `main` (8080141). It is NOT
> deployed and NOT runtime validated.**

## Canonical BE1 implementation is now on main

```text
Merge commit:        8080141
Reviewed head:       0bb9944
Final technical verdict: BE1_TECHNICAL_VERDICT: PASS (independent closure review 2e1c369)
```

## Authoritative BE1 facts

```text
Deadline predicate:   due_at > statement_timestamp()
Answer timestamps:    answered_at = statement_timestamp(); updated_at = statement_timestamp()
Time semantics:       now() == transaction_timestamp() (transaction-start time; NOT used for the
                      claim deadline). statement_timestamp() is the authoritative claim-execution
                      clock (constant within one statement).

Outbox foundation:    disabled / no live producer / no relay / no scheduler
Outbox durability fields:
                      available_at (NOT NULL, DEFAULT statement_timestamp())
                      dead_at
                      last_error (bounded; DB CHECK <= 500 chars)
                      published_at
                      attempts (CHECK >= 0)
                      status ('pending' | 'published' | 'dead', with a status/timestamp coherence CHECK)
                      idempotency_key (UNIQUE)
Payload model:        event-type positive allowlist (scalar-only values; nested/list/raw content
                      and column-owned keys rejected; canonical dotted event names)

Migration 031:        present in the repository on main; NOT applied to any shared runtime.
Runtime status:       NOT DEPLOYED / NOT RUNTIME VALIDATED
```

## Disabled-foundation invariant (reaffirmed)

```text
Without an active relay:
  - existing producers remain on their current audit/event paths (unchanged transport);
  - there are no runtime lifecycle outbox writes;
  - there are no unconsumed outbox events accumulating from runtime paths;
  - the disabled foundation exists only as schema + repository helpers + isolated tests.
```

## BE1 Runtime Compatibility Gate (still in force)

```text
The gate recorded in contract-source-of-truth-record.md is NOT weakened by this merge. Merging the
foundation does not authorize, and does not perform, a producer cutover. A runtime producer cutover
still requires relay, retry, DLQ, observability and rollback paths to be simultaneously available,
under a separately authorized stage. BE2 is the NEXT CANDIDATE but is NOT authorized.
```

## Later housekeeping (recommendation only, not executed)

```text
Review-evidence branches:
  review/66c4-be1-technical-security-migration @ f5417f4
  review/66c4-be1-r1-remediation-closure @ 2e1c369
Recommendation: ARCHIVE_OR_CLOSE_AFTER_SOURCE_OF_TRUTH_ACCEPTANCE.
This stage does NOT delete, close, force-push, or rewrite them.
```

## Statement

Source-of-truth record only. No deployment. No shared-runtime migration. No scheduler or relay
activation. No live producer cutover. No runtime outbox write. No dispatch/resume. No external
notification. No production or external action.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=true image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
