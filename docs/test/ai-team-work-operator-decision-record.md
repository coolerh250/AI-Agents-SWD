# AI Agents Team Work — Operator Decision Record (Step 66A.2)

> **Documentation only. No UI implementation, no backend change, no runtime change, no workflow
> execution, no external action, no production action.**
> **These are the operator's own decisions, recorded verbatim. Claude Code did not change them.**

Authoritative record of the operator's (Zachary) decisions on the Step 66A.1 decision register D1–D14,
made 2026-07-08. This locks the AI Agents Team Work MVP product direction and feeds the Step 66A.3
blueprint. Where a decision differs from Claude Code's earlier non-final recommendation, the
**operator's decision governs**.

## D1–D14 recorded decisions

| ID | Decision | Recorded value | vs. earlier recommendation |
| --- | --- | --- | --- |
| **D1** | Role permissions model | **B — Conservative RBAC** | matches |
| **D2** | MVP task-type priority | **B — software delivery + documentation + platform improvement** | matches |
| **D3** | Intake channel order | **B — Admin Console + API first; Slack/Discord second; Telegram third** | matches |
| **D4** | Clarification timeout | **B — reminder, then blocked / clarification_expired** | **operator override** (rec was wait-forever) |
| **D5** | Delivery acceptance transitions | **B — Delivery Ready → Accept / Reject / Request Changes / Re-run QA / Escalate / Archive** | matches |
| **D6** | Fixed team boundary | **B — fixed team covers software + docs + platform improvement; other types enter intake/research queue** | matches |
| **D7** | Notification routing | **B — Admin Console + Discord first; Slack next; Telegram later** | matches |
| **D8** | Approval / DLQ / Retry UI priority | **A — Approvals + DLQ/Retry both P0** | matches |
| **D9** | Chat-style Agent Workroom | **A — full chat-style Agent Workroom is in MVP** | **operator override** (rec was phased/later) |
| **D10** | Web research governance | **C — whitelist sources only** (+ propose top-10 for operator confirmation) | operator refinement |
| **D11** | Request Changes behavior | **C — small changes same workflow; major changes new workflow** | **operator override** (rec was same-workflow) |
| **D12** | Re-run QA limits | **B — PM / Eng Lead / Reviewer may re-run; max 3 per delivery** | matches |
| **D13** | Retry / manual replay permission | **C — Platform Admin / Agent Operator only** | matches |
| **D14** | Non-software tasks in MVP UI | **B — UI shows task-type selection; non-software tasks go through intake / planning / documentation first** | matches |

## Decision detail (operator meaning, recorded)

- **D1 (B — Conservative RBAC):** general users create + track tasks; PM / Engineering Lead / Reviewer
  review + accept delivery; Platform Admin / Agent Operator manage retry, replay, integrations, and
  higher-risk operations. Exact permission matrix is a recommended default for 66A.3, not finalized here.
- **D2 (B):** MVP is not limited to software; first-class MVP task types = software delivery,
  documentation, platform improvement. Other AI-agent-capable types stay in the taxonomy / roadmap.
- **D3 (B):** Admin Console + API = P0; Slack + Discord = P1; Telegram = P2. No channel dropped.
- **D4 (B):** pause → notify → wait; after timeout the task transitions to **blocked /
  clarification_expired**. Recommended default: first reminder after **24h**, blocked/expired after
  **72h**, **admin-configurable**.
- **D5 (B):** full action set — Accept, Reject, Request Changes, Re-run QA, Escalate, Archive.
- **D6 (B):** MVP fixed Software Delivery Team handles software / docs / platform improvement; other
  task types are accepted at intake/planning level but do not run the full delivery pipeline until
  future templates exist.
- **D7 (B):** Admin Console notification center P0; Discord lifecycle notification P1 (reuse the Step
  65-validated Discord rail); Slack after Discord; Telegram later.
- **D8 (A):** close the Step 65 operator-flagged UX gaps early — Approvals UI **and** DLQ/Retry Admin
  Console are both **P0**.
- **D9 (A):** MVP must include a **real chat-style workroom** (not only forms/static comments),
  supporting agent clarification questions, human replies, agent progress messages, request-changes
  discussion, delivery-review discussion, pause/resume context, and audit-trail linkage. 66A.3 must
  separate the **minimum viable chat workroom** from later advanced features (see blueprint inputs).
- **D10 (C):** web research is required but governed by an **operator-approved source whitelist**. A
  proposed **top-10** source whitelist is provided for operator review (see
  `ai-team-work-web-research-source-whitelist-proposal.md`); it is a **proposal pending operator
  confirmation**, not an approved final whitelist, and **not** evidence of live research. The runtime
  currently has **no browsing/search connector** — a missing capability; no web browsing is performed.
- **D11 (C):** Request Changes classifies change size — **small** changes continue as a revision cycle
  within the same work item / workflow; **major** changes create a new workflow under the same or a
  linked work item. 66A.3 defines the classification criteria.
- **D12 (B):** Re-run QA is bounded — only PM / Engineering Lead / Reviewer may trigger; default limit
  **3 per delivery**; an admin override may be proposed later (not finalized).
- **D13 (C):** Retry / manual DLQ replay is a high-risk operator action — **Platform Admin / Agent
  Operator only**; general users, requesters, PMs, and reviewers cannot trigger DLQ replay.
- **D14 (B):** MVP UI shows task-type selection; software / documentation / platform improvement have
  first-class MVP paths; non-software tasks are accepted into intake / planning / documentation flow
  first; full specialized pipelines for non-software tasks are future work.

## Plain statements (for verifier)

- Operator decisions D1 through D14 are recorded exactly as the operator provided them.
- D7 is B. D9 is A. D10 is C. D11 is C.
- Claude Code did not change operator decisions.
- No UI implementation, no backend implementation, no runtime change, no workflow execution occurred.
- No external action occurred and no production action occurred.
- The web research top-10 source list is a proposal pending operator confirmation, not an approved
  final whitelist, and not evidence of live research.

---
_Non-production only. No production action. No production data._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
