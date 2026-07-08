# AI Agents Team Work — MVP Scope Lock (Step 66A.2)

> **Documentation only. No UI implementation, no backend change, no runtime change, no external action,
> no production action.**
> **Scope locked from the operator's D1–D14 decisions (see `ai-team-work-operator-decision-record.md`).**

## In-scope (MVP)

Derived directly from the recorded operator decisions:

1. **Multi-role AI Agents Team Work experience** — Conservative RBAC (D1).
2. **Admin Console + API intake first** (D3, P0).
3. **Discord lifecycle notification first among chat channels**; Admin Console notification center P0
   (D7).
4. **Full chat-style Agent Workroom in MVP** (D9) — clarification Q&A, human replies, progress
   messages, request-changes + delivery-review discussion, pause/resume context, audit linkage.
5. **Clarification: pause / notify / wait / resume**, with timeout → **blocked / clarification_expired**
   (reminder 24h, expire 72h, admin-configurable) (D4).
6. **Delivery Inbox** + delivery detail package.
7. **Acceptance gate: Accept / Reject / Request Changes / Re-run QA / Escalate / Archive** (D5).
   - Request Changes size-classified: small → same workflow; major → new/linked workflow (D11).
   - Re-run QA: PM / Lead / Reviewer only, **max 3 per delivery** (D12).
8. **Fixed Software Delivery Team** (intake → requirement → development → qa → devops) (D6).
9. **Task-type selection in the UI** (D14); first-class MVP paths = **software delivery, documentation,
   platform improvement** (D2); non-software tasks accepted into intake / planning / documentation
   flow first.
10. **Approvals UI = P0** and **DLQ / Retry Admin Console = P0** (D8), plus Operator Action Center
    queues.
    - Retry / manual DLQ replay restricted to **Platform Admin / Agent Operator** (D13).
11. **Web research by operator-approved source whitelist only** (D10), **pending** a browsing/search
    connector capability (currently missing) and explicit authorization — not built in MVP execution.

## MVP scope-lock summary (for report)

- Users: multi-role, Conservative RBAC.
- Task types: software delivery + documentation + platform improvement (first-class); others via
  intake/planning.
- Intake: Admin Console + API first.
- Workroom: full chat-style workroom in MVP.
- Clarification: pause/notify/wait/resume + timeout to blocked/expired.
- Delivery: inbox + Accept/Reject/Request-Changes/Re-run-QA/Escalate/Archive.
- Team: fixed Software Delivery Team.
- Notifications: Admin Console + Discord first.
- Operator action center: Approvals + DLQ/Retry P0.
- Web research: whitelist-only, pending connector.

## Out-of-scope for MVP (unless the operator later changes a decision)

- Custom agent team composition.
- AI-suggested team composition.
- Full specialized pipelines for every non-software task type.
- Unrestricted web browsing; unapproved web sources.
- Telegram as P0; Slack as P0.
- Production deployment; production secret handling; production-effect execution.
- Automatic external writes without approval.

## Plain statements (for verifier)

- The MVP scope lock is defined from operator decisions D1–D14.
- An explicit out-of-scope list is documented.
- No implementation occurred; no runtime change; no external action; no production action.

---
_Non-production only. No production action. No production data._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
