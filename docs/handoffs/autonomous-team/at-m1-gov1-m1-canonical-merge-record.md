# AT-M1-GOV1-M1 — Canonical Merge Record (GOV-STAGE-FAMILY-ALLOWLIST-01)

> **Merge and record only. No backend, API, frontend, runtime, migration, table, repository, ORM
> model, event, identity, secret, feature-gate or deployment change. No container, database, Redis,
> Kubernetes, Vault, OIDC provider, agent workflow or external provider started.
> `production_executed_true_count: 0`.**

## 1. Identity

```text
Stage:                AT-M1-GOV1-M1
Finding closed:       GOV-STAGE-FAMILY-ALLOWLIST-01
Authority:            Product Owner
Executor:             Claude Code
PR:                   #30  governance/at-m1-stage-family-compatibility -> main
Merge authorization:  GRANTED
```

## 2. Commit chain

```text
Pre-merge main:       2d4da808b1a89ea278fbb760e27f49047995165e
PR #30 head:          2faa9c7fe68dcd1bb04aab971c34a6d0bb047e2c
Merge commit:         d2d9b7380b3c8e95e276547e46e83b9989ce5955
Merge parent 1:       2d4da808b1a89ea278fbb760e27f49047995165e
Merge parent 2:       2faa9c7fe68dcd1bb04aab971c34a6d0bb047e2c
```

```text
Merge method:                    NON-SQUASH MERGE (true merge commit)
Parent count:                    2
PR commit count:                 7
Original commits preserved:      YES -- all 7 are ancestors of main
  964ca7a  fix(governance): make stage-family verifier admission explicit
  aa77b0b  test(governance): verify bounded AT stage-family compatibility
  690ed76  fix(governance): assert historical set-difference expressions
  5b939b7  docs(governance): record AT-M1 GOV1 evidence
  36176e4  fix(governance): make historical equality guard behavioral
  800679d  fix(governance): close GOV1 typing gate
  2faa9c7  docs(governance): record R1 verdict and RM1 closure evidence
Rebase / Squash / Amend:         NO / NO / NO
Force-push:                      NO
PR final state:                  MERGED (2026-08-12T01:28:14Z)
```

Non-squash was required rather than preferred: commits 4–7 are the RM1 closure of an independent
review finding, and collapsing them would erase the provenance that the defect was reproduced
before it was fixed.

## 3. What is now canonical

Governance admission is bound to a **registered stage family**, not to a stage-family name.

```text
REGISTERED_GOVERNANCE_FAMILIES
  step66            ^scripts/verify_step66[a-z0-9_]*\.py$   ^tests/test_step66[a-z0-9_]*\.py$
  autonomous-team   ^scripts/verify_at_m\d+[a-z0-9_]*\.py$  ^tests/test_at_m\d+[a-z0-9_]*\.py$
```

```text
Admission rule:                  is_admitted_current_state_path (single source)
Consumed by:                     ALIGN1 verifier check30 AND the mirrored ALIGN1 test
Living under scripts/ or tests/: NOT SUFFICIENT
Unregistered family:             REJECTED
Empty path:                      REJECTED
Future AT-M2 .. AT-M8:           ADMITTED without a further historical verifier edit
Arbitrary future stage prefix:   NOT trusted -- registration is explicit and closed
```

### Historical truth, unchanged

```text
ALIGN1 CANONICAL_MAIN:           64467fefc9a9ec303f9ddf4c0ce6d46486504d71   UNCHANGED
ALIGN1_STAGE_HEAD:               6a8a7bfa2ae758e944b1126881a69fef2d122dcb   UNCHANGED
ALIGN1_EXPECTED_PATHS:           34 paths                                   UNCHANGED
check33_positive_exact_scope:    two frozen endpoints, exact set equality    UNCHANGED
```

Only the current-state admission rule was changed. The distinction was settled by **git range
arity**, not by stated intent: `check30` diffs one endpoint (live HEAD, current-state governance),
`check33` diffs two frozen endpoints (historical truth).

## 4. Scope

```text
Changed paths:                   5 exact (2d4da80...2faa9c7)
  M  scripts/verify_step66d_align1_delivery_decision_model.py
  M  tests/test_step66d_align1_delivery_decision_model.py
  A  scripts/verify_at_m1_gov1_stage_family_compatibility.py
  A  tests/test_at_m1_gov1_stage_family_compatibility.py
  A  docs/handoffs/autonomous-team/at-m1-gov1-stage-family-compatibility-evidence.md

Architecture / precedence / milestone manifest:  0
source/progress.md:                              UNCHANGED
Runtime / migration / frontend / infra / CI:     0
PR #29 content / PR #28 content:                 0
```

`source/progress.md` was deliberately left unchanged, consistent with `ADV-DRIFT-PROGRESS-01` in the
66D-BE1-CR1-M1 record: three canonical-merge tests diff it against HEAD, and touching it here would
trigger that known drift without being required by this stage.

### Post-merge positive-scope freeze

The GOV1 verifier computed `GOV1_BASELINE...HEAD`, safe while the branch was open because `HEAD` was
the PR head bounded by the exact 5-path registry. Merged, `HEAD` is `main` and advances. This record
adds three paths, all of which the repaired admission rule admits by construction:

```text
docs/handoffs/autonomous-team/at-m1-gov1-m1-canonical-merge-record.md   docs/ prefix
scripts/verify_at_m1_gov1_m1_canonical_merge.py                        autonomous-team family
tests/test_at_m1_gov1_m1_canonical_merge.py                            autonomous-team family
```

Admitted by the current-state rule, but still **unexpected** against a positive registry of exactly
five paths — so the positive scope was frozen at canonicalization, the same treatment the
66D-BE1-CR1-M1 record applied to the CR1 verifier:

```text
GOV1_BASELINE:       2d4da808b1a89ea278fbb760e27f49047995165e
GOV1_STAGE_HEAD:     2faa9c7fe68dcd1bb04aab971c34a6d0bb047e2c
Positive range:      2d4da80...2faa9c7   (frozen; was BASELINE...HEAD)
Expected paths:      5        Actual paths: 5        Exact equality: YES
Positive HEAD endpoints remaining:  0
```

The rejection guards were deliberately **not** frozen with it: they stay HEAD-relative and feed the
denylist only, so a runtime or architecture path introduced by any later commit is still caught.

This freeze is recorded as it happened. It was written into this record before it was implemented,
landed one commit later than the record, and the omission was caught by the final
post-canonicalization regression rather than by inspection — the same class of HEAD-endpoint debt
that A-01 now carries for AT-M1.

## 5. Independent review history

```text
AT-M1-GOV1-R1   PASS_WITH_ADVISORY   fresh reviewer, own worktrees and probes
  D-01  check11 textual, not behavioral (X2/X3 enforcement-deletion escapes)   -> RM1
  D-02  3 mypy errors in the GOV1 test module                                  -> RM1
  A-01  AT-M1 baseline re-pin needed post-merge                                -> AT-M1-RM1
  A-02  regression selection not recorded in-repo                              -> TRACKED
  A-03  bare family names admitted by design                                   -> INFORMATIONAL

AT-M1-GOV1-RM1  PASS                 D-01 and D-02 closed
AT-M1-GOV1-R2   PASS_WITH_ADVISORY   escapes independently reproduced at 5b939b7, then rejected
```

D-01 is closed **behaviorally**, not textually: `check11a`/`check11b` perturb the imported ALIGN1
registry in each direction, call the real `check33_positive_exact_scope()`, and require a recorded
failure; `check11c` is the untampered control. Module state is restored after every probe.

## 6. Verification

Pre-merge at PR head `2faa9c7`, and re-run post-merge at `d2d9b73` — identical results:

```text
AT_M1_GOV1_STAGE_FAMILY_COMPATIBILITY_VERIFY:  PASS   79 checks, 0 failures
STEP66D_ALIGN1_DELIVERY_DECISION_MODEL_VERIFY: PASS
GOV1 tests    42 passed · ALIGN1 tests 64 passed        all 0 failed, 0 skipped
Four-file mypy gate:  Success: no issues found in 4 source files
ruff / black / git diff --check:  PASS / PASS / CLEAN
secret / credential / identifier / local-path scans:  0 in all seven categories
```

Mutation probes M01–M09 plus X2/X3 all REJECTED, untampered control PASS — each applies one
forbidden change inside a disposable git worktree and runs the real verifier as a subprocess.

### Regression

```text
Selection rule:   grep -rl "name-only" tests/  UNION  test_step66d_*, test_step66sync1_*,
                  test_step66align2_*, test_step66m0_*, test_step66c4_be3_ra2m*
                  derived fresh from the post-merge repository, sequential, -p no:randomly
Modules:          34        Collected: 1398        core.longpaths: true

Post-merge main d2d9b73     1389 passed, 9 failed, 0 skipped
Accepted baseline           failure ID set IDENTICAL (9 IDs)
New failure IDs:            0            Network retries: 0
```

The module and test counts grew because the selection rule, applied to the post-merge repository,
now also matches GOV1's own test module. The nine failures are pre-existing debt, unchanged and out
of scope.

## 7. Advisories — tracked, deliberately not remediated

```text
A-01   AT-M1 baseline re-pin           CONFIRMED / MANDATORY INPUT TO AT-M1-RM1
A-02   regression selection prose-only PARTIALLY MITIGATED / NON-BLOCKING
A-03   bare family names admitted      INFORMATIONAL / BY DESIGN
ADV-AT-PRECEDENCE-01                   OUT OF SCOPE / pre-authorized for AT-M1-RM1
ADV-GOV1-LONGPATH-01                   NEW / NON-BLOCKING -- core.longpaths is machine-local and
                                       uncommitted; a fresh clone or CI runner without it will see
                                       phantom "Filename too long" failures in deep checkouts
ADV-GOV1-NETFLAKE-01                   NEW / NON-BLOCKING -- three tests in
                                       test_step66sync1_final_partner_reconciliation.py call
                                       git ls-remote origin; a single red run is not by itself
                                       evidence of a regression
ADV-DRIFT-PROGRESS-01                  TRACKED / NOT REMEDIATED (see section 4)
```

## 8. A-01 handoff to AT-M1-RM1

PR #29 pins `AT_M1_BASELINE = 2d4da808…`, which this merge has advanced past. Verified by
construction, not by argument: with GOV1's five paths committed on top of PR #29's head, the AT-M1
verifier reports `checks=164 failures=2` — `check02` names GOV1's five paths as unexpected and
`check09` also fires. The control run against the old main passes.

```text
Old baseline:     2d4da808b1a89ea278fbb760e27f49047995165e
New baseline:     POST_GOV1_CANONICAL_MAIN -- head of main after this record commit
                  (read with: git rev-parse origin/main)

AT-M1-RM1 must re-pin, in PR #29:
  scripts/verify_at_m1_architecture_reset.py    AT_M1_BASELINE, AT_M1_BASELINE_SHORT,
                                                and the checks at lines 294 / 659 / 720
  tests/test_at_m1_architecture_reset.py        AT_M1_BASELINE
  docs/architecture/autonomous-team/at-m1-architecture-reset.md
  docs/contracts/autonomous-team/at-binding-decisions.md
  docs/contracts/autonomous-team/at-canonical-terminology-registry.md
  docs/contracts/autonomous-team/at-capability-state-registry.json   canonical_baseline
  docs/decisions/at-m1-architecture-decisions.md
  docs/handoffs/autonomous-team/at-m1-evidence.md
then recompute PR #29 positive scope as POST_GOV1_CANONICAL_MAIN...AT-M1 stage head.
```

Not performed in this stage. PR #29 was not modified.

## 9. Canonical state

```text
AT_M1_GOV1_M1:                         PASS
PR30:                                  MERGED
GOV_STAGE_FAMILY_ALLOWLIST_01:         CLOSED / CANONICALIZED
HISTORICAL_TRUTH:                      PRESERVED
AT_FAMILY_COMPATIBILITY:               ESTABLISHED / BINDING
PR29:                                  OPEN / UNCHANGED / BLOCKED ON A-01
PR28:                                  OPEN / HOLD / UNCHANGED
AT_M1_RM1:                             AUTHORIZED TO START / NOT STARTED
AT_M2:                                 NOT AUTHORIZED
SHARED_MIGRATION:                      NOT APPLIED
DEPLOYMENT:                            NONE
PRODUCTION_EXECUTED_TRUE_COUNT:        0
```

No runtime, migration, table, repository, API, frontend, event or read model was created or changed.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
