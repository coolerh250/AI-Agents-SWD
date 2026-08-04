# Step 66SYNC.1-C — Claude Design UX Gap Register

> Read-only UX gap register. No frontend/backend/API/runtime/deployment/POC implementation was
> performed. Absorbs the Codex frontend gap register (FE-POC-G1..G10, Codex sync head `78aa4ee`) and
> the master snapshot gaps (Claude Code sync head `828ea90`). Classifications: `POC_BLOCKER`,
> `POC_HIGH`, `POC_MEDIUM`, `DECISION_DEPENDENT`, `POST_POC`.

```text
CONTEXT_ID: AIAT-SYNC-20260803-01
BASELINE: canonical main c1db4cc
Claude Code sync head: 828ea90
Codex sync head: 78aa4ee
UNRESOLVED_CANONICAL_MISMATCHES: 0
OPEN_PRODUCT_OWNER_DECISIONS: 3
production_executed_true_count=0
```

## Absorbed Codex/snapshot findings (explicit)

```text
- Task UI is NOT the pipeline source of truth        (Codex FE-POC-G1 / snapshot D-1/G-1)
- backend-agent and frontend-agent are absent         (Codex FE-POC-G2 / snapshot D-2/G-2)
- delivery/approval surfaces are placeholders         (Codex FE-POC-G6 / snapshot G-9)
- POC visibility is fragmented                        (Codex FE-POC-G10)
```

---

### UX-POC-B1 — Entry-point source of truth
```text
Gap ID: UX-POC-B1
Journey step: 1, 6, 7, 8 (goal entry, task graph, collaboration, observe)
User need: Prove that what the PO submitted is the thing actually executing.
Current frontend state: /tasks surface is non-dispatching (dispatch_enabled=false); Path A != Path B.
Required behavior: A goal-entry -> execution path where the observed work provably belongs to the
  PO's goal; the current Task surface must not be presented as the execution source of truth.
Frontend dependency: Goal Entry, Project Overview, Task Graph, Agent/Partner Timeline.
Backend/API dependency: POC entry-point/dispatch contract.
Product decision dependency: D-1.
Risk: Critical — a PO could believe a created task is running agents when it is not.
Recommended future stage: POC.0 scope decision, then M1 linkage.
Status: POC_BLOCKER / DECISION_DEPENDENT (D-1). Absorbs FE-POC-G1, FE-POC-G9.
```

### UX-POC-B2 — Runtime agent vs external AI partner
```text
Gap ID: UX-POC-B2
Journey step: 6, 7, 8, 11.
User need: Know who/what is responsible for each part (esp. backend/frontend work).
Current frontend state: /agent-executions shows runtime agents only; no partner execution model;
  backend-agent/frontend-agent absent.
Required behavior: Distinguish runtime_agent vs ai_partner vs human; show partner assigned task,
  status, artifact, commit, branch, Draft PR, test/review evidence, handoff; never disguise a
  partner as a runtime agent.
Frontend dependency: Agent/Partner Timeline, Task Graph, Artifact Explorer, Delivery Package.
Backend/API dependency: unified activity read model incl. partner model.
Product decision dependency: D-2.
Risk: Critical — UI could overstate the runtime agent roster or hide real partner work.
Recommended future stage: POC.0.
Status: POC_BLOCKER / DECISION_DEPENDENT (D-2). Absorbs FE-POC-G2.
```

### UX-POC-B3 — Delivery / acceptance surfaces are placeholders
```text
Gap ID: UX-POC-B3
Journey step: 11, 12.
User need: Review the delivery and record final acceptance (the objective's endpoint).
Current frontend state: /delivery-inbox, /delivery-detail, /approvals are placeholders;
  /delivery-package partial; Operator has package-level controls only.
Required behavior: PO-friendly Delivery Inbox/Detail, acceptance decision
  (ACCEPTED/ACCEPTED_WITH_FOLLOW_UP/REJECTED), requested changes, approval requirements.
Frontend dependency: Delivery Package, Delivery Inbox/Detail, Final Acceptance, Approval Center.
Backend/API dependency: Step 66D delivery/acceptance + approval queue contract.
Product decision dependency: — (gated on 66D contract).
Risk: Critical — the POC ends with PO acceptance, but the formal surfaces are placeholders.
Recommended future stage: POC.0 / M2.
Status: POC_BLOCKER. Absorbs FE-POC-G6.
```

### UX-POC-B4 — Fragmented POC observation
```text
Gap ID: UX-POC-B4
Journey step: all.
User need: Observe the whole POC (goal -> delivery) coherently, not via scattered diagnostic pages.
Current frontend state: POC-critical views split across evidence pages + placeholders;
  /demo-evidence is diagnostic, not a formal product UI.
Required behavior: A POC Control Center IA (unified or coordinated) connecting goal, work items,
  activity, artifacts, approvals/failures, QA, delivery, acceptance.
Frontend dependency: POC Control Center IA + Project Overview.
Backend/API dependency: unified POC read model OR coordinated contracts.
Product decision dependency: IA option (non-binding; PO discussion).
Risk: Critical — PO observation path is fragmented.
Recommended future stage: POC.0.
Status: POC_BLOCKER. Absorbs FE-POC-G10.
```

### UX-POC-H1 — Artifact provenance & generation mode
```text
Gap ID: UX-POC-H1
Journey step: 5, 8, 10, 11.
User need: Know how each artifact was produced (plan-only / template / partner / human).
Current frontend state: generation mode/provenance not consistently shown.
Required behavior: every artifact shows generation mode, implementation partner, provenance, review
  status, test status, safety mode.
Frontend dependency: Artifact Explorer, QA Dashboard, Execution Plan, Delivery Package.
Backend/API dependency: artifact provenance contract.
Product decision dependency: D-3.
Risk: High — delivery misrepresented as LLM/agent-generated when it is template/partner evidence.
Recommended future stage: POC.0.
Status: POC_HIGH / DECISION_DEPENDENT (D-3). Absorbs FE-POC-G3.
```

### UX-POC-H2 — Requirement-to-work traceability
```text
Gap ID: UX-POC-H2
Journey step: 2, 4, 6.
User need: Know which requirement each work item/agent action corresponds to.
Current frontend state: no single requirement -> work-item -> agent trace.
Required behavior: goal, acceptance criteria, requirements, work items, assignments, delivery
  evidence connected in one PO-observable path.
Frontend dependency: Requirements panel, Task Graph, Project Overview.
Backend/API dependency: requirement/work-item/agent linkage contract.
Product decision dependency: —.
Risk: High — PO cannot tell whether observed work satisfies the request.
Recommended future stage: POC.0 / M1-M2 linkage.
Status: POC_HIGH. Absorbs FE-POC-G4.
```

### UX-POC-H3 — Task-scoped failure / retry / DLQ visibility
```text
Gap ID: UX-POC-H3
Journey step: 9, 10.
User need: See which step failed/retried and whether it entered DLQ.
Current frontend state: /dlq-retry placeholder; incidents/metrics summary only.
Required behavior: task/work-item scoped failure, retry attempt, terminal failure, DLQ, remediation.
Frontend dependency: Blocker & Failure Center.
Backend/API dependency: task-scoped retry/DLQ read contract.
Product decision dependency: —.
Risk: High — PO cannot distinguish in-progress from failed/recovering work.
Recommended future stage: POC.0 / delivery-failure slice.
Status: POC_HIGH. Absorbs FE-POC-G5.
```

### UX-POC-H4 — Source-control / review evidence panel
```text
Gap ID: UX-POC-H4
Journey step: 8, 11.
User need: See commits, branches, Draft PRs, and review evidence for the POC work.
Current frontend state: read-only fragments in /sandbox-github, /workspace, /demo-evidence.
Required behavior: task-scoped commit/branch/Draft PR/test/review evidence panel.
Frontend dependency: Artifact Explorer.
Backend/API dependency: source-control evidence contract.
Product decision dependency: —.
Risk: High — PO cannot inspect what was actually produced/reviewed.
Recommended future stage: POC.0 / M2.
Status: POC_HIGH. Absorbs FE-POC-G7.
```

### UX-POC-M1 — POC-scoped safety / external-action accounting
```text
Gap ID: UX-POC-M1
Journey step: 9, 13.
User need: See POC-scoped external-action count, production-action count, and safety mode in one place.
Current frontend state: global posture visible; POC-specific accounting split across pages.
Required behavior: consolidated Cost & External Actions + Safety Summary (POC-scoped), server-computed.
Frontend dependency: Cost & External Actions, Safety Summary.
Backend/API dependency: POC-scoped counters (no new global status requested).
Product decision dependency: —.
Risk: Medium — global posture visible; POC-specific accounting partial.
Recommended future stage: POC.0 / M6 safety slice.
Status: POC_MEDIUM. Absorbs FE-POC-G8.
```

### UX-POC-M2 — Status-language mapping gaps
```text
Gap ID: UX-POC-M2
Journey step: all.
User need: Consistent product-language status across every screen.
Current frontend state: statuses shown per-page; several display statuses have no backend source.
Required behavior: unified display status model with a backend-to-display mapping; where no backend
  status exists, mark MAPPING_GAP (Waiting for AI Partner, In DLQ task-scoped, Remediating, Accepted
  with Follow-up).
Frontend dependency: shared status component across screens.
Backend/API dependency: none new is requested; MAPPING_GAP items await their owning contract.
Product decision dependency: —.
Risk: Medium — inconsistent status language undermines the command-center feel.
Recommended future stage: POC.0 (as screens are built).
Status: POC_MEDIUM.
```

### UX-POST-1 — External notification channels & autonomous generation
```text
Gap ID: UX-POST-1
Journey step: 8, 9, 13.
User need: (future) external channel notifications; (future) autonomous runtime code generation.
Current frontend state: notifications placeholder; plan-only restriction in force.
Required behavior: external channels stay disabled/honest until authorized; autonomous-runtime
  generation shown only as a labelled NOT-enabled state (D-3 restriction not lifted).
Frontend dependency: Notification/Action Center (later), Artifact Explorer labelling.
Backend/API dependency: channel + (hypothetical) generation contracts — not requested here.
Product decision dependency: future.
Risk: Low for POC.
Recommended future stage: POST_POC.
Status: POST_POC.
```

## Summary

```text
POC_BLOCKER:        UX-POC-B1, UX-POC-B2, UX-POC-B3, UX-POC-B4
POC_HIGH:           UX-POC-H1, UX-POC-H2, UX-POC-H3, UX-POC-H4
POC_MEDIUM:         UX-POC-M1, UX-POC-M2
DECISION_DEPENDENT: UX-POC-B1 (D-1), UX-POC-B2 (D-2), UX-POC-H1 (D-3)
POST_POC:           UX-POST-1
```

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
