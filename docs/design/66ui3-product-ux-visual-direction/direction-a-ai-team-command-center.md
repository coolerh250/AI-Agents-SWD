# Direction A — AI Team Command Center

> Owner: Claude Design. One of three product visual/interaction directions for DESIGN-66UI.3. Not
> selected by default — see `product-owner-discussion-guide.md`.

1. **Direction name:** AI Team Command Center.

2. **Design concept:** The console is the bridge of an operation the human oversees. The home
   surface answers, at a glance, *what is the AI team doing, where is it blocked, and what needs my
   decision* — across all tasks. Individual work is reached by drilling from that operational
   picture. The AI team is a visible actor: agents have identity and activity state; the interface
   portrays a team at work, not a table of records.

3. **Best suited users:** PM / Engineering Lead, Platform Admin, Agent Operator — roles managing
   many concurrent tasks and needing cross-task situational awareness.

4. **Page layout model:** Persistent left IA nav (from 66UI.2) + a calm safety posture strip; main
   area is a command dashboard of live "decision / delivery / blockage / risk" queues; drilling into
   a task opens a focused task view. Density is medium — operational but not spreadsheet-dense.

5. **Navigation treatment:** Keep the 7 groups; visually elevate **Team Work** and **Operator
   Center** as the daily-driver groups; **Platform Ops** stays collapsed and visually quiet. Active
   group/route clearly indicated so the user always knows "where in the operation" they are.

6. **Dashboard treatment:** Attention-first. Top row = human-action queues: *Decisions waiting*
   (clarifications), *Deliveries to review*, *Blocked tasks*, *Approvals required*. Second row =
   AI-team activity (which agents are active, on what) and *risk/safety posture* as one calm
   indicator. Metrics (throughput, counts) are present but below the fold.

7. **Workroom treatment:** A task "operations room" — conversation timeline with clear agent
   identity and turn-taking, a pinned "current status: the team is waiting on your answer" banner
   when blocked, and the clarification/decision surfaced at the top rather than buried in the log.
   Still plain-text bodies.

8. **Safety / audit treatment:** One calm, always-visible posture indicator ("Automated actions:
   off · No production actions · Fully audited") that expands to the detailed fields on demand.
   Audit reads as a human-legible activity trail; hashes/lengths are secondary detail, not the
   headline.

9. **Operator Center treatment:** First-class. A unified operational picture (incidents, agent
   executions, and — once 66D/66C.4 land — DLQ/retry and overdue) that an operator can scan and act
   on. Highest prominence of the three directions.

10. **Visual tone:** Calm, confident "mission control." Keep the dark ground; introduce hierarchy
    (elevated surfaces for live/attention content, quiet surfaces for reference), and reserve
    saturated semantic color for genuine state. Restrained, operational, trustworthy.

11. **Pros:**
    - Directly serves the roles that manage volume; best "what needs me across everything" answer.
    - Makes the AI-team-as-actor premise visible and central.
    - Builds naturally on the 66UI.2 IA and the existing dashboard pattern (lower churn than a
      full re-layout).

12. **Cons:**
    - Less optimized for a Requester whose whole world is one task — they pass through an
      operational lens they may not need.
    - Risk of re-creating an "ops dashboard" feel if the attention-queues aren't disciplined — the
      very thing we're moving away from, if executed carelessly.

13. **Implementation risk:** Medium. Dashboard restructure + safety-posture component + Workroom
    status framing are real work, but all read from existing endpoints; no new data shape required
    for the round-1 slice (attention counts that depend on 66D/66C.4 remain placeholders).

14. **What should be redesigned first:** The **safety posture indicator** (removes the rawest
    engineering signal app-wide) and the **Overview dashboard** (turns metrics-first into
    attention-first) — these define the "command center" feel before touching individual pages.

## Safety UX (mandatory, all directions)

`dispatch_enabled=false` / `resume_dispatch_enabled=false` / `production_executed_true_count=0`
render inside the single calm posture indicator (server-computed, displayed-as-returned, never
inferred). `production_effect` warnings, external-action-disabled, approval-required, RBAC-denied,
and audit-restricted all keep their current semantics and readable messaging — only the visual
treatment becomes calmer and product-grade. No control implies dispatch/resume/production/external
action.

## Statement

Design direction only. No runtime code. No production action. No Codex implementation authorized.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
