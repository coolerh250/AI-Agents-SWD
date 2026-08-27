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
RECONCILED_ON:               2026-08-27
RECONCILED_AGAINST_MAIN:     d6442bde67586bb8031365a5696cf74164c6c905
RECONCILED_BY_STAGE:         AT-M3.2-CANONICALIZATION-1 / PRODUCT ACCEPTANCE
```

`RECONCILED_AGAINST_MAIN` is the commit this snapshot was verified against. It is expected to fall
behind as work lands. Falling behind is **staleness**, which is tolerated and reported; naming a
commit that is unknown to the repository, or that is not an ancestor of `main`, is **drift**, which
is a conflict.

## 2. Position

```text
CURRENT_MILESTONE:           AT-M3
CURRENT_MILESTONE_STATE:     IN PROGRESS -- AT-M3.1 and AT-M3.2 MERGED / CLOSED; AT-M3.3 is the
                              next implementation slice
PREVIOUS_COMPLETED_STAGE:    AT-M3.2 (canonical merge)
CURRENT_GATE:                NONE -- AT-M3.2 canonically merged; AT-M3.3 .. AT-M3.6A are already
                              authorized under AT-D14 (see section 5a), so no new gate is open for
                              them; AT-M3.6B, production and AT-M4 remain closed
CURRENT_STAGE:                AT-M3.2-CANONICALIZATION-1 / PRODUCT ACCEPTANCE
NEXT_PERMITTED_STAGE:        AT-M3.3 IMPLEMENTATION -- Bounded Team Discussion. Already
                              authorized under AT-D14; no new Product Owner decision is required
                              unless the architecture materially changes, an authorization/security
                              boundary expands, external network/model use is introduced, or
                              production becomes involved.
```

AT-M2 was canonicalized by AT-D13 (`docs/decisions/at-d13-at-m2-merge-authorization.md`), which authorized
merging the validated candidate and recorded the real Governance Validation 2 result. The merge was
a fast-forward: `origin/main` `192ebb74…` to `0986c895e85b426f3ca56239ad7cdb39288a8546`, the exact
validated `at-m2-team-core` tip. No conflict, no rebase, no history rewrite.

AT-M3.1 (Reasoning Contract & Provider Abstraction) was accepted and canonicalized by AT-D15
(`docs/decisions/at-d15-at-m3-1-acceptance-and-merge-authorization.md`), which records the
Validation 1 (FAIL, 3 blockers) → AT-M3.1-REMEDIATION-1 → Validation 2 (PASS) evidence chain and
authorizes the merge. The merge was a fast-forward: `origin/main` `44cdd6f…` to
`1e9fe3b445e1ddaefe0c4ed0bdc5be8af4d0ad96`, the exact validated candidate tip plus one docs-only
commit recording AT-D15 itself. No conflict, no rebase, no history rewrite. AT-M3.1's own
implementation authorization is AT-D14 (`docs/decisions/at-d14-at-m3-live-reasoning-authorization.md`);
AT-D15 authorizes the merge only, exactly as AT-D13 did for AT-D11/AT-M2. See section 5a.

AT-M3.2 (Goal + immutable PlanRevision) was accepted and canonicalized by AT-D19
(`docs/decisions/at-d19-at-m3-2-acceptance-and-merge-authorization.md`), which records the
Validation 1 (FAIL, 2 blockers) → AT-M3.2-IMPLEMENTATION-REMEDIATION-1 → Validation 2 (PASS)
evidence chain and authorizes the merge. The merge was a fast-forward from `origin/main`
`d5880d2…` to the exact validated candidate `d6442bde67586bb8031365a5696cf74164c6c905` plus one
docs-only commit recording AT-D19 and this reconciliation. No conflict, no rebase, no history
rewrite. `AT_M3_2_IMPLEMENTATION_END` stays at the validated commit and does not follow the
branch tip. See section 5a.

AT-M1 stays `CLOSED / CANONICAL`; it is no longer the *current* milestone because AT-D11
authorized its successor. Position moved off the PCP remediation chain at the same decision — see
section 5.

```text
AT_M1_LIFECYCLE:             SUPERSEDED BY AT-M2
AT_M1_SUPERSESSION_COMMIT:   192ebb74ba600f7a53ddf5967a7254a1f7a72fb8
```

AT-M1 was not the only stage carrying a "this stage introduced no implementation" guard asked
from a frozen baseline to HEAD. Fifteen such guards exist across the 66C4-BE3, 66D, 66SYNC1 and
66UI4 families, and AT-M2 — the first implementation milestone since those baselines — trips
every one of them. Individually relaxing fifteen guards would be fifteen chances to weaken one by
accident, so they share **one** mechanism, `scripts/successor_lifecycle.py`, driven by the three
fields below. It decides only WHERE a stage's rejection window ends; it changes no other
assertion in any guard and never widens a positive scope.

```text
SUCCESSOR_IMPLEMENTATION_MILESTONE: AT-M2
SUCCESSOR_LIFECYCLE_BOUNDARY:       192ebb74ba600f7a53ddf5967a7254a1f7a72fb8
SUCCESSOR_AUTHORIZATION_RECORD:     docs/decisions/at-m2-authorization.md
```

The mechanism fails closed on every prerequisite: the snapshot must name the milestone, the
boundary and the decision record; the milestone must be recorded AUTHORIZED with its authorizing
decision named; that decision must exist, be `RESOLVED / BINDING`, and name the SAME boundary;
the boundary must exist and be an ancestor of HEAD; and it must be a DESCENDANT of the calling
guard's own baseline, so it can never be walked backwards over a stage's own commits.

A stage's "no implementation" claim is historical and correctly bounded at the field above. A
runtime denylist is not: it must keep rejecting a protected path forever, not just up to the
boundary, or an unauthorized change landing after AT-M2 would never be seen again. The only thing
such a live guard has to tolerate is AT-M2's own already-reviewed work, which is recorded here by
CONTENT rather than by window, so a later, unauthorized edit to a path AT-M2 already touched is
still caught:

```text
SUCCESSOR_AUTHORIZED_CHANGESET_END: 9c002e06029a682f586013671e8cb30ed1a475f4
```

Not a new authorization, a machine-checkable pointer at work AT-D11 already authorizes: the AT-M2
candidate tip through the completed live/historical guard-split implementation
(`fix(governance): split live runtime denylists from the historical successor window`). A live
guard excludes a changed path only where its content at HEAD is byte-identical to its content at
this commit; anything else, including a second edit to the same path, is live-checked and
rejected. This field records reviewed work, not the tip: a later commit that only records this
field's own value forward does not itself become "reviewed" by that act, and this remediation
does not move the field to name itself. If AT-M2 gains further reviewed implementation commits
before merge, this field moves forward again to name them; it does not move on its own.

Three artifacts are historical stage evidence and live machinery at the same time — two RA-2
guards that must still scan current state, and one route inventory that must still describe
current source. A byte-freeze stops them working; free editing dissolves the freeze contract for
every stage. AT-D12 resolves that conflict with an exhaustive named set and two amendment shapes
that keep the historical content provable. The same module enforces it, from these two fields:

```text
SUCCESSOR_FREEZE_AMENDMENT_DECISION: AT-D12
SUCCESSOR_FREEZE_AMENDMENT_RECORD:   docs/decisions/at-d12-successor-freeze-amendment.md
```

This too fails closed: no snapshot fields, no record on disk, a record that is not
`RESOLVED / BINDING`, a record naming a different successor milestone, or a path the record does
not list — any one of them and every frozen artifact is immutable again. AT-D12 changes no
scope, retires no debt, registers no failure as debt, and grants no authorization.

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
AT_M2:                       AUTHORIZED / MERGED / CLOSED
AT_M2_IMPLEMENTATION:        COMPLETE
AT_M2_RUNTIME_TEAM_CORE:     ACCEPTED
AT_M2_GOVERNANCE_TRANSITION: CLOSED
AT_M2_AUTHORIZED_BY:         AT-D11 / docs/decisions/at-m2-authorization.md
AT_M2_MERGE_AUTHORIZED_BY:   AT-D13 / docs/decisions/at-d13-at-m2-merge-authorization.md
AT_M2_SCOPE:                 AT-M2-TEAM-CORE only
AT_M2_CANONICAL_MAIN:        0986c895e85b426f3ca56239ad7cdb39288a8546
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

`AT_M2` here is the **live** authorization state, and its authority is the AT-D11 (implementation)
and AT-D13 (merge) decision records, not this snapshot. The AT-M1 binding-decisions contract still
records `AT_M2: NOT AUTHORIZED`, which stays true of AT-M1: a later authorization supersedes an
earlier position without falsifying the record of it. `AT_M2` keeps the literal word `AUTHORIZED`
immediately after the field name even though the milestone is now merged and closed, because
`scripts/successor_lifecycle.py`'s `authorized_successor()` parses exactly that spelling to decide
whether a successor is live at all — rewording it would silently reopen every historical guard's
window and blind every live runtime denylist to AT-M2's own already-reviewed work, which is the
opposite of what closing the milestone should do.

`AT_M3_TO_AT_M8: NOT AUTHORIZED` is unchanged and stays exact as a record of what AT-D12 itself
authorized (nothing) — the same "a later authorization supersedes an earlier position without
falsifying the record of it" rule this file already applies to AT-M1's `AT_M2: NOT AUTHORIZED`
line applies here too. AT-D14, recorded after this line was first written, narrows it for a named
subset: non-production, non-external-network implementation of AT-M3.1 through AT-M3.6A is now
authorized, and AT-D15 has accepted and merged AT-M3.1 specifically — see section 5a for the live
state. `AT-M3.6B` (a real external model call) and everything beyond AT-M3.6A still require their
own Product Owner decision, the same rule AT-D11 and AT-D13 restated for AT-M2.

`PCP_V2_1_GATES` is the re-sequencing, and it is a **move, not a waiver**. PCP-V2.1's own state
above is unchanged, no registered debt is retired, and `PCP-V2.1 PASS` is not claimed. The open
item is a governance measurement reconciliation that reaches no authorization, production-safety,
security, destructive-action or data-integrity control, so it gates production authorization
rather than a non-production milestone that cannot cross any of those boundaries.

## 5a. AT-M3 progress

AT-D14 authorizes non-production, non-external-network implementation and mock/local validation of
AT-M3.1 through AT-M3.6A (schema evolution included). AT-D15 accepts and merges AT-M3.1
specifically; AT-D19 does the same for AT-M3.2. Authorization scope and implementation state are
different questions; this section answers both, and is additive to — never a replacement for — the
`AT_M3_TO_AT_M8` line in section 5.

```text
AT_M3_1:                       AUTHORIZED / MERGED / CLOSED
AT_M3_1_IMPLEMENTATION:        COMPLETE
AT_M3_1_VALIDATION:            PASS -- 2 of 2 (Validation 1 FAIL / 3 blockers ->
                                AT-M3.1-REMEDIATION-1 -> Validation 2 PASS; no Validation 3)
AT_M3_1_ACCEPTANCE:            PO ACCEPTED
AT_M3_1_AUTHORIZED_BY:         AT-D14 / docs/decisions/at-d14-at-m3-live-reasoning-authorization.md
AT_M3_1_MERGE_AUTHORIZED_BY:   AT-D15 / docs/decisions/at-d15-at-m3-1-acceptance-and-merge-authorization.md
AT_M3_1_CANONICAL_MAIN:        1e9fe3b445e1ddaefe0c4ed0bdc5be8af4d0ad96
AT_M3_2:                       AUTHORIZED / VALIDATED / PO_ACCEPTED / MERGED / CANONICAL / CLOSED
AT_M3_2_IMPLEMENTATION:        COMPLETE
AT_M3_2_VALIDATION:            PASS / COMPLETE -- 2 of 2 (Validation 1 FAIL / 2 blockers ->
                                AT-M3.2-IMPLEMENTATION-REMEDIATION-1 -> Validation 2 PASS; no
                                Validation 3)
AT_M3_2_ACCEPTANCE:            PO ACCEPTED
AT_M3_2_AUTHORIZED_BY:         AT-D14 / docs/decisions/at-d14-at-m3-live-reasoning-authorization.md
AT_M3_2_MERGE_AUTHORIZED_BY:   AT-D19 / docs/decisions/at-d19-at-m3-2-acceptance-and-merge-authorization.md
AT_M3_2_IMPLEMENTATION_END:    d6442bde67586bb8031365a5696cf74164c6c905
AT_M3_3:                       NOT YET STARTED
AT_M3_3_THROUGH_AT_M3_6A:      AUTHORIZED (AT-D14) / NOT YET IMPLEMENTED
PRODUCT_CRITICAL_PATH:         AT-M3.3
NEXT_PRODUCT_STAGE:            AT-M3.3 -- Bounded Team Discussion
AT_M3_6B:                      NOT AUTHORIZED
```

`AT_M3_1` and `AT_M3_2` keep the literal word `AUTHORIZED` immediately after the field name for the
same reason `AT_M2` does (section 5): it is the live authorization state, not a claim that
validation is still open. `AT_M3_3_THROUGH_AT_M3_6A` records that AT-D14 already authorizes that
work; it is not itself an implementation-complete claim, and each of those slices still needs its
own implementation report and its own Validation 1/2 pass before it can read the way `AT_M3_1` and
`AT_M3_2` do here. `AT_M3_2_IMPLEMENTATION_END` is the exact independently validated commit and
does not follow the branch tip: the acceptance and reconciliation commit that lands on top of it
is documentation, and moving the field to name it would silently claim validation coverage the
docs commit never had. `AT_M3_6B` names the boundary AT-D14 explicitly did not move: no real
external LLM/network call is authorized by any record in this file.

Four non-blocking observations were carried out of AT-M3.2 Validation 2 as backlog, not
remediated, and are recorded in full in AT-D19 section 6: creation-time non-draft PlanRevision
status (revisit in M3.4 so TeamDecision stays the canonical chooser); a duplicate no-op acceptance
audit event; audit emission depending on an injected client, so the HTTP path writes none; and the
inherited store-level key-screen / free-text-value / raw-SQL leaf-delete gaps. Under AT-D18-R05
all four are `NON-BLOCKING` — none reaches a Minimal Blocking Governance Kernel control — and none
is registered as debt here.

One non-blocking observation was carried out of AT-M3.1 Validation 2 as backlog, not remediated:
an unvalidated, caller-supplied `request.provider_name` can flow into an audit event's
summary/refs when an audit client is configured. It does not touch `reasoning_invocations`, mirrors
a pre-existing repo-wide audit-construction pattern, and is not registered as debt here — it is a
candidate for a future observability/audit-hardening slice, not a blocker of anything above.

## 6. Active HOLD items

```text
PR28_HOLD:                   HOLD / PRESERVE / NON-CANONICAL, future AT-M7 input
```

PR #28 blocks nothing in AT-M1 through AT-M6 and is not a dependency of any current work. It must
never be treated as a canonical dependency while it is on hold.

## 7. Blockers and debt

```text
BLOCKERS:                    PCP-V2.1-RM5 CANONICAL DEBT NOT RECONCILED; HAZARD_AT_M3_LIVE_DENYLIST
                              OPEN (see section 8) -- 25 historical stage-guard tests across 10
                              files newly fail after the AT-M3.1 merge, all one root cause, no
                              defect in AT-M3.1 itself
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

```text
HAZARD_AT_M3_LIVE_DENYLIST:  OPEN / DISPOSITION REQUIRED -- DISCOVERED AT AT-M3.1 CANONICAL MERGE
```

`scripts/successor_lifecycle.py`'s live guard (`live_guard_changed_paths`) is, by design, never
HEAD-relative-capped: it forever rejects a protected-path change (`apps/`, `agents/`, `shared/`,
`migrations/`, `infra/` among them) unless that change's content at HEAD is byte-identical to the
content recorded at `SUCCESSOR_AUTHORIZED_CHANGESET_END` — and that field is scoped to **AT-M2's
own** reviewed work specifically (`SUCCESSOR_IMPLEMENTATION_MILESTONE: AT-M2`), pinned at
`9c002e0`. It was never extended to recognise a later milestone's own authorized, validated work
as reviewed, because no milestone after AT-M2 had merged new content under those paths until now.

AT-M3.1 is that first crossing. Its own files
(`shared/sdk/agent_reasoning/*`, `migrations/037_at_m3_reasoning_invocations*.sql`) are genuinely
new, AT-D14/AT-D15-authorized, Validation-1/2-passed content under `shared/` and `migrations/` —
and the live guard, correctly doing exactly what it is built to do, does not yet have a mechanism
to recognise them as reviewed. Post-merge verification (this reconciliation) ran the ten
historical stage-guard test files that route through this mechanism
(`test_at_d12_successor_freeze_amendment.py` plus the 66C4-BE3/66D/66SYNC1 families) and found 25
newly-failing tests, all with the identical root cause and an identical offender list — no new,
independent defect in any of them, and no defect in AT-M3.1 itself.

This is not a defect in AT-M3.1, and it is not authorization to weaken any of those guards. Per
the same rule the AT-M1 hazard above states: **before this can be called a clean regression state,
an explicit decision extending (or otherwise dispositioning) the live-guard exemption to cover
AT-M3.1's own reviewed work is required — analogous to what AT-D12 did for AT-M2's own transition.
That decision is not made here**, and this reconciliation deliberately does not move
`SUCCESSOR_AUTHORIZED_CHANGESET_END` to cover it: that field's job is to record what AT-M2
specifically reviewed, and moving it to name AT-M3.1's content would misstate that.

## 8a. Project execution standard and 2026-08-26 postmortem disposition

The binding shared process standard for every partner is
[AI_AGENTS_PROJECT_EXECUTION_STANDARD.md](AI_AGENTS_PROJECT_EXECUTION_STANDARD.md). It is read
before any architecture, implementation, validation, roadmap, governance or blocker decision, and
it is what `CLAUDE.md` at the repository root points every fresh session at. It is process memory
only: it adds no verifier, no registry, no discovery and no runtime.

```text
PROJECT_EXECUTION_STANDARD:         ACTIVE / BINDING PROCESS MEMORY
PROJECT_EXECUTION_STANDARD_RECORD:  docs/governance/AI_AGENTS_PROJECT_EXECUTION_STANDARD.md
PROJECT_EXECUTION_STANDARD_ORIGIN:  AT-PROJECT-LOGIC-REVIEW-1 (2026-08-26)
```

An independent read-only forensic review on 2026-08-26 found that the hazard recorded in section 8
above had been answered by repeatedly generalizing exemption machinery — successor window, live
denylist, reviewed-changeset registry, exact authority binding, decision discovery, canonical
freeze — rather than by retiring assertions that had expired when their stage closed. The chain had
no finite root of trust and did not terminate. The AT-D16 and AT-D17 branches reached a deadlock in
which a decision's authority required presence on canonical `main`, presence on `main` required a
merge, and the merge required the guards the mechanism existed to satisfy.

```text
AT_D16_AT_D17_DISPOSITION:       FAILED / NONCANONICAL EXPERIMENTS -- NOT FOR MERGE
GOVERNANCE_RESET_RECOMMENDATION: OPTION B -- MINIMAL GOVERNANCE KERNEL + PRODUCT DECOUPLING
GOVERNANCE_RESET_STATE:          APPROVED / BINDING -- AT-D18 (2026-08-26)
```

`GOVERNANCE_RESET_STATE` moved from `RECOMMENDED / AWAITING PRODUCT OWNER RESET DECISION` to
approved when the Product Owner recorded AT-D18
(`docs/decisions/at-d18-project-governance-reset.md`). The recommendation line above it is left
exactly as written — it records what the postmortem recommended, which stays true of the
postmortem; the decision that followed is recorded in section 8b, not by editing the
recommendation.

Neither branch is a candidate for further remediation or merge unless a future explicit Product
Owner reset decision changes this. `HAZARD_AT_M3_LIVE_DENYLIST` in section 8 therefore stays
`OPEN` and is **not** dispositioned by this entry — the paragraphs above it stay unedited as the
record of how the hazard was discovered. Under the execution standard's classification the hazard
is `HISTORICAL_ONLY` in effect and blocks no product milestone by default, but retiring it
formally is a Product Owner decision this snapshot does not make.

This entry authorizes no milestone, retires no registered debt, reclassifies no recorded decision,
and grants no production or external authorization. AT-M3.2 remains implementation-authorized under
AT-D14 exactly as section 5a records; production, AT-M3.6B, AT-M4 and PCP remediation remain
unauthorized exactly as sections 5 and 5a record. `production_executed_true_count: 0`.

## 8b. Reset-0 — AT-D18 governance reset

AT-D18 (`docs/decisions/at-d18-project-governance-reset.md`) is the Product Owner decision that
adopts the postmortem's Option B recommendation and restores the product critical path. Reset-0 is
the canonicalization of that decision together with the shared process memory.

```text
PROJECT_PROCESS_MEMORY:      ACTIVE / CANONICAL
GOVERNANCE_RESET:            AT-D18 APPROVED / BINDING
RESET_OPTION:                OPTION B -- MINIMAL GOVERNANCE KERNEL + PRODUCT/GOVERNANCE DECOUPLING
RESET_0_STATE:               COMPLETE
PRODUCT_CRITICAL_PATH_AT_RESET_0: RESTORED
NEXT_PRODUCT_STAGE_AT_RESET_0:    AT-M3.2 -- Goal + immutable PlanRevision
AT_M3_2_STATE_AT_RESET_0:         AUTHORIZED UNDER AT-D14 / NOT YET STARTED
```

The last three keys carry the `_AT_RESET_0` suffix this section already uses for its authorization
boundaries, for the same reason: they record what was true **at Reset-0**, and Reset-0's position
is history now that AT-D19 has accepted AT-M3.2. Their values are unchanged. The live position is
`PRODUCT_CRITICAL_PATH` and `NEXT_PRODUCT_STAGE` in section 5a, which is where a register key must
appear exactly once — two sections holding the same key with different values would make the
snapshot ambiguous about which one is current.

Blocking disposition under AT-D18-R03 and AT-D18-R05. These are classifications of what may stop
**product** work; they weaken no control and retire no debt:

```text
PCP_META_GOVERNANCE_DISPOSITION:   PRE-PRODUCTION / NON-BLOCKING unless concrete P0/P1 evidence
HISTORICAL_GUARD_DISPOSITION:      HISTORICAL / NON-BLOCKING unless concrete P0/P1 evidence
BLOCKER_JUSTIFICATION_REQUIRED:    PROTECTED_RISK + SEVERITY + FAILURE_IMPACT + WHY_STOP_NOW
```

Authorization boundaries, restated here because Reset-0 changes none of them:

```text
PRODUCTION_AT_RESET_0:       NOT AUTHORIZED
AT_M3_6B_AT_RESET_0:         NOT AUTHORIZED
AT_M4_AT_RESET_0:            NOT AUTHORIZED unless separately authorized
PCP_REMEDIATION_AT_RESET_0:  NOT AUTHORIZED
RESET_0_PRODUCTION_EXECUTED_TRUE_COUNT: 0
```

Root of trust, as verifiable from the repository at Reset-0 — recorded as measured, never as
assumed. Establishing these primitives is a later minimal-kernel hardening stage:

```text
GITHUB_BRANCH_PROTECTION:    UNVERIFIED -- not determinable from the local environment
REQUIRED_REVIEW:             UNVERIFIED -- not determinable from the local environment
CI_WORKFLOWS:                NONE -- .github/workflows/ does not exist in this repository
COMMIT_SIGNING:              NOT IN USE
```

Reset-0 introduced no verifier, no registry, no decision discovery, no canonical activation and no
meta-governance runtime. It is documentation and one decision record. The `AT_M2` and `AT_M3_1`
fields in sections 5 and 5a keep their exact existing spellings, which repository controls parse;
nothing in this section restates them.

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
