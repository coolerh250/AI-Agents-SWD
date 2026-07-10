# Step 66C.1 — Known Gaps

> **Documentation only. No production action.**

## Blocking (none)

No blocking gaps — 66C.1 PASS criteria met (see
`step66c1-workroom-clarification-api-foundation-report.md`). Operator validation: `READY_WITH_GAPS`
(see `step66c1-operator-api-validation-record.md`). Final status: Step 66C.1 — PASS. Operator
validation — READY_WITH_GAPS. Does not block 66C.2.

## Operator-assigned gap IDs (66C.1-V) and their future-stage assignment

| ID | Gap | Assigned to |
| --- | --- | --- |
| **G1** | Message visibility filtering not implemented | 66C.3 |
| **G2** | Clarification reminder / expiry scheduler not implemented | 66C.4 |
| **G3** | Per-task audit lookup endpoint not implemented | 66C.3 |
| **G4** | Project/team RBAC scoping not implemented | 66S |
| **G5** | Answered-twice guard lacks a dedicated test | 66C.3 |

These correspond to non-blocking items 9, 6, 7, 8, and 10 below respectively. See
`step66c1-operator-api-validation-record.md` §5 for the full 66C.2/66C.3/66C.4/66S plan.

## Non-blocking

1. **No Admin Console Workroom UI.** Explicitly out of scope for 66C.1 — deferred to 66C.2. No
   `dangerouslySetInnerHTML`/HTML-rendering of message bodies is permitted when that UI is built
   (security addendum, binding constraint — see `step66c1-rbac-audit-safety-record.md` §4.3).
2. **No real-time/websocket delivery.** Messages/clarifications are read via `GET .../workroom`
   only; there is no push/subscribe mechanism. Deferred to 66C.2+.
3. **No agent autonomy.** No agent ever posts a message or creates a clarification in 66C.1 — there
   is no agent connector. `sender_type: agent` and `message_type: agent_message` are modeled but
   unused until an agent integration exists.
4. **No LLM-generated clarification.** Clarifications in 66C.1 are human/operator-created only, per
   spec. LLM-assisted clarification generation is future work.
5. **No workflow resume.** Answering a clarification never resumes or dispatches a workflow —
   `resume_dispatch_enabled=false` always. Actual resume is a distinct, not-yet-built capability.
6. **No scheduler for reminder/expiry.** `reminder_at` (24h) and `due_at` (72h) are computed and
   stored at creation time, but nothing currently reads them to send a reminder or transition a
   clarification to `expired`. A scheduler/cron consumer is future work.
7. **No per-task audit lookup endpoint.** Carried over from 66B.1/66B.3 — `correlation_id` remains
   the intended future join key; no `GET .../audit` exists yet.
8. **No project/team RBAC scoping.** Only Requester is scoped to own-task; all other five roles are
   unscoped by task ownership (fallback, documented in
   `step66c1-rbac-audit-safety-record.md` §2 — not overclaimed as real project/team RBAC).
9. **No message-visibility filtering.** All four `visibility` values are modeled and
   CHECK-constrained, but the API always creates messages with `visibility: task_participants` and
   `GET .../workroom` returns all messages regardless of the caller's role — per-visibility
   filtering (e.g. hiding `audit_only` messages from non-auditor roles) is not implemented in
   66C.1.
10. **Answering an already-answered clarification returns `409`** but this exact case is not covered
    by a dedicated 66C.1 test (the guard mirrors the existing, tested `task_api.py` submit-state-guard
    pattern). Non-blocking; may be added in a later stage.
11. **Real identity/session/CSRF remains future work** — unchanged from 66B.1/66B.3, restated here
    for completeness (see `step66c1-rbac-audit-safety-record.md` §4.8).

## Deferred to 66C.2

Admin Console Workroom UI (with the mandatory no-`dangerouslySetInnerHTML` / plain-text-rendering
constraint), real-time/websocket delivery, operator validation of the visual workroom.

## Deferred to later stages

Agent autonomy / LLM-generated clarification, workflow resume, reminder/expiry scheduler (**G2** →
66C.4), per-task audit lookup (**G3** → 66C.3), project/team RBAC scoping (**G4** → 66S),
message-visibility filtering (**G1** → 66C.3), answered-twice guard test (**G5** → 66C.3), Delivery
Inbox (66D), Accept/Reject/Request Changes/Re-run QA (66D), Approvals/DLQ-Retry UI (66D/66G),
lifecycle notifications (66G), Slack/Discord/Telegram intake (66F), real identity/session model +
CSRF (**66S**).

## Statement

Operator response is READY_WITH_GAPS. No production action occurred. No workflow dispatch occurred.
No workflow resume occurred. No external action occurred. Gaps above are all non-blocking for the
66C.1 PASS criteria and are planned into 66C.3, 66C.4, and 66S.

---
_Non-production only. No production action. No production data._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
