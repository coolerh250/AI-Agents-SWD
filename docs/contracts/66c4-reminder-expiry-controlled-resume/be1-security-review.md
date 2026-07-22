# Step 66C.4-BE1-R — Security Independent Review

> **Independent review artifact. No implementation change. No merge. No deployment. No production or
> external action. All probes were run by the reviewer against an isolated ephemeral test PostgreSQL.**

**Security verdict: NO CRITICAL, NO HIGH. One MEDIUM, three LOW, three INFORMATIONAL.**
(No security finding independently blocks PASS; the stage is nevertheless
`REMEDIATION_REQUIRED` for the deadline and outbox findings recorded elsewhere.)

## Scope reviewed

```text
migrations/031_clarification_lifecycle_outbox_foundation.sql (+ down)
shared/sdk/tasks/lifecycle_outbox.py
shared/sdk/tasks/workroom_store.py (claim_clarification_answer, _clar_row)
apps/orchestrator/src/workroom_api.py (answer_clarification 409 classification)
tests/test_step66c4_be1_data_model_deadline_outbox.py
```

## Findings

### M-1 (MEDIUM) — the payload-safety guard inspects only top-level keys, so a raw clarification body or a secret CAN reach the payload via nesting

`assert_safe_outbox_payload` iterates `for key in payload:` — the top level only — and compares each
key against an exact-match deny list. Independently probed:

```text
{'meta': {'answer': 'PATIENT SSN 123-45-6789 raw clarification body'}}  -> ACCEPTED
{'items': [{'token': 'ghp_realtokenvalue'}]}                            -> ACCEPTED
{'answer_body': 'raw body text'}                                        -> ACCEPTED
{'question_text': 'raw question'}                                       -> ACCEPTED
{'ANSWER': 'x'}                                                         -> rejected (case handled)
```

Case-insensitivity works (`str(key).strip().lower()`). Nesting does not, and exact-match means near
misses (`answer_body`, `question_text`, `auth_token`, `user_password`) pass. The canonical contract
requires the payload be "minimal, safe (no raw question/answer body; hash/length refs only)". The
guard as written does not enforce that requirement — it enforces a narrow subset of it.

Severity is MEDIUM, not HIGH, because there is no live producer: nothing in the runtime constructs an
outbox payload today, so no data can currently reach the table. The exposure becomes real the moment
BE2 writes a producer that relies on this guard as its safety boundary. Recommended minimum fix
(BE1-R1): walk the payload recursively, or invert to a positive key allowlist (`task_id`,
`clarification_id`, `reason`, `assigned_to`, `due_at`, `reminder_at`, hash/length refs), and reject
non-scalar leaf types.

### L-1 (LOW) — size cap and event-type allowlist are enforced only in the Python helper, not at the DB boundary

`MAX_PAYLOAD_BYTES = 2000` and `ALLOWED_EVENT_TYPES` live in `lifecycle_outbox.py`. The table has
CHECK constraints for status, non-negative attempts, and non-empty `event_type` / `idempotency_key`,
but none for payload size or event-type membership. Any code path that inserts with raw SQL rather
than through the helper bypasses both. Defence-in-depth suggestion: a
`CHECK (pg_column_size(payload) <= N)` and a CHECK or lookup constraint on `event_type`.

Note also that the size cap is measured on `json.dumps(payload)` before insertion, while the guard
runs before the event-type check — a caller passing an oversize payload and a bad event type gets the
size error first. Cosmetic only.

### L-2 (LOW) — `idempotency_key` is inserted unvalidated

The helper applies no length, charset or format validation to `idempotency_key`; the only guards are
the DB's non-empty CHECK and UNIQUE. There is no injection risk (see the SQL section), and the
contract's keys are deterministic and server-derived (`{clarification_id}:reminder`). The residual
risks are: (a) a caller could pass an operator-influenced string and thereby collide/suppress a
legitimate event, and (b) a key over roughly 2704 bytes cannot be indexed and raises a btree error at
insert time. Recommended: validate the key against the deterministic
`{uuid}:{event-suffix}` shape at the repository boundary so untrusted input can never become a key.

### L-3 (LOW) — `current is None` in the 409 classifier falls through to "already answered"

In `answer_clarification`, if the post-claim re-read returns `None` (row deleted between claim and
re-read), the handler reports `clarification_already_answered`. Misleading rather than unsafe: no
state is mutated and no information is disclosed. Deleting a clarification is not reachable through
any current code path.

### I-1 (INFORMATIONAL) — FK behaviour protects lifecycle evidence

Both outbox foreign keys (`clarification_id`, `task_id`) use the default `NO ACTION`. Deleting a
clarification or task that has outbox rows is therefore refused rather than cascading. This is the
safe direction for audit evidence: BE1 cannot silently destroy lifecycle events. No code path in this
repository deletes `operator_clarification_requests` rows, so no existing behaviour changes. Recorded
so that a future stage adding deletion does not discover it by surprise.

### I-2 (INFORMATIONAL) — no logging, so no payload leakage through logs

`lifecycle_outbox.py` and `workroom_store.py` contain no `logger`, `logging` or `print` calls; nothing
in the BE1 diff emits a payload, a question body, an answer body, or a connection string. The API diff
adds no logging either. The error messages raised by the guard include only the offending KEY name,
never the value — verified by inspection of the raised `ValueError` strings.

### I-3 (INFORMATIONAL) — SQL is fully parameterized

Every statement added by BE1 uses asyncpg positional parameters (`$1..$5`); there is no f-string,
`%`-format or concatenation of caller input into SQL anywhere in `lifecycle_outbox.py` or in the
modified `workroom_store.py`. `clarification_id` is additionally coerced through `uuid.UUID(...)`
before use in the CAS, which rejects any non-UUID string before it reaches the database. The payload
is passed as a bound parameter and cast with `$5::jsonb`, not interpolated.

## Explicit answers to the review questions

```text
Can a raw clarification body reach the payload?        YES, via a nested key -- finding M-1.
Can the key deny list be bypassed by nested keys?      YES -- finding M-1.
Can it be bypassed by case?                            NO (keys are lowercased and stripped).
Is the size cap enforced at the repository boundary?   YES in the helper; NOT at the DB -- L-1.
Are token/password/secret-like keys blocked?           At the top level only, by exact match -- M-1.
Is error metadata safe and bounded?                    YES: errors name the key, never the value; no
                                                       error text is persisted (there is no last_error
                                                       column -- see the outbox sufficiency review).
Is SQL parameterized?                                  YES, everywhere -- I-3.
Do logs emit full payloads?                            NO logging is added at all -- I-2.
Can the idempotency key be abused by untrusted input?  Not today (no producer); unvalidated -- L-2.
Does FK/delete behaviour endanger audit evidence?      NO -- NO ACTION protects it -- I-1.
Masking rule (no internal IP / SSH alias / username in committed files): the BE1 commit and this
  review's artifacts were checked; no internal IP, SSH alias or OS username appears in any
  committed file. Records use the neutral label "isolated ephemeral test Postgres".
```

## Statement

Independent security review artifact only. No implementation change. No secret handled. No external
action. No production action. No deployment. No merge.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
