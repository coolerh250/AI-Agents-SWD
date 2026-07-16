# Step 66UI.4-FE.1B.1-VP — PR #9 Test Runtime UI Validation Preview Deployment Record

Marker: `STEP66UI4_FE1B1_PREVIEW_DEPLOY_VERIFY: PASS`

> **Preview deployment record only. `main` was not merged by this stage. No backend changed. No API
> changed. No database changed. No workflow changed. No `/operations/safety` response shape change.
> No production action. No external action. No FE.1C/FE.1D implementation or authorization.**

Executed by: Claude Code (Lead Engineer / Architecture Owner — see
`docs/process/role-responsibility-matrix.md`), per explicit Product Owner authorization:

```text
授權 Claude Code 將 PR #9 frontend/66ui4-fe1b1-safety-field-mapping 部署到 test runtime 供 FE.1B.1 UI
validation；不 merge main；不授權 FE.1C/FE.1D implementation。
```

## Deployment source

```text
Branch: frontend/66ui4-fe1b1-safety-field-mapping (Draft PR #9)
Commit: 974822d940c0e1ed9d061fbfe68fbed40ebd1fc0
main merged: no
Deployment target: test runtime only (Admin Console static bundle, in-place swap)
Prior review: review/66ui4-fe1b1-safety-field-mapping @ f818ccc, STEP66UI4_FE1B1_REVIEW_VERIFY: PASS
Prior planning: review/66ui4-fe1b1-safety-field-mapping-plan @ ace3441 (read-only reference)
```

## Pre-deployment baseline (masked)

```text
Previous served bundle: index-D3ONvmz8.js / index-DcSljMgU.css (the FE.1B merged-main build,
  unchanged since Step 66UI.4-FE.1B-MD)
Admin Console HTTP status (before): 200
/operations/safety result (before): safe
/operations/safety production_executed_true_count (before): 0
/operations/safety workflow_production_executed_true_count (before): 0
Safety badge (before, expected per the accepted FE.1B-V gap): Unavailable
Containers: 28, all Up (unchanged baseline)
Deployment workspace: a fresh isolated git clone on the test host, fetched directly from the GitHub
  origin URL at the PR #9 branch tip -- never touching the host's own tracked main clone.
```

## Deployment method

```text
1. Created a fresh, isolated git clone on the test host (local clone of the tracked main clone's
   objects), then fetched frontend/66ui4-fe1b1-safety-field-mapping directly from the GitHub origin
   URL and checked out FETCH_HEAD -- confirmed at commit 974822d.
2. Built the Admin Console bundle from that isolated clone using an already-present node:20-slim
   container (`docker run --rm -v <isolated-clone>/apps/admin-console:/work -w /work node:20-slim
   sh -c 'npm ci --silent && npm run build'`) -- no image rebuild of any running service, no
   container restart.
3. Backed up the pre-existing served dist bundle from the running orchestrator container to a
   host-local backup directory before making any change.
4. Removed the prior deployment's asset files, then docker cp'd the new build's static/dist/*
   contents into the running orchestrator container's admin_console_static/dist/ (static-file
   replacement only; no `docker compose build`/`up`/`restart`).
5. Verified no orphaned old-hash asset files remained and that index.html referenced only the new
   hashes.
6. Verified health endpoint, Admin Console HTTP reachability, and the safety payload before and
   after, then removed the temporary isolated build clone from the test host (rollback backup
   retained).
```

## Deployment source confirmation

```text
Deployment source: frontend/66ui4-fe1b1-safety-field-mapping, commit 974822d (NOT main; main
  remains at 508c8e1, unmerged by this stage).
Build performed from an isolated clone checked out at 974822d.
Resulting bundle hash: index-CCkn0PAe.js (new -- expected, CalmSafetyPosture.tsx logic changed) /
  index-DcSljMgU.css (unchanged -- expected, no CSS change). Deterministic: this is byte-identical
  to the build independently produced from the same commit during the prior review stage
  (Step 66UI.4-FE.1B.1-R), confirming correct provenance.
```

## Post-deployment verification

| Check | Result |
| --- | --- |
| Deployment source is PR #9 commit `974822d` | Confirmed — isolated clone checked out at that commit |
| `main` not merged | Confirmed — `main` remains at `508c8e1` throughout |
| Admin Console loads | Confirmed — `GET /admin/` -> HTTP 200 |
| PR #9 bundle active | Confirmed — `index-CCkn0PAe.js` / `index-DcSljMgU.css` served, no orphaned old-hash files |
| Safety badge state | Confirmed resolves to **Safe** — independently verified by executing the actual compiled `getCalmSafetyPosture()` logic (via a disposable, uncommitted test harness, deleted after use) against the live `/operations/safety` payload fetched from the test host: tone `"safe"`, label `"Safe"`, title `"Safe - no automated or production actions will run."` |
| Raw evidence/details accessible | Confirmed — unchanged from the prior review stage's finding; `Evidence / details` disclosure is unconditional in the reviewed source |
| Retired fields behavior | Confirmed by source review (Step 66UI.4-FE.1B.1-R) — the four retired fields (`dispatch_enabled`, `resume_dispatch_enabled`, `approval_required`, `requires_approval`) are labeled `Not applicable at this endpoint`, not treated as missing risk |
| Approval wording | Confirmed by source review — "Approvals are tracked per task. Review task details for approval requirements.", not a global claim |
| Safety Center | Unaffected — `SafetyCenter.tsx` untouched by PR #9, same bundle serves it |
| SafetyStatusBar | Unaffected — `SafetyStatusBar.tsx` untouched by PR #9 |
| `/operations/safety` shape | Unchanged — 571 total fields, identical to pre-deployment; no orchestrator file touched |
| `/operations/safety` result | `"safe"` — unchanged before/after |
| `production_executed_true_count` | `0` before and after (unchanged) |
| `workflow_production_executed_true_count` | `0` before and after (unchanged) |
| Workflow dispatch/resume | Not triggered |
| Production/external action | Not triggered |
| Backend/API/database migration | None — only container-internal static files replaced |
| Unrelated service changed | None — all 28 containers unaffected (`docker ps` unchanged before/after; no restart of any container) |
| FE.1C/FE.1D UI | Not present — bundle contains only the FE.1B.1 mapping-calibration diff, confirmed in Step 66UI.4-FE.1B.1-R's scope review |

## Rollback

```text
Rollback used: no.
Rollback available: yes -- a pre-deployment bundle backup was taken on the test host immediately
  before this stage's swap. It contains the previously-served index-D3ONvmz8.js /
  index-DcSljMgU.css bundle and can be docker cp'd back into the running orchestrator container's
  admin_console_static/dist/ with no image rebuild or restart if the Product Owner rejects this
  preview.
```

## Local Artifact Reconciliation

```text
No local Windows absolute path committed: confirmed (git grep across main and the PR #9 diff, no
  matches).
No local username committed: confirmed (git grep for the operator's local account name, no
  matches).
No Documents/Codex path committed: confirmed (no matches).
No .tools/ directory committed: confirmed (no matches).
No unrelated local proposal file committed: confirmed -- PR #9's diff contains exactly the 11 files
  already enumerated in Step 66UI.4-FE.1B.1-R's review record; no
  docs/product/platform-progress-admin-console-proposal.md or similar unrelated file present.
All PR #9 deliverables exist in repo-relative shared paths: confirmed -- all 11 changed files are
  present on origin/frontend/66ui4-fe1b1-safety-field-mapping at commit 974822d.
Local-only files/directories found: none requiring classification.
Deliverable still only on local disk: none found -- no blocking gap.
```

## Statement

Preview deployment record only. `main` was not merged. Test runtime only. No backend changed. No
API changed. No database changed. No workflow changed. No `/operations/safety` response shape
change. No workflow dispatch. No workflow resume. No external action. No production action. No
FE.1C/FE.1D implementation or authorization.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
