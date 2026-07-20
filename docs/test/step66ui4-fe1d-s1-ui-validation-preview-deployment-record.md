# Step 66UI.4-FE.1D-S1-VP — Test / Verification Record

Marker: `STEP66UI4_FE1D_S1_PREVIEW_DEPLOY_VERIFY: PASS`

Deployed: `frontend/66ui4-fe1d-s1-navigation-polish`, commit `72d8bff`, Draft PR #13, to the internal
test runtime, for Product Owner UI validation. **Main was NOT merged.** Test-runtime-only scope.

## Product Owner authorization

```text
授權 Claude Code 將 PR #13 frontend/66ui4-fe1d-s1-navigation-polish 部署到 test runtime，供 Step
66UI.4-FE.1D-S1 Product Owner UI validation；不 merge main；不得修改 backend/API/DB/workflow，不得
新增 endpoint/route，不得修復 SPA deep-link fallback，不得實作雙向 URL sync，不得授權或實作 FE.1D
Slice 2。
```

## Deployment source

```text
Branch: frontend/66ui4-fe1d-s1-navigation-polish
Commit: 72d8bff
Built in an isolated, disposable clone on the internal test runtime host (removed after use), via
  `node:20-slim` in a throwaway Docker container -- no repo state on the test runtime's own
  reference checkout was touched.
Deterministic build hashes: index-D_e3KYR_.css / index-mPDY7eq_.js -- identical to the independent
  build produced during Step 66UI.4-FE.1D-S1-R's own re-verification, confirming build provenance.
```

## Pre-deployment baseline (masked)

```text
Previous deployed bundle: index-A5KtnMef.js / index-tDSVCSFZ.css (from Step 66UI.4-FE.1C.1-MD, the
  current merged-main baseline).
Admin Console status: HTTP 200 (at /admin/).
/operations/safety: HTTP 200, production_executed_true_count = 0.
/operations/agent-executions: HTTP 200.
Service/container health: 26 of 27 application containers reporting "healthy" (one, the secrets
  service, runs without a declared healthcheck and reports "Up" only -- consistent with the
  established baseline pattern from every prior deployment stage in this project), plus the
  always-on monitoring container.
Deployment workspace: clean disposable clone at commit 72d8bff, no local modifications.
```

## Deployment steps

```text
1. Backed up the currently-deployed bundle inside the orchestrator container (index-A5KtnMef.js /
   index-tDSVCSFZ.css) to a rollback location inside the container.
2. Built the Admin Console frontend from PR #13 commit 72d8bff in the disposable clone, via
   `node:20-slim` (npm ci + npm run build) -- deterministic hashes index-D_e3KYR_.css /
   index-mPDY7eq_.js.
3. Removed the two previous asset files and `docker cp`'d the three new build outputs (index.html,
   the new CSS, the new JS) into the orchestrator container's static asset directory.
4. No container rebuild, no restart -- static files served directly from disk (confirmed via
   unchanged container uptime pre/post-swap: "Up 2 days (healthy)" both before and after).
5. Removed the disposable clone from the test runtime host after the build completed.
```

## Post-deployment verification

| # | Check | Result |
| --- | --- | --- |
| 1 | Admin Console loads | Confirmed -- HTTP 200 at `/admin/` |
| 2 | PR #13 bundle is active | Confirmed -- `index.html` references `index-mPDY7eq_.js` / `index-D_e3KYR_.css`; both files present and served |
| 3 | Navigation renders all 7 groups | Confirmed -- all 7 group subtitle strings present in the deployed JS (grep-verified) |
| 4 | Navigation renders group subtitles | Confirmed -- "Assign and collaborate with the AI team", "Handle operations, approvals, and recovery", "Safety and audit evidence", "Roles, integrations, and policy", and the remaining 3 subtitle strings all present |
| 5 | Soon badges render only on planned placeholder items | Confirmed by source-level review in Step 66UI.4-FE.1D-S1-R (TypeScript union type constrains badge values; every Soon-badged item verified against `App.tsx`'s `PlaceholderPage` routes); the deployed bundle contains the "Soon" string |
| 6 | Read-only badges render only on read-only/status/diagnostic surfaces | Confirmed by the same source-level review; the deployed bundle contains the "Read-only" string |
| 7 | Evidence badges render only on evidence/audit/recovery/demo evidence surfaces | Confirmed by the same source-level review; the deployed bundle contains the "Evidence" string |
| 8 | Platform Ops renders compactly and remains readable | Confirmed -- `nav-group-compact` CSS class present in the deployed bundle; padding/font-size reduction is modest (not below readable thresholds), reviewed in Step 66UI.4-FE.1D-S1-R |
| 9 | Platform Ops keeps all prior items | Confirmed -- all 19 Platform Ops route paths present in the deployed bundle (grep-verified spot check: `/delivery-package`, plus full-set confirmation via the Step 66UI.4-FE.1D-S1-R route-snapshot regression test, which the deployed commit shares byte-for-byte) |
| 10 | Delivery Package remains under Platform Ops | Confirmed -- `/delivery-package` route present; "Delivery evidence / package record" subtitle string present in the deployed bundle, matching the Platform-Ops-only placement |
| 11 | Delivery Package is not moved to Deliveries | Confirmed -- same source-level review; Deliveries group's item set unchanged (`/delivery-inbox`, `/delivery-detail` only) |
| 12 | Route paths remain unchanged | Confirmed -- spot-checked 8 route paths (`/tasks`, `/delivery-package`, `/delivery-inbox`, `/settings/roles-permissions`, `/audit-evidence`, `/agent-executions`, `/dlq-retry`, `/safety`) all present in the deployed bundle; full 39-route preservation already confirmed at the source level in Step 66UI.4-FE.1D-S1-R |
| 13 | Existing pages remain accessible via navigation | Confirmed -- no route removed from `App.tsx`'s route table (unchanged by this PR) |
| 14 | No fake clickable control appears | Confirmed -- badges/subtitles are non-interactive `<span>` elements (source-level review, Step 66UI.4-FE.1D-S1-R) |
| 15 | No FE.1D Slice 2 microcopy/field-label changes appear | Confirmed -- zero Slice 2 files in the PR #13 diff (TaskList.tsx, ExecutiveOverview.tsx, TaskDetail.tsx, PlaceholderPanel.tsx, CalmSafetyPosture.tsx, SafetyStatusBar.tsx all absent from the diff) |
| 16 | `+ Create task` remains unchanged | Confirmed -- string present in the deployed bundle; "New task" confirmed absent |
| 17 | `delivery_package_ready_for_admin_console` remains unchanged/deferred | Confirmed -- "Ready to publish" confirmed absent from the deployed bundle |
| 18 | SPA deep-link fallback remains known gap, not fixed | Confirmed -- no change to `apps/orchestrator/src/main.py` anywhere in this stage; the known-gap record remains unmodified |
| 19 | Two-way URL sync not implemented | Confirmed -- `TaskList.tsx` (the only file with any `useSearchParams()` usage) is untouched by PR #13 |
| 20 | `/operations/safety` unchanged | Confirmed -- HTTP 200, `production_executed_true_count` = 0, same as pre-deployment baseline |
| 21 | `/operations/agent-executions` unchanged | Confirmed -- HTTP 200 |
| 22 | `production_executed_true_count` remains 0 | Confirmed |
| 23 | No workflow dispatch/resume occurred | Confirmed -- read-only GET requests plus a static-asset swap only |
| 24 | No production/external action occurred | Confirmed |
| 25 | No backend/API/database/workflow migration occurred | Confirmed -- only `apps/admin-console/**` files were built; no backend service was rebuilt, restarted, or touched |

## Rollback

```text
Rollback backup location (masked): a temporary directory inside the orchestrator container,
  containing an untouched copy of the pre-swap dist/assets (index-A5KtnMef.js /
  index-tDSVCSFZ.css -- the FE.1C.1-MD-sourced merged-main bundle).
Rollback used: no -- deployment succeeded without incident.
```

## Services changed

```text
None restarted. Only the orchestrator container's static Admin Console asset files were replaced
  on disk (docker cp swap). Container uptime unaffected ("Up 2 days (healthy)" before and after).
No other service/container touched.
```

## Secret scan

```text
python scripts/run_local_secret_scan.py (run on this repo checkout) -> critical=0, high=0,
  informational=100 (baseline, unchanged -- this stage introduces no new findings).
```

## Local Artifact Reconciliation

```text
git grep for local Windows absolute paths, local username, Documents/Codex path, .tools/ across
  every file this stage adds/modifies -- the only matches are prior-stage documentation describing
  checks performed, not real leaked paths.
git ls-files check for .tools/ or platform-progress-admin-console-proposal.md -- no matches.
No blocking gap.
```

## Statement

Test/verification record only. Frontend preview deployment of already-planned, reviewed PR #13 to
the internal test runtime for Product Owner UI validation. `main` was NOT merged. No backend/API/
database/workflow change. No new endpoint. No new route. No production/external action. FE.1D
Slice 2 remains unauthorized. SPA deep-link fallback remains a known, separately-tracked platform
gap, not fixed. Two-way URL sync not implemented.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
