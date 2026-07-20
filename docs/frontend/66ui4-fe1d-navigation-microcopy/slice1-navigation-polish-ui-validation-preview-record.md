# Slice 1 Navigation Polish — UI Validation Preview Record

> **Preview deployment record. Frontend implementation deployed to test runtime for Product Owner
> UI validation. `main` NOT merged. No backend/API/database/workflow change. No new endpoint. No
> new route. No production/external action. FE.1D Slice 2 remains unauthorized. Admin Console SPA
> deep-link fallback gap remains an existing platform limitation, not fixed by this document.**

Executed by: Claude Code (Lead Engineer / Architecture Owner — see
`docs/process/role-responsibility-matrix.md`), per Product Owner explicit authorization:

```text
授權 Claude Code 將 PR #13 frontend/66ui4-fe1d-s1-navigation-polish 部署到 test runtime，供 Step
66UI.4-FE.1D-S1 Product Owner UI validation；不 merge main；不得修改 backend/API/DB/workflow，不得
新增 endpoint/route，不得修復 SPA deep-link fallback，不得實作雙向 URL sync，不得授權或實作 FE.1D
Slice 2。
```

## What was deployed

```text
PR #13 branch: frontend/66ui4-fe1d-s1-navigation-polish
Commit deployed: 72d8bff
Draft PR: #13
main merged: NO -- deployment source is the PR branch only.
Deployment target: internal test runtime ONLY. No production deployment.
Product Owner validation: PENDING (this document prepares the checklist; the verdict itself is
  recorded separately once the Product Owner responds).
```

## Behavior confirmed after deployment

```text
7 navigation groups: all present, unchanged group IDs (overview, team-work, deliveries,
  operator-center, governance, platform-ops, settings).
Group subtitles: all 7 groups render a visible, product-language subtitle.
Soon badges: render only on planned placeholder destinations (Notifications, Clarifications,
  Reminder / Expiry, Delivery Inbox, Delivery Detail, Approvals, DLQ / Retry, and the 5 Settings
  placeholders).
Read-only badges: render only on read-only/status/diagnostic surfaces (Safety Center and most
  Platform Ops posture/status pages).
Evidence badges: render only on audit/evidence/recovery surfaces (Audit Evidence, Agent Executions,
  and the Platform Ops rows the design's density spec marked Evidence).
Platform Ops compact density: collapsed by default (unchanged), renders in a modestly denser
  presentation, remains readable.
Delivery Package placement: remains under Platform Ops, NOT under Deliveries.
Route preservation: all 39 pre-existing route paths preserved byte-identical; no new route added.
No fake controls: badges/subtitles are non-interactive display text only.
Slice 2 not implemented: zero TaskList/ExecutiveOverview/TaskDetail/PlaceholderPanel/
  CalmSafetyPosture/SafetyStatusBar changes present.
"+ Create task": unchanged.
delivery_package_ready_for_admin_console: unchanged, not renamed, remains deferred to Step 66D.
SPA deep-link fallback: not fixed, remains a known, separately-tracked platform gap.
Two-way URL sync: not implemented.
```

## Product Owner validation instructions

```text
Access method: the Admin Console at the internal test runtime's admin console local tunnel (same
  access method used for every prior FE.1B/FE.1C/FE.1C.1 UI validation in this project). Sign in
  with your usual test-runtime role/credentials; navigate the left-hand sidebar to review the
  updated navigation.
```

### Validation checklist

| # | Question | Expected |
| --- | --- | --- |
| 1 | Navigation 整體是否更像產品介面？ | 是 |
| 2 | 7 個 group subtitle 是否清楚、簡短、不暴露工程細節？ | 是 |
| 3 | Soon badge 是否只出現在尚未啟用的 placeholder 頁面？ | 是 |
| 4 | Read-only badge 是否有助於理解這些頁面不可操作？ | 是 |
| 5 | Evidence badge 是否有助於辨識 audit/evidence/recovery/demo evidence 類頁面？ | 是 |
| 6 | Platform Ops 是否比之前更緊湊、可讀？ | 是 |
| 7 | Delivery Package 是否仍在 Platform Ops？ | 是 |
| 8 | Deliveries group 是否沒有被加入未授權的新功能？ | 是 |
| 9 | 所有原本可進入的頁面是否仍可從 navigation 進入？ | 是 |
| 10 | 是否沒有 fake buttons / fake controls？ | 是 |
| 11 | 是否沒有 Slice 2 的 microcopy / field-label 變更？ | 是 |
| 12 | 是否沒有 backend/API/DB/workflow 行為變更？ | 是 |

**Expected result: 全部 12 項應為「是」。**

### Accepted out-of-scope items

```text
1. 不修 SPA deep-link fallback -- 已知既有平台限制，另案追蹤，不在本次驗證範圍。
2. 不做 two-way URL sync -- 未實作，符合預期。
3. 不做 FE.1D Slice 2 -- 未實作，符合預期。
4. 不實作 Delivery / Reminder / Notifications / Pipeline 真功能 -- 維持 placeholder，符合預期。
```

### Rollback instruction if Product Owner rejects

```text
If the Product Owner finds any checklist item unsatisfactory, Claude Code will restore the
pre-deployment bundle from the rollback backup recorded in
docs/test/step66ui4-fe1d-s1-ui-validation-preview-deployment-record.md (a masked, temporary
in-container copy of the pre-swap index-A5KtnMef.js / index-tDSVCSFZ.css assets), with no
container rebuild/restart required -- the same low-risk swap mechanism used for the deployment
itself, reversed. No merge has occurred, so no revert to `main` is needed regardless of the
Product Owner's verdict.
```

## Statement

Preview deployment record. Frontend implementation deployed to test runtime for Product Owner UI
validation. `main` NOT merged. No backend/API/database/workflow change. No new endpoint. No new
route. No production/external action. FE.1D Slice 2 remains unauthorized. Admin Console SPA
deep-link fallback gap remains an existing platform limitation, not fixed by this document.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
