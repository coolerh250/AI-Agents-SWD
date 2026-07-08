# AI Agents Team Work — Interaction Model Discovery & Decision Brief (Step 66A.1)

> **Planning / discovery only. No UI implementation. No workflow execution. No external action. No production action.**
> **Claude Code did not decide operator product decisions; recommendations below are non-final and require operator review.**

Defines the product interaction model for **AI Agents Team Work** — how a human manager assigns work
to an AI agent team, interacts with agents, and receives/accepts delivery — building on the Step 65
platform layer. This is the umbrella brief; each domain has its own detailed model doc.

## 1. Why this stage exists

Step 65 accepted the **platform** functional layer (`PASS_WITH_ACCEPTED_GAPS`): core engine,
5-agent pipeline, controlled GitHub/Discord/LLM rails, and governance controls — all validated with
`production_executed_true_count=0`. But the operator cannot yet:

- interact with AI agents from a UI / chat,
- assign tasks from the UI,
- receive a complete delivery result,
- manage the work like an **AI Agents Team Work** team.

Step 66 closes that product gap. Step 66A.1 is **discovery only** — models, options, and a decision
register; **no implementation**.

## 2. Operator decisions already provided (integrated as requirements, not re-decided)

| # | Decision | Integrated as |
| --- | --- | --- |
| D1 | Primary users: **multi-role** | `ai-team-work-user-role-model.md` (8 roles) |
| D2 | Task types: **all AI-agent-capable tasks** (not software-only) incl. web research | `ai-team-work-task-type-taxonomy.md` |
| D3 | Intake: **Admin Console + Slack + Discord + Telegram + API** | `ai-team-work-multi-channel-intake-model.md` |
| D4 | Clarification: **pause, notify, wait for human** | `ai-team-work-agent-clarification-model.md` |
| D5 | Delivery: **Accept / Reject / Request Changes / Re-run QA** (+ Escalate / Archive) | `ai-team-work-delivery-acceptance-model.md` |
| D6 | Agent team MVP: **fixed Software Delivery Team** first | `ai-team-work-agent-team-model.md` |

These six are **operator-provided direction** and are not re-opened. Detailed sub-decisions derived
from them are tracked in `ai-team-work-decision-register.md` (D1–D14).

## 3. Analysis domains (each has a dedicated doc)

1. Multi-role user model — `ai-team-work-user-role-model.md`
2. Task type taxonomy — `ai-team-work-task-type-taxonomy.md`
3. Multi-channel intake model — `ai-team-work-multi-channel-intake-model.md`
4. Agent clarification / pause / resume model — `ai-team-work-agent-clarification-model.md`
5. Delivery inbox & acceptance gate model — `ai-team-work-delivery-acceptance-model.md`
6. Agent team model (fixed MVP + future templates) — `ai-team-work-agent-team-model.md`
7. Lifecycle notification model — `ai-team-work-lifecycle-notification-model.md`
8. Operator Action Center model — `ai-team-work-operator-action-center-model.md`
9. Web research capability model — `ai-team-work-web-research-capability-model.md`
10. Current gap analysis vs. backend — `ai-team-work-current-gap-analysis.md`
11. Decision register (D1–D14) — `ai-team-work-decision-register.md`
12. Step 66 roadmap proposal — `ai-team-work-step66-roadmap-proposal.md`

## 4. Interaction model at a glance (proposed, non-final)

```
Manager (Admin Console / Slack / Discord / Telegram / API)
   │  assign task
   ▼
Task record ──► Fixed Software Delivery Team (intake→requirement→development→qa→devops)
   │                     │
   │                     ├─ needs clarification? → PAUSE → notify human → wait → resume
   │                     └─ governed actions → approval gate (existing approval-engine)
   ▼
Agent Workroom (conversation / clarification / discussion, operator-visible)
   ▼
Delivery Inbox ──► Delivery detail (requirement, implementation, QA, draft PR, cost, audit, risks)
   ▼
Acceptance gate: Accept / Reject / Request Changes / Re-run QA / Escalate / Archive
   ▼
Operator Action Center (approvals, clarifications, deliveries, failures, DLQ/retry, incidents)
```

## 5. Web research capability — capability gap flagged

The operator requires tasks that **collect the latest AI-Agents-Team-Work-related information online**.
The current runtime has **no browsing / web-search connector** wired into the agent pipeline. This is
recorded as a **missing capability / future connector requirement** (see
`ai-team-work-web-research-capability-model.md`), not assumed to exist. No web capability is
fabricated.

## 6. What this stage did NOT do

- No UI was implemented.
- No workflow was executed for product behavior.
- No external action (GitHub / Discord / Slack / Telegram / LLM live) occurred.
- No production action occurred.
- No product decision was finalized by Claude Code beyond the six operator-provided decisions;
  all recommendations are non-final and marked for operator review.

---
_Non-production only. No production action. No production data._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
