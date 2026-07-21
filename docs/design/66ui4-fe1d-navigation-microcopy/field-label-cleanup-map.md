# Field Label Cleanup Map — Step 66UI.4-FE.1D

> Owner: Claude Design. Before → after label map, grounded in actually-rendered labels on `main`
> @ `707cb8c`. Display-string changes only; underlying enum/field values and API calls are
> unchanged. Where uncertain, marked **[confirm with Claude Code]**.

## Important consistency note (read first)

**Safety fields are already mapped by FE.1B.1** in `CalmSafetyPosture.tsx` (`SAFETY_EVIDENCE_FIELDS`).
`dispatch_enabled` is already shown as **"Workflow dispatch"**, `production_executed_true_count` as
**"Production action count"**, etc. FE.1D must **reuse those existing labels**, not invent new ones.
The example rename in the stage prompt (`dispatch_enabled → "Automation dispatch"`) would **diverge**
from shipped FE.1B.1 wording — do **not** apply it. This map aligns to what already shipped.

## Rename map

| Current label / field | Recommended product label | Where it appears | Reason | Implementation note | Risk |
| --- | --- | --- | --- | --- | --- |
| "Production executed" (`production_executed_true_count`) | **Production actions** | Overview demoted metrics (`Metrics`) | align with CalmSafetyPosture "Production action count"; "executed" is engineering | label text only | low |
| "Ready for review packages" | **Packages ready for review** | Overview metrics | readability | label only | low |
| "Ready for admin console" (`delivery_package_ready_for_admin_console`) | **Ready to publish** [confirm with Claude Code] | Overview metrics | current label is internal-plumbing wording | label only; confirm intended meaning | med |
| "Backup gaps" (`backup_readiness_gaps`) | **Backup readiness gaps** | Overview metrics | clarity | label only | low |
| "Full regression" | **Regression status** | Overview metrics | clarity | label only | low |
| Status enum shown raw (`clarification_needed`, `delivery_ready`, …) | product labels via shared `TASK_STATUS_LABELS` | TaskList dropdown + badge; Overview | product language | display only; enum value unchanged (query param/API) | low |
| `task_type` raw | product label via existing `TASK_TYPE_OPTIONS.label` | TaskList table | product language | display only | low |
| `created_at` / `updated_at` (raw ISO) | **Created** / **Last updated** + relative time | TaskList table | timestamps as relative time; exact on hover | reuse Overview `relativeTime`; display only | low |
| "Production effect" (`production_effect` boolean badge) | **May affect production** (chip only when true) | TaskList table | boolean-badge-on-every-row is engineering | display only | low |
| "Requires approval" (`requires_approval` boolean badge) | **Needs approval** (chip only when true) | TaskList table | same | display only | low |
| "+ Create task" | **New task** | TaskList | product tone | label only | low |
| `requiredStep="future notifications stage"` | **"Planned"** phrasing (render "Not yet available. Planned.") [confirm with Claude Code] | `App.tsx` Notifications placeholder | current value renders "Requires Step future notifications stage." (awkward) | small copy change in the placeholder page props; may need a tiny `PlaceholderPanel` tweak to allow a non-"Requires Step" line — **[confirm with Claude Code: frontend-only]** | med |
| `requiredStep="66S or later"` | **"66S"** | `App.tsx` Settings placeholders | "Requires Step 66S." reads cleaner | prop value only | low |
| DLQ / Retry (nav + placeholder) | subtitle **"Needs recovery"** | Operator Center nav | "DLQ" is engineering jargon | nav subtitle/helper; keep route/label | low |
| `agent_execution` data | **AI team activity** | Overview (already done) | already shipped in FE.1C | none (confirm consistency) | none |

## IDs / hashes / correlation fields

| Field | Category (see `engineering-field-exposure-reduction.md`) | Action |
| --- | --- | --- |
| `task_id` (as link target) | keep | used for routing; not shown as raw text — no change |
| `task_id` / `work_item_id` / `execution_id` / `event_id` shown as raw text (Audit / Evidence / Operator pages) | B (move to details) | move to a "Technical details" disclosure where a page renders them raw **[confirm which pages actually render raw IDs with Claude Code]** |
| `body_hash` / `payload_hash` / `metadata_hash` | B (move to details) | keep in the existing evidence disclosure (already the pattern in CalmSafetyPosture); relabel "…hash" → "Integrity check" [confirm] |
| `correlation_id` / `message_id` / `clarification_id` (Audit Evidence) | B | move under "Technical details"; keep the human event line primary |

## Rules

- Never invent a field or value not present in the data. Anything uncertain is **[confirm with
  Claude Code]** and excluded from FE.1D implementation until confirmed.
- Enum/boolean/timestamp underlying values and API payloads are unchanged — only display text/format.
- Safety fields keep their FE.1B.1 labels — no re-rename.

## Statement

Design specification only. No runtime code. No production action.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
