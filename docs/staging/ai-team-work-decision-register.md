# AI Agents Team Work — Decision Register (Step 66A.1)

> **Planning / discovery only. No UI implementation. No production action.**
> **Claude Code did not finalize any product decision beyond the six operator-provided directions; all recommendations below are non-final and require operator review.**

The six operator-provided directions (D1 users, D2 task types, D3 channels, D4 clarification, D5
delivery actions, D6 fixed team) are **integrated as requirements**. The items below are the detailed
sub-decisions still needed to reach a final UX blueprint (66A.3).

| ID | Question | Operator context | Options | Recommendation (NON-FINAL) | Impact if deferred | Answer before 66A.3? |
| --- | --- | --- | --- | --- | --- | --- |
| **D1** | Detailed role permissions for the multi-role model | D1: multi-role | (a) recommended default matrix (b) stricter (c) looser | adopt default matrix in `user-role-model.md`, tighten retry/secret mgmt | RBAC ambiguity blocks 66B/66D | **yes** |
| **D2** | MVP task-type priority within the broad taxonomy | D2: all AI-capable tasks | (a) software-only MVP (b) +docs/platform (c) +research | software delivery + docs + platform-improvement for MVP | scope creep in MVP | **yes** |
| **D3** | Intake channel implementation order | D3: Console+Slack+Discord+Telegram+API | (a) Console+API first (b) +Discord (c) all at once | Console+API P0 → Slack/Discord P1 → Telegram P2 | rework if built out of order | **yes** |
| **D4** | Clarification timeout behavior | D4: pause/notify/wait | (a) wait forever (b) escalate after N (c) auto-cancel after N | wait-forever MVP; add escalate pre-prod (ties gap #2) | stuck tasks with no policy | **yes** |
| **D5** | Delivery acceptance state transitions | D5: Accept/Reject/Request-Changes/Re-run-QA | confirm transition table in delivery model | adopt table in `delivery-acceptance-model.md` | 66D acceptance gate blocked | **yes** |
| **D6** | Fixed Software Delivery Team scope boundaries | D6: fixed team MVP | (a) software+docs+platform (b) software-only | software+docs+platform; others → "not supported yet" | unclear team scope | **yes** |
| **D7** | Notification channel priority & routing | — | (a) Console-only P0 (b) +Discord (c) all | Console P0 + Discord P1 (existing rail); per-role routing | noisy/insufficient notifications | no (can start 66G with default) |
| **D8** | Approval / DLQ / Retry UI priority | Step 65 gaps #6/#7 | (a) both P0 (b) approvals first (c) DLQ first | both P0 (close operator-flagged gaps first) | operator gaps persist | **yes** |
| **D9** | Is a chat-style agent workroom MVP or later (66C)? | operator wants agent interaction | (a) MVP (b) 66C phased (c) later | phased 66C: clarification-first, chat later | interaction feels incomplete | no (66C decides) |
| **D10** | Web research governance policy | D2 web research | (a) no connector MVP (b) governed rail later | no connector in MVP; governed rail later (off by default) | research tasks stay blocked | no (documented gap) |
| **D11** | Request Changes: same workflow or new workflow | D5 | (a) same+note (b) new linked workflow | same workflow + change-request note for MVP | acceptance-loop ambiguity | **yes** |
| **D12** | Re-run QA behavior & limits | D5 | (a) cap ≤3 (b) unlimited (c) cost-gated | cap ≤3, eng-lead/agent-op only, audit each | cost / loop risk | **yes** |
| **D13** | Who can trigger retry / manual replay | Step 65 governance | (a) admin/agent-op only (b) +PM | admin + agent-operator only (governed, audited) | governance risk | **yes** |
| **D14** | Non-software tasks in MVP UI or later via templates | D2/D6 | (a) MVP UI (b) later via templates | later via templates; MVP fixed team only | MVP scope creep | **yes** |

## Summary buckets

- **Must decide before 66A.3:** D1, D2, D3, D4, D5, D6, D8, D11, D12, D13, D14.
- **Can decide during 66B/66G:** D7.
- **Can defer (documented):** D9 (66C), D10 (web connector future).

## Statement

These are open decisions for the operator. Claude Code did **not** finalize them. No UI was
implemented; no workflow ran; no external action; no production action.

---
_Non-production only. No production action. No production data._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
