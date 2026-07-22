# Step 66C.4-BE1 Deferred LOW Findings

> **Deferral record. Nothing in this file was fixed in Step 66C.4-BE1-R1. No implementation change
> is authorized by this document.**

These findings come from the Step 66C.4-BE1-R independent review
(`review/66c4-be1-technical-security-migration` @ f5417f4). They are recorded here so they are
tracked rather than silently carried, and deliberately NOT fixed in BE1-R1, whose scope is the two
blocking findings and the medium payload finding only.

## L-3 -- a deleted clarification is reported as "already answered"

```text
Finding:        In apps/orchestrator/src/workroom_api.py::answer_clarification, when the post-claim
                re-read returns None (the row disappeared between the claim attempt and the
                re-read), the handler falls through to 409 clarification_already_answered.
Severity:       LOW (independent security review L-3).
Current impact: Misleading, not unsafe. No state is mutated, no information is disclosed, and no
                code path in this repository deletes operator_clarification_requests rows, so the
                condition is unreachable today.
Reason for
deferral:       Fixing it means introducing a new API error semantic (a not-found / gone
                classification) for the answer endpoint. Step 66C.4-BE1-R1 is explicitly scoped to
                the deadline predicate and timestamp for API-adjacent change; widening error
                semantics here would be an unauthorized scope expansion and would change a
                response contract the Admin Console consumes.
Recommended
future stage:   Step 66C.4-BE3, or a 66C.4 API hardening slice, together with any other
                answer-endpoint error-semantics work so the frontend contract changes once.
Status:         OPEN, DEFERRED. Not fixed in BE1-R1.
```

## L-2 -- idempotency_key is inserted without format validation

```text
Finding:        shared/sdk/tasks/lifecycle_outbox.py applies no length, charset or format
                validation to idempotency_key; the only guards are the DB non-empty CHECK and
                UNIQUE.
Severity:       LOW (independent security review L-2).
Current impact: No injection risk (SQL is fully parameterized). Keys are deterministic and
                server-derived ("{clarification_id}:reminder"), and there is no live producer, so
                no operator-influenced string can reach the column today. Residual risks are a
                deliberately crafted colliding key suppressing a legitimate event, and a key over
                roughly 2704 bytes raising a btree index error at insert time.
Reason for
deferral:       The risk becomes real only when BE2 introduces a producer. Validating the key shape
                belongs with the producer that constructs it, so validation and key derivation are
                reviewed together rather than drifting apart.
Recommended
future stage:   Step 66C.4-BE2, as part of the producer/relay slice, validating against the
                deterministic "{uuid}:{event-suffix}" shape at the repository boundary.
Status:         OPEN, DEFERRED. Not fixed in BE1-R1.
```

## L-1 -- payload size cap and event-type allowlist are not DB-enforced

```text
Finding:        MAX_PAYLOAD_BYTES and the event-type allowlist live in the Python helper; the table
                has no payload-size or event-type CHECK.
Severity:       LOW (independent security review L-1).
Current impact: None today (no producer). A future code path inserting with raw SQL would bypass
                both.
Partial action
in BE1-R1:      last_error IS now bounded by a DB CHECK (chk_clo_last_error_bounded), because that
                column is written on every failure path and its content is operator-facing. The
                payload-size and event-type CHECKs were NOT added.
Reason for
deferral:       Adding schema beyond what the blocking findings require is the self-expansion this
                stage must avoid, and the protection is weak against the stated threat: a producer
                willing to bypass the helper can equally construct a payload that satisfies a size
                CHECK.
Recommended
future stage:   Step 66C.4-BE2, decided together with the producer's insert path.
Status:         OPEN, DEFERRED. Not fixed in BE1-R1.
```

## Informational items carried forward (no action required)

```text
I-1  Outbox foreign keys use NO ACTION, so deleting a clarification/task that has outbox rows is
     refused rather than cascading. This is the SAFE direction for audit evidence. Recorded so a
     future stage adding deletion does not discover it by surprise.
I-2  No logging is emitted by the BE1/BE1-R1 modules, so no payload can leak through logs.
I-3  All SQL added by BE1/BE1-R1 is fully parameterized; clarification_id is coerced through
     uuid.UUID(...) before use.
```

## Statement

Deferral record only. No implementation change. No API change. No schema change beyond the
blocking-finding remediation recorded elsewhere. No deployment. No merge.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
