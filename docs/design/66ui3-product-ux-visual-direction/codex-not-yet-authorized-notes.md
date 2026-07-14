# Codex — Not Yet Authorized (DESIGN-66UI.3)

> Owner: Claude Design, addressed to Codex (Frontend Engineer). **This stage is a product-UX review
> and visual-direction proposal. Codex is NOT authorized to implement anything from it.** Consistent
> with `docs/frontend/66ui2-navigation-ia/codex-implementation-plan-boundary.md` and the
> role-responsibility matrix.

## Authorization status

- **No Codex implementation is authorized by this stage.** This stage ends in a Product Owner
  direction choice (`product-owner-discussion-guide.md`), after which Claude Design writes a Phase 1
  detailed brief, Claude Code reviews it, and only then may the Product Owner authorize
  implementation.

## Explicitly NOT to implement in this stage

```text
- No runtime code changes.
- No backend / API changes.
- No workflow dispatch.
- No workflow resume.
- No workflow state mutation.
- No production actions; production_executed_true_count stays server-computed and displayed as 0.
- No external actions (GitHub write / Discord / Slack / Telegram / LLM send).
- No Delivery real UI until the Step 66D contract exists (placeholder-only).
- No Reminder / Expiry real UI until the Step 66C.4 contract exists (placeholder-only).
- No Lifecycle Pipeline board.
- No drag-and-drop / manual stage transition.
- No client-side-only RBAC; server remains the access-control authority.
- No production / external controls of any kind.
```

## When implementation is eventually authorized (future stages)

Each redesign phase (see `redesign-roadmap.md`) will come as its own design brief + Claude Code
review + explicit Product Owner authorization. General constraints that will carry into all of them:

- **Reuse existing endpoints only** unless Claude Code publishes a new contract. The visual redesign
  reads the same data the deployed pages already read (`GET /tasks`, `GET /tasks/{id}`,
  `GET /tasks/{id}/workroom`, `GET /tasks/{id}/audit-evidence`, `/operations/safety`, etc.).
- **Safety values stay server-computed and displayed-as-returned** — a calmer *presentation* of
  `dispatch_enabled` / `resume_dispatch_enabled` / `production_executed_true_count` must never
  hardcode or infer them client-side.
- **Plain-text rendering of user/agent content stays** — richer Workroom *message treatment* changes
  the container, never the body rendering (no markdown-to-HTML, no auto-linking, no
  `dangerouslySetInnerHTML`).
- **Agent identity / activity states** must come from real server data, not be invented client-side.
- **Placeholders keep their exact safety semantics** ("Not yet available", the specific required
  stage, "No workflow action available", no actionable controls).

## What Codex may do now

Nothing implementation-wise. Codex may **read** this stage's docs to understand the intended
direction, but must wait for a Phase 1 brief and explicit Product Owner authorization before writing
any code.

## Statement

Boundary note only. No runtime code. No production action. No Codex implementation authorized by
this document.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
