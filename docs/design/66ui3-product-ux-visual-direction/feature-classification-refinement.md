# Feature Classification Refinement — DESIGN-66UI.3

> Owner: Claude Design. Re-classifies the **deployed** navigation (7 groups, `main` @ `51ad83d`)
> into product-experience tiers, and flags which deployed components are too engineering-ish. This
> refines the 66UI.2 grouping; it does not change the IA.

## Classification tiers

### Core product experience (must feel like a product)

| Item | Deployed location | Note |
| --- | --- | --- |
| Dashboard / Overview | Overview | Should become attention-first, not metrics-first |
| Tasks (list) | Team Work | Triage-first, not a 10-col grid |
| Create Task | Team Work | Delegation framing, plain language |
| Task Detail | Team Work | Task header, not a raw object dump |
| Task Workroom | Team Work (contextual) | The centerpiece; human–AI-team collaboration |
| Clarifications | Team Work | Decision-request experience |

### Supporting governance (present, legible, calm — not dominant)

| Item | Deployed location | Note |
| --- | --- | --- |
| Safety Center | Governance | Reassurance-first posture, detail on demand |
| Audit Evidence | Governance | Human-readable events, hashes as detail |
| Safety status bar | Global (top of every page) | Highest-priority de-engineering target |

### Operator-only tools (first-class for operators, secondary for others)

| Item | Deployed location | Note |
| --- | --- | --- |
| Operator Console | Operator Center | Keep; light consistency pass |
| Incidents | Operator Center | Keep |
| Agent Executions | Operator Center | Feeds agent-activity presentation |
| Approvals, DLQ / Retry | Operator Center | Placeholder until 66D |

### Platform maintenance (must exist; must not define the product feel)

| Item | Deployed location | Note |
| --- | --- | --- |
| Projects, Projects/Work Items, Task Graph, QA/Code, Design Review, Workspace Execution, Mini Delivery Pilot, Delivery Package, Regression, Cost/LLM, Runtime, Identity/Secret/Security Posture, Sandbox GitHub, Release Governance, Backup/DR, Production Readiness, Controlled Rollout Review | Platform Ops (collapsed) | 20 pages; grouping-only, no redesign this round; keep visually quiet |

### Future placeholders (safe, non-misleading, coming later)

| Item | Deployed location | Gating |
| --- | --- | --- |
| Delivery Inbox, Delivery Detail | Deliveries | Step 66D |
| Reminder / Expiry | Team Work | Step 66C.4 |
| Approvals, DLQ / Retry | Operator Center | Step 66D |
| Roles & Permissions, Identity / Session | Settings | Step 66S |
| Integrations, Web Research Sources, Approval Policy | Settings | Coming later |
| Notifications | Overview | In-app only this round |

## Components that are too engineering-ish (deployed today)

| Component / page | Why it's too engineering | Tier it belongs to |
| --- | --- | --- |
| `SafetyStatusBar.tsx` | Raw 12 snake_case fields as `key: value`, grey, on every page | Supporting governance — must read as calm reassurance |
| `TaskDetail.tsx` `KeyValueTable` | Dumps the entire raw task object | Core product — must be a task header |
| `TaskWorkroom.tsx` message cards | Uniform log-style cards; no agent identity/turn-taking | Core product — the centerpiece |
| `TaskList.tsx` 10-column grid | Field-complete ticket grid; attention-blind | Core product — triage list |
| Audit evidence rows | Hashes/lengths foregrounded | Supporting governance — readable events |
| Task Detail safety panel | snake_case field list | Supporting governance — posture chip |
| `ExecutiveOverview` KPI cards | Metrics-first | Core product — attention-first |

## What this refinement does NOT change

- The 7-group IA and every route (66UI.2, deployed and PO-validated) — unchanged.
- Platform Ops membership — unchanged (grouping-only; Delivery Package stays under Platform Ops per
  the deployed, PO-validated state; see the PR #2 reconciliation note in
  `product-owner-discussion-guide.md`).
- Placeholder safety semantics — unchanged.

## Statement

Design classification only. No runtime code. No production action.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
