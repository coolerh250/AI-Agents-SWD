# AI Agent Team — Functional POC Control Center Specification

> Owner: Claude Design (UX / IA / Product Experience partner). Step 66SYNC.1-C. **Read-only
> reconciliation + specification. No frontend/runtime/backend/API change. No Codex authorization.
> No final visual design. No deployment or Agent workflow execution. Every classification is based
> on the committed partner inventories at canonical main `c1db4cc`, not assumed.**

```text
CONTEXT_ID:                     AIAT-SYNC-20260803-01
Canonical main:                 c1db4cc
Claude Code sync head:          828ea90  (planning/66sync1-claude-code-state-reconciliation)
Codex sync head:                78aa4ee  (planning/66sync1-codex-frontend-reconciliation)
UNRESOLVED_CANONICAL_MISMATCHES: 0
OPEN_PRODUCT_OWNER_DECISIONS:    3  (D-1, D-2, D-3)
production_executed_true_count:  0
Basis:                          master partner-context-snapshot-20260803 (828ea90);
                                Codex frontend gap register + acknowledgement (78aa4ee)
```

This spec defines the *experience and information architecture* of a Product-Owner-facing POC
Control Center. It authorizes nothing; it does not select any option; it marks every
decision-gated area `DECISION_DEPENDENT`.

---

## 1. Central constraint carried from the partner snapshots

**Path A ≠ Path B (D-1).** The operator-facing Task API (`/tasks`, rendered by TaskNew / TaskList /
TaskDetail / TaskGraph / TaskWorkroom) does **not** dispatch to the agent pipeline — every response
returns `dispatch_enabled: false` and `submit()` stops at `intake_review`. The working agent
pipeline is a separate lineage (`workflow.py::dispatch_node → dispatch.py → stream.tasks → the ten
implemented agents`). **No code path connects them.** Therefore this spec must **never** present the
current Task surface as the POC execution source of truth. Any "watch my task run" experience is
`DECISION_DEPENDENT` on D-1.

**Runtime Agents ≠ External AI Partners (D-2).** Ten runtime agents exist and are tested;
`backend-agent` and `frontend-agent` are ABSENT (empty dirs). External AI partners (Claude Code,
Codex, Claude Design) do real work but are **not** runtime Agent services. The activity model must
visibly distinguish `runtime_agent` from `ai_partner`, and must never render a partner as an
implemented runtime agent.

**Generation mode is constrained (D-3).** The runtime real-LLM provider is **plan-only** (patch/test
generation raises by design); code generation is a deterministic template generator (three families:
documentation, demo_api, simple_utility). Provenance and generation-mode must be shown; the
plan-only restriction must not be presented as removable, and this spec does **not** recommend
lifting it.

---

## 2. Product Owner POC journey (13 steps)

Each step records: PO objective · Information required · Primary action · System response · Evidence
displayed · Approval required · Failure state · Recovery path · Current UI support · Frontend gap ·
Backend/API dependency · Decision dependency.

### Step 1 — Product Owner inputs a development goal
- **PO objective:** state what should be built.
- **Information required:** goal text, target outcome, constraints.
- **Primary action:** submit a development goal.
- **System response:** goal captured; a problem-statement interpretation begins.
- **Evidence displayed:** the captured goal + timestamp + actor.
- **Approval required:** none yet.
- **Failure state:** goal not captured / validation error.
- **Recovery path:** re-submit; edit while draft.
- **Current UI support:** partial — `/tasks/new` captures a task, but that surface does not dispatch.
- **Frontend gap:** FE-POC-G1 (entry point), FE-POC-G9 (unified current work).
- **Backend/API dependency:** POC entry-point contract.
- **Decision dependency:** **D-1**.

### Step 2 — System interprets the problem statement
- **PO objective:** confirm the system understood the goal.
- **Information required:** interpreted problem statement, assumptions.
- **Primary action:** review interpretation.
- **System response:** shows interpretation + assumptions (Intake/Requirement agent lineage).
- **Evidence displayed:** interpretation summary, not raw prompts.
- **Approval required:** none (review only).
- **Failure state:** interpretation unavailable / low confidence.
- **Recovery path:** clarify goal; ask for re-interpretation.
- **Current UI support:** partial — requirement agent exists (Path B), not shown against a PO goal.
- **Frontend gap:** FE-POC-G4 (requirement traceability).
- **Backend/API dependency:** requirement linkage contract.
- **Decision dependency:** D-1.

### Step 3 — PO reviews scope and non-scope
- **PO objective:** agree what is in / out of scope.
- **Information required:** scope, explicit non-scope.
- **Primary action:** review scope statement.
- **System response:** scope + non-scope presented for approval.
- **Evidence displayed:** scope list, non-scope list.
- **Approval required:** **scope approval** (Step 4).
- **Failure state:** scope incomplete/ambiguous.
- **Recovery path:** request scope revision.
- **Current UI support:** none formal.
- **Frontend gap:** FE-POC-G10 (fragmented), new Scope & Acceptance screen.
- **Backend/API dependency:** scope/acceptance read model.
- **Decision dependency:** D-1.

### Step 4 — PO approves requirements and acceptance criteria
- **PO objective:** lock requirements + acceptance criteria.
- **Information required:** requirements list, acceptance matrix.
- **Primary action:** **approve** (requirements approval).
- **System response:** records approval; unlocks planning.
- **Evidence displayed:** approved requirements, acceptance matrix, approval record.
- **Approval required:** **requirements approval** (PO).
- **Failure state:** approval expired / rejected.
- **Recovery path:** revise + re-approve.
- **Current UI support:** none formal.
- **Frontend gap:** Approval Center + Scope & Acceptance screens.
- **Backend/API dependency:** approval queue + acceptance contract.
- **Decision dependency:** D-1.

### Step 5 — AI Team builds an execution plan
- **PO objective:** see how the work will be done.
- **Information required:** plan, task graph, responsibilities.
- **Primary action:** review plan.
- **System response:** plan produced (project-planner agent; note D-3 plan-only for LLM plans).
- **Evidence displayed:** plan summary, generation mode, provenance.
- **Approval required:** **execution-plan approval** (Step 6).
- **Failure state:** plan generation blocked (unclassifiable → template generator returns `blocked`).
- **Recovery path:** refine goal/scope; re-plan.
- **Current UI support:** partial — planner agent exists; no PO plan-review surface.
- **Frontend gap:** Execution Plan screen; FE-POC-G3 (generation mode).
- **Backend/API dependency:** plan read model + provenance.
- **Decision dependency:** **D-1**, **D-3**.

### Step 6 — PO reviews task graph and responsibility allocation
- **PO objective:** understand who/what does each part.
- **Information required:** task graph, per-node owner (runtime_agent vs ai_partner vs human).
- **Primary action:** review + approve plan.
- **System response:** task graph rendered with owners and states.
- **Evidence displayed:** nodes, dependencies, assigned actor + type.
- **Approval required:** **execution-plan approval** (PO).
- **Failure state:** graph incomplete / owner unresolved (esp. backend/frontend — D-2).
- **Recovery path:** reassign / re-plan.
- **Current UI support:** partial — `/task-graph` renders the Path A model (non-dispatching).
- **Frontend gap:** FE-POC-G2 (agent vs partner), FE-POC-G4.
- **Backend/API dependency:** task-graph read model with actor typing.
- **Decision dependency:** **D-1**, **D-2**.

### Step 7 — AI Agents and AI partners begin collaboration
- **PO objective:** see work start.
- **Information required:** who started, on what, when.
- **Primary action:** observe (read-only).
- **System response:** activity stream begins.
- **Evidence displayed:** actor, action summary, input/output artifact refs, started time, status.
- **Approval required:** none (unless a gated action arises).
- **Failure state:** actor fails to start / blocked.
- **Recovery path:** retry / escalate (Operator).
- **Current UI support:** partial — `/agent-executions` shows runtime agent rows only.
- **Frontend gap:** FE-POC-G2, FE-POC-G9; Agent/Partner Timeline screen.
- **Backend/API dependency:** unified activity read model (agents + partners).
- **Decision dependency:** **D-1**, **D-2**.

### Step 8 — PO observes real-time progress and artifacts
- **PO objective:** watch progress and see outputs.
- **Information required:** live status, artifacts, provenance.
- **Primary action:** observe; open artifacts.
- **System response:** progress + artifact list with provenance/generation-mode/safety-mode.
- **Evidence displayed:** artifacts, commit/branch/Draft PR, test evidence, review evidence.
- **Approval required:** none for observation.
- **Failure state:** stale/unavailable data; artifact missing.
- **Recovery path:** refresh; consult evidence page.
- **Current UI support:** partial/fragmented — `/qa-code`, `/workspace`, `/sandbox-github`, `/demo-evidence`.
- **Frontend gap:** FE-POC-G3, FE-POC-G7, FE-POC-G10; Artifact Explorer screen.
- **Backend/API dependency:** artifact provenance + source-control evidence contract.
- **Decision dependency:** **D-3**.

### Step 9 — PO handles approval, blocker, or scope change
- **PO objective:** unblock / decide on gated actions or scope changes.
- **Information required:** what needs a decision, impact, cost, external action.
- **Primary action:** approve / reject / request scope change.
- **System response:** records decision; routes accordingly.
- **Evidence displayed:** requester, reason, scope, impact, cost, external action, expiry, evidence.
- **Approval required:** **scope-change approval**, **external-operation approval**, others as raised.
- **Failure state:** approval expired; blocker unresolved.
- **Recovery path:** re-request; escalate; abort (with confirmation).
- **Current UI support:** placeholder — `/approvals` is a placeholder; Operator has package-level controls.
- **Frontend gap:** FE-POC-G5, FE-POC-G6; Approval Center + Blocker/Failure Center.
- **Backend/API dependency:** approval queue + blocker/DLQ read contract.
- **Decision dependency:** D-1.

### Step 10 — QA runs verification and defect remediation
- **PO objective:** confirm quality.
- **Information required:** QA results, defects, remediation state.
- **Primary action:** review QA outcome.
- **System response:** QA status (qa agent), defect list, remediation.
- **Evidence displayed:** QA report, pass/fail, defects, re-run outcome.
- **Approval required:** none (QA is verification, not PO approval).
- **Failure state:** QA failed; rerun failed.
- **Recovery path:** request changes / re-run QA (distinct — see §7 Delivery).
- **Current UI support:** partial — `/qa-code` shows workspace/QA summary.
- **Frontend gap:** QA Dashboard screen.
- **Backend/API dependency:** QA read model (task-scoped).
- **Decision dependency:** D-1.

### Step 11 — AI Team builds the delivery package
- **PO objective:** receive a reviewable delivery.
- **Information required:** the full delivery package (see §14).
- **Primary action:** open the delivery package.
- **System response:** package assembled (delivery-package agent).
- **Evidence displayed:** goal, requirements, acceptance matrix, branch, Draft PR, commits, tests,
  known limits, security boundary, run instructions, demo evidence, cost, external-op summary, audit.
- **Approval required:** leads to final acceptance (Step 12).
- **Failure state:** package incomplete.
- **Recovery path:** request changes; re-run QA; re-assemble.
- **Current UI support:** partial — `/delivery-package` shows latest package/gate/human-acceptance;
  `/delivery-inbox` and `/delivery-detail` are placeholders (Requires Step 66D).
- **Frontend gap:** FE-POC-G6, FE-POC-G7; Delivery Package screen.
- **Backend/API dependency:** Step 66D delivery/acceptance contract.
- **Decision dependency:** D-1.

### Step 12 — PO performs final acceptance
- **PO objective:** accept / accept-with-follow-up / reject.
- **Information required:** delivery package + acceptance matrix + evidence.
- **Primary action:** **final acceptance decision** (ACCEPTED / ACCEPTED_WITH_FOLLOW_UP / REJECTED).
- **System response:** records decision, reason, follow-ups, timestamp, actor.
- **Evidence displayed:** decision record + supporting evidence.
- **Approval required:** **delivery acceptance** (PO only — an agent "complete" is NOT acceptance).
- **Failure state:** cannot decide (missing evidence).
- **Recovery path:** request changes; re-run QA; re-deliver.
- **Current UI support:** placeholder — no PO-friendly final-acceptance surface.
- **Frontend gap:** FE-POC-G6; Final Acceptance screen.
- **Backend/API dependency:** Step 66D acceptance decision contract.
- **Decision dependency:** D-1.

### Step 13 — System presents a retrospective
- **PO objective:** learn what happened, cost, and follow-ups.
- **Information required:** timeline, cost, external actions, defects, follow-ups.
- **Primary action:** review retrospective.
- **System response:** retrospective assembled from audit + cost + acceptance.
- **Evidence displayed:** audit timeline, cost summary, external-op summary, follow-up items.
- **Approval required:** none.
- **Failure state:** incomplete history.
- **Recovery path:** consult audit evidence.
- **Current UI support:** partial — audit/metrics fragments; no consolidated retrospective.
- **Frontend gap:** Retrospective screen.
- **Backend/API dependency:** retrospective read model (audit + cost + acceptance).
- **Decision dependency:** D-1.

**Journey coverage: 13/13 steps documented. Approval points: 6 (requirements, scope,
execution-plan, external-operation, scope-change, delivery acceptance; abort confirmation is a
guarded confirmation, not a routine wait). Failure paths and recovery paths: documented per step.
Delivery path: Steps 11–12. Acceptance path: Step 12.**

---

## 3. D-1 — POC entry point (two non-binding UI models)

The current Task surface must **not** be assumed to be the POC execution source of truth. Three
concepts must be shown as distinct:

```text
1. Existing non-dispatching Task surface   (/tasks, dispatch_enabled=false)
2. Existing intake/work-item/workflow pipeline  (workflow.py -> dispatch.py -> stream.tasks -> agents)
3. Proposed POC goal-entry journey  (Step 1 above)
```

**Option A — Dedicated POC Development Goal entry → Project → Work Item → Workflow.** A new goal-entry
surface that maps directly onto the dispatching pipeline; the legacy Task surface stays as-is and is
not the POC path.

**Option B — Extend existing Task entry → explicit conversion/dispatch step → Work Item → Workflow.**
Reuse the familiar Task entry, then add an explicit, clearly-labelled "convert/dispatch to the agent
pipeline" step so the user knows exactly when execution begins.

Non-binding UX assessment (not a selection):

| Dimension | Option A | Option B |
| --- | --- | --- |
| Clarity of "when does it run" | high (separate surface) | high *if* the conversion step is explicit and unmissable |
| Reuses familiar Task UI | no | yes |
| Risk of "I thought my task was running" | lowest | present unless conversion step is prominent |
| Build effort (UI) | new surface | new conversion step over existing surface |
| Backend dependency | POC entry contract | POC entry + conversion/dispatch contract |

```text
Decision dependency: D-1
Status: PRODUCT_OWNER_DECISION_REQUIRED
Claude Design position: non-binding assessment only. NOT selected. NOT approved.
```

---

## 4. D-2 — Backend/Frontend workstream (two observability models)

The UI must support both, and must never disguise an external AI partner as a runtime Agent service.

**Runtime Agent model** — fields: agent service, execution id, workflow event, retry/DLQ, runtime
artifact. Applies to the ten implemented runtime agents.

**External AI Partner model** — fields: partner (Claude Code / Codex / Claude Design), assigned task,
execution status, artifact, commit, branch, Draft PR, test evidence, review result, handoff. Applies
to work done by external AI partners (e.g. backend/frontend development for which no runtime agent
exists — G-2).

```text
Decision dependency: D-2   (affects Agent/Partner Timeline, Project Overview, Task Graph,
                            Artifact Explorer, Delivery Package)
Status: PRODUCT_OWNER_DECISION_REQUIRED
```

---

## 5. D-3 — Code-generation mode (display model)

Every artifact must be able to display its **generation mode** and provenance:

```text
Generation mode:
  - plan-only
  - deterministic-template
  - external-partner-generated
  - human-authored
  - future autonomous-runtime-generated   (labelled clearly as NOT currently enabled)

Alongside: implementation partner · artifact provenance · review status · test status · safety mode
```

This spec does **not** recommend lifting the plan-only restriction; `future
autonomous-runtime-generated` is shown only as a labelled, not-enabled state.

```text
Decision dependency: D-3   (affects Artifact Explorer, QA Dashboard, Delivery Package, Execution Plan)
Status: PRODUCT_OWNER_DECISION_REQUIRED
```

---

## 6. Information architecture (per-area reuse judgement, based on Codex inventory)

Reuse vocabulary: `reuse existing route` · `reuse with enhancement` · `consolidate multiple routes` ·
`new route required` · `new panel/tab required` · `backend API dependency` · `PO decision dependency`.

| IA area | Judgement | Basis (Codex inventory) |
| --- | --- | --- |
| POC Overview | new route/panel required | no unified POC overview (FE-POC-G10) |
| Goal and Acceptance | new route required | no scope/acceptance surface |
| Requirements | new panel + backend dependency | no requirement traceability (FE-POC-G4) |
| Work Items | reuse with enhancement (`/delivery`, `/projects`) + PO decision (D-1) | operational context exists, not POC-linked |
| Task Graph | reuse with enhancement (`/task-graph`) + PO decision (D-1, D-2) | renders Path A (non-dispatching) |
| Agent and Partner Activity | consolidate + new panel + PO decision (D-2) | `/agent-executions` runtime-only |
| Artifacts and Evidence | consolidate multiple routes (`/qa-code`,`/workspace`,`/sandbox-github`,`/demo-evidence`) + backend dependency (D-3) | fragmented (FE-POC-G3/G7) |
| Approvals and Blockers | new route required + backend dependency | `/approvals` placeholder (FE-POC-G6) |
| Failures and Recovery | new route + backend dependency | `/dlq-retry` placeholder (FE-POC-G5) |
| QA and Validation | reuse with enhancement (`/qa-code`) + backend dependency | summary only |
| Delivery Package | reuse with enhancement (`/delivery-package`) + new inbox/detail + 66D dependency | inbox/detail placeholders (FE-POC-G6) |
| Final Acceptance | new route required + 66D dependency | no PO acceptance surface |
| Cost and External Actions | consolidate + backend dependency | split across pages (FE-POC-G8) |
| Safety | reuse existing (`/safety`, calm posture) + POC-scoped enhancement | global posture exists |
| Retrospective | new route required + backend dependency | none consolidated |

### 6.1 Unified vs fragmented experience (two non-binding IA options)

Codex determined current POC visibility is **fragmented** (FE-POC-G10). Two options, not selected:

**Option 1 — Unified POC Control Center:** a single project-level route with an overview + tabs
(the IA areas above as tabs/panels).

**Option 2 — Coordinated existing routes:** keep existing pages, add a POC Overview plus a
consistent navigation/context header that threads goal→delivery context across them.

| Dimension | Option 1 (Unified) | Option 2 (Coordinated) |
| --- | --- | --- |
| Navigation clarity | high (one place) | medium (context header helps) |
| Data consistency | high if one read model | depends on cross-endpoint consistency |
| Implementation effort | higher (new container) | lower (reuse + header) |
| Backend read-model dependency | strong (unified POC read model) | moderate (coordinated contracts) |
| PO observation efficiency | high | medium-high |
| Mobile/responsive impact | one responsive surface to design | many surfaces to keep consistent |

```text
Claude Design position: non-binding. NOT selected. Recommended for Product Owner discussion.
```

---

## 7. Required screen specifications (15)

Each screen: Purpose · Primary user · Entry point · Primary data · Primary actions · Read-only
actions · Approval actions · Status states · Empty · Loading · Error · Blocked · Retry · Completed ·
Evidence links · Current implementation · Frontend dependency · Backend dependency · Decision
dependency.

### 7.1 POC Goal Entry
- **Purpose:** capture a development goal to start the POC.
- **Primary user:** Product Owner. **Entry point:** POC Control Center / Overview.
- **Primary data:** goal text, constraints, target outcome.
- **Primary actions:** submit goal. **Read-only:** view draft. **Approval:** none.
- **Status states:** Not Started, Ready, In Progress, Waiting for Product Owner.
- **Empty:** "Describe the goal for the AI team." **Loading:** skeleton. **Error:** readable submit
  error. **Blocked:** entry disabled pending D-1. **Retry:** re-submit. **Completed:** goal captured.
- **Evidence links:** captured goal record.
- **Current implementation:** partial (`/tasks/new`, non-dispatching). **Frontend dependency:** new
  goal-entry surface. **Backend dependency:** POC entry contract. **Decision dependency:** **D-1**.

### 7.2 Scope and Acceptance Review
- **Purpose:** review/approve scope, non-scope, requirements, acceptance criteria.
- **Primary user:** PO. **Entry:** after goal interpretation.
- **Primary data:** scope, non-scope, requirements, acceptance matrix.
- **Primary actions:** approve requirements/scope; request revision. **Approval:** requirements
  approval, scope approval.
- **Status states:** Ready, Waiting for Approval, Accepted, Rejected.
- **Empty/Loading/Error/Blocked/Retry/Completed:** "No scope yet" / skeleton / readable error /
  blocked pending D-1 / re-submit / approved.
- **Evidence links:** approval records, acceptance matrix.
- **Current implementation:** none formal. **Frontend dependency:** new screen. **Backend:**
  scope/acceptance + approval contract. **Decision dependency:** D-1.

### 7.3 Execution Plan
- **Purpose:** show the plan + task graph + responsibilities for approval.
- **Primary user:** PO. **Entry:** after requirements approval.
- **Primary data:** plan, task nodes, owners (typed), generation mode.
- **Primary actions:** approve execution plan; request re-plan. **Approval:** execution-plan approval.
- **Status states:** In Progress, Waiting for Approval, Blocked, Ready.
- **States (empty/loading/error/blocked/retry/completed):** documented (plan blocked → template
  generator `blocked`).
- **Evidence links:** plan record, provenance.
- **Current implementation:** partial (planner agent, no PO surface). **Frontend:** new screen.
  **Backend:** plan read model. **Decision dependency:** **D-1, D-3**.

### 7.4 Project Overview
- **Purpose:** single POC status view (goal → delivery).
- **Primary user:** PO. **Entry:** Control Center root.
- **Primary data:** goal, phase, work-item rollup, activity summary, safety summary.
- **Primary actions:** navigate to areas. **Read-only:** all. **Approval:** none here.
- **Status states:** the shared status model (§9).
- **States:** empty ("POC not started") / loading / error / blocked (D-1) / n/a / completed.
- **Evidence links:** into each area.
- **Current implementation:** partial (`/`, Overview attention-first). **Frontend:** unified overview.
  **Backend:** unified POC read model. **Decision dependency:** D-1.

### 7.5 Task Graph
- **Purpose:** show work decomposition + dependencies + owners.
- **Primary user:** PO/operator. **Entry:** Project Overview.
- **Primary data:** nodes, edges, owner (runtime_agent | ai_partner | human), node status.
- **Primary actions:** open node. **Read-only:** view. **Approval:** none.
- **Status states:** per node (§9).
- **States:** empty/loading/error/blocked(D-1)/retry/completed documented.
- **Evidence links:** node → activity/artifacts.
- **Current implementation:** `/task-graph` renders Path A (non-dispatching). **Frontend:** enhance
  with actor typing + POC linkage. **Backend:** task-graph read model. **Decision dependency:** **D-1, D-2**.

### 7.6 Agent/Partner Timeline
- **Purpose:** chronological activity of runtime agents AND external AI partners.
- **Primary user:** PO/operator. **Entry:** Project Overview.
- **Primary data:** the activity model (§10).
- **Primary actions:** open an activity/artifact. **Read-only:** view. **Approval:** none.
- **Status states:** per activity (§9).
- **States:** empty ("No activity yet") / loading / error / blocked / retry / completed.
- **Evidence links:** activity → artifact/commit/PR/test/review.
- **Current implementation:** `/agent-executions` runtime-only. **Frontend:** consolidate + partner
  model. **Backend:** unified activity read model. **Decision dependency:** **D-1, D-2**.

### 7.7 Artifact Explorer
- **Purpose:** browse artifacts with provenance + generation mode + safety mode.
- **Primary user:** PO. **Entry:** activity/timeline/delivery.
- **Primary data:** artifacts, generation mode (§5), provenance, review/test status, safety mode.
- **Primary actions:** open artifact; open commit/branch/Draft PR. **Approval:** none.
- **Status states:** review/test states (§9).
- **States:** empty/loading/error/blocked/retry/completed documented.
- **Evidence links:** commit, branch, Draft PR, tests, review.
- **Current implementation:** fragmented (`/qa-code`,`/workspace`,`/sandbox-github`,`/demo-evidence`).
  **Frontend:** consolidate. **Backend:** provenance + source-control evidence contract. **Decision
  dependency:** **D-3**.

### 7.8 Approval Center
- **Purpose:** all approvals requiring the PO/approver.
- **Primary user:** PO / Reviewer-Approver. **Entry:** Control Center / notifications.
- **Primary data:** approval items (§12 fields).
- **Primary actions:** approve, reject, request more info. **Approval:** yes (all types §12).
- **Status states:** Waiting for Approval, Accepted, Rejected, expired.
- **States:** empty ("Nothing needs approval") / loading / error / blocked / retry / completed.
- **Evidence links:** per-approval evidence.
- **Current implementation:** `/approvals` placeholder. **Frontend:** new screen. **Backend:**
  approval queue contract. **Decision dependency:** D-1.

### 7.9 Blocker and Failure Center
- **Purpose:** failures, retries, DLQ, remediation, aborts.
- **Primary user:** operator + PO (for decisions). **Entry:** Control Center / activity.
- **Primary data:** failure/recovery model (§13).
- **Primary actions:** (operator, if authorized) retry/replay/mark-terminal; (PO) approve where
  required; abort (confirmation). **Approval:** where required.
- **Status states:** Blocked, Retrying, Failed, In DLQ, Remediating, Aborted.
- **States:** empty ("Nothing blocked") / loading / error / blocked / retry / completed.
- **Evidence links:** failure evidence, retry history.
- **Current implementation:** `/dlq-retry` placeholder; `/incidents` summary. **Frontend:** new
  screen. **Backend:** task-scoped retry/DLQ read contract. **Decision dependency:** D-1.

### 7.10 QA Dashboard
- **Purpose:** QA results, defects, remediation, rerun outcome.
- **Primary user:** PO/operator. **Entry:** Project Overview / delivery.
- **Primary data:** QA results, defects, rerun state.
- **Primary actions:** review; request changes / re-run QA (distinct — §11). **Approval:** none (QA
  is verification).
- **Status states:** Ready for QA, QA Failed, QA Passed, Remediating.
- **States:** empty/loading/error/blocked/retry/completed documented.
- **Evidence links:** QA report, defects, rerun evidence.
- **Current implementation:** `/qa-code` summary. **Frontend:** enhance. **Backend:** QA read model.
  **Decision dependency:** D-1.

### 7.11 Delivery Package
- **Purpose:** the reviewable delivery (§14 contents).
- **Primary user:** PO. **Entry:** Delivery Inbox / Project Overview.
- **Primary data:** the §14 package.
- **Primary actions:** open package; proceed to final acceptance. **Approval:** leads to acceptance.
- **Status states:** Ready for Delivery, Delivered.
- **States:** empty/loading/error/blocked/retry/completed documented.
- **Evidence links:** branch, Draft PR, commits, tests, demo, audit, cost.
- **Current implementation:** `/delivery-package` partial; inbox/detail placeholder. **Frontend:**
  enhance + inbox/detail. **Backend:** Step 66D contract. **Decision dependency:** D-1.

### 7.12 Final Acceptance
- **Purpose:** PO records ACCEPTED / ACCEPTED_WITH_FOLLOW_UP / REJECTED.
- **Primary user:** PO. **Entry:** Delivery Package.
- **Primary data:** package + acceptance matrix + evidence.
- **Primary actions:** submit decision (§15). **Approval:** delivery acceptance (PO only).
- **Status states:** Delivered, Accepted, Accepted with Follow-up, Rejected.
- **States:** empty/loading/error/blocked/retry/completed documented.
- **Evidence links:** decision record + evidence.
- **Current implementation:** placeholder. **Frontend:** new screen. **Backend:** Step 66D acceptance
  contract. **Decision dependency:** D-1. **Rule:** an agent-marked "complete" is NOT PO acceptance.

### 7.13 Cost and External Actions
- **Purpose:** POC-scoped cost + external-action + production-action accounting, in one place.
- **Primary user:** PO / security. **Entry:** Control Center / Safety.
- **Primary data:** POC-scoped external action count, production action count, cost, safety mode.
- **Primary actions:** view. **Approval:** external-operation approval originates here / Approval
  Center. **Read-only:** counts.
- **Status states:** informational.
- **States:** empty/loading/error/blocked/n-a/completed documented.
- **Evidence links:** external-op records, cost records.
- **Current implementation:** split across `/metrics`,`/safety`,`/sandbox-github` (FE-POC-G8).
  **Frontend:** consolidate. **Backend:** POC-scoped counters. **Decision dependency:** —.

### 7.14 Safety Summary
- **Purpose:** POC-scoped safety posture (reassurance-first).
- **Primary user:** PO / security / operator. **Entry:** Control Center.
- **Primary data:** dispatch/resume/production/external state; `production_executed_true_count`;
  safety mode. All **server-computed, displayed-as-returned** (reuse the calm posture component).
- **Primary actions:** view; open evidence. **Approval:** none.
- **Status states:** Safe / Attention / Unavailable (existing calm-posture vocabulary).
- **States:** empty/loading/error/blocked/n-a/completed documented.
- **Evidence links:** safety evidence (metadata only).
- **Current implementation:** `/safety` calm posture exists. **Frontend:** POC-scoped view. **Backend:**
  reuse existing safety endpoint. **Decision dependency:** —.

### 7.15 Retrospective
- **Purpose:** post-delivery summary: timeline, cost, external actions, defects, follow-ups.
- **Primary user:** PO. **Entry:** after Final Acceptance.
- **Primary data:** audit timeline, cost, external-op summary, follow-up items.
- **Primary actions:** review; export (read-only). **Approval:** none.
- **Status states:** Completed / Accepted / Accepted with Follow-up / Rejected (of the POC).
- **States:** empty/loading/error/blocked/n-a/completed documented.
- **Evidence links:** audit timeline, cost, acceptance record.
- **Current implementation:** fragmented. **Frontend:** new screen. **Backend:** retrospective read
  model. **Decision dependency:** —.

**Screen coverage: 15/15 required screens specified.**

---

## 8. Shared status display model + backend-to-display mapping

Display statuses (unified language):

```text
Not Started · Ready · In Progress · Waiting for Agent · Waiting for AI Partner ·
Waiting for Product Owner · Waiting for Approval · Blocked · Retrying · Failed · In DLQ ·
Remediating · Ready for QA · QA Failed · QA Passed · Ready for Delivery · Delivered · Accepted ·
Accepted with Follow-up · Rejected · Aborted
```

Backend-to-display mapping (illustrative, based on the snapshot's implemented models; where no
backend status exists, marked `MAPPING_GAP` — this spec does **not** request a new global backend
status):

| Display status | Candidate backend source | Note |
| --- | --- | --- |
| Not Started | task `draft` | — |
| Ready | task `intake_review` / `approved_for_execution` | — |
| In Progress | task `running` / agent-execution running | Path B (D-1) |
| Waiting for Agent | agent-execution pending | Path B (D-1) |
| Waiting for AI Partner | — | **MAPPING_GAP** (external-partner model, D-2) |
| Waiting for Product Owner | task `clarification_needed` / awaiting acceptance | partial |
| Waiting for Approval | task `waiting_approval` / approval `pending` | — |
| Blocked | task `blocked` | — |
| Retrying | retry-scheduler attempt state | — |
| Failed | agent-execution `failed` | — |
| In DLQ | DLQ dead state | task-scoped read **MAPPING_GAP** (FE-POC-G5) |
| Remediating | — | **MAPPING_GAP** (manual remediation state) |
| Ready for QA | task `delivery_ready` pre-QA | partial |
| QA Failed / QA Passed | qa-agent result | — |
| Ready for Delivery | `delivery_ready` | — |
| Delivered | delivery `submitted`/package present | 66D |
| Accepted / Rejected | delivery review decision | 66D |
| Accepted with Follow-up | — | **MAPPING_GAP** (66D acceptance contract) |
| Aborted | task `aborted` / cancel | — |

`MAPPING_GAP` items are carried into the UX gap register; none is a request to add a global backend
status.

---

## 9. Agent and partner activity model

Fields the PO should see per activity:

```text
actor name · actor type (runtime_agent | ai_partner | human) · role · assigned task ·
current action summary · input artifact reference · output artifact reference · started time ·
completed time · status · retry count · cost · commit/branch/PR · test evidence · review evidence ·
failure reason · next owner
```

**Must NOT be displayed** (hard rule): private chain of thought · raw system prompt · raw token ·
secret · credential · unredacted sensitive prompt.

**May be displayed only:** action summary · decision rationale summary · artifact · audit evidence ·
review result.

---

## 10. Approval types

At least: requirements approval · scope approval · execution-plan approval · external-operation
approval · scope-change approval · delivery acceptance · abort confirmation.

Each approval shows: requester · approver · reason · scope · impact · cost · external action ·
expiry · status · evidence.

**Rule:** an ordinary wait state (Waiting for Agent / Waiting for AI Partner) is **not** a PO
approval and must be visually distinct from an approval that requires a human decision.

---

## 11. Failure and recovery

Covers: agent failure · AI partner failure · LLM failure · GitHub failure · test failure ·
integration failure · retry · DLQ · manual remediation · abort · partial delivery.

Each shows: what failed · impact · automatic action · retry count · current owner · next allowed
action · whether PO approval is required · available evidence.

**Request Changes vs Re-run QA (disambiguation):** Request Changes = a content revision and always
requires a written "what to change"; Re-run QA = a verification re-run with no change requested.
Different affordances, different consequences (carried from the M2 delivery experience).

---

## 12. Delivery package + Product Owner acceptance

**Delivery package contents:** development goal · approved requirements · acceptance matrix ·
architecture summary · UX specification · source branch · Draft PR · commits · test report · known
limitations · security boundary · run instructions · demo evidence · cost summary ·
external-operation summary · audit timeline.

**Product Owner decision (only these three):** `ACCEPTED` · `ACCEPTED_WITH_FOLLOW_UP` · `REJECTED`.
Each records: reason · follow-up items · evidence · decision timestamp · actor.

**Rule:** an Agent marking work "complete" is **not** equivalent to PO acceptance.

---

## 13. Safety, privacy, and scope statements

- All safety values are **server-computed and displayed-as-returned**; the UI never infers or
  hardcodes them. `production_executed_true_count = 0` at baseline and must be shown truthfully.
- No screen implies workflow dispatch/resume, external action, or production action is enabled.
- Private reasoning / prompts / tokens / secrets / credentials are **excluded** from every screen
  (see §9).
- This document does **not**: start final visual design, authorize Codex, modify frontend/backend/
  API/runtime, deploy, migrate, or run any Agent workflow.

## Statement

Design/UX specification and reconciliation only. No runtime code. No frontend implementation. No
backend/API/database/workflow change. No deployment. No Agent workflow execution. No production
action. `production_executed_true_count=0`. No Codex authorization. No option selected. No final
visual design.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
