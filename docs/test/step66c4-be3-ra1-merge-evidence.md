# Step 66C.4-BE3-RA-1M — RA-1 Merge Verification Evidence

> **Test/verification record for the controlled merge of Draft PR #21 into canonical main. NOT a
> shared-migration, deployment, or runtime-activation record — this stage is source-control only.**

## Marker

```text
STEP66C4_BE3_RA1_MERGE_VERIFY: PASS
```

## Preflight (executed before any merge action)

```text
git fetch origin --prune                                          -> OK
git status --porcelain=v1 --untracked-files=all                   -> empty (clean, no untracked)
origin/main                     18f11fe5ff02ed3cc0def7a448da1c7f5c3e257e -> starts with 18f11fe: OK
origin/feature/...-rehearsal    97e56d47c8617cac5082c7f3bb00a7a4eea9cb8e -> starts with 97e56d4: OK
origin/review/...-rollback      1f3a66f4beda4b6e961169747b5a6c5385cad757 -> starts with 1f3a66f: OK
```

## PR #21 pre-merge validation

```text
gh pr view 21 --json number,state,isDraft,baseRefName,headRefName,headRefOid,mergeable,mergedAt,mergeCommit
-> number=21, state=OPEN, isDraft=true, baseRefName=main,
   headRefName=feature/66c4-be3-ra1-migration-rehearsal,
   headRefOid=97e56d47c8617cac5082c7f3bb00a7a4eea9cb8e (exact match to approved feature head),
   mergeable=MERGEABLE, mergedAt=null
```

## Evidence preservation checks

```text
git cat-file -e 352d546^{commit}   -> exists
git cat-file -e 9cd841f^{commit}   -> exists
git cat-file -e 800035b^{commit}   -> exists
git cat-file -e 1f3a66f^{commit}   -> exists
git merge-base --is-ancestor 1f3a66f origin/main   -> NOT an ancestor (before merge)
git merge-base --is-ancestor 19cff82 origin/main   -> NOT an ancestor
git merge-base --is-ancestor 07f839f origin/main   -> NOT an ancestor
git merge-base --is-ancestor 7c6b830 origin/main   -> NOT an ancestor
```

## Pre-merge safety verification

```text
BE3_RESUME_API_ENABLED        -> os.environ.get(..., "false") at 97e56d4: default false
BE3_RESUME_COMMAND_ENABLED    -> os.environ.get(..., "false") at 97e56d4: default false
BE3_REPLAY_API_ENABLED        -> os.environ.get(..., "false") at 97e56d4: default false
BE3_REPLAY_EXECUTION_ENABLED  -> os.environ.get(..., "false") at 97e56d4: default false
production_executed_true_count recorded as 0 throughout source/progress.md history
No shared DB migration execution, deployment, or runtime worker/relay/consumer activation recorded
  or attempted at any point in this stage.
```

## Ready + immediate re-lock

```text
gh pr ready 21                     -> "Pull request coolerh250/AI-Agents-SWD#21 is marked as
                                        ready for review"
HEAD_OID (post-ready)              -> 97e56d47c8617cac5082c7f3bb00a7a4eea9cb8e (== approved feature head)
CURRENT_MAIN_OID (post-ready)      -> 18f11fe5ff02ed3cc0def7a448da1c7f5c3e257e (== pre-merge main, unchanged)
```

## Authorized merge

```text
gh pr merge 21 --merge --match-head-commit 97e56d47c8617cac5082c7f3bb00a7a4eea9cb8e
-> no error; PR #21 state immediately re-queried: MERGED (not pending auto-merge)
   mergeCommit.oid = 48004e3edd78aa3786c3808e1b09a734fd5adb69
```

## Post-merge verification

```text
git fetch origin --prune
PR_STATE           = MERGED
MERGE_OID           = 48004e3edd78aa3786c3808e1b09a734fd5adb69
POST_MERGE_MAIN     = 48004e3edd78aa3786c3808e1b09a734fd5adb69  (MERGE_OID == POST_MERGE_MAIN: OK)

git show --no-patch --format='%H%n%P' 48004e3
-> 48004e3edd78aa3786c3808e1b09a734fd5adb69
   18f11fe5ff02ed3cc0def7a448da1c7f5c3e257e 97e56d47c8617cac5082c7f3bb00a7a4eea9cb8e
-> exactly two parents, correct order (parent 1 = pre-merge main, parent 2 = approved feature head)
```

## Main ancestry verification (post-merge)

```text
git merge-base --is-ancestor 97e56d4 origin/main   -> true  (approved feature head IS a main ancestor)
git merge-base --is-ancestor 1f3a66f origin/main   -> false (review branch head is NOT a main ancestor)
352d546 / 9cd841f / 800035b / 1f3a66f: all reachable from origin/review/66c4-be3-ra1-migration-rollback,
  none reachable from origin/main
```

## Quality / integrity gates on this stage's own new files

```text
ruff check (verify_step66c4_be3_ra1_merge.py, test_step66c4_be3_ra1_merge.py):  PASS
black --check (same files):                                                     PASS
mypy (same files):                                                               PASS
git diff --check:                                                                PASS
Secret / internal-identifier scan of committed files:                           PASS (neutral
  labels only; no internal IP, SSH alias, or username)
```

## Final local-vs-remote check

```text
git checkout main && git pull --ff-only origin main
LOCAL_MAIN  == REMOTE_MAIN                     -> OK (both 48004e3, after the source-of-truth commit
                                                       both advance together)
git status --porcelain=v1 --untracked-files=all -> empty (clean, no untracked)
scripts/verify_step66c4_be3_ra1_merge.py        -> PASS
pytest -q tests/test_step66c4_be3_ra1_merge.py  -> all passed, 0 failed, 0 skipped
```

## Posture

```text
PR #21:                 MERGED (merge commit 48004e3, two parents, correct order)
Review branch:           preserved at 1f3a66f, unmerged, not a main ancestor
RA-1 findings:           H-1/M-1/M-2A/M-2B/M-3A/M-3B all CLOSED (final verdict RA1_TECHNICAL_VERDICT: PASS)
Shared migration:        NOT APPLIED | Deployment: NONE | Runtime validation: NONE | Activation: NONE
Feature gates:           unchanged, default false | Worker/relay/consumer: none started
production_executed_true_count: 0
Gates 1/2/6:             PENDING RUNTIME/SHARED EXECUTION
RA-2:                    NOT AUTHORIZED
```

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=true image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
