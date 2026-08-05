# Step 66D-ALIGN1-RM1 — Stage Boundary Manifest

> **Immutable boundary record for cross-stage scope verification. Governance artifact only. No
> runtime, frontend, backend, API, database, migration, deployment, identity or secret change.
> `production_executed_true_count: 0`.**

Each historical stage below is verified over a **frozen commit range**. No entry may resolve to
`HEAD`, to a branch tip, or to the working tree. The verifier constants and the entries here are
cross-checked against each other by
`scripts/verify_step66d_align1_rm1_fixed_range_remediation.py`; a mismatch fails the gate.

## Why this exists

Step 66D-ALIGN1-R1 established that every historical stage verifier compared its baseline to
*current HEAD* — a range that grows with every later commit — and that Step 66D-ALIGN1 had made
that range passable by admitting the generic prefixes `docs/`, `scripts/verify_step66` and
`tests/test_step66`. Three independent mutation probes (an unregistered document, an unregistered
`verify_step66*` script, an unregistered `test_step66*` test) were accepted by all seven verifiers.
A frozen range plus an exact registered path set removes both halves of that defect: the range
cannot drift, and nothing passes on the strength of a prefix.

## Boundary authority

```text
boundary_authority:     Product Owner, Step 66D-ALIGN1-RM1 authorization
sha_source:             Git ancestry plus committed stage artifacts
                        (Step 66SYNC.1 canonicalization manifest, merge records,
                         pre-existing verifier constants)
update_rule:            a boundary value may change only when an authorized stage records a new
                        immutable boundary here AND in the verifier constant; changing one alone
                        fails verification
forbidden_endpoints:    HEAD, ORIG_HEAD, branch tips, tags, working tree, environment overrides
```

## Stages

### Step66SYNC.1 Claude Code reconciliation

```text
stage_id:                   step66sync1-claude-code-reconciliation
baseline_commit:            c1db4ccbfd88fa775e4761c932835896b9b980ed
exact_stage_head:           828ea900d53edab6f8441f50723e52955a1049e1
record_commit:              n/a (partner reconciliation branch, no separate record commit)
verification_range:         c1db4cc..828ea90  (frozen)
scope_source:               EXPECTED_STAGE_PATHS in the stage verifier and test
expected_paths_source:      git diff --name-only c1db4cc 828ea90
expected_path_count:        8
```

### Step66SYNC.1 Final Partner reconciliation

```text
stage_id:                   step66sync1-final-partner-reconciliation
baseline_commit:            c1db4ccbfd88fa775e4761c932835896b9b980ed
exact_stage_head:           2396c6c7002387c886463bd38158b9ddc3bfb9e2
record_commit:              n/a
verification_range:         c1db4cc..2396c6c  (frozen)
scope_source:               EXPECTED_STAGE_PATHS in the stage verifier and test
expected_paths_source:      git diff --name-only c1db4cc 2396c6c
expected_path_count:        9
```

### Step66SYNC.1-M1 canonicalization preparation

```text
stage_id:                   step66sync1-m1-canonicalization
baseline_commit:            c1db4ccbfd88fa775e4761c932835896b9b980ed
exact_stage_head:           1278b8944e3a8f824a9b35f82382fa8587e7989d
record_commit:              n/a (preparation stage; merge recorded by M2)
verification_range:         c1db4cc..1278b89  (frozen)
scope_source:               EXPECTED_STAGE_PATHS in the stage verifier and test
expected_paths_source:      git diff --name-only c1db4cc 1278b89
expected_path_count:        34
```

### Step66SYNC.1-M2 canonical merge record

```text
stage_id:                   step66sync1-m2-canonical-merge
baseline_commit:            7971ae0c5a5d90a186efd4c52f75988720ce214e   (merge commit)
exact_stage_head:           44ab32ceab60d417ef1e0800be6cd00fc730b12e   (record commit)
record_commit:              44ab32ceab60d417ef1e0800be6cd00fc730b12e
verification_range:         7971ae0..44ab32c  (frozen)
scope_source:               exact allowed set in the stage verifier and test
expected_paths_source:      git diff --name-only 7971ae0 44ab32c
expected_path_count:        6
```

### Step66C.4-BE3-RA-2M1

```text
stage_id:                   step66c4-be3-ra2m-canonicalization
baseline_commit:            44ab32ceab60d417ef1e0800be6cd00fc730b12e
exact_stage_head:           edafc0ca9111bc6dd76bc3ab59b5ea110f2f05d6
record_commit:              n/a (canonicalization stage; merge recorded by RA-2M2)
verification_range:         44ab32c..edafc0c  (frozen)
scope_source:               EXPECTED_STAGE_PATHS in the stage verifier and test
expected_paths_source:      git diff --name-only 44ab32c edafc0c
expected_path_count:        16
```

### Step66C.4-BE3-RA-2M2

```text
stage_id:                   step66c4-be3-ra2m2-canonical-merge
baseline_commit:            aa02ad5b7fa5ed3997d44420c2f2ec8a2c87c798   (merge commit)
exact_stage_head:           64467fefc9a9ec303f9ddf4c0ce6d46486504d71   (record commit)
record_commit:              64467fefc9a9ec303f9ddf4c0ce6d46486504d71
verification_range:         aa02ad5..64467fe  (frozen)
scope_source:               exact allowed set in the stage verifier and test
expected_paths_source:      git diff --name-only aa02ad5 64467fe
expected_path_count:        6
```

## Step 66D-ALIGN1 (open pull request)

Step 66D-ALIGN1 is not yet merged, so it has no frozen post-merge boundary. Until it is merged its
verifier compares canonical main to the working branch and requires **exact equality** with a
registered 34-path set — an unregistered path fails, and so does a registered path that disappears.

```text
stage_id:                   step66d-align1
baseline_commit:            64467fefc9a9ec303f9ddf4c0ce6d46486504d71
exact_stage_head:           6a8a7bfa2ae758e944b1126881a69fef2d122dcb
merge_commit:               ad2d218186c8cb26af0a2fad6d3fa86a43703db5
verification_range:         64467fe..6a8a7bf  (frozen)
scope_source:               ALIGN1_EXPECTED_PATHS in the Step 66D-ALIGN1 verifier
expected_paths_source:      git diff --name-only 64467fe 6a8a7bf
expected_path_count:        34
boundary_established_by:    Step 66D-ALIGN1-M1 canonical merge
```

The open-PR boundary this section originally carried was established by **Step 66D-ALIGN1-M1** when
PR #24 was merged as `ad2d218` (non-squash, two parents `64467fe` and `6a8a7bf`). The stage's
positive scope is now frozen exactly like the six historical stages above; only the runtime
denylists remain HEAD-relative, and they can only reject.

```text
step66d-align1-rm1     f25d12b..6a8a7bf   exactly 1 commit (frozen)
```

## Runtime denylist

Fixed-range scope is **not** a substitute for the runtime denylist. Both are required and both are
present in every stage verifier. No protected prefix was removed or relaxed by this stage:

```text
apps/  agents/  services/  shared/  migrations/  infra/
frontend runtime source (.tsx .ts .jsx .js .vue .css .scss)
Docker Compose, Kubernetes, Helm, Vault, OIDC
feature-gate defaults, secret configuration
```

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
