# Core Loop Experience Definition — M1 (Step 66ALIGN.1, Claude Design)

> Owner: Claude Design. The M1 experience: Assign → Converse → Clarify → Wait/Resume → Observe. This
> is where the product becomes an AI team command center rather than a task form + log viewer.
> Analysis only; no runtime code.

## M1 goal

A human can start a piece of work with the AI team, hold a legible conversation with it, ask/answer
a formal decision (clarification), and clearly see when the team is working, when it is waiting on
the human, and that nothing resumes automatically.

## Workroom: the agent/team states M1 must present

Today the Workroom renders a uniform message thread (log-style). M1 must present **team state**, not
just messages. Required states, all sourced from real server data (no fabricated activity):

| State | Meaning | Presentation |
| --- | --- | --- |
| **Team working** | an agent is actively progressing the task | active indicator + which agent + since when |
| **Waiting on you** | a clarification/decision blocks progress | pinned banner at top: "The Requirement Agent needs your decision to continue" |
| **Paused — will not resume automatically** | task is in a safe wait; workflow resume is disabled by design | explicit calm statement, not an error; "A person decides the next step" |
| **Idle / no active run** | nothing running now | calm "No active agent run" (never faked) |
| **Blocked (operational)** | a failure/retry condition (links to Operator Center in M3) | clear, links out; not silently hidden |

Message authorship must be visually distinct by kind — **human / agent / system / clarification** —
with agent identity (name + monogram) rather than a raw `sender_id`. Bodies remain plain text (no
markdown-to-HTML, no auto-linking) — differentiation is in the container, never in rendering the
body as rich content.

## Clarification as a decision request (not a form)

The clarification is the primary human decision point of M1. It must read as **"an AI agent is
asking you to decide,"** not as a generic text field:

- A decision-request card: which agent is asking, why the task is blocked without an answer, the
  question in plain language, and one clear "Answer" affordance.
- Keep **"Ask the AI team for a decision" (Create Clarification)** and **"Send a message" (general
  discussion)** as clearly separate, differently-weighted actions — preserving the hard-won 66C.2-R
  distinction; a decision request is heavier than a chat message.
- On answer: confirm "Answer recorded" and state plainly that answering **does not** auto-restart the
  team (resume is disabled by design; a person decides the next step).

## Wait / Resume — the safety-critical state

- The "waiting" state is a **first-class, calm** state, not an error and not a dead end.
- The UI must never imply that answering a clarification, or any Workroom action, dispatches or
  resumes a workflow. `dispatch_enabled=false` / `resume_dispatch_enabled=false` remain
  server-computed and surfaced (reuse the FE.1B calm posture, task-scoped).
- If/when workflow resume is ever authorized, it becomes an explicit human action with its own
  confirmation — not an implicit side effect. Until then it stays disabled and clearly stated.

## Pages / states / decision points (M1 summary)

- **Pages:** Create Task; Tasks; Task Workspace (Detail + Workroom); clarification decision-request
  within the Workspace.
- **States:** task lifecycle; message-authorship kinds; the five team states above; safe wait.
- **Empty/error/loading:** empty Workroom; loading skeleton; role-restricted; safe wait (not error).
- **Human decision points:** answer clarification (primary); send message; submit/assign task.

## Agent visibility requirements (M1 slice; full model in `team-visibility-model.md`)

M1 needs *task-scoped* team visibility (who is acting on THIS task and its state). Cross-task team
visibility is M3. M1 must not fake multi-agent orchestration it can't yet source.

## Product-language requirements

"Assign work to the AI team"; "Ask the AI team for a decision"; "Send a message"; "The team is
working"; "Waiting on your answer"; "Paused — won't resume automatically"; "Answer recorded". No raw
status enums, `sender_id`, or `snake_case` in the primary surface (apply FE.1D-S2 standards here as
this surface is built).

## Accessibility

Authorship distinguished by more than color (icon + label); the "waiting on you" banner is
programmatically associated and announced; new messages use an appropriate live region; the decision
request is fully keyboard-operable.

## Product Owner validation checklist (M1)

```text
- Can assign a task to the AI team.
- Can hold a legible conversation (human vs agent vs system vs clarification are visually distinct).
- Can raise a clarification and answer it; it reads as a decision request, not a form.
- The task's "working / waiting on you / paused" state is unmistakable at a glance.
- Answering never implies auto-dispatch/resume; safety posture (dispatch/resume OFF) stays visible.
- No fabricated agent activity; empty/idle states read calmly.
```

## What must remain placeholder-only in M1

- The **Delivery** tab/area (until M2).
- **Workflow resume** as an action (stays disabled/safe-stated until explicitly authorized).
- **Cross-task / multi-agent orchestration controls** (M3).

## Statement

Design analysis only. No runtime code. No production action. No merge. No Codex authorization.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
