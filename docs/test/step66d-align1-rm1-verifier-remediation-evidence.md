# Step 66D-ALIGN1-RM1 — Fixed-range Verifier Integrity Remediation Evidence

> **Verification-framework remediation only. No product decision changed. No contract frozen. No
> runtime, frontend, backend, API, database, event, migration, deployment, identity, secret or
> feature-gate change. No container, database, Redis, Kubernetes, Vault, OIDC provider, agent
> workflow or external provider started. `production_executed_true_count: 0`.**

```text
Canonical baseline:  main 64467fe
Original ALIGN1:     f25d12b   (preserved, never amended, rebased or squashed)
Branch:              planning/66d-align-delivery-decision-model
Marker:              STEP66D_ALIGN1_RM1_FIXED_RANGE_REMEDIATION_VERIFY: PASS
MERGE AUTHORIZATION: NOT GRANTED
```

## 1. Source findings

Step 66D-ALIGN1-R1, an independent review session, found that the repair shipped in `f25d12b`
fixed the *symptom* rather than the *range*. It made six stage gates accept more, instead of making
them evaluate a correct, frozen scope. Its probe results at `f25d12b`, reproduced again in this
session before any change was made:

```text
docs/review-probes/unrelated-governance-probe.md        ACCEPTED by all 7 verifiers
scripts/verify_step66_unrelated_probe.py                ACCEPTED by all 7 verifiers
tests/test_step66_unrelated_probe.py                    ACCEPTED by all 7 verifiers
apps/review_probe/unauthorized_runtime_change.txt       REJECTED by all 7 verifiers
```

R1 also independently reproduced the main regression (488 collected, 479 passed, **9 failed**,
0 skipped at `64467fe`) and the PR-head result (**553 passed**, 0 failed, 0 skipped at `f25d12b`),
and confirmed no genuine artifact drift was hidden underneath the 9 failures.

## 2. Findings closed

```text
R1-F01  generic "docs/" allowlist admitted any unregistered document          REMEDIATED
R1-F02  generic "scripts/verify_step66" prefix admitted any unregistered      REMEDIATED
        verifier
R1-F03  generic "tests/test_step66" prefix admitted any unregistered test     REMEDIATED
R1-F04  fixed record-boundary SHAs had no anti-reset protection               REMEDIATED
R1-F05  record inaccuracies: 11 vs 12 cross-stage files, 552 vs 553 tests     REMEDIATED
```

## 3. Exact 12-file cross-stage inventory

The previous records said **11**. The correct figure is **12** — six verifiers and six tests. The
omitted entry is marked; it was missing from the ALIGN1 evidence, the progress entry, the `f25d12b`
commit message and the original PR body.

```text
scripts/verify_step66sync1_claude_code_reconciliation.py
tests/test_step66sync1_claude_code_reconciliation.py
scripts/verify_step66sync1_final_partner_reconciliation.py
tests/test_step66sync1_final_partner_reconciliation.py
scripts/verify_step66sync1_m1_canonicalization.py
tests/test_step66sync1_m1_canonicalization.py
scripts/verify_step66sync1_m2_canonical_merge.py
tests/test_step66sync1_m2_canonical_merge.py
scripts/verify_step66c4_be3_ra2m_canonicalization.py
tests/test_step66c4_be3_ra2m_canonicalization.py
scripts/verify_step66c4_be3_ra2m2_canonical_merge.py
tests/test_step66c4_be3_ra2m2_canonical_merge.py     <- PREVIOUSLY OMITTED (+8 / -2)
```

## 4. Before and after semantics

```text
BEFORE (f25d12b)                              AFTER (this remediation)
------------------------------------------    ------------------------------------------
claude_code    c1db4cc -> HEAD    drifting     c1db4cc -> 828ea90    frozen
final_partner  c1db4cc -> HEAD    drifting     c1db4cc -> 2396c6c    frozen
m1             c1db4cc -> HEAD    drifting     c1db4cc -> 1278b89    frozen
m2             7971ae0 -> HEAD    drifting     7971ae0 -> 44ab32c    frozen
ra2m           44ab32c -> worktree drifting    44ab32c -> edafc0c    frozen
ra2m2          aa02ad5 -> HEAD    drifting     aa02ad5 -> 64467fe    frozen
align1         denylist only, no positive      64467fe -> branch, EXACT-SET equality
               stage scope at all              against a registered 34-path set

Acceptance rule  startswith(prefix tuple)      set(actual) == set(registered)
```

Under a frozen range, a file committed later is not in the range at all, so a historical stage gate
can no longer be *satisfied* by it — and it can no longer be *broken* by it either, which is what
produced the 9 main failures. Under exact-set equality, an unregistered path fails and a registered
path that disappears also fails. Both halves of R1-F01..F03 are closed.

## 5. Fixed boundary matrix

Full SHAs, sources and expected path counts are recorded in
`docs/handoffs/66d-delivery-acceptance/step66d-align1-rm1-stage-boundary-manifest.md`. Every SHA
was confirmed present in canonical main history and traceable to a committed artifact (the
Step 66SYNC.1 canonicalization manifest, the M2 and RA-2M2 merge records, or the pre-existing
verifier constants). No SHA was guessed.

```text
step66sync1-claude-code-reconciliation      c1db4cc..828ea90     8 paths
step66sync1-final-partner-reconciliation    c1db4cc..2396c6c     9 paths
step66sync1-m1-canonicalization             c1db4cc..1278b89    34 paths
step66sync1-m2-canonical-merge              7971ae0..44ab32c     6 paths
step66c4-be3-ra2m-canonicalization          44ab32c..edafc0c    16 paths
step66c4-be3-ra2m2-canonical-merge          aa02ad5..64467fe     6 paths
step66d-align1                              64467fe..branch     34 paths (open-PR exact set)
```

## 6. Generic prefixes removed

```text
"docs/",                    removed from all 12 files      0 remaining
"scripts/verify_step66",    removed from all 12 files      0 remaining
"tests/test_step66",        removed from all 12 files      0 remaining
Equivalent broad globs substituted:                        0 (test-enforced)
```

The Step 66SYNC.1-M1 `TRANSFORMED` gate, which previously *required* those three entries to be
present in the four partner scope files, now requires the opposite: a fixed boundary must be
present and the generic prefixes must be absent. The defect cannot be reintroduced without failing
that gate.

## 7. Boundary-reset protection (R1-F04)

```text
Every boundary is a literal 40-character SHA                        test-enforced
No boundary resolves via HEAD, origin/, refs/, rev-parse, ORIG_HEAD test-enforced
No boundary is overridable from the environment                     test-enforced
Every constant is also recorded in the boundary manifest            test-enforced
Manifest records boundary_authority, sha_source, update_rule and
forbidden_endpoints                                                 test-enforced
```

Moving a boundary now requires editing the verifier constant **and** the manifest; changing either
alone fails verification.

## 8. Negative tests added

Each probe was committed into a disposable local worktree and every verifier was re-run.

```text
A  unregistered documentation path          REJECTED  (ALIGN1 + RM1 exact-set gates)
B  unregistered verify_step66* path         REJECTED  (ALIGN1 + RM1 exact-set gates)
C  unregistered test_step66* path           REJECTED  (ALIGN1 + RM1 exact-set gates)
D  runtime path                             REJECTED  by all 8 verifiers
E  STAGE_HEAD replaced with "HEAD"          REJECTED  (M1 + RM1)
E2 STAGE_HEAD moved to another real commit  REJECTED  (M1 + RM1)
F  pre-marker word edited                   REJECTED  (M1 + ALIGN1 + RM1)
G  pre-marker line deleted                  REJECTED  (M1 + ALIGN1 + RM1)
G2 OPEN_PRODUCT_OWNER_DECISIONS 3 -> 0      REJECTED  (M1 + ALIGN1 + RM1)
H  legitimate append below the marker       ACCEPTED  by all 8 verifiers
```

For A, B and C the six historical gates report PASS because the probe path lies **outside their
frozen range** — they no longer evaluate it at all, which is the point of freezing. Rejection is
performed by the two gates that do evaluate the current branch. For H, an earlier run showed the
RM1 gate rejecting; that was `check03` counting the probe's own extra commit, not the annotation.
Re-run as a working-tree change, H is accepted by all eight.

Tests exercise the real decision logic: `check33` is called with mutated path sets and must record
a failure; registered path sets are re-derived from Git and compared to the range; boundaries are
parsed out of source. No test asserts merely that a verifier printed `PASS`.

## 8b. A regression this stage introduced and then fixed

Freezing the six stage ranges initially **broke the runtime denylist** in those six verifiers.
Their protected-path loops consumed the same path list as the scope check, so once that list became
the frozen range, a runtime file added by any later commit was invisible to them. The mandatory
post-change mutation recheck caught it: probe D was accepted by all six historical verifiers, where
before the remediation it had been rejected by all seven.

```text
Fix:  a separate RUNTIME_GUARD_ANCHOR in each of the 12 files, scanning
      <that stage's baseline>..HEAD -- deliberately HEAD-relative, feeding the
      denylist only. It can reject; it can never admit or widen the stage scope.
Now:  probe D is REJECTED by all 8 verifiers, and the guard covers more than before --
      services/ and frontend/compose/Helm/Kubernetes extensions are named explicitly.
```

`check06` permits exactly this one HEAD reference and still fails any other; `check06b` requires the
guard to be present in all twelve files and to scan up to current HEAD. Both are test-enforced. The
defect existed only within this session and never reached a pushed commit, but it is recorded here
because it is precisely the class of weakening this remediation exists to prevent.

## 9. Runtime denylist unchanged

```text
apps/  agents/  services/  shared/  migrations/  infra/     still rejected by all 12 files
frontend runtime source, Docker Compose, Kubernetes, Helm    still rejected
Vault, OIDC, feature-gate defaults, secret configuration     untouched
Protected prefixes removed or relaxed by this stage:         0
```

Fixed-range scope is an addition, not a replacement: both controls are present in every stage
verifier.

## 10. Historical provenance unchanged

The Step 66SYNC.1-M1 append-only guard — byte-exact preserved prefix, zero deletions above the
marker, historical wording preserved, post-decision wording excluded from the preserved portion,
legitimate later annotation permitted — is intact and independently re-tested here. R1 confirmed it
rejects all four tampering probes and accepts a legitimate append; this remediation did not touch
it.

## 11. Accuracy corrections (R1-F05)

```text
Cross-stage files   previously recorded 11   correct 12   (6 verifiers + 6 tests)
Omitted path        tests/test_step66c4_be3_ra2m2_canonical_merge.py
Stage-family tests  previously recorded 552  correct 553  (verified at f25d12b)
```

Corrections appear in this record, in the ALIGN1 alignment evidence (with the original erroneous
values left visible and labelled, not overwritten), in `source/progress.md` and in the PR body.
The `f25d12b` commit message still contains 552 and the 11-file list: **history is not rewritten**,
and no rebase, amend, squash or force-push was performed.

## 12. Commands and results

```bash
python scripts/verify_step66d_align1_rm1_fixed_range_remediation.py
python -m pytest -q tests/test_step66d_align1_rm1_fixed_range_remediation.py
python -m pytest -q <the ten stage suites plus the RM1 suite>
```

```text
STEP66D_ALIGN1_RM1_FIXED_RANGE_REMEDIATION_VERIFY: PASS   (27 numbered checks)
All seven pre-existing stage verifier markers:            PASS
RM1 suite:                                                193 passed
Step 66D-ALIGN1 suite:                                     62 passed
Ten pre-existing stage suites:                            560 passed
Eleven suites combined:                                   753 passed, 0 failed, 0 skipped
```

The ten pre-existing suites were **553** at `f25d12b` and are **560** here: the Step 66SYNC.1-M1
suite gained one net test (two `TRANSFORMED` tests replaced by three), and each of the six
cross-stage test files gained a runtime-guard test. No test was deleted without a stricter
replacement.

All counts above were measured by execution after the remediation commit, not carried over from a
plan. One test — the Codex partner verifier's `test_verifier_passes` — is working-tree-based and
fails while changes are uncommitted; it passes once committed, which is the state recorded here.

## 13. Scope, secret and path scans

```text
Total changed paths vs 64467fe:  34
  docs/alignment                  5
  docs/contracts                  2
  docs/design                     1
  docs/handoffs                   7
  docs/test                       2
  scripts/verify_step66*.py       8
  tests/test_step66*.py           8
  source/progress.md              1 (append-only)

apps/ agents/ services/ shared/ migrations/ infra/        0 paths
frontend source, .yaml/.yml, compose/Helm/Kubernetes      0 paths
legacy DeliveryPackage source                             0 paths
66D-D01..D04 binding record, terminology registry,
supersession matrix                                       0 changes (test-enforced)

git diff --check:          clean
ruff / black / mypy:       clean
SECRET_SCAN:               CLEAN
LOCAL_ABSOLUTE_PATH_SCAN:  CLEAN
Working tree after commit: clean
```

## 14. Status

```text
STEP66D_ALIGN1_RM1:              PASS
R1_F01 / F02 / F03 / F04 / F05:  REMEDIATED
PR24:                            OPEN / UPDATED / NOT MERGED
PR24_MERGE_READINESS:            PENDING INDEPENDENT R2 CLOSURE REVIEW
STEP66D_ARCH1:                   NOT AUTHORIZED
STEP66D_DESIGN:                  NOT AUTHORIZED
STEP66D implementation:          NOT AUTHORIZED
STEP67POC0:                      NOT AUTHORIZED
RA2I0:                           NOT AUTHORIZED
BE3 resume/replay:               DISABLED, all four gates default false
PRODUCTION_EXECUTED_TRUE_COUNT:  0
```

This stage changed verification machinery and records only. No product decision, no contract, no
schema, no API and no user-visible behaviour was altered. Passing this gate is a process marker, not
an independent judgement that the framework is now correct — that is what the Step 66D-ALIGN1-R2
closure review is for.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
