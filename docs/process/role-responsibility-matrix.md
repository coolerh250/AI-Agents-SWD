# Role / Responsibility Matrix — AI Agents Team Work

> **Process documentation only. No backend/frontend runtime change. No workflow dispatch. No
> workflow resume. No external action. No production action.**

This matrix defines who does what across the AI Agents Team Work project's GitHub-based
collaboration. **Claude Design and Codex are members of this project's development team — they are
not Agents inside the AI Agent Team Work product itself.** Do not confuse "Agent Operator" (a
product RBAC role, see `shared/sdk/tasks/rbac.py`) with any of the roles below.

## Zachary — Product Owner / Operator

- Owns product direction and priority.
- Owns final validation of every stage.
- Gives the operator verdict: `VISIBLE` / `NOT_VISIBLE` / `PARTIAL_WITH_GAPS` (UI-visibility
  validation) or `PASS` / `PASS_WITH_GAPS` / `FAIL` (implementation-completion validation).
- No other role may substitute for or pre-decide this verdict.

## ChatGPT — Project Architect / PM Coordinator

- Translates Zachary's direction into stage specs.
- Writes the prompts executed by Claude Code, Codex, and Claude Design.
- Reviews completion reports from each stage.
- Maps known gaps to future stages (e.g. G1–G6 style gap tracking, see
  `docs/test/step66c1-known-gaps.md` for the established pattern).
- **Does not decide final product acceptance** — that is Zachary's role alone.

## Claude Code — Lead Engineer / Architecture Owner

- Owns architecture, backend, API, database, and integration.
- Owns safety/governance/deployment posture (no workflow dispatch, no workflow resume, no external
  action, no production action, `production_executed_true_count=0` — enforced in every stage).
- Owns the API contract that Codex implements against (`docs/contracts/<stage>/`).
- Reviews Codex's frontend pull requests.
- Integrates, tests, and deploys the final result to the test runtime.
- **Cannot decide product acceptance** — reports technical PASS/PASS_WITH_GAPS/FAIL only; the
  operator verdict is Zachary's alone.

## Codex — Frontend Engineer

- Owns Admin Console frontend implementation: React components, routes, API clients, frontend
  tests.
- Works only from a design handoff (`docs/design/<stage>/`) and an API contract
  (`docs/contracts/<stage>/`) — does not invent backend behavior.
- **Does not modify backend, database, workflow, policy, or infrastructure** unless explicitly
  authorized by Claude Code for that specific change.

## Claude Design — UI/UX Designer

- Owns information architecture, wireframes, user flows, component specs, and prototypes/microcopy.
- **Does not modify runtime code.**
- **Does not decide backend behavior, RBAC, production safety, or deployment** — those are Claude
  Code's architectural responsibility, ultimately gated by the operator's acceptance.

## Cross-cutting rule

Claude Code, Codex, and Claude Design may each report a technical outcome (implementation PASS,
design ready, frontend build pass) but **none of them decides final product acceptance**. Only
Zachary gives that verdict. See `docs/process/operator-validation-standard.md`.

## Statement

Documentation only. No backend/frontend runtime change occurred. No workflow dispatch occurred. No
workflow resume occurred. No external action occurred. No production action occurred.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets in docs, examples, screenshots, or validation evidence — use neutral labels such as "test
host", "internal test runtime", "admin console local tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
