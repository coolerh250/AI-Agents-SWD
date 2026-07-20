# Product Owner Decision Record — Step 66UI.4-FE.1D-BOUNDARY

> **Decision record only. No runtime code changed by this document. No production action.**

## Authorization (verbatim)

```text
接受 Step 66UI.4-FE.1D-TECH-REVIEW 判定為 PASS_WITH_GAPS；PO 決策如下：
1. 維持目前 "+ Create task" 文案，不改為 "New task"。
2. 不在 FE.1D 將 delivery_package_ready_for_admin_console 改為 "Ready to publish"，此項 deferred 到
   66D Delivery 階段。
授權 Claude Code 依上述決策整理 FE.1D Codex Implementation Boundary；仍不得授權 Codex 實作，不得修改
frontend/backend/API/DB/workflow，不得新增 endpoint，不得部署。
```

## Recorded decisions

**1. Step 66UI.4-FE.1D-TECH-REVIEW accepted as PASS_WITH_GAPS.**
The Product Owner accepts the technical readiness review's verdict (`STEP66UI4_FE1D_TECHNICAL_
READINESS_VERIFY: PASS`, overall result `PASS_WITH_GAPS`) as-is. No re-review of the design or the
technical readiness assessment was requested.

**2. "+ Create task" remains unchanged.**
`TaskList.tsx`'s current button text `"+ Create task"` is NOT renamed to `"New task"`. This resolves
open item #2 from the technical readiness review (§6 of `claude-code-technical-readiness-review.md`)
in favor of the status quo. Every FE.1D slice (§6, §7 of `codex-implementation-boundary.md`)
excludes this rename.

**3. `delivery_package_ready_for_admin_console` rename deferred to 66D.**
The proposed rename to `"Ready to publish"` is NOT part of FE.1D. This resolves open item #5 from
the technical readiness review in favor of deferral rather than immediate confirmation of intended
meaning -- the semantic question itself remains open and is pushed to Step 66D (Delivery), where
the field's actual product context will be established. `delivery_package_ready_for_admin_console`
keeps its current label unchanged through the entirety of FE.1D.

**4. Codex is not authorized yet.**
This decision authorizes Claude Code to produce the FE.1D Codex Implementation Boundary
(`codex-implementation-boundary.md`) and its companion documents. It does not authorize Codex to
begin implementation. A separate, explicit, future Product Owner authorization is required before
any Codex implementation stage may begin.

**5. No runtime changes authorized.**
This decision does not authorize any change to `apps/**`, `services/**`, `infra/**`,
`migrations/**`, `database/**`, `helm/**`, `k8s/**`, or `.github/workflows/**`. No frontend,
backend, API, database, or workflow file may be touched by this stage or by any document it
produces.

**6. No deployment authorized.**
This decision does not authorize any deployment, to test runtime or otherwise. No merge of PR #12
(or any future implementation PR) is authorized by this decision.

## Effect on the technical readiness review's open items

| Review item (§6 of `claude-code-technical-readiness-review.md`) | Resolution |
| --- | --- |
| #2 "New task" vs "Create task" | Resolved: keep "+ Create task" (this record, item 2) |
| #5 `delivery_package_ready_for_admin_console` rename meaning | Resolved: deferred to 66D, not decided now (this record, item 3) |
| #1 Platform Ops subtitles | Unchanged -- already resolved by the review's own default-rule application (ALLOW); no Product Owner input required or given on this item |
| #1b Platform Ops visual sub-headers | Unchanged -- remains a Product-Owner-optional item; not addressed by this decision; defaults to the design's documented fallback (labels + markers + density only) per `codex-implementation-boundary.md` §8 |
| #3 Notifications "Planned" wording | Unchanged -- already resolved by the review's own default-rule application (ALLOW); no Product Owner input required or given on this item |
| #4 `dispatch_enabled` label conflict | Unchanged -- already correctly resolved in the design docs themselves; not a decision item |

## Statement

Decision record only. No runtime code changed by this document. No backend/API/database/workflow
change. No new endpoint. No deployment. No merge. No production/external action. Codex remains
unauthorized. FE.1D implementation remains unauthorized.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
