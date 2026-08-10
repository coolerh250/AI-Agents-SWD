# Step 66D-DESIGN — Existing Admin Console UI / Route Inventory (MEASURED)

> **Read-only inventory. No frontend source modified. Reading frontend source for inventory is not
> frontend implementation. `production_executed_true_count: 0`.**

```text
CANONICAL_BASELINE:  main 9c5210d190b82b76575ba8d456b5d2005c2867d2
GOVERNANCE:          MEASURED_COUNTS_ONLY -- every count below has a stated source
SOURCES READ:        apps/admin-console/src/App.tsx
                     apps/admin-console/src/components/Nav.tsx
                     apps/admin-console/src/pages/*.tsx
                     apps/admin-console/src/components/*.tsx
```

## 1. Measured counts and their sources

| Count | Value | Source (deterministic) |
| --- | --- | --- |
| Routes declared | **44** | regex `<Route\s+path="([^"]+)"` over `App.tsx` |
| Routes rendering `PlaceholderPage` | **12** | per-`<Route>` block split over `App.tsx`, matching blocks containing `PlaceholderPage` |
| Routes with a real page component | **32** | 44 − 12 (same parser) |
| Navigation items | **40** | regex `to:\s*"..",\s*label:\s*".."` over `Nav.tsx` |
| Navigation groups | **7** | regex `id:\s*"..",\n\s*label:\s*".."` over `Nav.tsx` |
| Nav badges: `Read-only` | **14** | regex `badge:\s*"([\w-]+)"` over `Nav.tsx` |
| Nav badges: `Soon` | **12** | same |
| Nav badges: `Evidence` | **8** | same |
| Page component files | **33** | `glob apps/admin-console/src/pages/*.tsx` |
| Shared component files | **16** | `glob apps/admin-console/src/components/*.tsx` |
| Semantic mutation surfaces (pages) | **5** | per-method write classification + transitive import/call trace (see §1.1) |

Parser used: a single deterministic Python script over the two source files plus two globs, and the
semantic write-surface tracer in §1.1. No count in this design package was hand-estimated or taken
from conversation.

### 1.1 Correction — semantic mutation-surface inventory (was 7, is 5)

The original inventory reported **7** using a text grep
(`grep -rlE 'apiPost|POST|taskApi\.(submit|create)|mutation'`). That grep is not a semantic
method: it matched read-only pages that merely mention `POST` in prose/comments or call read
methods on a client module that happens to contain a write helper.

The corrected method (used by the verifier) is deterministic and semantic:

```text
1. strip comments from every apps/admin-console/src/**/*.ts(x) file
2. identify PRIVATE WRITE HELPERS -- functions whose body sets method: "POST"|"PATCH"|"PUT"|"DELETE"
   (including the `const verb = "POST"; ... method: verb` indirection)
3. identify PUBLIC WRITE METHODS -- exported API-object methods / functions that call a write helper
4. mark a page as a mutation surface if it calls a public write method directly OR transitively
   through an imported local component
```

Measured write clients and their public write methods:

| Write client | Private write helper | Public write methods |
| --- | --- | --- |
| `apps/admin-console/src/tasks/taskClient.ts` | `taskPost` | `create`, `submit` |
| `apps/admin-console/src/tasks/workroomClient.ts` | `workroomPost` | `postMessage`, `createClarification`, `answerClarification` |
| `apps/admin-console/src/operator/actionClient.ts` | `post` | `accept`, `reject`, `requestChanges`, `addNote`, `rerunVerification`, `runVerification`, `confirmAndExecute`, `issueConfirmation`, `createProject`, `createWorkItem`, `dispatchWorkItem`, `testLogin`, `logout` |

Canonical mutation surfaces — **exactly 5**:

| Source path | Write client | Write methods reached | Target entity | Safety classification |
| --- | --- | --- | --- | --- |
| `apps/admin-console/src/pages/TaskNew.tsx` | `taskClient` | `create` | task | test-role header auth; non-dispatching (`dispatch_enabled: false`); no production action |
| `apps/admin-console/src/pages/TaskDetail.tsx` | `taskClient` | `submit` | task | non-dispatching; stops at `intake_review`; no production action |
| `apps/admin-console/src/pages/TaskWorkroom.tsx` | `workroomClient` | `postMessage`, `createClarification`, `answerClarification` | workroom message / clarification | no workflow dispatch or resume |
| `apps/admin-console/src/pages/MultiProjectDelivery.tsx` | `actionClient` | `createProject`, `createWorkItem`, `dispatchWorkItem` | project / work item (Step 57) | operator session + CSRF + reason + audit; `production_effect` routes to `waiting_approval` |
| `apps/admin-console/src/pages/OperatorConsole.tsx` | `actionClient` (via `OperatorReviewPanel`) | `accept`, `reject`, `requestChanges`, `addNote`, `rerunVerification` (transitive) | legacy `DeliveryPackage` review | operator session + CSRF + two-step confirmation nonce |

Removed false positives (they contain no write-method call; the grep matched prose such as
"no mutation action" or a read-only client import):

```text
apps/admin-console/src/pages/BackupDr.tsx
apps/admin-console/src/pages/IdentityPosture.tsx
apps/admin-console/src/pages/RuntimeBaseline.tsx
apps/admin-console/src/pages/SecurityPosture.tsx
```

False negative recovered: `OperatorConsole.tsx` — missed by the original grep because it delegates
its writes to the imported `OperatorReviewPanel` component. This is also the source of gap
**DG-16** (see the duplication analysis in `step66d-design-route-and-drilldown-map.md` §4.1).

Comment text such as `NO mutation`, `no mutation action` or `not production data mutation` cannot
produce a false positive under the corrected method, because comments are stripped before analysis.

## 2. Placeholder routes (measured — all 12)

```text
/approvals                        /clarification-reminders
/clarifications                   /delivery-detail
/delivery-inbox                   /dlq-retry
/notifications                    /settings/approval-policy
/settings/identity-session        /settings/integrations
/settings/roles-permissions       /settings/web-research-sources
```

Each renders `PlaceholderPage` → `PlaceholderPanel` ("Not yet available." / "Requires Step X." /
"No workflow action available."). **None is an implemented product surface.**

## 3. 66D-relevant route existence check (measured)

| Semantic surface needed by 66D | Route present? | State |
| --- | --- | --- |
| Delivery Inbox | yes — `/delivery-inbox` | **PLACEHOLDER** |
| Unified Control Center | no — `grep 'control-center' App.tsx` → 0 matches | **PLANNED / NOT IMPLEMENTED** |
| Delivery Review (submission-scoped) | no — `grep 'delivery-submissions' App.tsx` → 0 matches | **PLANNED / NOT IMPLEMENTED** |
| `/delivery-detail` (id-less) | yes | **PLACEHOLDER**, superseded by the submission-scoped review route |

## 4. Semantic surface inventory required by §8 of the stage prompt

Actual names/paths from source (not from conversation):

| Semantic surface | Actual route | Actual page component | Implemented state | Write capability observed |
| --- | --- | --- | --- | --- |
| Delivery (multi-project work items) | `/delivery` | `MultiProjectDelivery.tsx` | IMPLEMENTED | yes — existing audited mutations (Step 57), outside 66D scope |
| Agent Executions | `/agent-executions` | `AgentExecutions.tsx` | IMPLEMENTED | none observed |
| Task Graph | `/task-graph` | `TaskGraph.tsx` | IMPLEMENTED | none observed |
| QA / Code Evidence | `/qa-code` | `QaCode.tsx` | IMPLEMENTED | none observed |
| Audit Evidence | `/audit-evidence` | `AuditEvidence.tsx` | IMPLEMENTED | none observed |
| Safety Center | `/safety` | `SafetyCenter.tsx` | IMPLEMENTED | none observed |
| Dead Letter / Retry | `/dlq-retry` | `PlaceholderPage` | **PLACEHOLDER** | none |
| Approvals | `/approvals` | `PlaceholderPage` | **PLACEHOLDER** | none |
| Metrics / Cost | `/metrics`, `/cost-llm` | `OperationalMetrics.tsx`, `CostLlmGovernance.tsx` | IMPLEMENTED | none observed |
| Project / Work Item | `/projects`, `/projects/:projectId` | `Projects.tsx`, `ProjectDetail.tsx` | IMPLEMENTED | none observed |
| Legacy Delivery Package | `/delivery-package` | `DeliveryPackage.tsx` | IMPLEMENTED | legacy semantics unchanged (66D-D04) |
| Operator Console | `/operator` | `OperatorConsole.tsx` | IMPLEMENTED | existing controlled/audited operator actions |
| Task surfaces | `/tasks`, `/tasks/new`, `/tasks/:taskId`, `/tasks/:taskId/workroom` | `TaskList/TaskNew/TaskDetail/TaskWorkroom` | IMPLEMENTED | yes (`TaskNew`, `TaskDetail`) — **non-dispatching**, `dispatch_enabled: false` (66D-D03) |

## 5. Navigation structure (measured — 7 groups, 40 items)

```text
Overview (2)        Dashboard, Notifications[Soon]
Team Work (4)       Tasks, Create Task, Clarifications[Soon], Reminder / Expiry[Soon]
Deliveries (2)      Delivery Inbox[Soon], Delivery Detail[Soon]
Operator Center (5) Operator Console, Incidents, Agent Executions[Evidence],
                    Approvals[Soon], DLQ / Retry[Soon]
Governance (2)      Safety Center[Read-only], Audit Evidence[Evidence]
Platform Ops (20)   collapsed, compact; Projects, Work Items[Read-only], Task Graph[Evidence],
                    QA / Code[Evidence], Design Review[Evidence], Workspace Execution[Evidence],
                    Mini Delivery Pilot[Evidence], Delivery Package[Evidence],
                    Regression[Read-only], Cost / LLM[Read-only], Runtime Baseline[Read-only],
                    Identity Posture[Read-only], Secret Posture[Read-only], Security[Read-only],
                    Operational Metrics[Read-only], Sandbox GitHub[Read-only],
                    Release Governance[Read-only], Backup & DR[Read-only],
                    Production Readiness[Read-only], Rollout Review[Read-only]
Settings (5)        Roles & Permissions[Soon], Identity / Session[Soon], Integrations[Soon],
                    Web Research Sources[Soon], Approval Policy[Soon]
```

`Deliveries` currently contains only the two `Soon` placeholders — consistent with 66D not being
implemented. `/demo-evidence` exists as a route but is **not** in the navigation (diagnostic only).

## 6. Findings that constrain the design

```text
F-1  The Unified Control Center route does not exist. It must be created by FE1 (not by this stage).
F-2  /delivery-inbox exists but is a placeholder; FE1 replaces the element, not the path.
F-3  There is no submission-scoped review route; /delivery-detail cannot address a submission.
F-4  Router convention is `:colonCamelCase`; the canonical semantic routes are expressed in it.
F-5  Existing Task write surfaces are non-dispatching and must not be re-described as the Agent
     execution entry point (66D-D03-R3).
F-6  `CalmSafetyPosture` already exists and is the reuse candidate for the Safety Summary.
F-8  /operator already hosts a legacy accept/reject review surface (OperatorReviewPanel, addressed
     by packageId). Its contract differs from the 66D DeliverySubmission model on every material
     axis; Delivery Review must remain the single canonical Product Owner Decision entry point.
     Tracked as DG-16 (analysis in step66d-design-route-and-drilldown-map.md section 4.1).
F-7  No 66D API client exists in apps/admin-console/src/api or src/tasks; every 66D endpoint is
     NOT IMPLEMENTED.
```

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
