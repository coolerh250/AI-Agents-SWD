# Handoff — Claude Design → Claude Code (DESIGN-66UI.4-FE.1C)

> Follows `docs/process/partner-handoff-standard.md`. Design/handoff only. No runtime code. No Codex
> implementation authorized.

## Stage

`66UI.4-FE.1C — Overview Attention-first Cleanup` (design brief). Branch
`design/66ui4-fe1c-overview-attention-first`, off `main` @ `77ab4e0`.

## What changed

- Added the FE.1C design brief set under `docs/design/66ui4-fe1c-overview-attention-first/` (10
  docs): brief, current-overview analysis, IA, wireframe, existing-data mapping, placeholder/empty-
  state strategy, microcopy, Codex boundary, PO validation checklist, open-questions/risks.
- Added stage artifacts under `docs/stages/66ui4-fe1c/` (manifest, context receipt, stage gate
  report) and this handoff.
- Added a verifier + test and a `source/progress.md` entry.
- **No runtime code changed.** No `apps/**` file touched.

## What this design says (summary)

Turn the Overview (`/` route, `ExecutiveOverview.tsx`) from a flat 12-card metrics grid into an
attention-first AI Team Command Center home, using **existing data only**:
attention (tasks: clarification_needed/blocked) → AI team activity (agent-executions) → current work
(recent tasks) → calm posture (reuse FE.1B) → demoted metrics (existing 12 cards) → honest future
placeholders (66D/66C.4/Notifications/Pipeline).

## What remains undecided (for Claude Code)

1. Whether the Overview may call `GET /tasks` (new call site of an existing endpoint) for attention
   counts + current-work; if not, those degrade to honest empty states.
2. How FE.1C reuses the FE.1B posture summary (reusable component vs. a minimal `getOverview()`-based
   one-liner + link) — must not duplicate FE.1B detail.
3. Confirmation that agent-execution data maps cleanly to product-readable status words.

See `docs/design/66ui4-fe1c-overview-attention-first/open-questions-and-risks.md`.

## What requires Claude Code review

- Architecture/safety review of this brief (Design Review Gate): confirm existing-data-only, no
  contract change, no forbidden path, honest placeholders, FE.1B not duplicated.
- Confirm/deny the three undecided items above and set the implementation boundary before Codex
  starts.

## What requires Product Owner decision

- Accept the brief (`READY_FOR_CODE_REVIEW` / `PARTIAL_WITH_GAPS` / `NEEDS_ANOTHER_ROUND`).
- Preferences in open-questions #4 (recent-task count/sort).
- Explicit authorization for Codex to implement FE.1C (separate from accepting the brief).

## What Codex must NOT implement yet

- Anything — Codex is not authorized by this brief. When authorized: existing data only; no new
  endpoint/DB/workflow; no FE.1A/FE.1B change; no IA/route change; no fabricated numbers; no fake
  controls; no dispatch/resume/production/external action; honest 66D/66C.4 placeholders.

## Safety / governance

No workflow dispatch/resume, no external action, no production action, no new backend/API/DB/
workflow requested, no secrets/internal identifiers. `production_executed_true_count` stays
server-computed and displayed-as-returned.

## Statement

Handoff/documentation only. No runtime code. No production action. No Codex implementation
authorized by this document.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
