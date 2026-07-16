# Step 66UI.4-FE.1B.1-MD — Merged-main Test Runtime Deployment / Calibration Record

Marker: `STEP66UI4_FE1B1_MERGE_DEPLOY_VERIFY: PASS`

Merge commit deployed: `7aff12a` (final `main` HEAD after merging PR #9 `frontend/66ui4-fe1b1-safety-field-mapping`,
commit `974822d`, plus the FE.1B.1 planning/review/preview-deploy consolidation branches, into `main`).

## Product Owner authorization

```text
授權執行 Step 66UI.4-FE.1B.1-MD — merge PR #9 到 main，並將 merged main 校準到 test runtime；同時整理
FE.1B.1 planning/review/preview/validation 必要紀錄進 main；不得修改 backend/API/DB/workflow，不得修改
/operations/safety response shape，不得授權 FE.1C/FE.1D implementation。
```

## Pre-deployment baseline (recorded before this stage's deployment action)

```text
Containers: 28, all Up (unchanged from baseline)
Orchestrator: Up (healthy)
Served Admin Console bundle before this stage's deploy action: index-CCkn0PAe.js /
  index-DcSljMgU.css (already live from the prior Step 66UI.4-FE.1B.1-VP temporary preview
  deployment, built from PR branch commit 974822d)
production_executed_true_count (before): 0
workflow_production_executed_true_count (before): 0
/operations/safety result (before): safe
Safety badge state (before): Safe (per Step 66UI.4-FE.1B.1-V confirmation; unchanged going into
  this deployment)
```

## Deployment method

```text
1. Created a fresh, isolated git clone on the test host (local clone of the tracked main clone's
   objects), fetched merge commit 7aff12a directly from the GitHub origin URL, then checked it out
   -- never touching the host's tracked main clone's working directory.
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
   (in this case, identical) hashes.
6. Verified health endpoint, Admin Console HTTP reachability, and the safety payload before and
   after, then removed the temporary isolated build clone from the test host (rollback backups
   retained).
```

## Deployment source confirmation

```text
Deployment source: merged main, commit 7aff12a (NOT the PR branch commit 974822d directly, and NOT
  any of the four consolidation branches).
Build performed from an isolated clone checked out at 7aff12a.
Resulting bundle hash: index-CCkn0PAe.js / index-DcSljMgU.css -- deterministic, byte-identical to
  the build previously produced from PR branch commit 974822d (expected: apps/admin-console/**
  content is unchanged between 974822d and the 7aff12a merge chain -- the merges added no further
  changes to that path -- so an identical hash confirms, rather than contradicts, correct
  provenance).
```

## Post-deployment verification

| Check | Result |
| --- | --- |
| Test runtime source is merged main commit | Confirmed — build performed from an isolated clone checked out at `7aff12a` |
| Admin Console loads | Confirmed — `GET /admin/` → HTTP 200 |
| Merged main FE.1B.1 bundle active | Confirmed — `index-CCkn0PAe.js` / `index-DcSljMgU.css`, no orphaned old-hash files |
| Safety badge state | **Safe** — independently re-confirmed by executing the actual compiled `getCalmSafetyPosture()` logic (via a disposable, uncommitted test harness, deleted immediately after use) against a freshly re-fetched live `/operations/safety` payload: tone `"safe"`, label `"Safe"`, title `"Safe - no automated or production actions will run."` |
| Raw safety evidence / details accessible | Confirmed — `Evidence / details` disclosure present and unconditional |
| Retired fields | Confirmed — labeled `Not applicable at this endpoint` |
| Approval wording | Confirmed — per-task, not global |
| Safety Center | Confirmed working — unaffected by this stage's changes |
| SafetyStatusBar | Confirmed working — unaffected by this stage's changes |
| `/operations/safety` response shape | Unchanged — 571 total fields, identical before/after |
| `/operations/safety` result | `"safe"` — unchanged before/after |
| `production_executed_true_count` | `0` before and after (unchanged) |
| `workflow_production_executed_true_count` | `0` before and after (unchanged) |
| Workflow dispatch/resume | Not triggered |
| Production/external action | Not triggered |
| Backend/API/database migration | None — only container-internal static files replaced |
| Unrelated service changed | None — all 28 containers unaffected (`docker ps` unchanged before/after; no restart of any container) |
| FE.1C / FE.1D UI | Not present — bundle contains only the reviewed FE.1B.1 diff |
| Deployed bundle assets | Exactly `index-CCkn0PAe.js`, `index-DcSljMgU.css` — no orphaned old-hash files |

## Rollback

```text
Rollback used: no.
Rollback available: yes -- a pre-deployment bundle backup was taken on the test host immediately
  before this stage's swap (in addition to the backups retained from the earlier
  Step 66UI.4-FE.1B.1-VP temporary deployment). All backups contain byte-identical content to what
  is currently served, since the bundle hash did not change across any of these deployment actions.
```

## Safety / scope statement

Runtime code changed on `main`: yes (merge of PR #9, frontend-only mapping calibration, recorded in
the merge record). Backend changed: no. API changed: no. Database changed: no. Workflow changed: no.
Production action: no. External action: no. `/operations/safety` response shape change: no. New
safety endpoint: no. New backend safety computation: no. FE.1C / FE.1D: still not authorized.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
