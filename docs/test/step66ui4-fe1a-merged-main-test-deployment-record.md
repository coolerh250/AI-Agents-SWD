# Step 66UI.4-FE.1A-MD — Merged-main Test Runtime Deployment / Calibration Record

Marker: `STEP66UI4_FE1A_MERGE_DEPLOY_VERIFY: PASS`

Merge commit deployed: `09fe5f2` (merge of PR #6 `frontend/66ui4-fe1a-visual-polish`, commit
`7e6422f`, into `main`).

## Product Owner authorization

```text
授權 merge PR #6 到 main；暫時部署維持運行，不回滾；merge 後再執行 merged main 到 test runtime 的正式
部署/校準；不授權 FE.1B/FE.1C/FE.1D。
```

## Pre-deployment baseline (recorded before this stage's deployment action)

```text
Test runtime main-clone commit (unrelated to deploy source): ac11bea (stale; not used as deploy
  source — the deploy source is an isolated clone built at merge commit 09fe5f2, per the "do not
  deploy from PR branch, do not disturb the host's tracked main clone" rule)
Containers: 28, all Up (27 healthy + 1 vault with no healthcheck defined, unchanged from baseline)
Orchestrator: Up (healthy)
Served Admin Console bundle before this stage's deploy action: index-DZBN-FWE.js /
  index-Cnlye4s4.css (already live from the prior FE.1A-V temporary deployment, built from PR
  branch commit 7e6422f)
production_executed_true_count (before): 0
/operations/safety result (before): safe
```

## Deployment method

```text
1. Confirmed the test host's outbound GitHub connectivity and fetched origin/main into the host's
   existing tracked main clone's git objects only (git fetch, no checkout/pull/merge performed
   against that clone's working tree, so its own in-progress operational output files were never
   touched).
2. Created a fresh, isolated git clone on the test host (local clone of the tracked main clone's
   objects, then git checkout of the exact merge commit 09fe5f2) -- never touching the host's
   tracked main clone's working directory.
3. Built the Admin Console bundle from that isolated clone using an already-present node:20-slim
   container (`docker run --rm -v <isolated-clone>/apps/admin-console:/work -w /work node:20-slim
   sh -c 'npm ci --silent && npm run build'`) -- no image rebuild of any running service, no
   container restart.
4. Backed up the pre-existing served dist bundle from the running orchestrator container to a
   host-local backup directory before making any change.
5. docker cp'd the new build's static/dist/* into the running orchestrator container's
   admin_console_static/dist/ (static-file replacement only; no `docker compose build`/`up`/
   `restart`).
6. Verified no orphaned old-hash asset files remained (`docker exec ... ls assets/` showed exactly
   the two expected files) and that index.html referenced only the new (in this case, identical)
   hashes.
7. Verified health endpoint, Admin Console HTTP reachability, and the safety endpoint before and
   after, then removed the temporary isolated build clone from the test host.
```

## Deployment source confirmation

```text
Deployment source: merged main, commit 09fe5f2 (NOT the PR branch commit 7e6422f directly).
Build performed from an isolated clone checked out at 09fe5f2.
Resulting bundle hash: index-DZBN-FWE.js / index-Cnlye4s4.css -- deterministic, byte-identical to
  the build previously produced from PR branch commit 7e6422f (expected: apps/admin-console/**
  content is unchanged between 7e6422f and the 09fe5f2 merge commit -- the merge added no further
  changes to that path -- so an identical hash confirms, rather than contradicts, correct
  provenance).
```

## Post-deployment verification

| Check | Result |
| --- | --- |
| Test runtime source is merged main commit | Confirmed — build performed from an isolated clone checked out at `09fe5f2` |
| Admin Console loads | Confirmed — `GET /admin/` → HTTP 200 |
| Visual polish visible | Confirmed — same bundle previously validated `VISIBLE` by the Product Owner (Step 66UI.4-FE.1A-V); hash unchanged |
| Core pages reachable | Confirmed — orchestrator health endpoint `{"service":"orchestrator","status":"ok"}` |
| Safety endpoint healthy | Confirmed — `/operations/safety` → `"result":"safe"` |
| `production_executed_true_count` | `0` before and after (unchanged) |
| Workflow dispatch/resume | Not triggered |
| Production/external action | Not triggered |
| Backend/API/database migration | None — only container-internal static files replaced |
| Unrelated service changed | None — all 28 containers unaffected (`docker ps` unchanged before/after; no restart of any container) |
| Deployed bundle assets | Exactly `index-DZBN-FWE.js`, `index-Cnlye4s4.css` — no orphaned old-hash files |

## Rollback

```text
Rollback used: no.
Rollback available: yes -- a pre-deployment bundle backup was taken on the test host immediately
  before this stage's swap (in addition to the backup retained from the earlier FE.1A-V temporary
  deployment). Both backups contain byte-identical content to what is currently served, since the
  bundle hash did not change across either deployment action.
```

## Safety / scope statement

Runtime code changed on `main`: yes (merge of PR #6, CSS-only, recorded in the merge record). Backend
changed: no. API changed: no. Database changed: no. Workflow changed: no. Production action: no.
External action: no. FE.1B / FE.1C / FE.1D: still not authorized.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
