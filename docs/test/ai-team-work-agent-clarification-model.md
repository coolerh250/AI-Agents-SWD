# AI Agents Team Work — Agent Clarification / Pause / Resume Model (Step 66A.1)

> **Planning / discovery only. No UI implementation. No workflow execution. No production action.**

Operator decision **D4: when a requirement is unclear, the agent must PAUSE, NOTIFY the human, and
WAIT for a response** — it must not assume-and-continue except under strict conditions.

## 1. Default behavior (MVP)

```
pause_for_clarification → notify_human → wait_for_response → resume_after_answer
```

An agent may only assume-and-continue when **all** hold (else it must pause):
1. operator has explicitly authorized assumptions for that task,
2. the agent records the assumption explicitly,
3. task risk is low,
4. no external write / production effect is involved.

MVP default is **pause** (assume-and-continue is off unless the four conditions are met).

## 2. State machine

| State | Meaning | Entry | Exit |
| --- | --- | --- | --- |
| `running` | agent working | task assigned | needs clarification / done / fail |
| `clarification_needed` | paused, question posted | agent raises question | human answers → `running` |
| `waiting_human` | notified, awaiting reply | notification sent | reply received / timeout |
| `resumed` | continues after answer | human answered | back to `running` |

## 3. Clarification thread

- A **question thread** attached to the task: agent question(s), human answer(s), timestamps, author.
- Human response can arrive via **any intake channel** (Admin Console, Slack, Discord, Telegram, API)
  and routes back to the same thread (see intake model).
- Each question, answer, pause, and resume emits an **audit event** and a **notification**
  (`clarification needed`, `human replied`).

## 4. Timeout behavior (decision item D4 — requires operator answer)

Options (NON-FINAL):
- **A. Wait indefinitely** (safest; nothing proceeds without a human) — recommended MVP default.
- **B. Escalate after N** (notify a higher role / Action Center) — recommended pre-production.
- **C. Auto-cancel after N** (task ends, requires re-submit) — only with explicit opt-in.

Recommendation: **A for MVP**, add **B** before production. This ties to Step 65 gap #2 (safe
approval-expiry/timeout mechanism). Final choice is **D4**.

## 5. Admin Console UI (target)

- A clarification queue in the Operator Action Center; per-task clarification thread with reply box;
  clear `clarification_needed` / `waiting_human` badges.

## 6. Current state (honest)

- The pipeline already records **discussion** per hop, but there is **no operator-facing clarification
  thread UI** and no first-class `clarification_needed` pause/resume surfaced to a human today. This is
  new work in **66C**.

## 7. Statement

No clarification workflow was executed. No notification was sent. No external action occurred. No
production action occurred. Timeout behavior is an open decision (D4).

---
_Non-production only. No production action. No production data._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
