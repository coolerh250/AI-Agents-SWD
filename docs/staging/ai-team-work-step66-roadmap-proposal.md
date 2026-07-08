# AI Agents Team Work — Step 66 Roadmap Proposal (Step 66A.1)

> **Planning / discovery only. No UI implementation. No production action.**
> **Proposed sequence is a recommendation; the operator decides scope and order.**

Proposed Step 66 sub-stages to deliver the AI Agents Team Work MVP experience on top of the Step
65-accepted platform layer.

## Proposed sequence

| Sub-stage | Title | Scope | Key decisions |
| --- | --- | --- | --- |
| **66A.0** | Environment Reset / Switch to Test Runtime | *(done)* staging torn down, test runtime redeployed | — |
| **66A.1** | Interaction Model Discovery & Decision Brief | *(this stage)* models + decision register + roadmap | — |
| **66A.2** | Operator Decision Review | operator answers D1–D14 (esp. must-decide set) | D1–D6, D8, D11–D14 |
| **66A.3** | Final UX Blueprint & Implementation Scope | lock blueprint from operator answers; scope MVP | all answered decisions |
| **66B** | Operator Task Assignment UI | Admin Console assign form + API intake; role-gated | D1, D2, D3 |
| **66C** | Agent Workroom / Clarification Layer | clarification thread, pause/notify/wait/resume UI | D4, D9 |
| **66D** | Delivery Inbox & Acceptance Gate | inbox + delivery detail + Accept/Reject/Request-Changes/Re-run-QA + approvals/DLQ pages | D5, D8, D11, D12, D13 |
| **66E** | Fixed Software Delivery Team MVP Integration | wire assign→pipeline→delivery for the fixed team | D6, D14 |
| **66F** | Multi-channel Intake Foundation | Admin+API built; Slack/Discord/Telegram design + phased build | D3 |
| **66G** | Lifecycle Notification & Operator Action Center | unified notifications + Action Center queues | D7, D8 |
| **66H** | AI Team Work E2E Pilot | full manager journey pilot on test runtime (controlled) | — |

## Rationale / sequencing notes

- **Decisions gate build:** 66A.2 (operator answers) precedes 66A.3 (blueprint) precedes any build
  (66B+). Claude Code does not build UI before the operator locks the blueprint.
- **Front-load the operator-flagged Step 65 gaps:** the approvals page (#7) and DLQ/Retry page (#6)
  land in **66D** (and consolidate in 66G Action Center) so the operator's flagged gaps close early.
- **Reuse existing plumbing first:** API intake + Discord rail already exist → Admin+API and
  Discord-channel work is cheaper than net-new Slack/Telegram gateways (66F phasing).
- **Fixed team keeps MVP small:** 66E integrates only the validated `intake→…→devops` team; template
  / custom / AI-suggested composition is explicitly out of MVP.
- **Web research is not in the MVP build** — it is a future governed connector (D10), flagged, not
  fabricated.

## Alternative considered

- Building all five intake channels together (66F) up front was **rejected** for MVP — it front-loads
  net-new Slack/Telegram gateways before the core assign→deliver loop exists. Recommend Console+API
  first, then phased channels.

## Statement

This roadmap is a recommendation. No sub-stage was implemented. No workflow ran; no external action;
no production action. The operator decides scope, order, and kickoff.

---
_Non-production only. No production action. No production data._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
