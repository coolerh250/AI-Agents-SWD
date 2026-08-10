# Step 66D-BE1-CR1 — Active-State Contract Evidence

> **Documentation and contract amendment only. No backend, API, frontend, runtime, migration,
> table, repository, ORM model, event, deployment, identity, secret or feature-gate change. No
> container, database, Redis, Kubernetes, Vault, OIDC provider, agent workflow or external provider
> started. `production_executed_true_count: 0`.**

```text
Canonical baseline:  main af40b3bf9792fe8182e9620fb9d134af67cf4a12
Branch:              contracts/66d-be1-review-task-active-state
Marker:              STEP66D_BE1_CR1_ACTIVE_STATE_CONTRACT_VERIFY: PASS
Decision:            66D-D05 (BINDING, Product Owner)
```

## 1. The original conflict

Step 66D-BE1 stopped at its canonical contract gate before creating a branch or writing any code.
Two canonical, merged, binding artifacts disagreed about `DeliveryReviewTask` state storage, which
made the ARCH1 relationship "exactly one active review task per submission version" impossible to
implement deterministically.

```text
ARCH1  step66d-arch1-domain-and-state-model.md section 2, merged ab19dad
       review_status "mirrors submission review state for the assignee's view"
       -> implies the nine canonical DeliverySubmission statuses

DESIGN step66d-design-delivery-inbox-spec.md section 3 + contract manifest, merged bb8eab7
       DeliveryReviewTask.status is an independent review-task lifecycle, enum NOT IMPLEMENTED,
       NOT interchangeable with DeliverySubmission.status, and a closed review task against an
       EXPIRED submission must remain expressible
```

Reproduced independently in this stage by fresh-reading both artifacts at `af40b3b`. The precedence
record resolves the D01–D04 vocabulary conflicts and does not rank ARCH1 against DESIGN here; Tier 1
does not define review-task lifecycle values either.

## 2. Product Owner decision — 66D-D05

```text
DeliveryReviewTask.active  :=  closed_at IS NULL
DeliveryReviewTask.closed  :=  closed_at IS NOT NULL
```

```text
Active state:            structural, derived from one existing canonical ARCH1 field
Lifecycle enum:          NOT DEFINED / deferred
Submission mirroring:    forbidden as lifecycle authority
Persistence invariant:   AT MOST ONE structurally active task per delivery_submission_id
Partial unique boundary: delivery_submission_id
Required existence:      deferred -- BE1 must not force a task to always exist
closed_at meaning:       structural only; never an outcome, decision, expiry or QA signal
Transitions:             reopen / close action / reopen-after-close / automatic closure /
                         closure by decision / closure by expiry -- all deferred
```

Ten binding requirements `D05-R1 … D05-R10` are recorded in the binding decisions registry.

### Why `delivery_submission_id` is the version boundary

ARCH1 rules 6 and 7 make every submission version a distinct row: a re-submission after
`CHANGES_REQUESTED` creates a **new** `DeliverySubmission` linked by `supersedes_submission_id`, and
an existing submission is never rewritten in place. `delivery_submission_id` therefore already *is*
the submission-version boundary, and no version column is needed on the review task to scope the
constraint.

### Canonical implementation requirement for BE1 (not built here)

```sql
CREATE UNIQUE INDEX ...
    ON delivery_review_tasks (delivery_submission_id)
    WHERE closed_at IS NULL;
```

### At-most-one versus required existence

```text
AT MOST ONE active task per submission   BINDING, enforced by BE1 persistence
WHEN an active task MUST exist           DEFERRED to a future lifecycle / orchestration stage
```

A submission with zero active review tasks is a legal persistence state in BE1. No trigger,
constraint or backfill may force otherwise.

## 3. Superseded and preserved

```text
SUPERSEDED  the ARCH1 mirroring sentence, as lifecycle and storage authority for BE1 persistence.
            The original sentence is annotated in place in the ARCH1 document and is NOT deleted;
            a test asserts it is still present.
PRESERVED   the DESIGN requirement that review-task status and submission status are NOT
            interchangeable. 66D-D05 satisfies it: structural closure is independent of submission
            status, so a closed review task against an EXPIRED submission stays expressible.
UNCHANGED   66D-D01, 66D-D02, 66D-D03, 66D-D04, ADR-66D-09.
```

`delivery_review_task_status` keeps its identity as a reserved product / read-model concept:
`PLANNED / NOT IMPLEMENTED`, lifecycle enum not defined, BE1 persistence source none. It must not be
derived from `DeliverySubmission.status`, must not be derived as an `OPEN`/`CLOSED` value from
`closed_at`, and must not be described as an existing backend field.

## 4. Changed paths — exactly 10

```text
docs/contracts/66d-delivery-acceptance/step66d-d05-review-task-active-state-amendment.md   (new)
docs/contracts/66d-delivery-acceptance/step66d-delivery-decision-model-binding-decisions.md
docs/contracts/66d-delivery-acceptance/step66d-canonical-terminology-registry.md
docs/architecture/66d-delivery-acceptance/step66d-arch1-domain-and-state-model.md
docs/design/66d-delivery-acceptance/step66d-design-delivery-inbox-spec.md
docs/design/66d-delivery-acceptance/step66d-design-contract-manifest.json
docs/handoffs/66d-delivery-acceptance/step66d-canonical-conflict-supersession-matrix.md
docs/handoffs/66d-delivery-acceptance/step66d-be1-cr1-active-state-contract-evidence.md    (new)
scripts/verify_step66d_be1_cr1_active_state_contract.py                                    (new)
tests/test_step66d_be1_cr1_active_state_contract.py                                        (new)
```

```text
Implementation paths (apps/ agents/ services/ shared/ migrations/ infra/ runtime/):  0
API / router / controller:                                                           0
Frontend:                                                                            0
TASK_ROLES / identity:                                                               0
source/progress.md:                                                                  UNCHANGED
Historical merge records (ARCH1-M1, DESIGN-M1):                                       UNCHANGED
```

## 5. Verification

```text
STEP66D_BE1_CR1_ACTIVE_STATE_CONTRACT_VERIFY: PASS
CR1 tests:            23 passed, 0 failed, 0 skipped
ruff / black / mypy:  PASS / PASS / PASS
git diff --check:     clean
```

The verifier's positive scope is a fixed baseline (`af40b3b`) plus an explicit 10-path registry
compared by **set equality**; it never admits paths by an unbounded `baseline...HEAD` range.

### Negative mutation probes — all rejected

Each probe copies the contract package into a temporary git repository, tampers with exactly one
thing, and asserts rejection. No probe is committed to this repository.

```text
control  untampered tree                                                        PASS
A        re-declare review_status mirrors DeliverySubmission.status              REJECTED
B        add DeliveryReviewTask.status = OPEN | CLOSED                           REJECTED
C        define active as status IN (...)                                        REJECTED
D        map delivery_review_task_status to DeliverySubmission.status            REJECTED
E        assert closed_at IS NOT NULL means a ProductOwnerDecision exists        REJECTED
F        claim the database guarantees exactly one task always exists            REJECTED
G        define reopen semantics                                                 REJECTED
H        add an implementation / migration path                                  REJECTED
+        lifecycle values OPEN / CLOSED / CANCELLED near DeliveryReviewTask       REJECTED (3)
```

Three probes initially leaked and the **checks** were corrected, never the probes: the supersession
cue list was too permissive (a stray "conflict" in unrelated prose vouched for a re-assertion), the
SQL predicate `IS NOT NULL` was being read as a negation, and lifecycle-value context windows were
computed over a concatenation, which let one section's negation wording vouch for another's claim.
Windows are now computed from original document offsets.

## 6. Regression

```text
CR1 tests                       23 passed, 0 failed, 0 skipped
Step 66D-ARCH1 contract freeze  PASS
Step 66D-DESIGN package         PASS
Step 66D-DESIGN-M1 merge        PASS
Step 66D-ALIGN1 decision model  PASS
```

No historical verifier or test was modified. Where an existing assertion could have been affected,
the amendment was written to satisfy it rather than the test being relaxed: the nine-status enum
block, the D01 mapping table, the `### Delivery review status (permitted values)` block and both
Delivery Inbox filter names are all left intact.

## 7. Scope and safety

```text
Backend implementation:   NOT STARTED       Shared DB:            NOT APPLIED
Migration:                NOT STARTED       Staging/production:   NOT TOUCHED
delivery_review_tasks:    NOT CREATED       Secret access:        NONE
Repository / ORM model:   NOT CREATED       External action:      NONE
API / router:             NOT CREATED       Resume/replay:        NONE
Event / outbox / relay:   NOT CREATED       Deployment:           NONE
production_executed_true_count:  0
```

## 8. Governance advisories — untouched

```text
ADV-UTF8-01              TRACKED / OUT OF SCOPE / NOT REMEDIATED
ADV-SUITE-01             TRACKED / OUT OF SCOPE / NOT REMEDIATED
GOV-REPO-IDENTIFIER-01   TRACKED / OUT OF SCOPE / NOT REMEDIATED
```

None was fixed in this stage, and `source/progress.md` was deliberately not modified so that its
pre-existing historical identifier contamination is not carried into this diff.

## 9. Status

```text
STEP66D_BE1_CR1:                 PASS
66D_D05:                         DOCUMENTED / PROPOSED FOR CANONICAL MERGE
BE1_IMPLEMENTATION:              PAUSED
MIGRATION:                       NOT STARTED
SHARED_DB:                       NOT APPLIED
PR:                              OPEN / NOT MERGED
CR1_R1:                          REQUIRED
PRODUCTION_EXECUTED_TRUE_COUNT:  0
```

Step 66D-BE1 resumes only after this amendment is independently reviewed and canonically merged.

---

# Step 66D-BE1-CR1-RM1 — Correction Addendum

> Appended by Step 66D-BE1-CR1-RM1 under explicit Product Owner authorization to repair one
> historical test file. This is a **verification-range repair, not a contract change**. 66D-D05 is
> untouched. The original CR1 commit `c820dfb` is preserved and was not amended.

## RM1.1 Finding

```text
Finding:                Two Step 66D-DESIGN-M1 tests asserted what the DESIGN-M1 record commit
                        changed using an OPEN-ENDED range, git diff e4efb88..HEAD:
                          test_no_historical_verifier_or_test_was_modified_by_this_stage
                          test_merge_record_commit_touched_no_product_design_content
                        Because the endpoint followed HEAD, they attributed every later stage's
                        commits to Step 66D-DESIGN-M1 and failed for ANY subsequent commit.
Introduced by:          the Step 66D-DESIGN-M1 historical test implementation
Relationship to 66D-D05: NONE. No D05 statement conflicts with any DESIGN-M1 assertion.
Discovered by:          Step 66D-BE1-CR1, which reported it rather than silently fixing it
```

## RM1.2 Measured ranges

```text
Moving range   e4efb88...HEAD          at PR #27 head   16 paths
                                       (DESIGN-M1 record scope + the CR1 paths)
Frozen range   e4efb88...af40b3b                         6 paths
                                       reproduces the DESIGN-M1 canonical record commit exactly
```

## RM1.3 Authorized repair

```text
Historical file:            tests/test_step66d_design_m1_canonical_merge.py   (the only one)
MERGE_COMMIT:               e4efb88bad01f72ccc73bdd0d13ff9b8e29fbda2
RECORD_COMMIT:              af40b3bf9792fe8182e9620fb9d134af67cf4a12   (new constant)
Old range:                  f"{MERGE_COMMIT}..HEAD"
Canonical frozen range:     f"{MERGE_COMMIT}..{RECORD_COMMIT}"
Open-ended HEAD ranges removed: 2
Assertions removed:         0     (61 before, 61 after)
Assertions weakened:        0     (no subset/contains/allowlist relaxation)
Tests removed or added:     0     (26 before, 26 after)
skip / xfail introduced:    0
Other semantic edits:       0     (diff is one constant + comment, and two endpoints)
Historical verifier changed: NO   scripts/verify_step66d_design_m1_canonical_merge.py untouched
Other historical tests changed: NO
Historical product semantics changed: NO
```

## RM1.4 Scope expansion

```text
CR1 original scope:      10 paths
CR1 RM1 scope:           11 paths
Additional authorized path: tests/test_step66d_design_m1_canonical_merge.py
```

The verifier records the exception as `AUTHORIZED_HISTORICAL_PATHS`, a frozenset holding exactly
one **literal** path. It is never a prefix, wildcard, glob or historical-test category, and new
checks `check03b..check03e` assert the exception stays a single literal, reject any other
historical verifier or test, and require the frozen `e4efb88..af40b3b` range to remain pinned.

## RM1.5 Verification

```text
DESIGN-M1 tests before repair:  24 passed, 2 failed, 0 skipped   (26 collected)
DESIGN-M1 tests after repair:   26 passed, 0 failed, 0 skipped
DESIGN-M1 historical verifier:  PASS (unmodified)

Negative regression probe   endpoint reverted to ..HEAD -> 2 failed, 24 passed
                            endpoint restored           -> 26 passed; tree byte-identical
Future-commit stability     an unrelated local-only commit on top -> DESIGN-M1 26 passed
New CR1 probes              unauthorized historical test path            REJECTED
                            reintroduced drifting ..HEAD range           REJECTED
```

## RM1.6 66D-D05 integrity — unchanged

```text
active := closed_at IS NULL                      UNCHANGED
closed := closed_at IS NOT NULL                  UNCHANGED
DeliveryReviewTask lifecycle enum                DEFERRED / UNCHANGED
DeliverySubmission.status mirroring              FORBIDDEN / UNCHANGED
delivery_review_task_status                      PLANNED / NOT IMPLEMENTED / UNCHANGED
at-most-one active per delivery_submission_id    UNCHANGED
required existence                               DEFERRED / UNCHANGED
reopen / transition semantics                    DEFERRED / UNCHANGED
```

No 66D-D05 document was edited by RM1 beyond this evidence addendum. There is no `D05_SCOPE_DRIFT`.

## RM1.7 Additional drift scan — reported, not fixed

Scan of `tests/test_step66d_*canonical_merge*.py` for the same drifting-range pattern is recorded
in the completion report. Any further findings are future governance items; RM1 changed only the
one authorized file.

## RM1.8 Status

```text
STEP66D_BE1_CR1_RM1:             PASS
DESIGN_M1_DRIFTING_HEAD:         CLOSED
66D_D05:                         UNCHANGED / READY FOR INDEPENDENT REVIEW
BE1_IMPLEMENTATION:              NOT STARTED / PAUSED
SHARED_MIGRATION:                NOT APPLIED
PR27:                            OPEN / UPDATED / NOT MERGED
CR1_R1:                          REQUIRED / NOT STARTED
PRODUCTION_EXECUTED_TRUE_COUNT:  0
```

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
