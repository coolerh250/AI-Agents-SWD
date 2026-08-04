# Step 66SYNC.1-M1 — Canonicalization Manifest

> **Provenance manifest for the canonicalization branch. No runtime, frontend, backend, API,
> database, workflow, deployment, migration, secret, or feature-gate change.
> `production_executed_true_count: 0`.**

```text
CONTEXT_ID:            AIAT-SYNC-20260803-01
Canonical baseline:    main c1db4cc
Branch:                integration/66sync1-canonicalization
Source commits:        Claude Code 828ea90 | Codex 78aa4ee | Claude Design 65c93a1
                       Final reconciliation 2396c6c
RA-2 planning head:    efa396d (unchanged, not imported)
Imported artifacts:    22 unchanged + 5 transformed
New canonical records: 5
```

## Method

No partner branch was merged. Every imported file was extracted from a committed Git object with
`git checkout <commit> -- <path>`, then verified byte-identical by comparing the source blob SHA
against the resulting index blob SHA. The local working directory was never used as a source.
All 26 comparisons returned IDENTICAL at import time; mismatches: 0. Five files were then
transformed for the reasons recorded below, each additively and each re-verified.

## Imported unchanged (22)

| Repository-relative path | Source partner | Source branch | Source commit | Source blob SHA (16) | Canonical destination | Imported unchanged | Reason if transformed |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `docs/alignment/66-project-completion/master/partner-context-snapshot-20260803.md` | Claude Code | `planning/66sync1-claude-code-state-reconciliation` | `828ea90` | `e0dd77d857245996` | same path | YES | -- |
| `docs/handoffs/program-sync/step66sync1-claude-code-acknowledgement.md` | Claude Code | `planning/66sync1-claude-code-state-reconciliation` | `828ea90` | `97157a39d9e3a918` | same path | YES | -- |
| `docs/handoffs/program-sync/step66sync1-context-discrepancy-register.md` | Claude Code | `planning/66sync1-claude-code-state-reconciliation` | `828ea90` | `cdcf1dccffe385bb` | same path | YES | -- |
| `docs/handoffs/program-sync/step66sync1-poc-backend-readiness-matrix.md` | Claude Code | `planning/66sync1-claude-code-state-reconciliation` | `828ea90` | `6fa5d8ec176f2c6e` | same path | YES | -- |
| `docs/test/step66sync1-claude-code-reconciliation-evidence.md` | Claude Code | `planning/66sync1-claude-code-state-reconciliation` | `828ea90` | `d91e35f0f0e888c8` | same path | YES | -- |
| `docs/handoffs/program-sync/step66sync1-codex-acknowledgement.md` | Codex | `planning/66sync1-codex-frontend-reconciliation` | `78aa4ee` | `bbb5acbaf32dcc2f` | same path | YES | -- |
| `docs/handoffs/program-sync/step66sync1-codex-frontend-gap-register.md` | Codex | `planning/66sync1-codex-frontend-reconciliation` | `78aa4ee` | `1651545ed9b05308` | same path | YES | -- |
| `docs/test/step66sync1-codex-frontend-reconciliation-evidence.md` | Codex | `planning/66sync1-codex-frontend-reconciliation` | `78aa4ee` | `90dbc4082a847840` | same path | YES | -- |
| `scripts/verify_step66sync1_codex_frontend_reconciliation.py` | Codex | `planning/66sync1-codex-frontend-reconciliation` | `78aa4ee` | `db0d3ed1c7fbfd4e` | same path | YES | -- |
| `tests/test_step66sync1_codex_frontend_reconciliation.py` | Codex | `planning/66sync1-codex-frontend-reconciliation` | `78aa4ee` | `ba074cda5bea34c9` | same path | YES | -- |
| `docs/design/ai-agent-team-functional-poc-control-center-spec.md` | Claude Design | `planning/66sync1-claude-design-ux-reconciliation` | `65c93a1` | `266f87f59a78c786` | same path | YES | -- |
| `docs/handoffs/program-sync/step66sync1-claude-design-acknowledgement.md` | Claude Design | `planning/66sync1-claude-design-ux-reconciliation` | `65c93a1` | `64f8d7acb6a4deda` | same path | YES | -- |
| `docs/handoffs/program-sync/step66sync1-claude-design-ux-gap-register.md` | Claude Design | `planning/66sync1-claude-design-ux-reconciliation` | `65c93a1` | `0b41fc3d9421fbec` | same path | YES | -- |
| `docs/test/step66sync1-claude-design-reconciliation-evidence.md` | Claude Design | `planning/66sync1-claude-design-ux-reconciliation` | `65c93a1` | `9dc8bfa91cf1df1b` | same path | YES | -- |
| `scripts/verify_step66sync1_claude_design_reconciliation.py` | Claude Design | `planning/66sync1-claude-design-ux-reconciliation` | `65c93a1` | `86bc9ef683e17ad1` | same path | YES | -- |
| `tests/test_step66sync1_claude_design_reconciliation.py` | Claude Design | `planning/66sync1-claude-design-ux-reconciliation` | `65c93a1` | `af54b07c9808b1f4` | same path | YES | -- |
| `docs/alignment/66-project-completion/master/partner-synchronized-program-state-20260803.md` | Claude Code (coordinator) | `planning/66sync1-final-partner-reconciliation` | `2396c6c` | `1f87ae149e7f73b4` | same path | YES | -- |
| `docs/handoffs/program-sync/step66sync1-final-partner-acknowledgement.md` | Claude Code (coordinator) | `planning/66sync1-final-partner-reconciliation` | `2396c6c` | `cfd1919da0093c65` | same path | YES | -- |
| `docs/handoffs/program-sync/step66sync1-final-context-discrepancy-register.md` | Claude Code (coordinator) | `planning/66sync1-final-partner-reconciliation` | `2396c6c` | `3c9fbe9fb25053bd` | same path | YES | -- |
| `docs/handoffs/program-sync/step66sync1-poc-scope-decision-package.md` | Claude Code (coordinator) | `planning/66sync1-final-partner-reconciliation` | `2396c6c` | `6aad54ec215c308a` | same path | YES | -- |
| `docs/handoffs/program-sync/step66sync1-poc0-consolidated-gap-register.md` | Claude Code (coordinator) | `planning/66sync1-final-partner-reconciliation` | `2396c6c` | `7652640045d4572c` | same path | YES | -- |
| `docs/test/step66sync1-final-partner-reconciliation-evidence.md` | Claude Code (coordinator) | `planning/66sync1-final-partner-reconciliation` | `2396c6c` | `b241f68e91515edd` | same path | YES | -- |

All 22 are partner historical evidence and are `Imported unchanged: YES`. No sentence, status line,
count, or classification in any of them was edited. In particular, every occurrence of
`OPEN_PRODUCT_OWNER_DECISIONS: 3` is preserved, because it was true when written. Every partner
acknowledgement, discrepancy register, gap register, decision package, evidence record, design
specification and program-state snapshot is in this group.

## Imported transformed — partner scope-check files (4)

| Repository-relative path | Source partner | Source commit | Source blob SHA (16) | Imported unchanged |
| --- | --- | --- | --- | --- |
| `scripts/verify_step66sync1_claude_code_reconciliation.py` | Claude Code | `828ea90` | `8d81e70206b46f03` | NO |
| `tests/test_step66sync1_claude_code_reconciliation.py` | Claude Code | `828ea90` | `d47fa70a7be1e093` | NO |
| `scripts/verify_step66sync1_final_partner_reconciliation.py` | Claude Code (coordinator) | `2396c6c` | `2e1a96bf7d726a00` | NO |
| `tests/test_step66sync1_final_partner_reconciliation.py` | Claude Code (coordinator) | `2396c6c` | `cd69dac1ff398f46` | NO |

```text
Reason if transformed:
  These four files carry a branch-scoped ALLOWED_PREFIXES tuple asserting that the only paths
  changed relative to c1db4cc are that one partner's own slice. On a canonicalization branch that
  assertion is false by construction and by authorization, because the branch legitimately carries
  all four partners' artifacts. Left unchanged they fail here and would keep failing on main after
  any merge -- an artifact of per-branch scoping, not evidence of a scope violation.

Transformation applied:
  Three entries added to each ALLOWED_PREFIXES tuple, with an explanatory comment:
      "docs/design/"
      "scripts/verify_step66sync1_"
      "tests/test_step66sync1_"

Bounds of the transformation:
  +6 lines, -0 lines per file (3 comment lines + 3 entries), verified by git numstat.
  No runtime prefix was admitted: apps/, agents/, shared/, services/, migrations/ and infra/
  remain rejected by all four files, and every substantive check in them is untouched.
  Both bounds are asserted by the Step 66SYNC.1-M1 verifier (check09) and by two dedicated tests.

Not transformed:
  The Codex and Claude Design verifiers and tests needed no change and are byte-identical. The
  Codex scope check is working-tree-based and passes unmodified once the canonicalization commit
  exists.
```

## Imported transformed — program record (1)

```text
Repository-relative path:  source/progress.md
Source partner:            Claude Code (Step 66SYNC.1-A / A1) and
                           Claude Code coordinator (Step 66SYNC.1-D)
Source branches:           planning/66sync1-claude-code-state-reconciliation
                           planning/66sync1-final-partner-reconciliation
Source commits:            828ea90 and 2396c6c
Source blob SHAs:          main  bfe66eef90ca82a5057e63963999c02e642af8b6  (1,111,698 bytes)
                           828ea90 363ccb2d988b4e210796815ecd556dd085e5e92e (1,120,920 bytes)
                           2396c6c 9577657034d591ed7069b6b63e541b3e1e45eb1e (1,116,581 bytes)
Canonical destination:     source/progress.md
Imported unchanged:        NO
Reason if transformed:     Both partner commits append a distinct section to the same file. Each
                           was byte-verified to be a pure append: bytes 0..1,111,697 of each
                           partner blob are identical to the canonical main blob. The canonical
                           file is main's content, followed by the 828ea90 append block
                           (66SYNC.1-A + 66SYNC.1-A1), followed by the 2396c6c append block
                           (66SYNC.1-D), followed by this stage's own 66SYNC.1-M1 section. No
                           existing line was edited, reordered, or deleted; `git diff origin/main`
                           reports 0 deleted lines.
```

## New canonical records (5)

These are not imports. They originate in the Product Owner's binding authorization for Step
66SYNC.1-M1 and in this stage's own verification work.

| Repository-relative path | Source | Imported unchanged | Note |
| --- | --- | --- | --- |
| `docs/handoffs/program-sync/step66sync1-poc-scope-binding-decisions.md` | Product Owner binding authorization in the Step 66SYNC.1-M1 prompt | N/A — new canonical record | Tier 1 source of truth |
| `docs/alignment/66-project-completion/master/partner-synchronized-program-state-20260804.md` | Product Owner binding authorization in the Step 66SYNC.1-M1 prompt | N/A — new canonical record | Append-only addendum to the 2026-08-03 snapshot |
| `docs/alignment/66-project-completion/master/canonical-source-of-truth-precedence.md` | Step 66SYNC.1-M1 | N/A — new canonical record | Precedence index |
| `docs/handoffs/program-sync/step66sync1-canonicalization-manifest.md` | Step 66SYNC.1-M1 | N/A — new canonical record | This document |
| `docs/test/step66sync1-m1-canonicalization-evidence.md` | Step 66SYNC.1-M1 | N/A — new canonical record | Verification evidence |

Plus the stage verifier and its tests:

```text
scripts/verify_step66sync1_m1_canonicalization.py   new, this stage
tests/test_step66sync1_m1_canonicalization.py       new, this stage
```

## Deliberately not imported

```text
.tools/                                                   Codex local untracked; absent from
                                                          commit 78aa4ee. Not imported.
docs/product/platform-progress-admin-console-proposal.md  Codex local untracked; absent from
                                                          commit 78aa4ee. Not imported.
Anything from Claude Code commit 1b86182                   Superseded by 828ea90 (Step 66SYNC.1-A1).
                                                          Only the 828ea90 versions were imported;
                                                          no superseded version is present.
Anything from planning/66c4-be3-ra2-identity-secret-       RA-2 remains a separate, unmerged
  decision (efa396d)                                       planning branch. Nothing imported; its
                                                          head is unchanged.
```

Presence of the two Codex untracked paths in commit `78aa4ee` was checked directly against the
commit tree; neither exists there, so both were excluded as required.

## Verification

```text
Blob-identity comparisons at import:   26 of 26 IDENTICAL, 0 mismatches
Files still byte-identical:            22
Files additively transformed:          5 (4 scope-check files, +6/-0 each; source/progress.md)
Lines deleted by any transformation:   0
Branch base:                    integration/66sync1-canonicalization cut from c1db4cc
Partner branches modified:      none
Marker:                         STEP66SYNC1_M1_CANONICALIZATION_PREP_VERIFY: PASS
```

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
