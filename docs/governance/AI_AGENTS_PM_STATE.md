# AI_AGENTS_PM_STATE

> **Governance artifact only. No backend/frontend runtime change. No production action.**

The canonical, repository-versioned **PM State Snapshot** for this project. It is the compact
project-control truth derived from engineering truth plus binding Product Owner decisions, and it
is the artifact a fresh session reads first.

It is **derived**, never primary. Where this file and `main` disagree, `main` wins and the
disagreement is a **PM_STATE_CONFLICT** that must stop work — see
[project-control-plane-v2.md](project-control-plane-v2.md).

This file does not replace `source/progress.md`, which remains the chronological ledger of record
under [the source-of-truth policy](../process/source-of-truth-policy.md). This is a recovery
snapshot, not a history.

## 1. Snapshot identity

```text
PM_STATE_VERSION:            1
PM_STATE_SCHEMA:             pcp-v2
RECONCILED_ON:               2026-08-19
RECONCILED_AGAINST_MAIN:     192ebb74ba600f7a53ddf5967a7254a1f7a72fb8
RECONCILED_BY_STAGE:         AT-M2-TEAM-CORE
```

`RECONCILED_AGAINST_MAIN` is the commit this snapshot was verified against. It is expected to fall
behind as work lands. Falling behind is **staleness**, which is tolerated and reported; naming a
commit that is unknown to the repository, or that is not an ancestor of `main`, is **drift**, which
is a conflict.

## 2. Position

```text
CURRENT_MILESTONE:           AT-M2
CURRENT_MILESTONE_STATE:     IN PROGRESS / AT-M2-TEAM-CORE
PREVIOUS_COMPLETED_STAGE:    PCP-V2.1-RM5
CURRENT_GATE:                AT-M2 VALIDATION
CURRENT_STAGE:               AT-M2-TEAM-CORE
NEXT_PERMITTED_STAGE:        AT-M2 VALIDATION 1
```

AT-M1 stays `CLOSED / CANONICAL`; it is no longer the *current* milestone because AT-D11
authorized its successor. Position moved off the PCP remediation chain at the same decision — see
section 5.

```text
AT_M1_LIFECYCLE:             SUPERSEDED BY AT-M2
AT_M1_SUPERSESSION_COMMIT:   192ebb74ba600f7a53ddf5967a7254a1f7a72fb8
```

Supersession closes AT-M1's **no-implementation window** at the canonical main that was HEAD when
AT-M2 was authorized, and does nothing else. Every commit AT-M1 could have contributed is inside
that window and is still checked by `scripts/verify_at_m1_architecture_reset.py`; code written
after it belongs to AT-M2's authorization and is not an AT-M1 scope breach. INV-01 … INV-09 stay
live and HEAD-relative, and `shared/sdk/tasks/rbac.py` is now **permanently** protected rather
than protected only for AT-M1's window.

## 3. Engineering truth

```text
AT_M1:                       CLOSED / CANONICAL
AT_M1_BASELINE:              fa5e5c4e6712fbbc59bf18d2ee33421c28f9b009
AT_M1_STAGE_HEAD:            c80350ecc19e28212d9a95cddeb80a24aabe6eae
AT_M1_MERGE_COMMIT:          db4e7a781dcddf4f5ab4ac413457a88bc7bdefa0
AT_M1_POSITIVE_SCOPE_PATHS:  19
PR29:                        MERGED
PR28:                        OPEN / HOLD / NON-CANONICAL
PR28_HEAD:                   c9145cd848a211a9dd2bbff672c532da364eaa55
```

`AT_M1_STAGE_HEAD` is the independently reviewed implementation state. It is the merge commit's
second parent, which is what pins it; `AT_M1_BASELINE` is the first parent.

## 4. Product Owner decisions

```text
AT-D01:                      RESOLVED / BINDING
AT-D02:                      RESOLVED / BINDING
AT-D03:                      RESOLVED / BINDING
AT-D04:                      RESOLVED / BINDING
AT-D05:                      RESOLVED / BINDING
AT-D10:                      RESOLVED / BINDING
AT-D10.1:                    RESOLVED / BINDING
```

```text
AT-D09:                      OPEN / DEFERRED
STEP_66C4_CONTRACT:          REMAINS AUTHORITATIVE
```

AT-D09 is an open question, not a decision. Nothing downstream may represent it as settled.

## 5. Authorization and safety

```text
AT_M2:                       AUTHORIZED / IN PROGRESS
AT_M2_AUTHORIZED_BY:         AT-D11 / docs/decisions/at-m2-authorization.md
AT_M2_SCOPE:                 AT-M2-TEAM-CORE only
AT_M3_TO_AT_M8:              NOT AUTHORIZED
PCP_V2_1:                    IN PROGRESS / REMEDIATION
PCP_V2_1_B:                  FAIL / HISTORICAL
PCP_V2_1_C:                  FAIL / HISTORICAL
PCP_V2_1_D:                  PASS_WITH_ADVISORY / REMEDIATION REQUIRED
PCP_V2_1_E:                  FAIL / DEF-PCPE-01 / REMEDIATED BY PCP-V2.1-RM4
PCP_V2_1_F:                  FAIL / BLK-PCPF-01 + BLK-PCPF-02 / REMEDIATION REQUIRED
PCP_V2_1_GATES:              PRODUCTION AUTHORIZATION
RUNTIME_IMPLEMENTATION:      AT-M2-TEAM-CORE / NON-PRODUCTION
PRODUCTION_AUTHORIZATION:    NOT GRANTED
PRODUCTION_EXECUTED_TRUE_COUNT: 0
```

`AT_M2` here is the **live** authorization state, and its authority is the AT-D11 decision record,
not this snapshot. The AT-M1 binding-decisions contract still records `AT_M2: NOT AUTHORIZED`,
which stays true of AT-M1: a later authorization supersedes an earlier position without falsifying
the record of it.

`PCP_V2_1_GATES` is the re-sequencing, and it is a **move, not a waiver**. PCP-V2.1's own state
above is unchanged, no registered debt is retired, and `PCP-V2.1 PASS` is not claimed. The open
item is a governance measurement reconciliation that reaches no authorization, production-safety,
security, destructive-action or data-integrity control, so it gates production authorization
rather than a non-production milestone that cannot cross any of those boundaries.

## 6. Active HOLD items

```text
PR28_HOLD:                   HOLD / PRESERVE / NON-CANONICAL, future AT-M7 input
```

PR #28 blocks nothing in AT-M1 through AT-M6 and is not a dependency of any current work. It must
never be treated as a canonical dependency while it is on hold.

## 7. Blockers and debt

```text
BLOCKERS:                    PCP-V2.1-RM5 CANONICAL DEBT NOT RECONCILED
GOVERNANCE_MEASUREMENT_STATE: STALE / RETAKE REQUIRED AT AT-M2 CANONICAL MERGE
GOVERNANCE_MEASURED_AT:      f1ab151838c4bb3cf21337a1c876f92d2e91f9a9
GOVERNANCE_INPUT_DIGEST:     48163467ef93662cbd0f3e48686cf219c5d9f75e765c25940078b3e5ed8e2d83
GOVERNANCE_DEBT_BASELINE:    2a2facc898aa3738322d4487cbfce591cfbadc46
CANONICAL_MEASURED_COMMIT:   f1ab151838c4bb3cf21337a1c876f92d2e91f9a9
MEASUREMENT_POLICY_ID:       pcp-v2-canonical-isolated
MEASUREMENT_POLICY_VERSION:  2
MEASUREMENT_POLICY_DIGEST:   a36bee95fc078d16cf3ce3292e18290bbee48599303f53e51e16370163739226
MEASUREMENT_ISOLATION_MODE:  standalone-clone+declared-refs+sanitized-environment
ADMISSIBILITY_CONTRACT:      2
```

### Measurement staleness declared by AT-M2-TEAM-CORE

AT-M2 changed governance authority inputs — this snapshot, two verifiers, and new test modules —
so the recorded measurement no longer describes them. `check18` reports that, correctly, and the
fields above are **left exactly as measured**: they still describe the last canonical measurement
truthfully, and overwriting them with a number nobody measured is the failure mode this whole
control plane exists to prevent.

The retake is deferred to the AT-M2 canonical merge, deliberately. A measurement taken on the
unmerged AT-M2 branch is **not comparable** to a canonical one: `DECLARED_REFS` is
`refs/heads/main`, so on a branch commit every stage verifier that asks "is this branch merged
into main" or "does the diff stay in scope against main" answers a different question than it
answers on main. A trial retake at the AT-M2 branch head produced 47 measured failures outside the
active register, dominated by exactly that class. **None of them is registered here.** Registering
branch-position artifacts as canonical repository debt would repeat DEF-PCPE-01 in a new costume —
recording "this checkout was not main" as a known governance failure.

```text
RETAKE_REQUIRED_AT:          the AT-M2 canonical merge commit on main
```

Two things the retake must not do: register the branch-measured failures as canonical debt, and
re-record a digest with no canonical measurement behind it.

The measurement is taken in a **disposable clean checkout** of `CANONICAL_MEASURED_COMMIT` under a
sanitized environment, never in a working tree. It used to run wherever the operator happened to
be, and three verifiers reading a gitignored `.runtime/` directory therefore passed on one
workstation and failed in a clean checkout of the same commit — with a byte-identical
`GOVERNANCE_INPUT_DIGEST`. That is DEF-PCPE-01, and it meant `BLOCKERS: NONE` described a machine.

`MEASUREMENT_POLICY_DIGEST` covers the policy, the environment it grants and the tracer that
implements admissibility, so changing how a measurement is taken invalidates the recorded result
exactly as changing what it reads does.

`BLOCKERS: NONE` is a **measured** claim, not an assertion that nobody noticed one. For the
governance domain it means exactly this: the applicable governance verification set was executed,
and every measured failure appears in the registered-debt list below. If any measured failure is
absent from that list, `BLOCKERS: NONE` is invalid and the control plane returns
`GOVERNANCE_REGRESSION`. The claim is only as fresh as `GOVERNANCE_MEASURED_AT`; if any governance
artifact has changed since that commit, the measurement must be retaken before the claim stands.

Every measured identity resolves to one of three admissibility states. Only **REPO_DETERMINISTIC**
identities appear below. **ENVIRONMENT_DEPENDENT** identities — whose truth needs an input a clean
checkout cannot contain — are reported by the measurement with the exact input and are deliberately
**not** registered here: repository debt means a known canonical governance failure, and must not
come to mean "this machine had no runtime evidence". **UNKNOWN** identities block outright.

### Active registered debt

Exact identities, never families. A new failure inside a verifier or test module that already
appears here is still a new failure — family-level debt would let a regression hide behind an
advisory with the same signature, which is how DEF-PCPB-01 stayed invisible.

Every identity below was measured failing at `GOVERNANCE_DEBT_BASELINE`, before any PCP-v2 work.
None of them is fixed by being listed. Reconciliation is **bidirectional**: an identity that stops
failing must be retired to the historical section below, because leaving it active would
pre-absolve whatever regression later reintroduces it.

```text
- test:tests/test_admin_console_demo_evidence_ui_remediation.py::test_demo_evidence_page_and_route_exist
- test:tests/test_local_secret_scan_baseline.py::test_fixtures_classified_informational
- test:tests/test_local_secret_scan_baseline.py::test_runs_and_reports_no_confirmed_secret
- test:tests/test_product_ui_integration_fix_test.py::test_demo_evidence_diagnostic_only_in_nav
- test:tests/test_product_ui_integration_fix_test.py::test_formal_pages_are_code_backed
- test:tests/test_step66c4_be1_merge.py::test_no_live_outbox_producer_on_main
- test:tests/test_step66c4_be3_planning.py::test_no_backend_api_migration_frontend_deployment_code_changed
- test:tests/test_step66d_align1_rm1_fixed_range_remediation.py::test_66d_decisions_untouched_by_this_remediation
- test:tests/test_step66d_align1_rm1_fixed_range_remediation.py::test_rm1_verifier_passes
- test:tests/test_step66m0_fe1d_sot_reconciliation_merge.py::test_alignment_branches_remain_unmerged
- test:tests/test_step66ui2_fe1_fix1_review.py::test_branch_not_merged_into_main
- test:tests/test_step66ui2_fe1_fix1_review.py::test_diff_stays_within_expected_scope
- test:tests/test_step66ui2_fe1_navigation_grouping.py::test_step66ui2_fe1_navigation_grouping_verifier_passes
- test:tests/test_step66ui2_fe1_review.py::test_branch_not_merged_into_main
- test:tests/test_step66ui2_fe1_review.py::test_diff_stays_within_expected_scope
- verifier:verify_admin_console_demo_evidence_ui_remediation.py
- verifier:verify_local_secret_scan_baseline.py
- verifier:verify_product_ui_integration_fix_test.py
- verifier:verify_step66c4_be1_data_model_deadline_outbox.py
- verifier:verify_step66c4_be1_merge.py
- verifier:verify_step66c4_be1_r1_remediation.py
- verifier:verify_step66c4_be2_r1_remediation.py
- verifier:verify_step66c4_be3_a_authorization_foundation.py
- verifier:verify_step66c4_be3_b_c1_authority_routing_alignment.py
- verifier:verify_step66c4_be3_b_operator_resume.py
- verifier:verify_step66c4_be3_c_authorized_replay.py
- verifier:verify_step66c4_be3_planning.py
- verifier:verify_step66d_align1_rm1_fixed_range_remediation.py
- verifier:verify_step66m0_fe1d_sot_reconciliation_merge.py
- verifier:verify_step66ui2_fe1_fix1_review.py
- verifier:verify_step66ui2_fe1_navigation_grouping.py
- verifier:verify_step66ui2_fe1_review.py
```

Groups, for human reading only — the machine authority is the exact list above:
**ADV-R4-01** the ALIGN1 fixed-range debt; **ADV-PCPRM1-01** the 66C4 live-reference verifiers and
their mirrored tests, plus the 66UI2-FE1 review verifiers surfaced once applicability stopped
depending on how a verifier spells its live reference.

Three identities were **removed** at PCP-V2.1-RM4, and removal is not repair. The verifiers
`verify_step66c4_be3_ra1b_migration_runner_remediation.py`,
`verify_step66c4_be3_ra1c_ledger_schema_cli.py` and
`verify_step66c4_be3_ra1d_missing_config_json.py` query pull-request state through the GitHub CLI,
whose credentials live in the operator's account rather than in the repository. Their result was
decided by whichever machine ran the measurement, so they are environment-dependent and cannot be
canonical repository debt. The underlying validations are **not** fixed and are **not** claimed to
pass; they have left the canonical repository-state domain, and the exclusion is printed with its
reason on every run.

### Historical debt

Identities that no longer fail. Audit record only: an entry here exempts nothing, so if one starts
failing again it is a new blocker.

```text
(none)
```

Carried governance debt, none of it blocking. Nothing here is closed by being listed.

| id | subject |
| --- | --- |
| ADV-R8-01 | carrier key must head with the subject; contract wording is looser than the rule |
| ADV-R8-02 | atomicity enforces punctuation shapes, narrower than its normative wording |
| ADV-R8-03 | subject-leading prose containing a colon is over-classified as a carrier |
| ADV-R8-04 | required-carrier registry has no self-integrity protection |
| ADV-R8-05 | a line that is only a backticked register is treated as a carrier |
| ADV-R8-06 | binding policy ownership rests on the focused tests, not the main verifier |
| ADV-R7-01 | canonical-artifact set is computed as a superset of its documented enumeration |
| ADV-R7-03 | prose contradiction advisory is implemented but never invoked |
| ADV-R7-04 | section-field discovery is asymmetric between subjects |
| ADV-R7-05 | dead historical verifier symbols with a now-false comment |
| ADV-R7-07 | register-looking non-subject-keyed lines read as authoritative to humans |
| ADV-R5-01 | stale self-referential counts in narrative evidence |
| ADV-R4-01 | ALIGN1 historical fixed-range debt; two known pre-existing test failures |

`ADV-R6-02` is closed for its pull-request metadata portion only. That closure does not generalize
to stale evidence elsewhere.

## 8. Known transition hazard

```text
HAZARD_AT_M1_DENYLIST:       OPEN / DISPOSITION REQUIRED BEFORE FIRST CROSSING MILESTONE
```

The AT-M1 verifier's current-state rejection checks are HEAD-relative from a fixed baseline, by
design, so that a forbidden path landing after the reviewed stage head is still caught. A later
**authorized** milestone may legitimately introduce paths AT-M1 currently rejects — `agents/`,
`apps/`, `shared/`, `migrations/`, `infra/` among them — and AT-M2 is the likely first.

This is not authorization to weaken AT-M1. The rule is: **before the first future authorized
milestone that legitimately crosses an AT-M1 HEAD-relative denylist boundary, an explicit verifier
lifecycle and supersession disposition is required.** That decision is not made here.

## 9. Source-of-truth precedence

```text
1  GitHub canonical main          engineering source of truth
2  this PM State Snapshot         derived project-control truth
3  persistent assistant memory    durable principles and decisions only
4  conversation history           convenience context, never required
```

Volatile facts — any SHA, pull-request state, test count, path count, current stage, current
blocker, merge state — must never be trusted from memory or from chat history alone. They are
reconcilable against canonical evidence and must be reconciled before use.

## 10. Freshness requirement

Before relying on this snapshot, run the drift gate:

```text
python scripts/verify_pcp_v2_control_plane.py
python scripts/verify_pcp_v2_control_plane.py --remote     # also machine-confirms PR state
```

A `PM_STATE_CONFLICT` verdict means this file and canonical engineering truth disagree. Stop, do
not pick the more convenient source, and reconcile from `main`.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
