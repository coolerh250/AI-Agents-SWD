# Placeholder & Empty-State Strategy — DESIGN-66UI.4-FE.1C

> Owner: Claude Design. How the Overview handles (a) features not yet built and (b) real sections
> that currently have no data. Honest, non-misleading, no fake controls.

## Two distinct cases — do not conflate

- **Placeholder** = the *feature* does not exist yet (66D / 66C.4 / future). Show what it will be +
  the gating stage + "no workflow action available." Never a control.
- **Empty state** = the *feature* exists and reads real data, but there is nothing to show right now
  (e.g. zero clarifications waiting). Show a calm, product-warm "all clear" message.

## Placeholder rules (features not yet available)

Required language (honest):

```text
Not yet available
Requires Step 66D            (Delivery Review, Approvals queue)
Requires Step 66C.4          (Reminder / Expiry)
Future                       (Notifications / Action Center)
Future (read-only only)      (Pipeline view; no drag/drop)
No workflow action available from this screen
```

Presentation:

- Muted / dashed treatment, visually distinct from active tiles.
- States what the feature will do, in one product sentence.
- **No buttons, no fake counts, no fake rows, no controls of any kind.**
- Never present the legacy `ready_for_review_packages_count` as the 66D "Deliveries to review"
  (see `existing-data-mapping.md`).

### Placeholder copy (exact)

```text
Deliveries to review
Not yet available. Requires Step 66D.
When available, delivered work will await your acceptance here.
No workflow action available from this screen.
```

```text
Reminder / Expiry
Not yet available. Requires Step 66C.4.
Clarification reminders and expiry will surface here once the scheduler ships.
No workflow action available from this screen.
```

```text
Notifications / Action Center
Future. A unified action center will consolidate items needing attention.
No workflow action available from this screen.
```

```text
Pipeline view
Future (read-only only). A lifecycle view of tasks by stage. View only — no drag-and-drop,
no stage changes from the UI.
No workflow action available from this screen.
```

## Empty-state rules (real sections, no data now)

Calm, product-warm, directive — never a bare "No data" or a raw zero with no meaning:

```text
Needs your attention (all clear):
  "You're all caught up. The AI team isn't waiting on you right now."

AI team activity (none):
  "No recent agent runs."

Current work (no tasks):
  "No tasks yet. Assign your first piece of work to the AI team."

Data unavailable (endpoint error / role-restricted):
  "This information isn't available for your role right now." (readable; never blank or a raw error)
```

## Degradation & honesty guarantees

- If `GET /tasks` is not called on the Overview (pending Claude Code confirmation — see open
  questions), the attention counts show the "all clear" empty state rather than a fabricated number.
- A count is shown **only** when it is a real count of existing data; otherwise the section shows an
  empty or placeholder state.
- Zero is shown as a calm "all clear," not as a red/alarming badge (an off/empty attention queue is
  good news).

## Statement

Design specification only. No runtime code. No production action.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
