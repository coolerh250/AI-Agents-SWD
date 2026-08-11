# AT-M1-GOV1 — Stage-Family Governance Compatibility (Evidence)

> **Governance compatibility remediation only. No architecture semantics changed, no runtime,
> backend, API, frontend, database, migration, event, deployment, identity, secret or feature-gate
> change. No shared database touched. No container, database, Redis, Kubernetes, Vault, OIDC
> provider, agent workflow or external provider started. `production_executed_true_count: 0`.**

Closes `GOV-STAGE-FAMILY-ALLOWLIST-01`.

## 1. Baseline and preflight

```text
Canonical baseline:  main 2d4da808b1a89ea278fbb760e27f49047995165e   (2d4da80)
Branch:              governance/at-m1-stage-family-compatibility, created from the exact baseline
Merge authorization: NOT GRANTED

PR #29 (AT-M1):      OPEN, NOT MERGED, head 3f18e070b8c9c7518ba65d06a2870b42328f7156 (3f18e07)
                     UNCHANGED -- not modified, rebased, cherry-picked, commented or merged
PR #28 (66D-BE1):    OPEN, NOT MERGED, head c9145cd848a211a9dd2bbff672c532da364eaa55 (c9145cd)
                     UNCHANGED / HOLD / PRESERVE
```

GOV1 branches from canonical main, never from PR #29.

## 2. Defect reproduction

Reproduced by applying the pre-remediation admission rule — read directly out of the verifier
source, not from any review prose — to the exact AT-M1 artifacts:

```text
Pre-remediation rule (scripts/verify_step66d_align1_delivery_decision_model.py, check30):

    stray = [
        p for p in changed
        if not p.startswith(("docs/", "scripts/verify_step66", "tests/test_step66"))
        and p != "source/progress.md"
    ]

scripts/verify_at_m1_architecture_reset.py                  admitted = False
tests/test_at_m1_architecture_reset.py                      admitted = False

scripts/verify_step66d_align1_delivery_decision_model.py    admitted = True
tests/test_step66d_align1_delivery_decision_model.py        admitted = True
```

```text
GOV-STAGE-FAMILY-ALLOWLIST-01:  CONFIRMED
```

The two rejected paths are the **same two artifact categories** the rule exists to permit — a stage
governance verifier and its test. They are rejected solely because their stage family is named `AT`
rather than `step66`. The identical categories under a `step66` name are admitted. Rejection is by
naming, not by architecture or runtime scope.

The mirrored rule was duplicated inline in
`tests/test_step66d_align1_delivery_decision_model.py::test_changed_paths_are_within_scope`, giving
two independent allowlists that could drift apart.

## 3. Historical vs current-state classification

This classification is the prerequisite for touching anything, and it is settled by the **git range
arity**, not by intent stated in prose:

```text
check30_no_implementation_change   git diff --name-only CANONICAL_MAIN
                                   ONE endpoint -> implicitly against live HEAD
                                   => CURRENT-STATE GOVERNANCE

check33_positive_exact_scope       git diff --name-only CANONICAL_MAIN ALIGN1_STAGE_HEAD
                                   TWO frozen endpoints
                                   => HISTORICAL STAGE TRUTH
```

The file's own header comment states the intent: *"The runtime denylists in this file stay
HEAD-relative on purpose -- they can only reject."* That is true of check30's three denylists
(forbidden source prefixes, frontend suffixes, infra manifests). It was **not** true of the fourth
rule: `stray` is an **admission** rule, and a HEAD-relative admission rule does not merely reject —
it gates all future repository evolution on a name.

Only the current-state admission rule is changed. The historical check is untouched.

## 4. Historical fixed-range proof

```text
Historical range:        64467fe..6a8a7bf   (CANONICAL_MAIN .. ALIGN1_STAGE_HEAD, both frozen)
Historical stage head:   6a8a7bfa2ae758e944b1126881a69fef2d122dcb
Expected exact paths:    34
Actual changed paths:    34
Exact equality:          TRUE  (both directions -- unexpected and missing)
Result before GOV1:      PASS
Result after GOV1:       PASS
Endpoint changed:        NO
Equality weakened:       NO
Registry modified:       NO
```

## 5. Old versus new admission semantics

```text
OLD  admitted  iff  path.startswith(("docs/", "scripts/verify_step66", "tests/test_step66"))
                    or path == "source/progress.md"

NEW  admitted  iff  path.startswith(ADMITTED_PATH_PREFIXES)          # ("docs/",)
                    or path in ADMITTED_EXACT_PATHS                  # ("source/progress.md",)
                    or is_registered_governance_artifact(path)
```

```python
REGISTERED_GOVERNANCE_FAMILIES = (
    ("step66",          r"^scripts/verify_step66[a-z0-9_]*\.py$",   r"^tests/test_step66[a-z0-9_]*\.py$"),
    ("autonomous-team", r"^scripts/verify_at_m\d+[a-z0-9_]*\.py$",  r"^tests/test_at_m\d+[a-z0-9_]*\.py$"),
)
```

Admission is **explicit and closed**: a path qualifies only when its stage family is registered
**and** its filename matches that family's exact convention. Living under `scripts/` or `tests/` is
deliberately insufficient, and an unregistered family is still rejected.

### Single source of truth

`is_admitted_current_state_path` lives in the verifier. The mirrored test imports it rather than
restating it, so the two rules cannot drift apart. The previous inline duplicate is gone.

## 6. Registered families and negative cases

```text
ADMITTED
  scripts/verify_step66d_align1_delivery_decision_model.py     step66 verifier
  tests/test_step66d_align1_delivery_decision_model.py         step66 test
  scripts/verify_step66c4_be3_ra2m_canonicalization.py         step66 verifier
  tests/test_step66sync1_m2_canonical_merge.py                 step66 test
  scripts/verify_at_m1_architecture_reset.py                   AT verifier
  tests/test_at_m1_architecture_reset.py                       AT test
  scripts/verify_at_m1_gov1_stage_family_compatibility.py      AT verifier (this stage)
  tests/test_at_m1_gov1_stage_family_compatibility.py          AT test (this stage)
  scripts/verify_at_m2_team_identity_collaboration.py          future AT milestone verifier
  tests/test_at_m2_team_identity_collaboration.py              future AT milestone test
  docs/**                                                      unchanged
  source/progress.md                                           unchanged

REJECTED
  scripts/at_runtime_patch.py            no verify_ prefix
  scripts/random_helper.py               not a governance artifact
  tests/at_random_helper.py              no test_ prefix
  tests/random_test_helper.py            not a governance artifact
  scripts/verify_unregistered_family.py  unregistered stage family
  tests/test_unregistered_family.py      unregistered stage family
  scripts/verify_.py  tests/test_.py     empty family segment
  agents/ apps/ shared/ migrations/ infra/ runtime/ .github/   runtime/source
  ""                                     empty path -- no fallback admission hole
```

## 7. Mutation probes

Each probe applies ONE forbidden change inside a **disposable git worktree** and runs the **real
GOV1 verifier as a subprocess**. A probe that only re-evaluates a predicate in memory cannot prove
the shipped verifier would have caught the change, so none of these do that.

```text
M01  remove AT verifier registration                REJECTED
M02  remove AT test registration                    REJECTED
M03  broad "scripts/" admission added               REJECTED
M04  broad "tests/" admission added                 REJECTED
M05  family logic replaced by catch-all verify_*    REJECTED
M06  unregistered stage family accepted             REJECTED
M07  historical frozen endpoint changed to HEAD     REJECTED
M08  historical equality weakened to subset         REJECTED
M09  shared/ and runtime/ admitted                  REJECTED
     untampered control                             PASS
```

## 8. AT-M1 compatibility probe

A disposable worktree at the exact PR #29 head with only the finalized GOV1 changes to the two
ALIGN1 files overlaid. Nothing committed, nothing pushed, PR #29 not modified.

```text
Probe worktree head:  3f18e070b8c9c7518ba65d06a2870b42328f7156
Overlay:              the two repaired ALIGN1 files only

tests/test_step66d_align1_delivery_decision_model.py::test_verifier_passes              PASS
tests/test_step66d_align1_delivery_decision_model.py::test_changed_paths_are_within_scope PASS
```

Both were the new failures AT-M1-R1 attributed to this defect (F3, F4).

## 9. Regression comparison

Same deterministic selection, run **sequentially** on every tree, never concurrently.

```text
canonical main 2d4da80          30 modules   992 passed,  2 failed, 0 skipped
GOV1 branch (clean, committed)  30 modules   994 passed,  2 failed, 0 skipped
PR #29 head + GOV1 overlay      29 modules   987 passed,  2 failed, 0 skipped
```

```text
Known baseline failures remaining:  2   (unchanged, out of GOV1 scope)
New failures introduced by GOV1:    0
AT-M1-attributable failures:        0   (F3 and F4 are closed by this remediation)
Real regressions:                   0
```

The GOV1 branch shows two more passing tests than the baseline because this stage adds two
registration tests to the ALIGN1 suite.

### Why the compatibility probe runs 29 modules, not 30

`tests/test_step66sync1_codex_frontend_reconciliation.py::test_verifier_passes` fails under the
overlay, and the cause is the probe method rather than this remediation. That verifier's
`assert_allowed_tracked_changes` reads:

```python
tracked = set(git_lines("diff", "--name-only", "HEAD"))
tracked.update(git_lines("diff", "--cached", "--name-only"))
```

It inspects **uncommitted working-tree state**, not commit history. §23 requires the compatibility
overlay to remain uncommitted, so the two repaired ALIGN1 files are necessarily dirty in that
worktree and the guard fires on the dirtiness itself.

The module is therefore excluded from the overlay measurement and verified separately on a clean,
committed tree: it **passes** in the GOV1 branch run above (994 passed / 2 failed), where the same
two files are committed and `git status` is clean. In any real merged state the files are committed,
so this condition cannot arise.

```text
Classification:  PROBE-METHOD ARTIFACT -- not a GOV1 regression, not AT-M1-attributable
Proven by:       reading the guard's source, and by the module passing on the committed GOV1 branch
```

### Known baseline failures — deliberately NOT fixed

```text
tests/test_step66d_align1_rm1_fixed_range_remediation.py::test_66d_decisions_untouched_by_this_remediation
tests/test_step66d_align1_rm1_fixed_range_remediation.py::test_rm1_verifier_passes
```

Both fail identically on canonical main. Their cause is a separate HEAD-relative diff in the
ALIGN1-RM1 verifier's `check23`, tripped by Step 66D-BE1-CR1 adding 66D-D05 to the decision
documents. That is different debt from `GOV-STAGE-FAMILY-ALLOWLIST-01`, it is explicitly out of
GOV1 scope, and no opportunistic repair was attempted.

## 10. Exact changed paths

```text
scripts/verify_step66d_align1_delivery_decision_model.py                          modified
tests/test_step66d_align1_delivery_decision_model.py                              modified
scripts/verify_at_m1_gov1_stage_family_compatibility.py                           added
tests/test_at_m1_gov1_stage_family_compatibility.py                               added
docs/handoffs/autonomous-team/at-m1-gov1-stage-family-compatibility-evidence.md   added

Expected: 5    Actual: 5    Exact equality: YES
```

`docs/handoffs/autonomous-team/` does not exist on canonical main; this branch creates it
independently of PR #29. The two branches add different files to that directory and do not
conflict.

## 11. Quality and scans

```text
ruff              PASS        black --check      PASS
mypy              PASS        git diff --check   CLEAN

REAL_SECRET 0 · REAL_CREDENTIAL 0 · NEW_INTERNAL_IP 0 · NEW_SSH_ALIAS 0
NEW_USERNAME 0 · REAL_LOCAL_ABSOLUTE_PATH 0 · UNKNOWN 0
```

## 12. Safety

```text
AT-M1 architecture paths   UNTOUCHED     AT binding decisions / ADRs   UNTOUCHED
AT capability registry     UNTOUCHED     Canonical precedence registry UNTOUCHED
Canonical milestone manifest UNTOUCHED   source/progress.md            UNCHANGED
PR #29                     UNCHANGED     PR #28                        UNCHANGED
Runtime / migration / frontend / infra   NONE
Shared DB NOT TOUCHED · Deployment NONE · External action NONE · Secret access NONE
production_executed_true_count:  0
```

`ADV-AT-PRECEDENCE-01` is explicitly OUT OF SCOPE here and remains pre-authorized for AT-M1-RM1,
after GOV1 is independently reviewed, merged and canonicalized.

## 13. Status

```text
AT_M1_GOV1:                        PASS
GOV_STAGE_FAMILY_ALLOWLIST_01:     CLOSED
HISTORICAL_TRUTH:                  PRESERVED
AT_FAMILY_COMPATIBILITY:           ESTABLISHED
GOV1_MERGE:                        NOT AUTHORIZED
PR29_MERGE:                        NOT AUTHORIZED
AT_M1_RM1:                         NOT STARTED
AT_M2:                             NOT AUTHORIZED
PRODUCTION_EXECUTED_TRUE_COUNT:    0
```

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
