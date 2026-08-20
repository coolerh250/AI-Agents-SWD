# AT-D12 — historical freeze versus authorized successor evolution

> **Product Owner decision record. Resolves a structural conflict between two correct
> governance rules. Authorizes no production action, no external action, no new milestone and
> no scope change. `production_executed_true_count: 0`.**

```text
AT-D12:                      RESOLVED / BINDING
Recorded_on:                 2026-08-20
Recorded_by:                 Product Owner
Canonical_main_at_decision:  192ebb74ba600f7a53ddf5967a7254a1f7a72fb8
Supersedes:                  nothing
Depends_on:                  AT-D11 (docs/decisions/at-m2-authorization.md)
```

## 1. The conflict

Two rules in this repository are each correct on their own and cannot both be satisfied
literally once an implementation milestone is authorized.

```text
Rule A  A completed stage's evidence is frozen byte-for-byte to its source commit, so that
        nobody can retroactively rewrite what a stage actually decided or measured.

Rule B  A live guard must scan CURRENT state, and a live inventory must describe CURRENT
        source. A guard frozen to a historical range stops guarding; an inventory frozen to a
        historical route list stops being true.
```

Three artifacts are, at the same time, historical evidence under Rule A **and** live
machinery under Rule B. AT-M2 is the first authorized milestone to add implementation and
routes after those stages closed, so it is the first to make the conflict observable.

```text
scripts/verify_step66c4_be3_ra2_identity_secret_decision.py   frozen AND a live guard
tests/test_step66c4_be3_ra2_identity_secret_decision.py       frozen AND a live guard
docs/test/step66sync1-codex-frontend-reconciliation-evidence.md
                                                              frozen AND a live route inventory
```

Neither side can yield by itself. Leaving them frozen makes the guards assert a range that
excludes an authorized milestone's own commits and makes the inventory misdescribe the running
application. Editing them freely dissolves Rule A for every stage at once.

## 2. Binding rule

```text
AT-D12-R01  Historical freeze contracts remain in force over original stage evidence.

AT-D12-R02  A freeze contract may not prevent an explicitly authorized successor milestone
            from maintaining a live governance, control or inventory artifact.

AT-D12-R03  A freeze assertion may be amended ONLY narrowly, and the amendment must:
              (a) rewrite no historical evidence;
              (b) be gated on explicit, fail-closed successor authorization;
              (c) leave every unrelated assertion unchanged;
              (d) keep the live guard or inventory truthful about current state;
              (e) weaken no production, security or authorization boundary.

AT-D12-R04  Amendment is permitted only for artifacts NAMED in this record. An artifact not
            named here stays absolutely frozen, with no exception path.

AT-D12-R05  With no authorized successor, ANY divergence from the historical blob is a
            failure. Absence of authorization is not absence of a rule.
```

## 3. Named amendable artifacts

This is the exhaustive list. It is read by `scripts/successor_lifecycle.py` and is the only
place the amendable set is defined.

```text
AT_D12_SUCCESSOR_MILESTONE: AT-M2

AMENDABLE_FROZEN_ARTIFACT: declared-line scripts/verify_step66c4_be3_ra2_identity_secret_decision.py
AMENDABLE_FROZEN_ARTIFACT: declared-line tests/test_step66c4_be3_ra2_identity_secret_decision.py
AMENDABLE_FROZEN_ARTIFACT: appended-note docs/test/step66sync1-codex-frontend-reconciliation-evidence.md
```

Three artifacts. No other frozen artifact of any stage becomes amendable by this decision, and
the six RA-2 historical decision documents in particular remain absolutely frozen.

## 4. The two permitted amendment shapes

Both shapes exist so that the amendment is visible in the artifact itself, not only in a diff.

### `declared-line` — for executable guards

Every line that differs from the historical blob must carry the marker `# AT-D12-AMENDED`.
A historical line may be replaced by a marked line; it may not simply be deleted. The
historical blob stays retrievable from its source commit, and the amendment is legible in place
without consulting git.

### `appended-note` — for evidence documents

The historical content must remain a **byte-exact prefix** of the current file. Everything the
successor adds goes after the marker `<!-- SUCCESSOR-NOTE-BEGIN: AT-D12 -->`, and the amendment
must delete zero lines. This is the same shape Step 66D-ALIGN1 already used for its supersession
notes, and it is stricter than "not rewritten": the original portion is proved byte-identical.

## 5. What this decision does NOT do

```text
Does NOT authorize AT-M3 .. AT-M8            -- each still needs its own decision
Does NOT change AT-M2 scope                  -- AT-D11 remains the scope authority
Does NOT reclassify or retire governance debt
Does NOT register any failure as historical debt
Does NOT grant production authorization      -- NOT GRANTED, unchanged
Does NOT relax TASK_ROLES, RBAC, policy or approval
Does NOT permit a third validation round for any capability
Does NOT amend any freeze assertion beyond the three artifacts in section 3
```

## 6. Fail-closed properties this decision requires

An implementation of AT-D12 must reject an amendment when any of these does not hold, and the
verifiers and tests must check them mechanically rather than by prose:

```text
1. this record exists and reads AT-D12: RESOLVED / BINDING
2. the canonical PM snapshot names this record as the freeze-amendment authority
3. a successor implementation milestone is authorized under AT-D11's lifecycle mechanism
4. the milestone named here matches the authorized successor milestone
5. the amended path is named in section 3
6. the amendment matches its declared shape exactly
```

Remove any one of them and the frozen artifact must be rejected as rewritten.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
