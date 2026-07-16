# Step 66UI.4-FE.1B-MD — Merged-main Test Runtime Deployment / Calibration Record

Marker: `STEP66UI4_FE1B_MERGE_DEPLOY_VERIFY: PASS`

Merge commit deployed: `5a2bc4e` (merge of PR #7 `frontend/66ui4-fe1b-calm-safety`, commit `6cf8efe`,
into `main`).

## Product Owner authorization

```text
授權 merge PR #7 到 main；接受目前 Safety badge 顯示 Unavailable 作為已知非阻斷 gap；暫時部署維持運行，
不回滾；merge 後執行 merged main 到 test runtime 的正式部署/校準；不授權 FE.1C/FE.1D implementation；
下一步另行規劃 FE.1B.1 Safety Field Mapping Calibration。
```

## Accepted non-blocking gap (preserved, not fixed by this deployment)

```text
Safety badge currently displays "Unavailable" rather than "Safe" because the real
/operations/safety response is missing these expected fields:
- dispatch_enabled
- resume_dispatch_enabled
- approval_required
- requires_approval

This is an accepted, non-blocking Product Owner validation gap.
The conservative FE.1B logic is correct because it does not claim safe when evidence is incomplete.
This is not a rollback condition.
This is not a safety defect.
This should be handled later by Step 66UI.4-FE.1B.1 -- Safety Field Mapping Calibration.
```

## Pre-deployment baseline (recorded before this stage's deployment action)

```text
Containers: 28, all Up (27 healthy + 1 vault with no healthcheck defined, unchanged from baseline)
Orchestrator: Up (healthy)
Served Admin Console bundle before this stage's deploy action: index-D3ONvmz8.js /
  index-DcSljMgU.css (already live from the prior FE.1B-V temporary deployment, built from PR
  branch commit 6cf8efe)
production_executed_true_count (before): 0
/operations/safety result (before): safe
Safety badge state (before): Unavailable (accepted gap, unchanged by this deployment)
```

## Deployment method

```text
1. Created a fresh, isolated git clone on the test host (local clone of the tracked main clone's
   objects, fetched merge commit 5a2bc4e directly from the GitHub origin URL, then checked it out)
   -- never touching the host's tracked main clone's working directory.
2. Built the Admin Console bundle from that isolated clone using an already-present node:20-slim
   container (`docker run --rm -v <isolated-clone>/apps/admin-console:/work -w /work node:20-slim
   sh -c 'npm ci --silent && npm run build'`) -- no image rebuild of any running service, no
   container restart.
3. Backed up the pre-existing served dist bundle from the running orchestrator container to a
   host-local backup directory before making any change.
4. docker cp'd the new build's static/dist/* into the running orchestrator container's
   admin_console_static/dist/ (static-file replacement only; no `docker compose build`/`up`/
   `restart`).
5. Verified no orphaned old-hash asset files remained (`docker exec ... ls assets/` showed exactly
   the two expected files) and that index.html referenced only the new (in this case, identical)
   hashes.
6. Verified health endpoint, Admin Console HTTP reachability, and the safety endpoint before and
   after, then removed the temporary isolated build clone from the test host.
```

## Deployment source confirmation

```text
Deployment source: merged main, commit 5a2bc4e (NOT the PR branch commit 6cf8efe directly).
Build performed from an isolated clone checked out at 5a2bc4e.
Resulting bundle hash: index-D3ONvmz8.js / index-DcSljMgU.css -- deterministic, byte-identical to
  the build previously produced from PR branch commit 6cf8efe (expected: apps/admin-console/**
  content is unchanged between 6cf8efe and the 5a2bc4e merge commit -- the merge added no further
  changes to that path -- so an identical hash confirms, rather than contradicts, correct
  provenance).
```

## Post-deployment verification

| Check | Result |
| --- | --- |
| Test runtime source is merged main commit | Confirmed — build performed from an isolated clone checked out at `5a2bc4e` |
| Admin Console loads | Confirmed — `GET /admin/` → HTTP 200 |
| FE.1B calm safety presentation visible | Confirmed — same bundle previously validated `VISIBLE` by the Product Owner (Step 66UI.4-FE.1B-V); hash unchanged |
| Safety badge state | `Unavailable` — accepted gap, not a failure of this deployment stage |
| Raw safety evidence / details accessible | Confirmed — `Evidence / details` disclosure present and unconditional, same as at validation |
| Core pages reachable | Confirmed — orchestrator health endpoint `{"service":"orchestrator","status":"ok"}` |
| Safety endpoint healthy | Confirmed — `/operations/safety` → `"result":"safe"` |
| `production_executed_true_count` | `0` before and after (unchanged) |
| Workflow dispatch/resume | Not triggered |
| Production/external action | Not triggered |
| Backend/API/database migration | None — only container-internal static files replaced |
| Unrelated service changed | None — all 28 containers unaffected (`docker ps` unchanged before/after; no restart of any container) |
| Deployed bundle assets | Exactly `index-D3ONvmz8.js`, `index-DcSljMgU.css` — no orphaned old-hash files |

## Rollback

```text
Rollback used: no.
Rollback available: yes -- a pre-deployment bundle backup was taken on the test host immediately
  before this stage's swap (in addition to the backup retained from the earlier FE.1B-V temporary
  deployment). Both backups contain byte-identical content to what is currently served, since the
  bundle hash did not change across either deployment action.
```

## Safety / scope statement

Runtime code changed on `main`: yes (merge of PR #7, frontend-only presentation, recorded in the
merge record). Backend changed: no. API changed: no. Database changed: no. Workflow changed: no.
Production action: no. External action: no. New safety endpoint: no. New backend safety computation:
no. FE.1C / FE.1D: still not authorized. FE.1B.1 Safety Field Mapping Calibration: recommended next,
not implemented in this stage.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
