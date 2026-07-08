# AI Agents Team Work — Lifecycle Notification Model (Step 66A.1)

> **Planning / discovery only. No UI implementation. No message sent. No external action. No production action.**

Defines the notification events across the task lifecycle, their target channels, and their rules.
Channel routing/priority is decision item **D7**.

## 1. Lifecycle events

| Event | Default target | Sensitive-data rule | Link-back | Rate limit | Audit |
| --- | --- | --- | --- | --- | --- |
| task submitted | requester + Action Center | no secrets | work item | per-task | ✔ |
| task accepted by agent team | requester | no secrets | work item | per-task | ✔ |
| clarification needed | assignee/requester | no secrets, redact payload | clarification thread | debounce | ✔ |
| human replied | assigned agent op | no secrets | thread | debounce | ✔ |
| approval required | approver + Action Center | no secrets | approval item | per-request | ✔ |
| approval granted | requester | no secrets | approval item | per-request | ✔ |
| approval denied | requester | reason only, no secrets | approval item | per-request | ✔ |
| agent started | Action Center | no secrets | task | low | ✔ |
| agent failed | agent op + Action Center | error class only | task | per-failure | ✔ |
| retry scheduled | agent op | no secrets | task | per-retry | ✔ |
| DLQ created | agent op + Action Center | reason class only | DLQ entry | per-entry | ✔ |
| delivery ready | manager/reviewer | no secrets | Delivery Inbox | per-delivery | ✔ |
| request changes submitted | assigned agent op | feedback text (no secrets) | task | per-action | ✔ |
| QA re-run started | reviewer | no secrets | task | per-action | ✔ |
| task accepted | requester | no secrets | task | per-action | ✔ |
| task rejected | requester | reason only | task | per-action | ✔ |
| task completed | requester + manager | no secrets | task | per-task | ✔ |
| task failed | agent op + Action Center | error class only | task | per-task | ✔ |

## 2. Channel rules

- **Target channels:** Admin Console (in-app), Slack, Discord, Telegram, email/API webhook (future).
- **Message format:** short summary + link-back to the work item; **never** include secrets, tokens,
  raw payloads, or customer data — only classes/summaries.
- **Rate limiting / debounce:** clarification and failure events debounced to avoid spam (ties to
  Step 65 "no spam" constraint).
- Every notification is also recorded as an **audit event**.

## 3. Decision item D7 (channel priority & routing — requires operator answer)

Recommendation (NON-FINAL): Admin Console in-app for all events (P0); Discord for
approval/clarification/delivery (P1, existing rail); Slack/Telegram later (P2). Per-role routing
preferences configurable.

## 4. Current state (honest)

- A **controlled Discord notification rail** exists; there is **no unified lifecycle notification
  model** wired across the full journey, and Slack/Telegram notification does not exist. This is new
  work in **66G**. No notification is sent in test posture unless a controlled rail is separately
  authorized.

## 5. Statement

No notification was sent. No external action occurred. No production action occurred. Routing is a
recommendation pending D7.

---
_Non-production only. No production action. No production data._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
