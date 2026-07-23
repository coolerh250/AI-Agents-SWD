# Step 66C.4-BE1-R — Review Result Handoff to the Product Owner

> **Independent review complete. Nothing was fixed, merged or deployed. PR #17 remains a draft and is
> NOT recommended for merge in its current state.**

```text
Review process marker : STEP66C4_BE1_INDEPENDENT_REVIEW_VERIFY: PASS
Technical verdict     : BE1_TECHNICAL_VERDICT: REMEDIATION_REQUIRED
Reviewed commit       : d2467f5   Main: e03c22d   PR: #17 (draft)
Review branch         : review/66c4-be1-technical-security-migration
Implementation files changed by this review: NONE
```

## One-paragraph summary

BE1 is a careful, well-disciplined slice. The migration is genuinely additive, idempotent,
non-rewriting and reversible; exactly the six canonical lifecycle columns exist and none of the
forbidden ones; the disabled-foundation posture is real (zero runtime producers, zero relay, zero
scheduler, audit/event transport byte-identical to main); the answer CAS is race-safe; and the
implementer honestly self-reported the outbox's missing durability columns. Two findings nevertheless
block merge, and neither is eligible for `PASS_WITH_GAPS` under the stage rules.

## Blocking finding 1 — the deadline is enforced at transaction-start time, not claim time

`now()` in PostgreSQL is `transaction_timestamp()`: frozen at BEGIN. Reproduced on a real Postgres —
a transaction opened 3 s before `due_at`, executing the exact committed CAS 2 s AFTER `due_at`,
claimed the row successfully and wrote a backdated `answered_at`.

Today's autocommit call shape hides this. But the canonical contract itself (`api-and-event-
contract.md` §11.3, binding) requires the lifecycle CAS and the outbox INSERT to commit in the same
transaction, and `data-model-contract.md` requires `resume_eligible_at` in the same transaction as the
answer-claim. BE2 is therefore contractually obliged to add the wrapping that activates the defect, at
which point the PO-approved guarantee "scheduler lag does not extend the answer window" becomes
silently false.

The root cause is in the contract, not only the code: `lifecycle-and-time-contract.md` §7.1 and
§7.3A.6 both state that "now() is evaluated per statement", which is incorrect for PostgreSQL.

## Blocking finding 2 — the outbox schema cannot carry the binding durability contract

The table matches the canonical columns exactly, but has no `available_at`/`next_attempt_at`, no
`dead_at` and no `last_error`. Without a persisted next-attempt time, §11.3's binding failure mode 1
("the relay publishes it when the publisher recovers — no loss") and failure mode 7 (bounded retries
then `dead`) cannot both hold: a bounded-attempt relay with no backoff will dead-letter healthy rows
within seconds of a publisher outage. Without `last_error`, the "explicit operator-reconciliation
item" that failure mode 8 promises arrives with no diagnosis.

BE2 would have to add durability columns ad hoc — the exact self-expansion BE1 correctly refused.
That makes this a BE1-R1 item, not a BE2 item.

## Non-blocking

```text
MEDIUM  the outbox payload guard inspects only top-level keys, so {'meta': {'answer': <raw body>}} or
        a near-miss key like 'answer_body' is accepted. Harmless today (no producer exists), but it is
        the safety boundary BE2's producer would rely on.
LOW     size cap / event-type allowlist not enforced at the DB; idempotency_key unvalidated; a deleted
        row is reported as "already answered".
TESTS   no transaction-crossing test (which is why finding 1 survived); the "exact boundary" test is a
        near-tautology; Postgres tests skip silently and the verifier cannot detect it; the fixtures
        DROP four tables with no ephemerality guard; no NOT NULL regression for due_at.
```

## Recommended remediation scope — Step 66C.4-BE1-R1 (small and bounded)

```text
1. Amend lifecycle-and-time-contract.md §7.1 / §7.3A.6 to state PostgreSQL's real now() semantics and
   make the binding predicate `due_at > statement_timestamp()` (or clock_timestamp()).
2. Change that one predicate in shared/sdk/tasks/workroom_store.py::claim_clarification_answer.
   Behaviour-identical today; correct once BE2 wraps the CAS.
3. Decide and record whether answered_at should also use statement/clock time (it is currently
   backdated to transaction start inside any wrapping transaction).
4. Amend data-model-contract.md's outbox section to add available_at (or next_attempt_at), dead_at and
   a bounded last_error, and define the operator-replay route into the existing DLQ tooling; extend
   migration 031 accordingly.
5. Make the payload guard recursive or invert it to a positive key allowlist.
6. Add the missing tests: cross-deadline transaction rejected; a true now()==due_at equality case; a
   due_at NOT NULL regression; an ephemerality guard before the destructive fixtures.
```

Items 1-3 and 4 are the merge blockers. Items 5-6 are cheap and best done in the same pass.

## Authorization posture (unchanged by this review)

```text
PR #17            : NOT recommended for merge. Remains a draft.
Deployment        : not performed, not recommended, not authorized.
Shared databases  : not touched. Only an isolated ephemeral test PostgreSQL was used, and it was
                    destroyed at the end of the review.
Step 66C.4-BE2    : NOT authorized. Should not start until BE1-R1 lands, because BE2 inherits both
                    the deadline semantics and the outbox schema.
Codex             : remains unauthorized.
Claude Design     : remains unauthorized.
Scheduler / relay / producer cutover / dispatch / resume / external notification : all remain
                    unbuilt and unauthorized.
production_executed_true_count : 0.
Next authorized step : Step 66C.4-BE1-R1 (scoped remediation), subject to Product Owner approval.
```

## Statement

Independent review handoff only. No implementation change. No migration change. No merge. No
deployment. No scheduler or relay activation. No dispatch/resume. No external notification. Product
Owner review and authorization required before any further step.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
