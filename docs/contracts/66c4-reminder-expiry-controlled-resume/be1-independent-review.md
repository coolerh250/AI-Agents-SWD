# Step 66C.4-BE1-R — Independent Technical, Security and Migration Review

> **Independent review artifact produced by a fresh review session in a separate git worktree. The
> reviewer did not write the code under review and received no private reasoning, scratch notes or
> uncommitted artefacts from the implementation session. No implementation file, migration, test or
> verifier under review was modified. No merge. No deployment. No shared database touched.**

```text
Reviewed commit:   d2467f5  (feature/66c4-be1-lifecycle-outbox-foundation, PR #17 draft)
Main at review:    e03c22d
Review branch:     review/66c4-be1-technical-security-migration
Review worktree:   separate worktree created from origin/feature/66c4-be1-lifecycle-outbox-foundation
Database used:     isolated ephemeral test PostgreSQL 16.14, created for this review and destroyed
                   afterwards. No shared test/staging/production database was migrated or touched.
```

**Review-process marker:** `STEP66C4_BE1_INDEPENDENT_REVIEW_VERIFY: PASS`
**Technical result:** `BE1_TECHNICAL_VERDICT: REMEDIATION_REQUIRED`

These two are separate statements. The first says only that the review was carried out and its
artefacts are complete. The second is the engineering judgement on the code.

## Companion artifacts

```text
be1-deadline-semantics-review.md              deadline / clock semantics   -> REMEDIATION_REQUIRED
be1-outbox-foundation-sufficiency-review.md   outbox durability matrix     -> FOUNDATION_REMEDIATION_
                                                                              REQUIRED_BEFORE_MERGE
be1-migration-review.md                       migration up/down/reapply    -> PASS
be1-security-review.md                        security / payload privacy   -> no critical, no high
be1-test-quality-review.md                    test rigour                  -> PASS_WITH_GAPS
docs/test/step66c4-be1-independent-review-record.md      reproduction evidence
docs/handoffs/.../be1-review-result-handoff.md           handoff to the Product Owner
```

## What BE1 got right

This is a careful, disciplined slice, and most of it holds up under independent reproduction:

```text
* The migration is genuinely additive, idempotent, non-rewriting (relfilenode unchanged), reversible
  and deterministic on reapply. Pre-existing rows survive untouched. Verified end to end on a real
  Postgres from a 029/030 baseline.
* Exactly the six canonical lifecycle columns exist, all nullable with no default; none of the
  explicitly-forbidden columns (resume_dispatched_at, resume_authorized_by, lock_version, ...) were
  added. BE1 did not self-expand the contract.
* The disabled-foundation posture is real, not asserted. Zero runtime producers, zero runtime outbox
  writes, zero relay loops, zero scheduler loops, zero startup registrations. shared/sdk/audit/** and
  shared/sdk/event_bus/** are byte-identical to main.
* The answer CAS is race-safe. Independently reproduced with two connections and an explicit lock
  hold: the loser blocks and then correctly fails.
* Transaction-aware outbox insert behaves exactly as documented: caller-owned transaction, rollback
  leaves zero rows, commit leaves one, duplicate idempotency key raises UniqueViolationError.
* SQL is fully parameterized, nothing is logged, and the implementer honestly self-reported the
  missing outbox durability columns rather than quietly deferring them.
```

## Blocking findings

### B-1 — a transaction that begins before `due_at` can still answer after it (deadline semantics)

`now()` is `transaction_timestamp()` in PostgreSQL: it is frozen at transaction BEGIN and does not
advance per statement. The committed predicate `due_at > now()` therefore evaluates the deadline at
transaction-start time, not claim-statement time. Reproduced on real Postgres: a transaction opened
~3 s before `due_at` and executing the exact committed CAS ~2 s AFTER `due_at` claimed the row
successfully and wrote a `answered_at` backdated by 5 s.

Today's autocommit call shape masks this (control run: correctly rejected). But `api-and-event-
contract.md` §11.3 (binding) requires the lifecycle CAS and the outbox INSERT to commit in the SAME
transaction, and `data-model-contract.md` requires `resume_eligible_at` to be set in the same
transaction as the answer-claim — so BE2 is contractually obliged to introduce exactly the wrapping
that activates the defect. The canonical guarantee "scheduler lag can never extend the answer window"
would then be silently false.

Note that the contract itself is the origin: `lifecycle-and-time-contract.md` §7.1 and §7.3A.6 both
assert that "now() is evaluated per statement", which is incorrect for PostgreSQL. The contract must
be amended alongside the code. Full evidence: `be1-deadline-semantics-review.md`.

### B-2 — the outbox schema cannot support the binding durability contract (foundation sufficiency)

The table implements the canonical columns exactly, but `available_at` / `next_attempt_at`, `dead_at`
and `last_error` are absent. Without a persisted next-attempt time, §11.3 binding failure mode 1
("the relay publishes it when the publisher recovers — no loss") and failure mode 7 (bounded retries
then `dead`) are mutually unsatisfiable: a relay with a bounded attempt cap and no backoff will burn
the cap within seconds of a publisher outage and dead-letter healthy rows. Without `last_error`, a
dead row becomes the "explicit operator-reconciliation item" that §11.3 failure mode 8 demands, with
no diagnosis attached.

BE2 would have to add durability columns ad hoc, which is precisely the self-expansion BE1 correctly
refused. The gap must be closed by a canonical-contract amendment plus a scoped migration extension
under BE1-R1, before the foundation is merged as sufficient. Full matrix:
`be1-outbox-foundation-sufficiency-review.md`.

## Non-blocking findings

```text
M-1 (medium, security)  payload guard checks only top-level keys -- a nested {'meta': {'answer': ...}}
                        or a near-miss key like 'answer_body' is accepted. No live producer exists, so
                        nothing can reach the table today. -> be1-security-review.md
L-1..L-3 (low)          size cap / event-type allowlist not enforced at the DB boundary; idempotency
                        key unvalidated; a deleted row is reported as "already answered".
G-1..G-6 (test quality) no transaction-crossing test; the "exact boundary" test is a near-tautology;
                        Postgres tests skip silently and the verifier cannot tell; the fixtures DROP
                        four tables with no ephemerality guard; no NOT NULL regression for due_at;
                        the concurrency test is timing-dependent. -> be1-test-quality-review.md
I-1..I-3 (informational) FK NO ACTION protects lifecycle evidence; no logging is added anywhere; all
                        SQL is parameterized and clarification ids are coerced through uuid.UUID().
```

## Verdict rationale

`PASS` is unavailable because the transaction-crossing-deadline reproduction succeeded and the outbox
schema cannot carry the binding retry/DLQ/replay contract. `PASS_WITH_GAPS` is explicitly barred for
deadline-time semantics and for outbox durability schema. The verdict is therefore
`REMEDIATION_REQUIRED`, with a small and well-bounded remediation scope: one contract amendment plus
one predicate change for B-1, and one contract amendment plus a migration extension for B-2.

Nothing was fixed by this review. Nothing was merged. Nothing was deployed.

## Statement

Independent review artifact only. No implementation change. No migration change. No test change. No
scheduler or relay activation. No producer cutover. No dispatch/resume. No external notification. No
shared-runtime migration. No deployment. No merge. `production_executed_true_count` remains 0. Codex
and Claude Design remain unauthorized. Product Owner review required.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
