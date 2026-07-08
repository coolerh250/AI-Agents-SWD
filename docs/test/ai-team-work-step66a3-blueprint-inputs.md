# AI Agents Team Work — Step 66A.3 Blueprint Inputs (Step 66A.2)

> **Documentation / blueprint-preparation only. No UI implementation, no backend change, no runtime
> change, no workflow execution, no external action, no production action.**

Prepares inputs for the Step 66A.3 Final UX Blueprint & Implementation Scope. Grounded in the recorded
operator decisions (`ai-team-work-operator-decision-record.md`), the MVP scope lock
(`ai-team-work-mvp-scope-lock.md`), and the current-backend gap analysis
(`ai-team-work-current-gap-analysis.md`). Nothing here is built; recommendations remain for operator
review at 66A.3.

## 1. Finalized operator decisions (D1–D14)

See `ai-team-work-operator-decision-record.md` for the authoritative record. Summary:
D1=B, D2=B, D3=B, D4=B, D5=B, D6=B, D7=B, D8=A, D9=A, D10=C, D11=C, D12=B, D13=C, D14=B.

## 2. Remaining open questions (for 66A.3)

- **D11 classification criteria** — the concrete rule for "small" vs "major" change (e.g. scope of
  files/requirements touched, QA impact, effort estimate). Needs a definition at 66A.3.
- **D4 timeout defaults** — confirm 24h reminder / 72h expire and the admin-config surface.
- **D1 exact permission matrix** — Conservative RBAC direction is set; the per-capability matrix needs
  operator sign-off at 66A.3.
- **D10 whitelist** — operator confirmation of the proposed top-10 sources, and connector authorization
  (currently a missing capability).
- **D9 workroom minimum-viable boundary** — confirm the MVP feature cut vs. later advanced features.
- **D12 admin override** — whether an admin may exceed the 3-re-run limit (proposed, not finalized).

## 3. MVP scope lock / out-of-scope

See `ai-team-work-mvp-scope-lock.md` (in-scope 11 items + out-of-scope list). Not repeated here.

## 4. Required backend changes (proposed)

Most governance backend already exists (approval-engine, policy-engine, retry-scheduler/DLQ, audit,
Discord rail); the gaps are product/UX surfaces and a few new endpoints/models.

- **Task assignment service/API** — accept operator-assigned tasks from Console/API into the existing
  intake path (build on comm-gateway intake).
- **Agent Workroom (chat) backend** (D9) — a conversation model + message stream per task: agent
  questions, human replies, progress events, request-changes + delivery-review threads; pause/resume
  state; audit linkage. Likely reuses the existing per-hop "discussion" records + a new message store.
- **Clarification state machine** (D4) — `clarification_needed` / `waiting_human` / `resumed` +
  timeout job → `blocked` / `clarification_expired` (reminder 24h, expire 72h, configurable).
- **Delivery inbox + acceptance backend** (D5/D11/D12) — delivery package assembly; acceptance actions
  with state transitions; Request-Changes size classification (small=same workflow, major=new/linked);
  Re-run QA counter (≤3) enforced.
- **Approvals + DLQ/Retry surfaces** (D8) — expose existing approval-engine + retry-scheduler via
  Operator Action Center endpoints; enforce D13 (replay = Platform Admin / Agent Operator only).
- **RBAC enforcement** (D1) — role → capability checks across the above.
- **Web research connector** (D10) — **not built in MVP execution**; design a future controlled rail
  (whitelist, budget, audit, citation). Flagged missing capability.

## 5. Required frontend pages (proposed)

- Task assignment / intake form (task-type selection — D14).
- Agent Workroom (chat-style) — D9.
- Delivery Inbox + Delivery detail (acceptance actions) — D5.
- Approvals page — D8 (closes Step 65 gap #7).
- DLQ / Retry Admin Console page — D8 (closes Step 65 operator-flagged gap #6).
- Operator Action Center (aggregated queues).
- Notification center (in-app) — D7.
- Role-aware navigation / visibility — D1.

## 6. Required APIs (proposed)

- `POST` task assignment; `GET` task list/detail (role-scoped).
- Workroom: `GET` messages, `POST` message/reply, clarification answer, resume.
- Delivery: `GET` inbox/detail; `POST` accept / reject / request-changes / re-run-qa / escalate /
  archive.
- Approvals: `GET` pending; `POST` approve/reject (existing approval-engine, surfaced).
- DLQ/Retry: `GET` queue; `POST` replay (role-gated to Platform Admin / Agent Operator — D13).
- Notifications: `GET` feed; mark-read.
- (Existing read-only `/operations/*` reused where possible.)

## 7. Required data-model additions (proposed)

- Workroom conversation + message entities (task-linked, author, type, timestamp, audit ref).
- Clarification state + timeout fields on task/work item.
- Delivery acceptance state + action history; Re-run-QA count; change-size classification on
  Request-Changes.
- Role assignments (user ↔ role) for RBAC.
- Notification records (event, target, read state) — with sensitive-data redaction.
- Web-research whitelist config (future; not populated in MVP).

## 8. Required notification changes (proposed)

- Unified lifecycle events (per `ai-team-work-lifecycle-notification-model.md`) routed to Admin
  Console (P0) + Discord (P1) per D7; Slack later; Telegram later.
- Redaction rules: no secrets/tokens/raw payloads/customer data — summaries + link-backs only.
- Reuse the Step 65-validated Discord rail; no send in test posture unless separately authorized.

## 9. Required governance changes (proposed)

- RBAC (D1) enforced on assignment, acceptance, approvals, retry/replay.
- Retry/replay restricted to Platform Admin / Agent Operator (D13).
- Re-run QA bounded to 3 (D12).
- Clarification timeout → blocked/expired (D4) as a safe, auditable transition.
- Web research whitelist-only + human approval when research affects a decision (D10).
- All new actions emit audit events; `production_executed_true_count=0` invariant preserved.

## 10. Test strategy (proposed)

- Unit/contract tests for each new API + state machine (clarification, acceptance, Request-Changes
  classification, Re-run-QA limit, RBAC gates, replay permission).
- Frontend component/integration tests (vitest) for each new page; role-visibility tests.
- E2E (test host `10.0.1.31`, `aiagents-test`): assign → agents work → clarification → workroom →
  delivery → accept/request-changes, all mock/dry-run, `prod_exec=0`.
- Governance tests: unauthorized role blocked; replay blocked for non-admin; Re-run-QA >3 blocked.
- Per-stage verifier + `pytest` + ruff/black/mypy + secret scan, as in prior stages.

## 11. Acceptance criteria (proposed, operator-owned)

- A manager can assign a task from the Console/API, watch the fixed team work, converse in the
  workroom, answer clarifications, and Accept / Reject / Request Changes / Re-run QA a delivery.
- Approvals and DLQ/Retry are operable from the Admin Console (Step 65 gaps #6/#7 closed).
- RBAC, replay permission, and Re-run-QA limits enforced; timeouts behave per D4.
- No external send / LLM / production action; `prod_exec=0`; operator-visible evidence.
- **Operator (not Claude Code) decides product acceptance** at the end of the build track.

## 12. Implementation risks

- **D9 full chat workroom raises MVP complexity** — realtime/message model, ordering, audit linkage;
  mitigate by cutting a minimum-viable workroom first.
- **D11 size classification** ambiguity → inconsistent routing; needs a crisp rule.
- **Web research connector missing** — research task types blocked until built + authorized.
- **RBAC breadth** across many surfaces → enforcement gaps; centralize checks.
- **Scope creep** from non-software task types → hold the D6/D14 boundary.

## Plain statements (for verifier)

- This document prepares Step 66A.3 blueprint inputs only.
- Finalized operator decisions D1–D14 are referenced; open questions are listed.
- No UI implementation, no backend implementation, no runtime change, no workflow execution occurred.
- No external action occurred; no production action occurred.

---
_Non-production only. No production action. No production data._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
