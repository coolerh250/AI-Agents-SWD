# Claude Code Technical Readiness Review — Step 66UI.4-FE.1D-TECH-REVIEW

> **Review only. No runtime code changed by this document. No backend/API/database/workflow
> change. No new endpoint. No deployment. No merge. No production/external action. Codex remains
> unauthorized. FE.1D implementation remains unauthorized.**

Executed by: Claude Code (Lead Engineer / Architecture Owner — see
`docs/process/role-responsibility-matrix.md`).

## 1. Product Owner context

```text
Product Owner agreed FE.1D proceeds in three stages: (1) Claude Design produces the design
(complete — Step 66UI.4-FE.1D-DESIGN, PASS), (2) Claude Code performs this technical readiness
review, (3) only after both pass does the Product Owner consider Codex implementation
authorization. FE.1C and FE.1C.1 are complete/closed. Main latest reviewed: 707cb8c (matches the
"707cb8c or later" expectation). Codex is not authorized for FE.1D. FE.1D implementation is not
authorized. The Admin Console SPA deep-link fallback is a known, separately tracked backend/
platform gap and is explicitly out of FE.1D scope.
```

## 2. PR #12 branch / commit reviewed

```text
Branch: design/66ui4-fe1d-navigation-microcopy
Draft PR: #12
Commit: 43269c5 (based directly on main @ 707cb8c)
```

## 3. Design marker

```text
DESIGN66UI4_FE1D_NAVIGATION_MICROCOPY_VERIFY: PASS
```

Independently re-verified in a disposable worktree checked out at `origin/design/66ui4-fe1d-navigation-microcopy`
(commit `43269c5`), not trusting Claude Design's own report:

```text
python scripts/verify_design66ui4_fe1d_navigation_microcopy.py -> PASS
pytest tests/test_design66ui4_fe1d_navigation_microcopy.py     -> 7 passed
```

Worktree removed after use (`git worktree remove --force`); no residual local state.

## 4. Design-only scope result

Confirmed via `git diff --name-only main...origin/design/66ui4-fe1d-navigation-microcopy`:

```text
docs/design/66ui4-fe1d-navigation-microcopy/*.md (8 files)
docs/stages/66ui4-fe1d-navigation-microcopy-design/*.{yaml,md} (3 files)
scripts/verify_design66ui4_fe1d_navigation_microcopy.py
tests/test_design66ui4_fe1d_navigation_microcopy.py
source/progress.md
```

No `apps/**`, `services/**`, `infra/**`, `migrations/**`, `database/**`, `helm/**`, `k8s/**`, or
`.github/workflows/**` path is present in the diff (checked via `grep -E` against the forbidden-path
list in `stage-manifest.yaml` — zero matches). PR #12 does not deploy, does not merge, and does not
authorize Codex (confirmed by direct text search of every design doc: each carries an explicit "No
Codex implementation authorized by this document" statement).

**Result: design-only scope CONFIRMED.**

## 5. Frontend-only feasibility classification

Grounded by reading the actual current source (read-only) referenced by the design docs — not by
trusting the design docs' own description of that source. Confirmed accurate: `Nav.tsx` (7 groups,
20-item Platform Ops list, `defaultExpanded: false`), `App.tsx` (routes + `PlaceholderPage`
`requiredStep` values, including `"future notifications stage"` and `"66S or later"`),
`PlaceholderPanel.tsx` (exact three-line pattern), `ExecutiveOverview.tsx` (partial
`TASK_STATUS_LABELS`, `Metrics` demoted-metric labels), `TaskList.tsx` (raw status enum options,
raw ISO timestamps, `"+ Create task"`, `"Step 66B"` note), `CalmSafetyPosture.tsx`
(`SAFETY_EVIDENCE_FIELDS`, dash-inconsistent tone titles at lines 154/145/141).

| # | Area | Classification | Basis |
| --- | --- | --- | --- |
| 1 | Navigation labels | **A** | `Nav.tsx` label strings only; no route/`to` value change proposed |
| 2 | Navigation group subtitles | **A** | text-only, additive, no structural change (see §6 default resolution) |
| 3 | Soon / read-only / evidence badges | **A** | badge/marker text + muted styling on existing nav items; route unchanged |
| 4 | Platform Ops compact density | **A** (labels/markers/density) / **B** (optional sub-headers) | shortened labels + read-only/evidence markers are display-only; the optional visual sub-headers add presentational structure inside one existing group — safe, but recommended as its own gated slice (see §6, §7) |
| 5 | Page titles | **A** | e.g. TaskList `<h2>Tasks</h2>` retained; note text only changes |
| 6 | Section titles | **A** | Overview/SafetyCenter/etc. section headers are static JSX strings |
| 7 | Empty states | **A** | `EmptyState` message props / `TaskTable`'s `"No tasks yet"` literal are plain strings |
| 8 | Placeholder wording | **A** (standardizing the 3-line pattern), **B** (Notifications "Planned" variant — needs a small `PlaceholderPanel` prop addition, still frontend-only, no route/data change) | confirmed `PlaceholderPanel.tsx` renders a fixed `Requires Step {requiredStep}.` sentence; a non-"Requires Step" line requires a tiny component change, not a route/data change |
| 9 | Status label map | **A, with a required correction before implementation** | see §6 — the design's own "missing entries to add" list is not accurate against the authoritative `TASK_STATUSES` enum; corrected list provided below |
| 10 | Field label cleanup map | **A** (most rows), **B** (rows marked `[confirm with Claude Code]` in the design doc itself) | display-string rename only; enum/API values unchanged (confirmed unchanged by design's own statement and by source read of `taskTypes.ts`) |
| 11 | Engineering-field exposure reduction | **A/B per row as the design already categorizes**, **C/D correctly excluded** | design's own A/B/C/D categorization matches what I found in source; category C (`workflow_id`) and D (fabricated fields) are correctly excluded from FE.1D |
| 12 | Safety wording cosmetic adjustments | **A** | confirmed by reading `CalmSafetyPosture.tsx`: the dash inconsistency ("Safe - no automated…", "Attention needed -…", "Safety status unavailable - check…") is real, and is plain string literals inside `title =` assignments — no threshold/field-set/tone logic touched by the proposed change |
| 13 | Raw evidence / details handling | **B, scope narrower than the design docs suggest** | confirmed `TaskDetail.tsx:54` renders a raw `KeyValueTable data={task}` full-object dump, and its safety panel (`TaskDetail.tsx:58-81`) renders literal snake_case labels (`production_effect:`, `requires_approval:`, `dispatch_enabled:`, `external_actions_enabled:`, `production_executed:`) as visible text — both are FE.1D-eligible (category A relabel + category B disclosure wrap). Also found, but **not enumerated by any FE.1D design doc**: `TaskWorkroom.tsx:487` renders a raw truncated `body_hash` inline (`` ` · body_hash: ${ev.body_hash.slice(0, 12)}…` ``), and `AuditEvidence.tsx` / `DemoEvidence.tsx` / the shared `EvidenceTable` component render literal snake_case column headers (`event_type`, `from_state`, `to_state`, `task_id`, `work_item_id`, `workflow_id`, `workspace_id`, `project_id`, …) across roughly 8 Platform Ops/evidence pages. These are real, but the design docs provide no before/after label map for them — **recommend deferring this wider surface to a later, separately-designed slice** rather than letting Codex improvise labels for it inside FE.1D (see §6, §9) |
| 14 | Relative time display | **A** | `TaskList.tsx:150-151` renders raw `t.created_at` / `t.updated_at` ISO strings directly in table cells; `ExecutiveOverview.tsx` already has a working `relativeTime()` helper to reuse |

## 6. Open Product Owner decisions

Per the stage prompt's own recommended default stance, resolving what can be resolved by default
and flagging what genuinely still needs the Product Owner:

| # | Decision | Resolution |
| --- | --- | --- |
| 1 | Platform Ops subtitles (`navigation-polish-spec.md` §1 group-subtitle table, which includes a Platform Ops row) | **Resolved by default: ALLOW.** Purely text-only, non-structural, matches the stage prompt's own default rule ("allow if purely text-only and not structural"). No PO decision required to proceed with this specific item. |
| 1b | Platform Ops **visual sub-headers** (`platform-ops-density-spec.md` §4 — a distinct item from the subtitle table above, and the design's own checklist item #3) | **Not resolved by default — recommend PO input, or default to the design's own documented fallback** (labels + markers + compact density only, no sub-headers) for the first implementation slice. This is presentational structure inside the nav, not label text, so I hold it to a slightly higher bar than plain subtitles. |
| 2 | "New task" vs "Create task" | **Genuinely open — recommend explicit PO confirmation.** The stage prompt's default rule is "use 'New task' if current product tone already uses it; otherwise record PO decision needed." Confirmed by source read: `TaskList.tsx:104` currently renders `"+ Create task"` — "New task" is not already-established product tone, so the default does not resolve this. Design's own recommendation is "New task"; I concur it is the better product-language choice but flag it as PO's call per the stage prompt's own rule. |
| 3 | Notifications "Planned" wording | **Resolved by default: ALLOW.** The proposed copy ("Not yet available. Planned.") is clearly placeholder-only and does not imply an active workflow, matching the stage prompt's default rule. The small `PlaceholderPanel` prop addition needed to render a non-"Requires Step" line is confirmed frontend-only (no route/data change). |
| 4 | `dispatch_enabled` label conflict | **Resolved — confirmed correct as already written in the design docs.** Source-verified: `CalmSafetyPosture.tsx`'s `SAFETY_EVIDENCE_FIELDS` already maps `dispatch_enabled` → `"Workflow dispatch"` (FE.1B.1, already shipped). `field-label-cleanup-map.md` already states this explicitly and correctly rejects the stage-prompt example rename ("Automation dispatch"). No further action needed; this is a correctly-resolved item, recorded here for completeness. |
| 5 | `delivery_package_ready_for_admin_console` → "Ready to publish" rename | **Genuinely open — cannot be resolved from source alone.** This is a semantic-meaning question (does "ready to publish" correctly describe what this field represents?), not a technical-feasibility question. Recommend either explicit PO/Claude Code confirmation of intended meaning before Codex applies it, or shipping the first implementation slice without this specific rename and adding it once confirmed. |

## 7. Claude Code confirmations

Per `product-owner-review-checklist.md` "For Claude Code" and `codex-implementation-notes.md` §3
("Needs Claude Code confirmation before implementing"):

**7.1 Authoritative `TASK_STATUSES` list — CORRECTION REQUIRED before Codex builds the status-label
map.** Read directly from `apps/admin-console/src/tasks/taskTypes.ts:34-52`, the authoritative
17-value enum is:

```text
draft, submitted, intake_review, clarification_needed, clarification_expired,
approved_for_execution, running, waiting_approval, blocked, failed, delivery_ready,
changes_requested, qa_rerun_requested, accepted, rejected, archived, canceled
```

`ExecutiveOverview.tsx`'s existing `TASK_STATUS_LABELS` already maps 9 of these: `intake_review`,
`clarification_needed`, `clarification_expired`, `approved_for_execution`, `running`,
`waiting_approval`, `delivery_ready`, `changes_requested`, `qa_rerun_requested`. The genuinely
**missing 8 entries** are: `draft`, `submitted`, `blocked`, `failed`, `accepted`, `rejected`,
`archived`, `canceled`.

`microcopy-guide.md`'s own "Missing entries to add" list (`draft`, `blocked`, `aborted`, `canceled`,
`completed`, `devops`, `requirement_analysis`) is **not accurate**: it correctly includes `draft`,
`blocked`, and `canceled`, but also lists four values that **do not exist** in the authoritative
enum (`aborted`, `completed`, `devops`, `requirement_analysis`), and it omits four real values that
do exist (`submitted`, `failed`, `accepted`, `rejected`, `archived` — five, not four). Codex must
build the shared status-label map from the corrected 8-entry list above, not from the design doc's
list, to avoid both dead map entries for non-existent statuses and missing labels for five real
ones.

**7.2 Which pages render raw IDs/hashes — narrower set confirmed than the design assumed.**
Confirmed FE.1D-eligible (category B, in scope): `TaskDetail.tsx` — raw `KeyValueTable` full-object
dump (line 54) and raw snake_case safety-panel labels (lines 58-81). Confirmed present but **not
enumerated by the design docs, so not authorized as part of this FE.1D round**: `TaskWorkroom.tsx`
(raw truncated `body_hash`, line 487) and the roughly 8 Platform Ops/Audit/Demo-Evidence pages that
render literal snake_case column headers via the shared `EvidenceTable` component and local `Table`
helpers (`AuditEvidence.tsx`, `DemoEvidence.tsx`, and by the same pattern likely others under
Platform Ops). Recommend these be scoped into a later, separately-designed slice with their own
before/after label map, rather than left to Codex's improvisation inside FE.1D.

**7.3 Task Detail raw `KeyValueTable` disclosure scope — CONFIRMED in scope for FE.1D.** Wrapping
`TaskDetail.tsx`'s raw object dump in a `<details>`/"Technical details" disclosure (category B) and
relabeling its safety-panel `<li>` items to the already-shipped `SAFETY_EVIDENCE_FIELDS` labels
(category A) are both frontend-only, display-only changes. One item needs Codex judgment during
implementation: `external_actions_enabled` in `TaskDetail.tsx` is a simplified aggregate that does
not map 1:1 to a single `SAFETY_EVIDENCE_FIELDS` entry (which has three separate external-integration
fields); recommend Codex use a descriptive label such as "External integrations" rather than
inventing a new aggregate concept.

**7.4 `PlaceholderPanel` non-"Requires Step" line — CONFIRMED safe.** A prop addition (e.g. an
optional `note`-style line that renders instead of "Requires Step {requiredStep}." when
`requiredStep` is a "Planned"-style value) is a small, self-contained component change with no
route or data impact.

**7.5 `delivery_package_ready_for_admin_console` → "Ready to publish"** — see §6 item 5; not
resolvable by Claude Code alone, forwarded as a genuine open decision.

## 8. Recommended Codex implementation slicing

**Recommended option: Option C (split more granularly)**, given the number of distinct files/
concerns identified above and the stage prompt's own preference for small, reviewable PRs. A single
combined PR (Option A) would mix a zero-risk single-file nav change with a higher-review-cost
multi-component microcopy change and a safety-adjacent (though logic-untouched) cosmetic change,
making the review harder to reason about in one pass.

```text
Slice 1 (FE.1D-A) — Nav.tsx only: group subtitles, Soon/read-only/evidence badges, shortened
  Platform Ops labels, Platform Ops compact density class. Single file, lowest risk, no PO-blocking
  item (Platform Ops sub-headers deferred/optional — see below).

Slice 2 (FE.1D-B) — Shared status-label module + TaskList.tsx + ExecutiveOverview.tsx microcopy:
  extract/complete TASK_STATUS_LABELS using the corrected 8-entry list (§7.1), relative-time display
  for created_at/updated_at, production_effect/requires_approval chips-only-when-true, empty-state
  standardization, Overview metric relabels. "New task" vs "Create task" button label held pending
  PO decision (§6 item 2) -- ship the rest of this slice first if the label decision lags.

Slice 3 (FE.1D-C) — TaskDetail.tsx: relabel safety-panel fields to shipped SAFETY_EVIDENCE_FIELDS
  wording, wrap the raw KeyValueTable dump in a "Technical details" disclosure. Self-contained,
  single file.

Slice 4 (FE.1D-D) — Placeholder/empty-state consistency + safety wording cosmetic polish:
  App.tsx requiredStep prop normalization ("66S or later" -> "66S"), PlaceholderPanel "Planned"
  line addition, Notifications placeholder copy, CalmSafetyPosture.tsx dash/case consistency
  (title-string literals only -- no change to getCalmSafetyPosture()'s logic).

Deferred / out of this authorization round entirely:
  - Platform Ops optional visual sub-headers (density-spec.md #4) -- ship only if PO explicitly
    wants it; otherwise the design's own documented fallback (labels+markers+density only) applies.
  - TaskWorkroom.tsx body_hash relabel, and the ~8-page Platform Ops/Audit/Demo-Evidence raw
    column-header surface (#7.2) -- no before/after map exists yet; needs its own design pass.
  - delivery_package_ready_for_admin_console rename, pending #6 item 5.
```

Risk read against the stage prompt's own risk list: navigation changes are confirmed low-risk
(Nav.tsx label-only, single file); microcopy/field-label changes touch multiple components,
which is exactly why slices 2 and 3 are kept separate rather than combined; safety wording is
confirmed to avoid reopening logic (§5 row 12) and is isolated into its own slice (4) specifically
so that diff is trivially reviewable as text-only; Platform Ops density scope creep is contained by
deferring sub-headers and the wider evidence-table surface (§7.2) out of this round.

## 9. Forbidden items (confirmed excluded)

```text
1. No new routes -- confirmed: App.tsx route list unchanged by any FE.1D proposal.
2. No new endpoints -- confirmed: no backend/API file in the design diff or in any proposal.
3. No backend/API/DB/workflow changes -- confirmed: diff and all proposals are frontend-display-only.
4. No SPA deep-link fallback fix -- confirmed excluded in every design doc; known-gap record
   (docs/frontend/admin-console-spa-deep-link-fallback-known-gap.md) untouched by the design diff.
5. No two-way URL sync -- confirmed: not proposed anywhere; TaskList.tsx's existing read-only
   useSearchParams() usage (from FE.1C.1) is unaffected.
6. No real Delivery / Reminder / Notifications / Pipeline functionality -- confirmed: all remain
   PlaceholderPage/PlaceholderItem, wording-only changes.
7. No safety logic changes -- confirmed: CalmSafetyPosture.tsx's getCalmSafetyPosture() tone/
   threshold/field-set logic is untouched by every proposal; only title-string literals change.
8. No RBAC changes -- confirmed: not proposed; no backend/server-side authority touched.
9. No new task status model -- confirmed: TASK_STATUSES enum in taskTypes.ts is unchanged; only
   the display-label map for existing values is extended (see #7.1 for the corrected list).
10. No production/external actions -- confirmed: no proposal invokes any workflow dispatch/resume,
    GitHub/Discord/LLM external call, or any other outbound integration.
```

## 10. Known platform gaps excluded

```text
Admin Console SPA deep-link / hard-refresh fallback (docs/frontend/admin-console-spa-deep-link-
fallback-known-gap.md) -- a backend gap (Starlette StaticFiles(html=True) has no catch-all
fallback, apps/orchestrator/src/main.py:260). Explicitly out of FE.1D scope by every design doc
and confirmed again here: no proposal in this review touches apps/orchestrator or any backend path.
Remains tracked separately, unresolved, non-blocking.
```

## 11. Local Artifact Reconciliation result

```text
git diff --name-only main...origin/design/66ui4-fe1d-navigation-microcopy: 14 files, all under
  docs/design/66ui4-fe1d-navigation-microcopy/**, docs/stages/66ui4-fe1d-navigation-microcopy-
  design/**, scripts/, tests/, and source/progress.md -- matches the design branch's own
  allowed_paths list exactly, zero forbidden-path matches.
git grep for local Windows absolute paths ("C:/Users", "C:\Users"), local username ("stpadmin"),
  "Documents/Codex" path, ".tools" across every file in the diff: the only matches are (a) the
  design branch's own verifier script's INFRA_SHAPES regex, which contains "stpadmin" as a literal
  forbidden-pattern string to check FOR (not a leaked path), and (b) source/progress.md's own prior-
  stage descriptive text stating that no such paths were found in earlier stages -- both are
  expected, non-leaking matches consistent with every prior stage's Local Artifact Reconciliation
  in this project.
git ls-files check for .tools/ or platform-progress-admin-console-proposal.md paths in the diff:
  no matches.
Secret-shape scan (private keys, GitHub/AWS/Slack/Anthropic token shapes) inside every design doc:
  no matches (also independently confirmed by the design branch's own verifier, which runs the same
  class of check and PASSed).
Follow-up required: none.
```

## 12. Whether Codex implementation can be authorized next

Not by this document. This review is technical-readiness only. Authorization requires an explicit
Product Owner go-ahead, and — per §6 — two decisions genuinely need the Product Owner's input first
("New task" vs "Create task"; `delivery_package_ready_for_admin_console` rename meaning) before the
slices touching those specific strings can proceed; the remaining slices are not blocked on those
two decisions and could proceed once Codex is authorized and given the corrected boundary from this
review (in particular the corrected `TASK_STATUSES` list in §7.1 and the narrower raw-ID/hash scope
in §7.2).

## 13. Whether PR #12 is merge-ready after PO review

PR #12 (the design branch itself) is a documentation-only design artifact — it contains no runtime
code, so "merge-ready" here means ready for the Product Owner to accept the design direction (per
`design-collaboration/SKILL.md`'s review chain), not a runtime deployment readiness question. Given
this review's PASS_WITH_GAPS verdict (design is usable; two decisions and one correction are needed
before Codex proceeds on the affected slices), PR #12 is **ready for Product Owner design-acceptance
review**, with the corrections in §7.1/§7.2 and the open decisions in §6 items 2 and 5 carried
forward as the scope Codex must respect once authorized.

## Overall verdict

```text
PASS_WITH_GAPS
```

Rationale (matching the stage's own decision criteria): the design is usable and can be safely
converted into bounded frontend-only implementation; no forbidden backend/API/DB/workflow item is
included or unflagged; the SPA deep-link fallback remains separate; safety logic remains untouched;
Codex remains unauthorized; no local artifact exposure. It is PASS_WITH_GAPS rather than a clean PASS
because (a) two Product Owner decisions are required before the affected slices can proceed (§6
items 2, 5), and (b) one design input needs trimming/correction before implementation — the status-
label "missing entries" list in `microcopy-guide.md` referenced non-existent enum values and omitted
real ones (§7.1), and the raw-ID/hash page scope needs narrowing to what was actually verified in
source (§7.2). None of these gaps involve a safety or scope violation.

## Statement

Review only. No runtime code changed by this document. No backend/API/database/workflow change. No
new endpoint. No deployment. No merge. No production/external action. Codex remains unauthorized.
FE.1D implementation remains unauthorized. SPA deep-link fallback remains excluded and separately
tracked.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
