# Post-Merge Verification Plan — Step 66M0-SOT-RECONCILE-P v2

> **Planning document only. This checklist is for a FUTURE execution stage to run after the merge
> plan in `recommended-merge-plan.md` is authorized and executed. No verification described here is
> run by this stage — this stage performs no merge.**

## Verifier / test re-runs (after each of the three merges completes)

```text
python scripts/verify_design66ui4_fe1d_navigation_microcopy.py    -> expect PASS
pytest tests/test_design66ui4_fe1d_navigation_microcopy.py         -> expect 7 passed
python scripts/verify_step66ui4_fe1d_technical_readiness.py       -> expect PASS
pytest tests/test_step66ui4_fe1d_technical_readiness.py            -> expect 21 passed
python scripts/verify_step66ui4_fe1d_boundary.py                  -> expect PASS
pytest tests/test_step66ui4_fe1d_boundary.py                       -> expect 17 passed
```

## Consolidated-artifact presence check

```text
All 11 + 5 + 10 = ~26 files listed in recommended-merge-plan.md §3 exist at their documented repo-
relative paths on main after all three merges. A future stage should perform an explicit file-
existence loop (the pattern used in every prior -MD stage in this project), not just trust the
three individual verifiers above.
```

## Annotation presence check

```text
grep for the three annotation strings specified in recommended-merge-plan.md §5, confirming each
appears in its target file exactly once, without altering any other existing content in that file
(a diff-based check: only the annotation lines should appear as additions in that specific file's
post-merge diff versus its pre-merge state).
```

## Progress-log integrity check

```text
grep -n "^## Stage 66UI.4-FE.1D" source/progress.md (and the DESIGN/TECH-REVIEW/BOUNDARY-specific
variants) after all three merges, confirming each stage section appears exactly once and in the
correct chronological position relative to the already-merged FE.1D-S1 sections.
```

## Decision-preservation re-check

```text
Re-run the same 11-item cross-branch decision verification from conflict-analysis.md §2 against
the POST-merge main, confirming every item still reads CONSISTENT (in particular items 2/3/4/6/7/
8/9/10/11, which must not change; item 5 "FE.1D-S1 recorded complete" should now ALSO be reflected
inside the merged boundary-branch text itself, closing the one documentation lag this reconciliation
stage identified).
```

## Scope / safety re-check

```text
git diff --name-only <pre-merge-main>...<post-merge-main> -- apps/ services/ infra/ migrations/
  database/ .github/workflows/   -> expect EMPTY (zero runtime/infra files touched by this
  documentation-only consolidation).
git diff --check    -> expect clean
git status --short  -> expect clean
Secret scan          -> expect critical=0, high=0, informational=100 (unchanged baseline; this
  consolidation introduces no new secret-scan findings, since it merges already-scanned-clean
  content).
```

## Test-runtime re-check

```text
NOT REQUIRED per recommended-merge-plan.md §11 (zero runtime file impact) -- but a future executing
stage should still perform a single confirmatory check (Admin Console HTTP 200,
production_executed_true_count still 0) purely as a "nothing unexpectedly broke" sanity check, not
because this consolidation could plausibly have changed runtime behavior.
```

## FE.1D Slice 2 authorization re-check (must remain false)

```text
After this merge plan executes, FE.1D Slice 2 MUST STILL read as unauthorized everywhere --
confirm no annotation added during this consolidation accidentally reads as an authorization
(the exact annotation wording in recommended-merge-plan.md §5 was deliberately worded to avoid
this: "still requires a separate, explicit Product Owner authorization").
```

## Statement

Planning document only. No verification described here is executed by this stage.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._
