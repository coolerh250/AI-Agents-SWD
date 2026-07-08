# AI Agents Team Work — Decision Register (Step 66A.1)

> **Updated 2026-07-08 (Step 66A.2): operator RECORDED decisions D1–D14 — see the Recorded column and
> `ai-team-work-operator-decision-record.md`.** Documentation only; no UI/backend/runtime change.
> **Claude Code did not change operator decisions.** Recommendations shown are the earlier non-final
> proposals; the **Recorded** column is the operator's binding decision.

The six operator-provided directions plus the detailed sub-decisions are now **decided**. The
**Recorded (66A.2)** column governs.

| ID | Question | Options | Recommendation (was NON-FINAL) | **Recorded (66A.2)** |
| --- | --- | --- | --- | --- |
| **D1** | Detailed role permissions for the multi-role model | (a) default matrix (b) stricter (c) looser | default matrix, tighten retry/secret mgmt | **B — Conservative RBAC** |
| **D2** | MVP task-type priority | (a) software-only (b) +docs/platform (c) +research | software + docs + platform | **B — software + documentation + platform improvement** |
| **D3** | Intake channel implementation order | (a) Console+API first (b) +Discord (c) all at once | Console+API P0 → Slack/Discord P1 → Telegram P2 | **B — Console+API first; Slack/Discord second; Telegram third** |
| **D4** | Clarification timeout behavior | (a) wait forever (b) reminder→blocked/expired (c) auto-cancel | wait-forever MVP; escalate pre-prod | **B — reminder, then blocked / clarification_expired** (24h/72h, admin-config) |
| **D5** | Delivery acceptance state transitions | confirm full action set | adopt table in `delivery-acceptance-model.md` | **B — Accept / Reject / Request Changes / Re-run QA / Escalate / Archive** |
| **D6** | Fixed Software Delivery Team boundary | (a) software+docs+platform (b) software-only | software+docs+platform; others "not supported yet" | **B — software+docs+platform; other types → intake/research queue** |
| **D7** | Notification channel priority & routing | (a) Console-only (b) +Discord (c) all | Console P0 + Discord P1 | **B — Admin Console + Discord first; Slack next; Telegram later** |
| **D8** | Approval / DLQ / Retry UI priority | (a) both P0 (b) approvals first (c) DLQ first | both P0 | **A — Approvals + DLQ/Retry both P0** |
| **D9** | Chat-style agent workroom MVP or later? | (a) MVP (b) phased (c) later | phased: clarification-first | **A — full chat-style Agent Workroom in MVP** |
| **D10** | Web research governance policy | (a) no connector (b) governed rail (c) whitelist-only | no connector in MVP | **C — whitelist sources only** (+ propose top-10, pending connector) |
| **D11** | Request Changes: same vs new workflow | (a) same+note (b) new linked (c) size-classified | same workflow + note | **C — small→same workflow; major→new workflow** |
| **D12** | Re-run QA behavior & limits | (a) cap ≤3 (b) roles+cap 3 (c) cost-gated | cap ≤3 | **B — PM/Lead/Reviewer; max 3 per delivery** |
| **D13** | Who can trigger retry / manual replay | (a) admin/agent-op only (b) +PM (c) admin/agent-op only | admin + agent-operator only | **C — Platform Admin / Agent Operator only** |
| **D14** | Non-software tasks in MVP UI or later | (a) MVP UI (b) selection + intake/planning first (c) later | later via templates | **B — UI shows task-type selection; non-software → intake/planning/documentation first** |

## Status

- **All D1–D14 RECORDED (2026-07-08).** Operator overrides vs. the earlier recommendation: **D4=B,
  D9=A, D11=C**. All others matched the recommendation. Verifier checks D7=B, D9=A, D10=C, D11=C.
- Remaining detail to resolve at 66A.3 (not re-decisions): D11 size-classification criteria; D4
  timeout-config surface; D1 exact permission matrix; D10 whitelist confirmation + connector auth;
  D9 minimum-viable-workroom boundary; D12 admin-override proposal.

## Statement

Operator decisions D1–D14 are recorded exactly as provided. Claude Code did not change operator
decisions. No UI was implemented; no backend change; no workflow ran; no external action; no
production action.

---
_Non-production only. No production action. No production data._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
