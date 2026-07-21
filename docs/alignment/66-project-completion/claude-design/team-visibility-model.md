# Team Visibility Model — Step 66ALIGN.1 (Claude Design)

> Owner: Claude Design. How the AI team is made visible across the roadmap so the product reads as a
> team command center — and how engineering/evidence surfaces stay secondary. Analysis only.

## Principle

The product's premise is "manage and collaborate with an AI team." The team must be a **visible
actor**, not a `sender_id` string or a row in an executions table. Visibility grows with the
milestones, always sourced from real server data — never fabricated.

## The fixed Software Delivery Team (v1)

Intake · Requirement · Development · QA · DevOps. Each agent gets a **stable identity**: product
name, a consistent monogram/color token, and an **activity state**.

## Activity states (shared vocabulary)

```text
idle            — no active run
working         — actively progressing a task
waiting-on-human— blocked on a human decision (clarification/approval)
needs-review    — finished with a result a human should look at (e.g. QA)
blocked/failed  — operational failure (links to Operator Center)
```

All states derive from existing/real data (task status, agent-execution records). Where data for a
state isn't available yet, show a calm "not reported" — never invent activity.

## Visibility by milestone (grows, never faked)

| Milestone | Scope of team visibility | Surface |
| --- | --- | --- |
| M1 | **Task-scoped**: who is acting on THIS task + state; "waiting on you" pinned | Task Workspace / Workroom |
| M1 (Overview, shipped) | lightweight recent agent-run summary | Overview "AI team activity" |
| M3 | **Cross-task**: the whole team's activity across tasks; blocked/failed with reason | Operator Center + a team-activity view |
| M5 | full-loop team activity for the pilot task | pilot surfaces |
| M6/M7 | team activity as **human-readable audit evidence** for trust/readiness | Governance/Audit |

## Keeping engineering / evidence surfaces secondary

A standing risk: the console already has many engineering/evidence surfaces (Platform Ops's 20
read-only/evidence pages, Audit Evidence, agent-execution evidence). Rules to keep them subordinate:

1. **Team state is product-language and primary; raw executions/evidence are secondary.** The
   Workroom/Overview show "Requirement Agent — waiting on your answer", not an executions table; the
   raw execution/evidence lives under Operator Center / Audit / a "Technical details" disclosure.
2. **Platform Ops stays collapsed, compact, and badged** (Read-only / Evidence) — already shipped in
   FE.1D-S1. It must never become the product's headline.
3. **Evidence is expandable detail, never the headline** — Delivery Detail, Audit, and safety all
   lead with a human summary and hide hashes/ids/payloads behind disclosure.
4. **Safety reads as reassurance** (FE.1B calm posture), not a raw field bar.
5. **One badge vocabulary** (Soon / Read-only / Evidence) marks secondary/technical surfaces
   consistently so users learn "this is reference, not the main flow."

## Agent visibility requirements summary

- M1: task-scoped identity + state + "waiting on you".
- M3: cross-task team activity + operational blocked/failed with reason.
- Everywhere: real data only; product-language labels; raw execution/evidence demoted to secondary.

## Product Owner validation (visibility)

```text
- The AI team is legible as agents-with-state, not a raw executions/id list.
- "Which agent, doing what, and is it waiting on me?" is answerable at a glance (task-scoped in M1,
  cross-task in M3).
- Platform Ops / Evidence / Safety are present but clearly secondary (collapsed/badged/calm).
- No fabricated agent activity anywhere.
```

## What must remain placeholder-only

- Cross-task / multi-agent orchestration visibility beyond what real data supports at each milestone
  (M1 task-scoped only; M3 cross-task) — no faked team activity ahead of its data.

## Statement

Design analysis only. No runtime code. No production action. No merge. No Codex authorization.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
