# Microcopy Guide — Step 66UI.4-FE.1D

> Owner: Claude Design. Concrete before/after strings for the FE.1D polish, grounded in the actual
> deployed copy. Consistent with the merged Phase 1 `product-microcopy-guide.md` and the shipped
> FE.1B/FE.1C wording. All are display-string changes only.

## Tone rules (unchanged from Phase 1)

Name things by what a person does; active voice; reassurance-first for safety; no raw `snake_case`
or `Step 66x` engineering references in primary copy; errors say what happened + what to do.

## Page / section titles

| Location | Before (deployed) | After |
| --- | --- | --- |
| TaskList note | "Operator task assignment (Step 66B). No workflow dispatch occurs from this page." | "Assign work to the AI team. Nothing runs automatically — you stay in control." |
| TaskList `<h2>` | "Tasks" | keep "Tasks" |
| TaskList empty | "No tasks yet" | "No tasks yet. Assign your first piece of work to the AI team." (match Overview) |
| Create link | "+ Create task" | "New task" or "Assign work" |

## Filter labels & options (TaskList)

| Before | After |
| --- | --- |
| Status option values shown as raw enums (`clarification_needed`, `delivery_ready`, …) | show product labels (shared `TASK_STATUS_LABELS`); **option value stays the raw enum** for the query param / API |
| "Task type" raw values | product labels via existing `TASK_TYPE_OPTIONS.label` (already available) |
| "(any)" | "All" |

## Status labels (shared map — reuse across TaskList + Overview)

`ExecutiveOverview.tsx` already defines a partial `TASK_STATUS_LABELS`. FE.1D: **extract it to a
shared module** and complete it so TaskList badges/dropdown and Overview use one product-label map.
Missing entries to add (display only; enum values unchanged):

```text
draft -> Draft
blocked -> Blocked
aborted -> Aborted
canceled -> Canceled
completed -> Completed
devops -> DevOps
requirement_analysis -> Requirement analysis
(plus the existing mapped set: intake_review, clarification_needed, clarification_expired,
 approved_for_execution, running->In development, waiting_approval, delivery_ready,
 changes_requested, qa_rerun_requested)
```

Codex to confirm the authoritative `TASK_STATUSES` list with Claude Code so no enum is missed.

## Table column headers (TaskList)

| Before | After |
| --- | --- |
| "Production effect" | "May affect production" — and show a chip only when true (blank when false), not a badge on every row |
| "Requires approval" | "Needs approval" — chip only when true |
| "Created" / "Updated" (raw ISO timestamp) | relative time ("2h ago"), exact ISO on hover (reuse Overview `relativeTime`) |
| "Owner / Created by" | keep |

## Empty states (consistency pass)

Standardize on the product-warm pattern already used in Overview:

```text
Tasks:          "No tasks yet. Assign your first piece of work to the AI team."
Workroom:       "No messages yet. Start a discussion or ask the AI team a question."
Clarifications: "No open decisions. The AI team doesn't need your input right now."
Role-restricted:"This information isn't available for your role right now."   (already used in Overview)
Load error:     "Couldn't load this. Retry, or check system status."
```

Replace bare `"No tasks yet"` / `.empty` "No data"-style strings with these.

## Placeholder wording — one consistent pattern

Two variants exist today: the full-page `PlaceholderPanel` ("Not yet available. / Requires Step X. /
No workflow action available.") and the Overview inline `PlaceholderItem` ("… No workflow action
available **from this screen**."). Standardize both on:

```text
Not yet available.
Requires Step <stage>.
No workflow action available.
```

And normalize the `requiredStep` values passed in `App.tsx` (see `field-label-cleanup-map.md`):
`"future notifications stage"` → a real stage or a "Planned" phrasing; `"66S or later"` → `"66S"`.
The rendered sentence is `Requires Step {requiredStep}.`, so `requiredStep` must be a bare stage id.

## Button / link labels

| Before | After |
| --- | --- |
| "View Safety" (Overview) | keep (already good) |
| "Evidence / details" (CalmSafetyPosture summary) | keep (already good) |
| "+ Create task" | "New task" |

## Safety wording — micro-polish only (do NOT change logic)

FE.1B/FE.1B.1 already shipped consistent product wording ("Safe — no automated or production actions
will run.", "No production actions have run", "Automated workflow dispatch: Off", "Not applicable at
this endpoint"). FE.1D optional cosmetic only:

- Normalize the summary dash: `"Safe - no automated…"` → `"Safe — no automated…"` (en/em dash
  consistency) across the three tone titles.
- Sentence-case "not reported" / "not applicable" consistently.
- No change to tone thresholds, field set, or the evidence disclosure. Safety logic is out of scope.

## Statement

Design specification only. No runtime code. No production action.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
