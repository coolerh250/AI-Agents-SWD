# Open Questions & Risks — DESIGN-66UI.4-FE.1C

> Owner: Claude Design. Things Claude Code / the Product Owner should decide or watch. None blocks
> accepting the brief; they shape the implementation.

## Open questions

1. **Should the Overview call `GET /tasks`?** (For Claude Code.) The attention counts (Decisions
   waiting, Blocked) and Current-work list are client-side reads of the existing `/tasks` endpoint —
   a **new call site of an existing endpoint**, not a new endpoint. Confirm this is acceptable. If
   not, those sections degrade to honest empty states and the Overview relies solely on
   `getOverview()` + agent-executions + FE.1B posture.
2. **How to embed the FE.1B posture summary.** (For Claude Code + Codex coordination.) FE.1C reuses
   FE.1B's calm posture output on the Overview. Confirm whether FE.1B exposes a reusable summary
   component/value, or whether the Overview should show a minimal one-line summary from
   `getOverview()`'s `safety_result` / `production_executed_true_count` and link to Safety Center.
   Either way, FE.1C must not duplicate FE.1B's detailed rendering.
3. **Agent-execution → product status mapping.** (For Claude Code.) Confirm the product-readable
   status words map cleanly from the existing agent-execution data shape (completed / running /
   needs input / failed). If the shape is thinner than assumed, the activity section shows what is
   available or the empty state.
4. **"Recently updated tasks" count / sort.** (Product Owner preference.) How many recent tasks to
   show (suggest 5) and default sort (suggest `updated_at` desc).

## Risks

1. **Re-introducing an ops-dashboard feel.** If the demoted metrics section is too prominent or the
   attention tiles are under-designed, the page can slide back toward the current metrics-grid feel.
   Mitigation: strict top-to-bottom priority (attention first), quiet surface for metrics.
2. **Conflating legacy delivery packages with 66D deliveries.** The overview's
   `ready_for_review_packages_count` is legacy, not 66D. Risk of showing it as the "Deliveries to
   review" attention item. Mitigation: explicit separation in `existing-data-mapping.md`; legacy
   count stays in demoted metrics, 66D item is a placeholder.
3. **FE.1B / FE.1C coupling.** FE.1C depends on FE.1B's posture output. If FE.1B's shape changes late,
   the Overview posture summary may need adjustment. Mitigation: keep the coupling to a thin
   summary + link; degrade to a `getOverview()`-based one-liner if needed.
4. **Empty-runtime demos.** On a fresh test runtime with no tasks/executions, most sections show
   empty states. Mitigation: the empty copy is product-warm and intentional (not an error), so an
   empty runtime still reads as a coherent product home.

## Non-risks (explicitly out of scope, not concerns for FE.1C)

- Delivery/Approval/Reminder real behavior (66D/66C.4) — placeholders only.
- Pipeline board — future, read-only only.
- Any backend/API/DB/workflow change — none requested.

## Statement

Design specification only. No runtime code. No production action.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
