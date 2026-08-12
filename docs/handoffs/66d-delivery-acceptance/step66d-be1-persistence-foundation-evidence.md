# Step 66D-BE1 — Delivery Acceptance Persistence Foundation (Evidence)

> **Persistence and domain layer only. No API, router, frontend, event producer, outbox row, relay,
> projector, read model, identity, RBAC, deployment or infra change. No shared, staging or
> production database was touched. No container, database, Redis, Kubernetes, Vault, OIDC provider,
> agent workflow or external provider was started. `production_executed_true_count: 0`.**

## 1. Canonical inputs

```text
Canonical baseline:   main 2d4da808b1a89ea278fbb760e27f49047995165e  (2d4da80)
Branch:               implementation/66d-be1-delivery-acceptance-persistence
Merge authorization:  NOT GRANTED
```

`BE1_CANONICAL_INPUTS`, all re-read at this stage rather than recalled:

```text
docs/contracts/66d-delivery-acceptance/step66d-d05-review-task-active-state-amendment.md
docs/contracts/66d-delivery-acceptance/step66d-delivery-decision-model-binding-decisions.md
docs/contracts/66d-delivery-acceptance/step66d-canonical-terminology-registry.md
docs/architecture/66d-delivery-acceptance/step66d-arch1-domain-and-state-model.md
docs/architecture/66d-delivery-acceptance/step66d-arch1-contract-freeze.md
docs/architecture/66d-delivery-acceptance/step66d-arch1-api-event-audit-contracts.md
docs/architecture/66d-delivery-acceptance/step66d-arch1-read-model-and-security-boundary.md
docs/handoffs/66d-delivery-acceptance/step66d-arch1-gap-and-implementation-slice-plan.md
docs/handoffs/66d-delivery-acceptance/step66d-be1-cr1-m1-canonical-merge-record.md
docs/design/66d-delivery-acceptance/step66d-design-delivery-inbox-spec.md
```

```text
66D-D05:                          BINDING / CANONICALIZED
BE1_CANONICAL_CONTRACT_CONFLICT:  CLOSED
```

## 2. Persistence inventory (machine-measured)

```text
Highest existing migration     035_be3_production_action_approvals.sql
New migration                  036_delivery_acceptance_persistence.sql (+ _down.sql)
Migration framework            numbered plain SQL, BEGIN/COMMIT, idempotent CREATE ... IF NOT
                               EXISTS, optional matching *_down.sql. No Alembic, no framework
                               migration table in the repository tree.
ORM / query framework          NONE. Raw asyncpg with parameterised SQL. No SQLAlchemy.
Repository convention          module-level async functions in shared/sdk/<domain>/*_repository.py
                               taking the CALLER's asyncpg.Connection, running inside the caller's
                               transaction, guarded UPDATE ... RETURNING for CAS, `_row()` helper
UUID / ID convention           UUID PRIMARY KEY DEFAULT uuid_generate_v4() (uuid-ossp, mig. 001)
Timestamp convention           TIMESTAMPTZ NOT NULL DEFAULT statement_timestamp() (66C.4 family)
Enum / check convention        TEXT column + CONSTRAINT chk_<prefix>_<name> CHECK (col IN (...)),
                               mirrored by a frozenset in the domain model module
Optimistic locking             guarded CAS UPDATE returning None on a miss. An integer row_version
                               column did not previously exist anywhere in the schema; ARCH1
                               section 1 requires one, so 036 introduces it for the two mutable
                               acceptance entities.
Transaction abstraction        caller-supplied connection; a repository never opens its own
PostgreSQL test strategy       BE1_TEST_DATABASE_URL + STEP66C4_ALLOW_DESTRUCTIVE_PG_TESTS=1,
                               refused fail-closed by tests/step66c4_pg_safety.py unless the DSN
                               names an isolated ephemeral database
Existing outbox persistence    clarification_lifecycle_outbox (migration 031). NOT used by BE1.
Lineage FK targets available   projects(id), project_work_items(id)  [migration 017]
                               operator_tasks(id)                    [migration 029]
                               delivery_packages(id)                 [migration 021, legacy]
Workflow / run entities        none with a canonical UUID primary key (workflow_states.task_id has
                               been TEXT since migration 003)
```

## 3. Entity and table mapping

| Canonical entity | Table | Identity | Mutability |
| --- | --- | --- | --- |
| DeliverySubmission | `delivery_submissions` | `delivery_submission_id` | CAS-mutable |
| DeliveryReviewTask | `delivery_review_tasks` | `delivery_review_task_id` | CAS-mutable |
| DeliveryReviewAction | `delivery_review_actions` | `review_action_id` | append-only |
| ProductOwnerDecision | `product_owner_decisions` | `decision_id` | append-only, supersedable |
| AcceptanceFollowUpItem | `acceptance_follow_up_items` | `follow_up_item_id` | CAS-mutable |
| Legacy DeliveryPackage | `delivery_packages` | unchanged | **reference-only, untouched** |

## 4. 66D-D05 implementation

```text
Active predicate                closed_at IS NULL
Closed predicate                closed_at IS NOT NULL
Lifecycle enum created          NO -- delivery_review_tasks has no status, review_status,
                                task_status, lifecycle or state column at all
Submission-status mirroring     NONE -- not one of the nine submission statuses appears anywhere
                                in the delivery_review_tasks DDL
delivery_review_task_status     PLANNED / NOT IMPLEMENTED -- no column, no model constant, no
                                repository accessor, no derivation from closed_at
Partial unique index            uq_drt_active_per_submission
At-most-one semantics           enforced by that index, by the database, not by application code
Exactly-one trigger             NONE -- migration 036 creates no trigger and no function
Required existence              DEFERRED -- zero active tasks is a legal, tested state
Transition semantics            DEFERRED -- no reopen, no automatic close, no close-on-accept,
                                close-on-reject or close-on-expiry primitive is invoked by BE1
closed_at business implication  NONE
```

```sql
CREATE UNIQUE INDEX IF NOT EXISTS uq_drt_active_per_submission
    ON delivery_review_tasks (delivery_submission_id)
    WHERE closed_at IS NULL;
```

`close_review_task` exists as a bare CAS primitive guarded by `closed_at IS NULL`. It decides
nothing: no BE1 code path calls it automatically, and there is no reopen counterpart.

Why `delivery_submission_id` alone scopes the constraint: ARCH1 rules 6 and 7 make every submission
version a distinct row linked by `supersedes_submission_id`, so the submission id **is** the
version boundary (D05-R5). No separate version column is needed on the review task.

### One derived consequence, recorded explicitly

ARCH1 section 1 lists `delivery_review_task_id` as a required field on `DeliverySubmission`, and
section 2 lists `delivery_submission_id` as required on `DeliveryReviewTask`. Both cannot be
`NOT NULL`: neither row could ever be inserted first. 66D-D05 (D05-R6) resolves the direction —
"a submission with zero active review tasks is a legal persistence state in BE1", and BE1 must not
force every submission to always have one. A `NOT NULL` reverse pointer would be exactly that
prohibited forcing. BE1 therefore persists the review task's reference to its submission and does
**not** persist a reverse pointer. The stage's own required-field list omits it as well.

## 5. Schema (machine-measured)

```text
New tables                   5
Foreign keys                 11
CHECK constraints            28
UNIQUE indexes                6
Indexes (total)              19
Partial indexes               7
UUID primary keys             5
DB-authoritative timestamps  created_at, updated_at, decided_at, closed_at -- every one defaults
                             to statement_timestamp(); no client clock is accepted anywhere
```

### Constraint matrix (the load-bearing ones)

| Constraint | Table | Guarantees |
| --- | --- | --- |
| `uq_drt_active_per_submission` | review tasks | at most one ACTIVE task per submission (D05-R4) |
| `chk_ds_status` | submissions | exactly the nine canonical statuses |
| `chk_ds_root_is_version_one` | submissions | version 1 ⟺ no predecessor |
| `uq_ds_supersedes` | submissions | at most one successor per version — no forked chain |
| `chk_ds_no_self_supersession` | submissions | a submission cannot supersede itself |
| `chk_dra_action_type` | review actions | exactly the six Review Gate Actions (D01-R9) |
| `chk_dra_reason_required` | review actions | reason required for REQUEST_CHANGES/RERUN_QA/ESCALATE/REJECT |
| `chk_dra_rerun_qa_scope` | review actions | RERUN_QA carries scope + previous QA reference |
| `uq_dra_submission_idempotency_key` | review actions | durable duplicate prevention |
| `chk_pod_decision_type` | decisions | exactly the three Final Decisions (D01-R8) |
| `uq_pod_submission_version` | decisions | `decision_version` monotonic per submission |
| `uq_pod_supersedes` | decisions | at most one successor — no forked history, no diamond |
| `chk_pod_no_self_supersession` | decisions | a decision cannot supersede itself |
| `chk_pod_root_is_version_one` | decisions | version 1 ⟺ no predecessor |
| `chk_afi_status` | follow-ups | OPEN / IN_PROGRESS / CLOSED / CANCELLED, this entity only |
| `chk_drt_assigned_roles` | review tasks | assignment roles ⊆ canonical `TASK_ROLES` |

## 6. CAS design

`row_version INTEGER NOT NULL DEFAULT 1` on `delivery_submissions`, `delivery_review_tasks` and
`acceptance_follow_up_items`. Every mutation is:

```sql
UPDATE <table> SET ..., row_version = row_version + 1, updated_at = statement_timestamp()
WHERE <id> = $1 AND row_version = $expected
RETURNING *
```

A matched precondition returns the row; a stale one returns `None` — a deterministic conflict
signal. Mapping it to `409 DELIVERY_VERSION_CONFLICT` is Step 66D-BE2/BE3; BE1 knows nothing about
HTTP.

## 7. Idempotency design

The uniqueness boundary follows the canonical ARCH1 wording ("unique per (submission, actor,
logical intent)") literally: `UNIQUE (delivery_submission_id, idempotency_key)` on both
`delivery_review_actions` and `product_owner_decisions`. A duplicate raises a database unique
violation. BE1 provides **durable duplicate prevention** only — no HTTP retry replay, no
middleware, no request dedupe controller.

## 8. Immutability guarantees — database vs repository

Stated separately, because they are not equally strong:

```text
DATABASE-LEVEL GUARANTEE
  delivery_review_actions and product_owner_decisions carry NO updated_at and NO row_version, so
  there is no column an in-place correction could legitimately advance.
  chk_pod_no_self_supersession, uq_pod_supersedes and chk_pod_root_is_version_one make the
  supersession chain strictly linear, so a cycle is structurally impossible: it would require a row
  whose version precedes itself.
  ON DELETE RESTRICT on every acceptance foreign key: no parent deletion silently cascades away
  acceptance history.

REPOSITORY-LEVEL GUARANTEE (weaker -- application-enforced, not database-enforced)
  The acceptance-domain repository exposes no update and no delete operation for either
  append-only table. A caller holding a raw connection could still issue arbitrary SQL.
  Cross-submission supersession is rejected by the repository, after locking the predecessor
  FOR UPDATE and comparing its submission id, before any write. It is NOT a database constraint:
  expressing it in SQL would need a trigger, and 66D-D05 plus §14 keep triggers out of BE1.

NOT CLAIMED
  No database trigger, rule or row-level security enforces append-only semantics. Nothing here
  should be described as tamper-proof at the database level.
```

## 9. Supersession model

```text
A                        decision_version 1, supersedes_decision_id NULL
B supersedes A           decision_version 2
C supersedes B           decision_version 3

history    A, B, C -- all three permanently queryable, none deleted or hidden (D02-R3)
effective  C -- the highest version not itself superseded
```

`decision_version` is derived from the locked predecessor, never caller-supplied. Rejected:
self-supersession (DB CHECK), a second successor for one predecessor (DB partial unique),
cross-submission supersession (repository), a cycle (structurally impossible).

The same shape governs submission versions: `create_next_submission_version` locks the predecessor,
inherits its project and work-item lineage so a new version cannot silently move, and derives
`submission_version = predecessor + 1`.

## 10. Lineage mapping (dual anchor, 66D-D03)

```text
Execution      project_id -> primary_work_item_id -> workflow_id -> run_id
               project_id and primary_work_item_id are NOT NULL with real foreign keys to
               projects(id) and project_work_items(id).
               workflow_id and run_id are recorded WITHOUT a foreign key and stay nullable: this
               repository has no canonical UUID-PK workflow or run entity to point at. This is the
               "workflow/run lineage where defined" case, and it is a BE4 dependency, not a
               silently dropped requirement.

Human review   delivery_review_task_id -> task_id -> TASK_ROLES
               task_id is NOT NULL with a foreign key to operator_tasks(id).
               TASK_ROLES: UNCHANGED. shared/sdk/tasks/rbac.py was not modified; migration 036
               references the six canonical roles as a CHECK allowlist and a test asserts that
               allowlist equals rbac.py exactly, so it cannot drift.

DeliveryReviewTask is NOT an execution source of truth (D03-R3): it holds no run, workflow or
dispatch field, and nothing reads execution state from it.
```

## 11. Legacy compatibility (66D-D04)

```text
delivery_packages and its family        UNCHANGED -- migration 036 contains no statement naming
                                        any legacy table or human_acceptance_status
human_acceptance_status                 NOT rewritten, NOT repurposed, NOT read
ProductOwnerDecision in a legacy field  NEVER -- decisions live only in product_owner_decisions
Historical backfill                     NONE -- 036 performs no INSERT, UPDATE or DELETE at all
Reference                               additive only, via
                                        delivery_submissions.legacy_delivery_package_refs (D04-R5)
```

## 12. Migration safety

```text
Additive                 YES -- 036 contains no ALTER, DROP, UPDATE, DELETE, INSERT or TRUNCATE
Idempotent               YES -- CREATE ... IF NOT EXISTS throughout; re-apply is tested
Deterministic            YES -- no clock-dependent or environment-dependent DDL
Reversible               YES -- 036_delivery_acceptance_persistence_down.sql drops exactly the
                         five new tables and nothing else
Legacy-safe              YES -- no existing table, column, constraint or row is touched
Runtime activation       NONE -- schema only; no endpoint, scheduler, relay or feature gate
Wired into the operator migration chain?  NO. scripts/run_platform_migrations.py drives a fixed,
                         ledger-governed chain (031-035) and is deliberately NOT modified by this
                         stage. Adding 036 to it is a separate authorized change and is recorded
                         below as a BE2 dependency.
```

```text
SHARED_MIGRATION_APPLIED:  NO
```

No shared development, shared test, staging or production database was contacted. The migration is
applied only inside the isolated ephemeral-database test fixture, and only when an operator
supplies a DSN that the fail-closed guard accepts.

## 13. PostgreSQL concurrency evidence

```text
CONCURRENCY_VALIDATION:  INCOMPLETE
```

This is the one gate this stage could not close, and it is reported as a gap rather than papered
over. The mandatory races are **written as real PostgreSQL tests** — there is no mock-only
substitute anywhere in this stage — but no authorized PostgreSQL was reachable from the execution
environment:

```text
asyncpg driver                       present
BE1_TEST_DATABASE_URL                not set
STEP66C4_ALLOW_DESTRUCTIVE_PG_TESTS  not set
local PostgreSQL server              none installed, nothing listening on the default port
container runtime                    none available
shared / staging / production DB     forbidden by this stage, and not used
```

The two mandatory races, both implemented and both currently skipped:

```text
Test A  test_pg_concurrency_a_submission_cas_race_has_exactly_one_winner
        Two transactions, same submission row, same expected row_version. The second blocks on
        the row lock, then re-evaluates its guard against the committed row.
        Asserts: exactly one success, exactly one conflict, row_version increments exactly once.

Test B  test_pg_concurrency_b_active_review_task_create_race_has_exactly_one_winner
        Two transactions creating an active review task for the same delivery_submission_id.
        Asserts: exactly one success, exactly one rejection by the authoritative partial unique
        index, exactly one surviving active task. This is the direct runtime proof of 66D-D05.
```

Also implemented and currently skipped: the D05 coexistence proof (a closed task and an active task
coexist for one submission, a second active task is refused — which a plain `UNIQUE` could not
satisfy), the `EXPIRED` submission with an active review task, migration clean apply and reversal,
supersession history, referential integrity, and every required negative case.

To close this gap, an operator supplies an isolated ephemeral PostgreSQL 16 database and runs the
suite with `STEP66C4_ALLOW_DESTRUCTIVE_PG_TESTS=1` and `BE1_TEST_DATABASE_URL` pointing at it. The
DSN is supplied at run time and is never stored in this repository.

## 14. Test results

```text
STEP66D_BE1_PERSISTENCE_FOUNDATION_VERIFY: PASS   (89 checks, 0 failures)

tests/test_step66d_be1_delivery_acceptance_persistence.py   21 passed, 18 skipped
tests/test_step66d_be1_persistence_foundation.py            33 passed,  0 skipped
```

The 18 skips are the real-PostgreSQL integration tests described in section 13. They are **new**
skips introduced by this stage, disclosed here separately and counted in the completion report
rather than folded into a total.

### Regression — ADV-DRIFT-BE1-GUARDS-01

Measured sequentially, one run at a time, over the 21 modules affected:

```text
canonical baseline 2d4da80    2 failed, 962 passed
this branch                  44 failed, 920 passed

Newly failing because of this stage:  42, across 21 modules
Pre-existing on canonical main:        2, both in
                                       tests/test_step66d_align1_rm1_fixed_range_remediation.py
```

The two pre-existing failures are not caused by BE1. The ALIGN1-RM1 verifier's `check23` diffs the
66D decision documents against `HEAD`, so Step 66D-BE1-CR1 adding 66D-D05 to the binding-decisions
registry, the terminology registry and the supersession matrix already trips it on main.

The 42 new failures have two mechanisms, neither of which is a defect in this stage's work:

```text
MECHANISM 1 -- a rejection denylist that outlived its authorization window (40 tests)
  Completed documentation-only and frontend stages assert that no migrations/ or shared/ path
  appears in `<their own baseline>...HEAD`. That guard was correct while backend implementation was
  unauthorized. Step 66D-BE1 is now authorized and adds exactly those paths, so each stage's guard
  fires on a change it has no authority over and did not make.

  This is the ADV-DRIFT-PROGRESS-01 family seen from the rejection side. HEAD-relative is the right
  design for a denylist belonging to the stage that currently owns main's tip; it is the wrong
  design for a completed, merged stage, whose rejection range should be frozen to what that stage
  itself changed -- exactly the frozen-range repair already applied to
  tests/test_step66d_design_m1_canonical_merge.py in Step 66D-BE1-CR1-RM1.

MECHANISM 2 -- "implementation has not started" asserted as a permanent truth (2 tests)
  tests/test_step66d_be1_cr1_active_state_contract.py::test_no_migration_or_implementation_was_created
  tests/test_step66d_be1_cr1_m1_canonical_merge.py::test_no_be1_implementation_exists
  Both assert `not (ROOT / "shared/sdk/delivery_acceptance").exists()` against the working tree.
  They were accurate when written and are necessarily falsified by BE1 starting, which the
  CR1-M1 merge record itself authorized ("BE1_IMPLEMENTATION: AUTHORIZED TO RESUME").
```

Affected modules and counts:

```text
 4  tests/test_step66c4_be3_ra2m2_canonical_merge.py
 4  tests/test_step66c4_be3_ra2m_canonicalization.py
 3  tests/test_step66d_align1_delivery_decision_model.py
 3  tests/test_step66d_be1_cr1_m1_canonical_merge.py
 3  tests/test_step66d_design_unified_control_center.py
 3  tests/test_step66sync1_m2_canonical_merge.py
 2  tests/test_step66c4_be3_ra2_identity_secret_decision.py
 2  tests/test_step66c4_be3_runtime_activation_planning.py
 2  tests/test_step66d_arch1_contract_freeze.py
 2  tests/test_step66d_be1_cr1_active_state_contract.py
 2  tests/test_step66sync1_claude_code_reconciliation.py
 2  tests/test_step66sync1_final_partner_reconciliation.py
 2  tests/test_step66sync1_m1_canonicalization.py
 1  tests/test_step66d_align1_rm1_fixed_range_remediation.py
 1  tests/test_step66sync1_codex_frontend_reconciliation.py
 1  tests/test_step66ui4_fe1a_visual_polish.py
 1  tests/test_step66ui4_fe1b1_mapping_calibration.py
 1  tests/test_step66ui4_fe1b_calm_safety.py
 1  tests/test_step66ui4_fe1c1_implementation.py
 1  tests/test_step66ui4_fe1c_implementation.py
 1  tests/test_step66ui4_fe1d_s1_implementation.py
```

**Not remediated here.** §36 forbids historical verifier and test repair, and §32 forbids touching
the drift-affected historical tests. Repairing 21 modules belonging to other stages would also be a
far larger change than this stage's scope permits. This is reported for an authorized remediation
stage and must be closed before Step 66D-BE1 can merge.

Measurement note: a whole-suite run was also taken on both trees, but the two runs overlapped on
one machine and several environment-sensitive suites (bash syntax checks, secret-scanner fixtures,
file-permission fixtures) reported differently under that contention. Those whole-suite totals are
therefore not quoted as authoritative. The sequential per-module figures above are.

## 15. Remaining dependencies

```text
Step 66D-BE2   submission and review-task APIs; TASK_ROLES capability mapping (ARCH1-G07);
               wiring migration 036 into the operator migration chain and its ledger;
               cross-project 404 masking
Step 66D-BE3   the six Review Gate Actions and three Final Decisions as commands; ACCEPT/REJECT
               atomically recording action + decision in one transaction; bounded QA rerun
               (ADR-66D-09); the ACCEPTED_WITH_FOLLOW_UP blocking-follow-up rule; review-task
               transition semantics once a lifecycle contract stage defines them
Step 66D-BE4   durable events, transactional outbox, audit actions, unified read model, cost and
               external-action accounting, DLQ evidence
RA-2           verified human identity. Until then `actor_ref` is a reference, never a verified
               identity, and no production-grade acceptance flow may be claimed (ARCH1-G08)
Future stage   a canonical workflow/run entity, so workflow_id and run_id can carry foreign keys
Future stage   the DeliveryReviewTask lifecycle enum, if the product ever needs
               delivery_review_task_status for real
```

## 16. Safety

```text
API / router                     NONE          Frontend                    NONE
Event / outbox activation        NONE          Read model / projector      NONE
TASK_ROLES                       UNCHANGED     Identity / auth             UNCHANGED
Runtime                          UNCHANGED     Infra / deployment          NONE
source/progress.md               UNCHANGED     Shared DB                   NOT APPLIED
Secret access                    NONE          External action             NONE
Resume / replay                  NONE          Legacy DeliveryPackage      UNCHANGED
production_executed_true_count:  0
```

No secret, credential, private key, client secret, DSN, internal credential identifier, real
account identifier, raw token or private chain of thought is stored by any column, written by any
test, or recorded in this document.

## 17. Advisories — tracked, deliberately not remediated

```text
ADV-DRIFT-PROGRESS-01     TRACKED / OUT OF SCOPE -- source/progress.md deliberately unchanged
ADV-UTF8-01               TRACKED / OUT OF SCOPE
ADV-SUITE-01              TRACKED / OUT OF SCOPE
GOV-REPO-IDENTIFIER-01    TRACKED / OUT OF SCOPE
ADV-DRIFT-BE1-GUARDS-01   NEW / BLOCKING FOR MERGE / NOT REMEDIATED -- section 14. 42 tests in 21
                          historical modules whose HEAD-relative rejection denylists, and two
                          "implementation not started" existence assertions, are invalidated by
                          this stage's authorized implementation. Repair is a separate authorized
                          remediation stage: freeze each completed stage's rejection range to that
                          stage's own head, the same way Step 66D-BE1-CR1-RM1 repaired the
                          DESIGN-M1 test.
```

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
