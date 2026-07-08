# AI Agents Team Work — Multi-Channel Intake Model (Step 66A.1)

> **Planning / discovery only. No UI implementation. No external action. No production action.**
> **Recommended sequencing is non-final; no channel is removed from the final target.**

Operator decision **D3: task assignment must be possible from Admin Console, Slack, Discord, Telegram,
and API.** All five remain in the final target. Only the **implementation order** is a recommendation
(decision item **D3**).

## 1. Target channels

| Channel | Create task | Identity mapping | Permission enforcement | Clarification handling | Delivery link-back | Audit | Impl priority (proposed) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| **Admin Console** | task form / assign UI | authenticated session → role | RBAC (role model) | in-app clarification thread | Delivery Inbox link | full audit | **P0** |
| **API** | `POST` task endpoint | API key/token → service/role | token scope | webhook / poll for clarification | response payload + link | full audit | **P0** |
| **Slack** | slash command / app | Slack user → mapped role | mapping table + RBAC | reply in thread → resume | reply with inbox link | full audit | P1 |
| **Discord** | command / bot | Discord user → mapped role | mapping + `DISCORD_ALLOWED_ROLE_ID` | reply in channel/thread | reply with inbox link | full audit | P1 |
| **Telegram** | bot command | Telegram user → mapped role | mapping + allowlist | reply in chat | reply with inbox link | full audit | P2 |

## 2. Current state (honest)

- **API intake exists** today (comm-gateway `/intake/mock` + project/work-item APIs).
- **Discord gateway exists** for controlled notification/send; a Discord **intake command** does not.
- **Slack and Telegram gateways do not exist** yet — new components.
- Admin Console has no task-assignment intake UI yet.

## 3. Recommended sequencing (NON-FINAL — decision item D3)

1. **66B/66F P0:** Admin Console intake + API intake (build on existing intake API).
2. **66F P1:** Slack + Discord intake commands (reuse Discord gateway plumbing).
3. **66F P2:** Telegram bot intake.

No channel is dropped; sequencing balances existing plumbing (API/Discord) vs. new components
(Slack/Telegram).

## 4. Cross-cutting rules

- Every channel maps external identity → platform role **before** honoring privileged actions;
  unmapped identity is treated as requester-level or rejected.
- Every intake produces the same internal task record and **full audit**, regardless of channel.
- Clarification replies from any channel route back to the same task's clarification thread.
- No channel sends externally in test posture unless a controlled rail is separately authorized.

## 5. Statement

No intake channel was implemented; no message was sent. No external action occurred. No production
action occurred. Sequencing is a recommendation only.

## Recorded decision (66A.2)

**D3 = B** — implementation order: **Admin Console + API = P0**; **Slack + Discord = P1**; **Telegram =
P2**. No channel is dropped. (Related: notification routing **D7 = B** — Admin Console + Discord first.)

---
_Non-production only. No production action. No production data._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
