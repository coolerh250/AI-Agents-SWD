# Step 66SYNC.1-D — POC.0 Consolidated Gap Register

> **Read-only consolidation of three partner gap registers. Nothing below is authorized, scheduled,
> or started. Every entry carries `Authorized: NO`. No runtime, frontend, backend, API, deployment,
> migration, secret, or feature-gate change was made. `production_executed_true_count: 0`.**

```text
CONTEXT_ID: AIAT-SYNC-20260803-01
Sources:    Claude Code 828ea90 (G-4..G-15 technical gaps, D-1/D-2/D-3)
            Codex        78aa4ee (FE-POC-G1..G10)
            Claude Design 65c93a1 (UX-POC-B1..B4, H1..H4, M1..M2)
Categories: POC0-BACKEND | POC0-FRONTEND | POC0-UX | POC0-ENVIRONMENT | POC0-INTEGRATION |
            POC0-SAFETY | POC0-DELIVERY
```

Severity: `CRITICAL` (POC cannot demonstrate its objective), `HIGH` (POC demonstrable but with a
material honesty or observability defect), `MEDIUM` (quality/completeness).

---

## POC0-BACKEND

### POC0-BACKEND-G1 — POC goal entry / dispatch contract

```text
Gap ID:                POC0-BACKEND-G1
Description:           No contract connects an operator-supplied goal to the agent pipeline. The
                       /tasks API returns dispatch_enabled: False and never publishes to
                       stream.tasks; the working pipeline is reachable only via workflow.py /
                       communication-gateway.
Source partner:        Claude Code (D-1, G-1), Codex (FE-POC-G1), Claude Design (UX-POC-B1)
Severity:              CRITICAL
Decision dependency:   D-1 (blocking -- the contract shape depends entirely on the answer)
Backend dependency:    New goal-entry + dispatch endpoint and its data model
Frontend dependency:   POC Goal Entry screen consumes it
UX dependency:         Spec 7.1 (POC Goal Entry); journey steps 1-2
Environment dependency:isolated POC runtime (POC0-ENVIRONMENT-G1)
Owner:                 Claude Code (contract + backend), Codex (UI after authorization)
Acceptance evidence:   an operator-entered goal produces a durable goal record and a dispatched
                       workflow whose agent executions are traceable back to that goal
Authorized:            NO
```

### POC0-BACKEND-G2 — Unified project-level read model

```text
Gap ID:                POC0-BACKEND-G2
Description:           No single read model returns goal -> project -> requirements -> work items ->
                       workflow -> agent/partner executions -> artifacts -> QA -> approvals ->
                       delivery for one POC run. A unified UI built without it would simply
                       re-fragment across inconsistent endpoints.
Source partner:        Codex (FE-POC-G10), Claude Design (UX-POC-B4), Claude Code (G-10)
Severity:              CRITICAL
Decision dependency:   shape depends on D-1 and D-2; existence does not
Backend dependency:    new aggregate read API
Frontend dependency:   POC Control Center / Project Overview
UX dependency:         spec §6.1 IA option must be chosen at POC.0 scoping; spec 7.4
Environment dependency:none beyond POC0-ENVIRONMENT-G1
Owner:                 Claude Code
Acceptance evidence:   one request returns a consistent, complete POC run view
Authorized:            NO
```

### POC0-BACKEND-G3 — External AI partner activity model

```text
Gap ID:                POC0-BACKEND-G3
Description:           No first-class model records external AI partner work (partner identity,
                       assigned work item, status, artifact, commit, branch, Draft PR, test and
                       review evidence). agents/backend-agent and agents/frontend-agent are absent,
                       so partner work is currently invisible to the platform.
Source partner:        Codex (FE-POC-G2), Claude Design (UX-POC-B2), Claude Code (D-2, G-2)
Severity:              CRITICAL
Decision dependency:   D-2 (blocking)
Backend dependency:    partner execution/evidence contract + storage
Frontend dependency:   Agent/Partner Timeline
UX dependency:         spec 7.6; runtime_agent vs ai_partner must never be conflated
Environment dependency:none
Owner:                 Claude Code (contract), Codex (UI after authorization)
Acceptance evidence:   partner work appears with full evidence and is visually distinct from
                       runtime agent executions
Authorized:            NO
```

### POC0-BACKEND-G4 — Requirement → work item → execution traceability

```text
Gap ID:                POC0-BACKEND-G4
Description:           Requirements, work items and executions exist as separate data with no
                       operator-visible linkage; an operator cannot answer "which requirement is
                       this execution satisfying?"
Source partner:        Claude Design (UX-POC-H2), Claude Code (capability #2/#3 PARTIAL)
Severity:              HIGH
Decision dependency:   none (shape influenced by D-1)
Backend dependency:    linkage model + read API
Frontend dependency:   Execution Plan, Task Graph, Artifact Explorer
UX dependency:         spec 7.3, 7.5, 7.7
Environment dependency:none
Owner:                 Claude Code
Acceptance evidence:   every execution and artifact resolves to an originating requirement
Authorized:            NO
```

### POC0-BACKEND-G5 — Task-scoped retry / DLQ read model

```text
Gap ID:                POC0-BACKEND-G5
Description:           Bounded retry, backoff and a terminal dead state are implemented and proven
                       for the AUDIT destination, but there is no task-scoped read path and the
                       ORCHESTRATOR_COMMAND destination has no consumer at all, so its DLQ
                       semantics have never been exercised.
Source partner:        Claude Code (G-4, G-11), Claude Design (UX-POC-H3), Codex (FE-POC-G7)
Severity:              HIGH
Decision dependency:   none
Backend dependency:    task-scoped retry/DLQ read API; a command-destination consumer if D-1
                       routes execution through the outbox command path
Frontend dependency:   Blocker and Failure Center
UX dependency:         spec 7.9
Environment dependency:none
Owner:                 Claude Code
Acceptance evidence:   an operator can see, for one task, every retry attempt and any dead row
Authorized:            NO
```

### POC0-BACKEND-G6 — Approval queue read/act contract

```text
Gap ID:                POC0-BACKEND-G6
Description:           The approval engine enforces holds server-side, but no queue endpoint lets
                       an operator see pending approvals and act on them. BE3 production-approval
                       grant/revoke additionally has zero production callers and no HTTP endpoint.
Source partner:        Claude Code (G-5), Codex (FE-POC-G6), Claude Design (spec 7.8)
Severity:              CRITICAL
Decision dependency:   none for the POC approval queue; the BE3 production-approval path is
                       separately gated by RA-1/RA-2 authorization
Backend dependency:    approval queue read + act endpoints
Frontend dependency:   Approval Center
UX dependency:         spec 7.8; journey step 9
Environment dependency:none
Owner:                 Claude Code
Acceptance evidence:   a held workflow surfaces in a queue and an authorized operator can release
                       or reject it, with audit evidence
Authorized:            NO
```

---

## POC0-FRONTEND

### POC0-FRONTEND-G1 — POC goal entry surface

```text
Gap ID:                POC0-FRONTEND-G1
Description:           No screen through which a Product Owner enters a development goal that will
                       actually execute.
Source partner:        Codex (FE-POC-G1), Claude Design (spec 7.1)
Severity:              CRITICAL
Decision dependency:   D-1 (blocking)
Backend dependency:    POC0-BACKEND-G1
Frontend dependency:   this IS the frontend gap
UX dependency:         spec 7.1
Environment dependency:none
Owner:                 Codex (after explicit authorization)
Acceptance evidence:   goal entered in UI produces a running, observable POC workflow
Authorized:            NO
```

### POC0-FRONTEND-G2 — Agent / partner timeline surface

```text
Gap ID:                POC0-FRONTEND-G2
Description:           /agent-executions shows runtime agent rows only; no surface distinguishes
                       runtime agents from external AI partners or shows partner artifacts.
Source partner:        Codex (FE-POC-G2), Claude Design (UX-POC-B2, spec 7.6)
Severity:              CRITICAL
Decision dependency:   D-2 (blocking)
Backend dependency:    POC0-BACKEND-G3
Frontend dependency:   this IS the frontend gap
UX dependency:         spec 7.6
Environment dependency:none
Owner:                 Codex (after explicit authorization)
Acceptance evidence:   both actor classes render distinctly with full evidence links
Authorized:            NO
```

### POC0-FRONTEND-G3 — Artifact provenance / source-control evidence surface

```text
Gap ID:                POC0-FRONTEND-G3
Description:           Generation mode, implementing actor, commit, branch, Draft PR and test
                       evidence are not consistently shown for an artifact.
Source partner:        Codex (FE-POC-G3), Claude Design (UX-POC-H1, UX-POC-H4, spec 7.7)
Severity:              HIGH
Decision dependency:   D-3 (blocking -- provenance semantics differ per generation mode)
Backend dependency:    provenance + source-control evidence contract
Frontend dependency:   Artifact Explorer
UX dependency:         spec 7.7
Environment dependency:none
Owner:                 Codex (after authorization), Claude Code (contract)
Acceptance evidence:   every artifact shows how it was produced and by whom, with links
Authorized:            NO
```

### POC0-FRONTEND-G4 — Unified POC observation surface (fragmented visibility)

```text
Gap ID:                POC0-FRONTEND-G4
Description:           POC visibility is fragmented across ~20 read-only pages; no surface threads
                       goal -> delivery. Classified IMPLEMENTATION_GAP -- explicitly NOT resolved
                       by D-1/D-2/D-3 nor by the Step 66D contract freeze alone.
Source partner:        Codex (FE-POC-G10), Claude Design (UX-POC-B4)
Severity:              CRITICAL
Decision dependency:   IA option (spec §6.1) to be chosen at POC.0 scoping -- a POC.0 DESIGN
                       OPTION, NOT a fourth Product Owner decision
Backend dependency:    POC0-BACKEND-G2 (without it, a unified UI re-fragments)
Frontend dependency:   this IS the frontend gap
UX dependency:         spec §6.1 + spec 7.4
Environment dependency:none
Owner:                 Claude Design (specification), Codex (implementation),
                       Claude Code (unified read model/API) -- all three required
Acceptance evidence:   one surface answers "what is my goal doing right now?" end-to-end
Authorized:            NO
```

### POC0-FRONTEND-G5 — Approval queue and blocker surfaces

```text
Gap ID:                POC0-FRONTEND-G5
Description:           No approval queue, no blocker/failure centre, no notifications/action centre.
Source partner:        Codex (FE-POC-G6, FE-POC-G7), Claude Design (spec 7.8, 7.9)
Severity:              CRITICAL (approval), HIGH (blocker/notifications)
Decision dependency:   none
Backend dependency:    POC0-BACKEND-G6, POC0-BACKEND-G5
Frontend dependency:   this IS the frontend gap
UX dependency:         spec 7.8, 7.9
Environment dependency:none
Owner:                 Codex (after explicit authorization)
Acceptance evidence:   an operator can find and act on every pending approval and blocker
Authorized:            NO
```

---

## POC0-UX

### POC0-UX-G1 — POC-scoped screen specifications not yet designed against a frozen contract

```text
Gap ID:                POC0-UX-G1
Description:           15 screens are specified (spec §7.1-7.15) but several depend on backend
                       contracts that are not frozen (POC entry, partner model, provenance,
                       delivery). Designing further against unfrozen contracts risks rework.
Source partner:        Claude Design
Severity:              HIGH
Decision dependency:   D-1, D-2, D-3
Backend dependency:    POC0-BACKEND-G1/G2/G3; Step 66D-ARCH for delivery/acceptance
Frontend dependency:   none yet
UX dependency:         this IS the UX gap
Environment dependency:none
Owner:                 Claude Design
Acceptance evidence:   screens finalized against frozen contracts, reviewed by Claude Code
Authorized:            NO
```

### POC0-UX-G2 — Status language / display model mapping

```text
Gap ID:                POC0-UX-G2
Description:           Backend states do not map cleanly onto operator-facing status language;
                       several states have no agreed display treatment.
Source partner:        Claude Design (UX-POC-M2)
Severity:              MEDIUM
Decision dependency:   none
Backend dependency:    state enumeration confirmation
Frontend dependency:   consistent status components
UX dependency:         spec §8 shared status display model
Environment dependency:none
Owner:                 Claude Design → Codex
Acceptance evidence:   every backend state renders with an agreed, honest label
Authorized:            NO
```

### POC0-UX-G3 — Unified observation experience specification

```text
Gap ID:                POC0-UX-G3
Description:           The IA choice between a Unified POC Control Center and Coordinated existing
                       routes is specified as two non-binding options and has not been selected.
Source partner:        Claude Design (spec §6.1), Codex (FE-POC-G10)
Severity:              HIGH
Decision dependency:   POC.0 DESIGN OPTION -- selected during POC.0 scoping, NOT a Product Owner
                       decision in the D-1/D-2/D-3 sense
Backend dependency:    POC0-BACKEND-G2
Frontend dependency:   POC0-FRONTEND-G4
UX dependency:         this IS the UX gap
Environment dependency:none
Owner:                 Claude Design
Acceptance evidence:   one IA chosen and specified end-to-end
Authorized:            NO
```

---

## POC0-ENVIRONMENT

### POC0-ENVIRONMENT-G1 — Isolated POC runtime

```text
Gap ID:                POC0-ENVIRONMENT-G1
Description:           The 27-service test stack exists but is fully down (all containers
                       Exited (255)); staging is decommissioned; Kubernetes/Helm is TEMPLATE_ONLY;
                       Vault runs only in `server -dev`. No isolated POC runtime is currently
                       designated or standing.
Source partner:        Claude Code
Severity:              CRITICAL (nothing can be demonstrated without a runtime)
Decision dependency:   none for the POC itself; interacts with RA2-D11 (first validation
                       environment) if identity work is ever in scope
Backend dependency:    none
Frontend dependency:   none
UX dependency:         none
Environment dependency:this IS the environment gap
Owner:                 Claude Code
Acceptance evidence:   an isolated, disposable POC runtime brought up and torn down cleanly, with
                       migrations 029-035 applied to its own isolated database
Authorized:            NO
```

### POC0-ENVIRONMENT-G2 — Sandbox reset / teardown for repeatable POC runs

```text
Gap ID:                POC0-ENVIRONMENT-G2
Description:           Reset/cleanup verifier scripts exist and the stack is disposable, but no
                       POC-scoped reset procedure guarantees a clean run-to-run baseline.
Source partner:        Claude Code
Severity:              MEDIUM
Decision dependency:   none
Backend dependency:    none
Frontend dependency:   none
UX dependency:         none
Environment dependency:builds on POC0-ENVIRONMENT-G1
Owner:                 Claude Code
Acceptance evidence:   two consecutive POC runs from an identical clean baseline
Authorized:            NO
```

---

## POC0-INTEGRATION

### POC0-INTEGRATION-G1 — Source-control / PR / test evidence chain

```text
Gap ID:                POC0-INTEGRATION-G1
Description:           GitHub automation is dry-run by default with a gated real sandbox path, but
                       no end-to-end evidence chain links a work item to a branch, Draft PR, test
                       run and review outcome.
Source partner:        Codex (FE-POC-G4, FE-POC-G5), Claude Design (UX-POC-H4), Claude Code
Severity:              HIGH
Decision dependency:   D-2 (who authors the change), D-3 (how it was generated)
Backend dependency:    evidence contract + GitHub sandbox wiring
Frontend dependency:   POC0-FRONTEND-G3
UX dependency:         spec 7.7
Environment dependency:sandbox repo scope must be explicit
Owner:                 Claude Code (contract/backend), Codex (UI)
Acceptance evidence:   a work item resolves to a branch, Draft PR and test result
Authorized:            NO
```

### POC0-INTEGRATION-G2 — Artifact / document storage

```text
Gap ID:                POC0-INTEGRATION-G2
Description:           No artifact or document store exists (zero Google Drive / equivalent
                       integration). Artifacts persist as DB rows and workspace files only.
Source partner:        Claude Code (G-8)
Severity:              MEDIUM
Decision dependency:   none
Backend dependency:    storage abstraction if durable artifacts are in POC scope
Frontend dependency:   Artifact Explorer download/links
UX dependency:         spec 7.7
Environment dependency:none
Owner:                 Claude Code
Acceptance evidence:   a delivery artifact is retrievable after the run
Authorized:            NO
```

---

## POC0-SAFETY

### POC0-SAFETY-G1 — POC-scoped cost and external-operation counters

```text
Gap ID:                POC0-SAFETY-G1
Description:           llm_budget/llm_usage_records and the real-integration/safety surfaces exist,
                       but no counters are scoped to a single POC run, and with the default mock
                       provider recorded cost is structurally zero.
Source partner:        Claude Design (UX-POC-M1), Codex (FE-POC-G8), Claude Code
Severity:              MEDIUM
Decision dependency:   D-3 (real vs mock provider changes what cost means)
Backend dependency:    POC-scoped counters
Frontend dependency:   Cost and External Actions screen
UX dependency:         spec 7.13, 7.14
Environment dependency:none
Owner:                 Claude Code → Codex
Acceptance evidence:   per-run cost and external-operation counts, with production count 0
Authorized:            NO
```

### POC0-SAFETY-G2 — Operator identity for meaningful acceptance

```text
Gap ID:                POC0-SAFETY-G2
Description:           No verifiable human operator identity: the BE3 surface accepts actor id AND
                       role verbatim from client headers, and the Admin Console authenticates one
                       fixed pseudo-identity. PO acceptance therefore cannot distinguish two real
                       humans, and separation of duties cannot be enforced.
Source partner:        Claude Code (G-12, G-13; RA-2 inventory at efa396d)
Severity:              HIGH for a POC that records "Product Owner acceptance"
Decision dependency:   RA-2 decisions RA2-D01/D02/D03 are accepted but NOT implemented; RA-2
                       implementation is NOT AUTHORIZED
Backend dependency:    RA-2I1 (operator identity foundation)
Frontend dependency:   session/identity display
UX dependency:         acceptance attribution
Environment dependency:none
Owner:                 Claude Code (under separate RA-2 authorization)
Acceptance evidence:   acceptance attributable to a verified human identity
Authorized:            NO
```

### POC0-SAFETY-G3 — Feature-gate and activation boundary for the POC

```text
Gap ID:                POC0-SAFETY-G3
Description:           All four BE3 gates are default false and must remain so unless a POC run
                       genuinely requires resume/replay -- which would pull in the RA-1 activation
                       gates (1/2/6, PENDING) and RA-2 identity work.
Source partner:        Claude Code
Severity:              HIGH (as a boundary to preserve, not a defect)
Decision dependency:   POC.0 scoping must state explicitly whether BE3 paths are in scope
Backend dependency:    none if excluded
Frontend dependency:   none if excluded
UX dependency:         none if excluded
Environment dependency:isolated runtime only
Owner:                 Product Owner (scope), Claude Code (enforcement)
Acceptance evidence:   POC runs with all four gates false and production count 0
Authorized:            NO
```

---

## POC0-DELIVERY

### POC0-DELIVERY-G1 — Delivery package and Product Owner acceptance lifecycle (Step 66D)

```text
Gap ID:                POC0-DELIVERY-G1
Description:           Delivery/acceptance surfaces are placeholders. The real delivery lifecycle
                       -- Delivery Inbox, Delivery Detail, 6-action acceptance gate, Approvals P0,
                       DLQ/Retry P0 -- is canonical Step 66D scope and its data model/API contract
                       has NOT been frozen.
Source partner:        Claude Design (UX-POC-B3), Codex (FE-POC-G9), Claude Code
Severity:              CRITICAL for "delivery POC"
Decision dependency:   NOT D-1/D-2/D-3. Blocked on Step 66D-ARCH, a separate canonical stage.
Backend dependency:    Step 66D-ARCH contract freeze (Claude Code, architecture only)
Frontend dependency:   Step 66D implementation slices (Codex, after authorization)
UX dependency:         Step 66D-DESIGN (Claude Design, against the frozen contract);
                       spec 7.11, 7.12
Environment dependency:none
Owner:                 Claude Code (66D-ARCH) → Claude Design (66D-DESIGN) → Codex (slices)
Acceptance evidence:   a delivery package is produced and formally accepted through the 6-action
                       gate with audit evidence
Authorized:            NO
Sequencing rule:       66D-ARCH must freeze the contract BEFORE any delivery UI is designed --
                       recorded on canonical main as "the single highest-priority sequencing rule
                       in this Master Plan".
```

### POC0-DELIVERY-G2 — Retrospective read model

```text
Gap ID:                POC0-DELIVERY-G2
Description:           No retrospective view summarising what the AI team did, cost, duration,
                       failures and outcomes for a completed POC run.
Source partner:        Claude Design (spec 7.15, journey step 13)
Severity:              MEDIUM
Decision dependency:   none
Backend dependency:    retrospective aggregate read
Frontend dependency:   Retrospective screen
UX dependency:         spec 7.15
Environment dependency:none
Owner:                 Claude Code → Codex
Acceptance evidence:   a completed run yields a coherent retrospective
Authorized:            NO
```

---

## Roll-up

```text
POC0-BACKEND:      6 gaps   (G1 CRITICAL, G2 CRITICAL, G3 CRITICAL, G4 HIGH, G5 HIGH, G6 CRITICAL)
POC0-FRONTEND:     5 gaps   (G1 CRITICAL, G2 CRITICAL, G3 HIGH, G4 CRITICAL, G5 CRITICAL/HIGH)
POC0-UX:           3 gaps   (G1 HIGH, G2 MEDIUM, G3 HIGH)
POC0-ENVIRONMENT:  2 gaps   (G1 CRITICAL, G2 MEDIUM)
POC0-INTEGRATION:  2 gaps   (G1 HIGH, G2 MEDIUM)
POC0-SAFETY:       3 gaps   (G1 MEDIUM, G2 HIGH, G3 HIGH)
POC0-DELIVERY:     2 gaps   (G1 CRITICAL, G2 MEDIUM)
                  --------
Total:            23 gaps

Decision-blocked (D-1/D-2/D-3):        POC0-BACKEND-G1/G3, POC0-FRONTEND-G1/G2/G3,
                                       POC0-UX-G1, POC0-INTEGRATION-G1, POC0-SAFETY-G1
Blocked on Step 66D-ARCH (separate):   POC0-DELIVERY-G1
Blocked on RA-2 authorization:         POC0-SAFETY-G2
Buildable once POC.0 is authorized:    POC0-BACKEND-G2/G4/G5/G6, POC0-FRONTEND-G4/G5,
                                       POC0-UX-G2/G3, POC0-ENVIRONMENT-G1/G2,
                                       POC0-INTEGRATION-G2, POC0-SAFETY-G3, POC0-DELIVERY-G2

Authorized: 0 of 23.
```

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
