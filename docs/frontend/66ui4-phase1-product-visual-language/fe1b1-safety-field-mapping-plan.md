# Safety Field Mapping Calibration Plan — Step 66UI.4-FE.1B.1

> **Planning document only. No runtime code changed. No backend/API/database/workflow change. No
> `/operations/safety` response shape change. Codex not authorized by this document.**

Owner: Claude Code (Lead Engineer / Architecture Owner — see
`docs/process/role-responsibility-matrix.md`). This plan addresses the Product-Owner-accepted,
non-blocking gap recorded at Step 66UI.4-FE.1B-V/FE.1B-MD: the Calm Safety Posture badge shows
"Unavailable" instead of "Safe" on the test runtime.

## 1. Accepted gap (restated exactly, unchanged)

```text
Safety badge currently displays "Unavailable" rather than "Safe" because the real
/operations/safety response is missing these expected fields:
- dispatch_enabled
- resume_dispatch_enabled
- approval_required
- requires_approval

This is an accepted, non-blocking Product Owner validation gap.
The conservative FE.1B logic is correct because it does not claim safe when evidence is incomplete.
This is not a rollback condition.
This is not a safety defect.
```

## 2. Live schema inspection (sanitized)

Inspected the live `/operations/safety` response on the test runtime (`main` at merge commit
`5a2bc4e`, i.e. current). No raw response, secret, or infrastructure identifier is reproduced below —
only a categorized field summary.

```text
Total top-level fields in the live response: 571
Fields relevant to CalmSafetyPosture's mapping, confirmed present and correctly typed:
  - production_executed_true_count            -> int  -> 0
  - workflow_production_executed_true_count    -> int  -> 0
  - task_api_workflow_dispatch_enabled          -> bool -> False
  - task_workroom_resume_dispatch_enabled       -> bool -> False
  - github_external_write_enabled                -> bool -> False
  - discord_external_send_enabled                -> bool -> False
  - llm_external_call_enabled                    -> bool -> False
  - production_delegation_allowed                 -> bool -> False
  - result                                        -> str  -> "safe"

Fields confirmed genuinely absent from the live response:
  - dispatch_enabled
  - resume_dispatch_enabled
  - approval_required
  - requires_approval
```

## 3. Root cause (confirmed via backend source, not assumed)

All four "missing" fields are **not missing data** — they are **fields that were never valid to
expect at this endpoint**, because each one is a genuine field of a *different, already-existing*
endpoint, scoped to an individual task, workroom message, or workflow, not to the global safety
summary:

| Field | Where it actually exists | Confirmed scope |
| --- | --- | --- |
| `dispatch_enabled` | `apps/orchestrator/src/task_api.py` (task get/submit responses), `apps/orchestrator/src/workroom_api.py` (workroom message/create responses) | Per-task / per-workroom-message; always `False` (hardcoded) |
| `resume_dispatch_enabled` | `apps/orchestrator/src/workroom_api.py` (workroom responses) | Per-workroom-message; always `False` (hardcoded) |
| `approval_required` | `apps/orchestrator/src/workflow.py`, `workflow_events.py`, `resume_engine.py`, and per-row in `GET /operations/workflows` (`operations.py:1538`) | Per-workflow |
| `requires_approval` | `Task` type (`apps/admin-console/src/tasks/taskTypes.ts`), already rendered per-task on `TaskList.tsx` as a badge | Per-task |

**This is a category/scope error inherited from the pre-FE.1A `SafetyStatusBar.tsx`'s original flat
field list, carried forward unchanged into FE.1B's `CalmSafetyPosture` mapping — not a genuine
data-availability gap, and not something a backend change should "fix."** The four fields were never
supposed to be read from `/operations/safety`; they belong to endpoints the frontend already calls
for other purposes (`/tasks`, `/tasks/{id}/workroom`, `/operations/workflows`).

**The existing, already-tracked global proxies are the correct fields for this purpose:**
`task_api_workflow_dispatch_enabled` and `task_workroom_resume_dispatch_enabled` are the genuine
system-wide "is task/workroom dispatch enabled" signals (both present, both currently `False`) — they
are already part of `AUTOMATION_FIELDS`. Once the two phantom field names are removed from the
expectation list, `AUTOMATION_FIELDS` legitimately evaluates to "all false," and the "Safe" tone
becomes reachable using only real, correctly-scoped data.

**Approval has no valid global equivalent, and should not have one.** Whether approval is required
varies per task/workflow; a single global "is approval required" boolean would not be a meaningful
safety-summary concept in the first place. The correct per-task signal already exists and is already
shown (`TaskList.tsx`'s `requires_approval` badge). The calibration should retire the *global*
"Approval requirement" fact from the safety-summary component rather than search for a substitute
global field that shouldn't exist.

## 4. A cautionary finding: do not substitute by name-similarity alone

While tracing the live schema, this review found a field named `work_item_dispatch_enabled` (present,
`true`) — superficially similar to the missing `dispatch_enabled`. Tracing its source
(`shared/sdk/work_items/safety.py`) shows it is a **feature-enabled flag** ("the multi-project
work-item dispatch subsystem exists"), always hardcoded `true`, entirely distinct in meaning from a
risk flag like "will something dispatch automatically." The genuinely risk-relevant fields in that
same module — `work_item_dispatch_external_side_effect_enabled`,
`work_item_dispatch_github_write_enabled`, `work_item_dispatch_argocd_sync_enabled`,
`work_item_dispatch_production_action_enabled` — are the ones that matter, and are all confirmed
`False` today. **This is recorded as a hard rule for FE.1B.1: never substitute a field into the
mapping on the basis of a similar name alone; confirm its actual semantics against backend source (or
a live response) first**, exactly as this planning stage did. Naively wiring up
`work_item_dispatch_enabled` in place of `dispatch_enabled` would have been a plausible-looking but
incorrect fix.

## 5. Required analysis (per stage prompt)

1. **What `/operations/safety` actually returns today:** 571 fields; the 9 fields CalmSafetyPosture
   needs and correctly reads are present and correctly typed (§2).
2. **What FE.1B currently expects:** 14 fields in `SAFETY_EVIDENCE_FIELDS`/`AUTOMATION_FIELDS`/
   `EXTERNAL_FIELDS`/`PRODUCTION_COUNT_FIELDS`, four of which (§1) do not exist at this endpoint.
3. **Which expected fields are missing:** `dispatch_enabled`, `resume_dispatch_enabled`,
   `approval_required`, `requires_approval` — see §3 for why, precisely.
4. **Which existing fields can safely support the intended facts:**
   `task_api_workflow_dispatch_enabled` + `task_workroom_resume_dispatch_enabled` fully and correctly
   support the "Automated workflow dispatch" fact without any substitute needed. No existing global
   field should be pressed into service for "Approval requirement" — see #5.
5. **Which safety facts should remain "not reported" due to insufficient evidence:** none, once §3's
   recalibration is applied — every remaining fact (production, automation, external, delegation) is
   backed by a genuinely-present, correctly-scoped field. "Approval requirement" should not be
   "not reported" either — it should be **removed as a global fact** (see #6) rather than shown as an
   unresolved unknown, since a global answer was never a coherent question.
6. **Whether "Safe" can be shown using existing fields without overclaiming:** yes — once
   `dispatch_enabled`/`resume_dispatch_enabled` are dropped from `AUTOMATION_FIELDS` (replaced by
   nothing; the two remaining task/workroom-dispatch fields already suffice) and the global
   "Approval requirement" fact/fields are retired, `automationOff && externalOff && noProduction`
   evaluates `true` against the live payload today, and "Safe — no automated or production actions
   will run." becomes an accurate statement, not an overclaim.
7. **Whether any current copy should change:** yes, one change — the "Approval requirement" line
   should be replaced with a line that honestly states approval is tracked per task (e.g. "Approvals:
   tracked per task — see Task List"), rather than either fabricating a global state or perpetually
   showing "not reported" for a question that was never answerable at this scope. No other summary
   copy needs to change; "Safe — no automated or production actions will run." remains correct as
   originally specified in `calm-safety-posture-spec.md` once the field list is corrected.
8. **Whether the summary badge should allow a partial-safe/limited-evidence state:** yes, as a
   defensive design improvement independent of this specific bug — recommend FE.1B.1 introduce a
   fourth tone (e.g. "Safe (limited evidence)") for the case where some, but not all, of the
   *genuinely-global* fields are missing in a future backend change, so a future partial-data
   scenario degrades gracefully rather than falling all the way to "Unavailable" or incorrectly to
   "Safe." This is a forward-looking hardening recommendation, not a requirement to close the current
   gap (which resolves cleanly via §3/#6 without needing this new state).
9. **How raw evidence remains accessible:** unchanged — `SAFETY_EVIDENCE_FIELDS`'s `Evidence /
   details` disclosure continues to render every tracked field and its exact value unconditionally;
   FE.1B.1 should simply remove the four phantom field rows (or, if kept for transparency, always
   show them as "not applicable at this endpoint" rather than "not reported," to avoid implying a
   data gap that isn't one) and add a short note that approval status is tracked per task.
10. **What tests should cover real-schema cases:** see §7.

## 6. Recommended calibration (frontend-only, plan level — not implemented in this stage)

```text
1. Remove "dispatch_enabled" and "resume_dispatch_enabled" from AUTOMATION_FIELDS. The remaining
   two fields (task_api_workflow_dispatch_enabled, task_workroom_resume_dispatch_enabled) are the
   correct, already-present, already-global signals for this fact.
2. Remove the global "Approval requirement" fact and its backing fields (approval_required,
   requires_approval) from getCalmSafetyPosture()'s tone computation and facts list. Replace with a
   short, honestly-scoped note ("Approvals: tracked per task — see Task List") rather than a
   pretended global boolean.
3. Keep SAFETY_EVIDENCE_FIELDS's raw-evidence disclosure accurate: either drop the four phantom rows
   or relabel them "Not applicable at this endpoint" (never "not reported," which implies a data gap
   rather than a scope mismatch).
4. Do not substitute any field by name-similarity alone (see §4) -- confirm semantics against
   backend source or a live response before wiring up any new field.
5. (Optional, future hardening, non-blocking) Consider a fourth "limited evidence" tone for a
   future case where a genuinely-global field goes missing, distinct from today's scope-mismatch
   bug.
```

No backend/API/database/workflow change is required or recommended to close this gap. If a future
stage wants `/operations/safety` to also carry global-scope approval/dispatch fields for other
reasons, that is explicitly **out of scope, future-only**, not part of this plan or of FE.1B.1.

## 7. Test cases required for FE.1B.1

```text
1. Real-schema fixture test: given the exact field set confirmed live in §2 (no dispatch_enabled/
   resume_dispatch_enabled/approval_required/requires_approval present), getCalmSafetyPosture()
   returns tone "safe".
2. Regression test: if task_api_workflow_dispatch_enabled or task_workroom_resume_dispatch_enabled
   becomes true, tone becomes "attention" (unchanged behavior, re-asserted against the corrected
   field list).
3. Test: the "Approval requirement" fact is replaced by the per-task-scoped note in all fixtures,
   and no longer contributes to tone (approvalRequired-driven "attention" no longer exists in this
   form -- approval-driven attention, if desired, would need its own future per-task-aware design,
   out of scope here).
4. Test: SAFETY_EVIDENCE_FIELDS no longer claims "not reported" for the four retired fields; either
   they are absent from the evidence list or labeled "Not applicable at this endpoint".
5. Test: existing safe/attention/unavailable fixtures for production count and external integrations
   continue to pass unchanged (regression safety net).
```

## 8. Statement

Planning document only. No runtime code changed. No backend/API/database/workflow change.
`/operations/safety` response shape unchanged. No production/external action. Codex not authorized by
this document. FE.1C/FE.1D remain unauthorized.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
