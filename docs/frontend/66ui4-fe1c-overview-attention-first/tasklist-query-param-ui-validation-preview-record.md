# UI Validation Preview Record — Step 66UI.4-FE.1C.1-VP

> **Preview deployment record only. `main` not merged. No frontend source code changed (only a
> test-runtime static-asset swap sourced verbatim from PR #11's own build). No backend/API/
> database/workflow change. No new endpoint. No production/external action. FE.1D not authorized.
> Bidirectional URL sync not implemented.**

Executed by: Claude Code (Lead Engineer / Architecture Owner — see
`docs/process/role-responsibility-matrix.md`), per Product Owner explicit authorization:

```text
授權 Claude Code 將 PR #11 frontend/66ui4-fe1c1-tasklist-query-param 部署到 test runtime，供 Step
66UI.4-FE.1C.1 Product Owner UI validation；不 merge main；不得修改 backend/API/DB/workflow，不得新增
endpoint，不得授權 FE.1D，不得實作雙向 URL sync。
```

## What was deployed

```text
PR: #11 (Draft)
Branch: frontend/66ui4-fe1c1-tasklist-query-param
Commit: cba5dd09e745f98df3d319af52621c11ad8fda25
Codex implementation marker: STEP66UI4_FE1C1_IMPLEMENTATION_VERIFY: PASS
Claude Code review: PASS (docs/test/step66ui4-fe1c1-tasklist-query-param-review-record.md)
Target: test runtime only. main unchanged (f933adf). No merge performed.
```

## Deployment state confirmed after swap

```text
1. /tasks?status=blocked: initializes the existing Status dropdown to "blocked" and the existing
   taskApi.list(filters) request includes status=blocked -- confirmed by the FE.1C.1-R review's own
   independent re-execution of the exact deployed commit's test suite (17 files/131 tests, including
   the dedicated TaskListQueryParam.test.tsx case for this exact scenario), and by this stage's
   confirmation that the deployed bundle is byte-identical (same deterministic hash) to that
   re-verified build.
2. /tasks?status=clarification_needed: same behavior, initializes to "clarification_needed".
3. /tasks?status=unknown (and other invalid values): the filter falls back to "(any)", the invalid
   value is never sent to the backend, and the URL is not mutated -- confirmed by the same
   independently re-run test suite covering "unknown", "", and "production_executed" cases.
4. Manual dropdown change does not update the URL query parameters: confirmed structurally
   (setSearchParams is never imported or called anywhere in TaskList.tsx) and behaviorally (a
   dedicated test asserts the URL stays at its original value after a manual dropdown edit).
5. Overview attention links (/tasks?status=clarification_needed, /tasks?status=blocked) are
   unchanged -- ExecutiveOverview.tsx is absent from PR #11's diff.
6. Overview itself was not redesigned -- confirmed by the same absence from the diff.
7. App routes unchanged -- App.tsx absent from the diff; /tasks already existed as a route.
8. No FE.1D navigation implementation appears -- App.tsx/main.tsx both absent from the diff.
9. Bidirectional URL sync was not implemented -- confirmed absent, per Product Owner authorization.
```

## Product Owner validation checklist

```text
1. 從 Overview 點 Decisions waiting，是否進入 TaskList 並預選 clarification_needed？
2. 從 Overview 點 Blocked tasks，是否進入 TaskList 並預選 blocked？
3. TaskList 是否顯示真實 filtered task data？
4. 直接開 /tasks?status=blocked，Status dropdown 是否顯示 blocked？
5. 直接開 /tasks?status=clarification_needed，Status dropdown 是否顯示 clarification_needed？
6. 直接開 /tasks?status=unknown，是否安全忽略並回到 any？
7. 手動改 Status dropdown 後，URL 是否沒有被改寫？
8. 是否沒有新增假數字、假按鈕、假控制？
9. 是否沒有 FE.1D navigation 變更？
10. 是否沒有 backend/API/DB/workflow 行為變更？
```

## Expected result

```text
全部 10 項應為「是」。
```

## Accepted out-of-scope items (disclosed to Product Owner)

```text
1. 不做雙向 URL sync（手動變更 dropdown 不會反映到網址列）。
2. 不做 browser-history restoration（瀏覽器上一頁/下一頁不會特別處理此 filter 狀態）。
3. 不實作 FE.1D。
```

## Access

```text
Admin Console: reachable at the test runtime's existing admin console path (same access method
  used for every prior FE.1B/FE.1B.1/FE.1C/FE.1C.1 preview-validation stage this project). No new
  URL, no new credential, no new access method introduced by this stage.
```

## Rollback

```text
A pre-deployment backup of the prior bundle (FE.1C-MD merged-main assets) was retained inside the
  orchestrator container before the swap. If the Product Owner rejects this preview, rollback is a
  simple asset-directory restore from that backup -- no rebuild, no restart, no config change,
  matching the low-risk method used to deploy. Not required in this stage; retained purely as a
  safety net.
```

## Scope / safety

```text
Backend changed: no.
API changed: no.
Database changed: no.
Workflow changed: no.
New endpoint: no.
Production action: no.
External action: no.
FE.1D: not authorized by this stage.
Bidirectional URL sync: not implemented.
Unexpected UI/features: none found -- deployed bundle matches exactly what was reviewed in Step
  66UI.4-FE.1C.1-R (same source commit, same deterministic asset hashes).
```

## Verification

| Command | Result |
| --- | --- |
| `python scripts/verify_step66ui4_fe1c1_preview_deploy.py` | PASS |
| `pytest tests/test_step66ui4_fe1c1_preview_deploy.py` | all passed |
| `git diff --check` | clean |
| `git status --short` | clean |
| Secret scan (`scripts/run_local_secret_scan.py`) | critical=0, high=0, informational=100 (baseline) |

## Statement

Preview deployment record only. `main` not merged. No frontend source code changed. No backend/API/
database/workflow change. No new endpoint. No production/external action. FE.1D not authorized by
this document. Bidirectional URL sync not implemented.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
