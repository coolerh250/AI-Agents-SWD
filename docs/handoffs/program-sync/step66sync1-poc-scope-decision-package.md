# Step 66SYNC.1-D — POC Scope Decision Package (D-1 / D-2 / D-3)

> **Product Owner decision package. Every option below is PROPOSED and NON-BINDING. No partner has
> selected, approved, or pre-answered any of them, and every `Product Owner selection` field is
> PENDING. No implementation, runtime, deployment, migration, secret, or feature-gate action was
> performed. `production_executed_true_count: 0`.**

```text
CONTEXT_ID: AIAT-SYNC-20260803-01
Baseline:   canonical main c1db4cc
Evidence:   Claude Code 828ea90 | Codex 78aa4ee | Claude Design 65c93a1
Status:     OPEN_PRODUCT_OWNER_DECISIONS: 3
```

All three decisions are `OPEN_PRODUCT_OWNER_DECISION` in the synchronization taxonomy: every
partner agrees on the technical facts, so they do **not** make partner context inconsistent — but
they **do** block POC scope finalization and all implementation.

---

## D-1 — POC entry point

```text
Decision ID:                D-1
Classification:             OPEN_PRODUCT_OWNER_DECISION
Status:                     PRODUCT_OWNER_DECISION_REQUIRED
IMPLEMENTATION_AUTHORIZED:  NO
```

### Observed technical state (agreed by all three partners)

```text
Claude Code:   apps/orchestrator/src/task_api.py states "No workflow dispatch, no external write,
               no production action". Every create/submit/update response returns
               `dispatch_enabled: False` (lines 144, 183, 223). submit() advances
               draft|submitted -> intake_review and stops. The module never publishes to
               stream.tasks. The working pipeline is a separate lineage:
               workflow.py::dispatch_node -> dispatch.py -> stream.tasks -> ten agents.
Codex:         FE-POC-G1 (Critical). taskClient.ts and page comments confirm no workflow dispatch;
               affected routes /tasks, /tasks/new, /tasks/:taskId, /tasks/:taskId/workroom.
               Risk recorded: "A PO could believe the task they created is running agents when it
               is not."
Claude Design: UX-POC-B1 (Blocker). All "watch my goal run" journey states marked
               DECISION_DEPENDENT; the current Task surface is NOT treated as the POC execution
               source of truth.
```

### Option A — Dedicated POC Development Goal → Project → Work Item → Workflow

```text
UX impact:            A new POC Goal Entry screen (spec 7.1) becomes the single, unambiguous
                      entry point. The operator journey is coherent end-to-end and no existing
                      screen changes meaning. Clean separation between "ordinary task" and "POC
                      development goal".
Backend impact:       New goal-entry endpoint and a dispatch contract into the existing pipeline.
                      The existing /tasks API is left untouched, so no regression risk to BE3 work
                      or to the 66B task model.
Data model impact:    A POC goal entity (or a typed project) linking goal -> project -> work items
                      -> workflow -> agent executions. Additive.
Traceability:         Strongest. A purpose-built chain can carry requirement -> work item ->
                      execution -> artifact -> QA -> delivery from the start (addresses UX-POC-H2).
Migration impact:     Likely one additive migration for the goal/linkage entity, following the
                      established RA-1 migration process (additive + down script + isolated
                      rehearsal).
Implementation effort:MEDIUM-HIGH. New surface + contract + read model, but no rework of existing
                      task semantics.
Risk:                 LOW-MEDIUM. Adds a parallel path rather than changing an existing one; two
                      task concepts continue to coexist, which must be made obvious in the UI or
                      it becomes confusing in its own right.
```

### Option B — Existing Task → explicit conversion/dispatch → Work Item → Workflow

```text
UX impact:            The operator keeps one familiar Task surface; an explicit, clearly-labelled
                      "dispatch to AI team" action converts a task into POC execution. Existing
                      Task pages gain real meaning rather than being bypassed.
Backend impact:       A conversion/dispatch endpoint on the existing task API, plus the mapping
                      from the 66B task model onto the pipeline's task model. Touches an API that
                      currently guarantees "no dispatch", so that guarantee and its tests must be
                      revised deliberately, not incidentally.
Data model impact:    Linkage between the 66B task row and the pipeline task/workflow. Additive,
                      but it couples two previously independent models.
Traceability:         Good, but inherits the 66B task model's existing shape; some POC-specific
                      fields may need to be bolted on.
Migration impact:     Likely one additive linkage migration.
Implementation effort:MEDIUM. Reuses existing screens; concentrated backend work.
Risk:                 MEDIUM-HIGH. The "no dispatch" property of /tasks is currently a deliberate,
                      test-enforced safety statement (production_effect tasks are forced to
                      `blocked` and never dispatched). Converting that surface into a dispatching
                      one must not weaken the production-effect block, and the existing safety
                      tests must be updated with intent rather than relaxed.
```

```text
Non-binding recommendation (Claude Code, engineering assessment only):
Option A is PROPOSED as lower-risk for a first POC, because it leaves the existing task API's
deliberate "never dispatches / production_effect always blocked" guarantee untouched and lets the
POC path be built with POC-shaped traceability from the start. Option B is PROPOSED as the better
long-term operator experience if the Product Owner wants a single task concept, but it should then
be scoped with an explicit review of the production-effect safety path.
RECOMMENDED FOR PRODUCT OWNER CONSIDERATION. NOT SELECTED.

Product Owner selection:  PENDING
Product Owner conditions: PENDING
```

---

## D-2 — Backend / Frontend execution model

```text
Decision ID:                D-2
Classification:             OPEN_PRODUCT_OWNER_DECISION
Status:                     PRODUCT_OWNER_DECISION_REQUIRED
IMPLEMENTATION_AUTHORIZED:  NO
```

### Observed technical state (agreed by all three partners)

```text
agents/backend-agent/    ABSENT -- contains ONLY .gitkeep, 0 .py files, no compose service.
agents/frontend-agent/   ABSENT -- contains ONLY .gitkeep, 0 .py files, no compose service.
Ten other agents ARE implemented (5,641 lines) and have run historically as a 27-service stack.
Codex FE-POC-G2 (Critical): no first-class partner execution model for external AI partner work.
Claude Design UX-POC-B2 (Blocker): the activity model must distinguish runtime_agent from
  ai_partner and must never render an external partner as an implemented runtime Agent service.
```

### Option A — Claude Code and Codex as externally tracked AI partners

```text
Model:                Backend and frontend implementation is performed by the existing external AI
                      partners (this project's actual working model today) and recorded in the
                      platform as partner activity, not as runtime agent executions.
Backend impact:       A partner execution/evidence contract: partner identity, assigned work item,
                      status, artifact, commit, branch, Draft PR, test evidence, review evidence.
                      No new runtime services.
UX impact:            The team view honestly shows two actor classes. Requires the Agent/Partner
                      Timeline screen (spec 7.6) to model both.
Effort:               MEDIUM (contract + read model + UI), no new long-running services.
Risk:                 LOW technically. The honesty risk is the important one: the UI must not imply
                      autonomous runtime agents are doing the work.
Fidelity to "AI agent team" objective: PARTIAL -- the team is real, but partly human-triggered
                      external partners rather than autonomous runtime services.
```

### Option B — Implement backend-agent / frontend-agent runtime services before POC

```text
Model:                Build the two missing agents as real stream consumers so the runtime roster
                      matches the POC narrative.
Backend impact:       Two new agent services + Dockerfiles + compose entries + their generation
                      capability. Their usefulness is tightly coupled to D-3: with the current
                      plan-only LLM and three-template generator, these agents could only emit
                      template output.
UX impact:            Simplest, most consistent team view -- every actor is a runtime agent.
Effort:               HIGH, and largely wasted unless D-3 chooses Option C (real generation).
Risk:                 MEDIUM-HIGH. Risk of building two services that demonstrate template output
                      and therefore do not actually advance the POC's value.
Fidelity:             HIGH in appearance; only as high as D-3 allows in substance.
```

### Option C — Hybrid: external partners for the POC, runtime agents deferred

```text
Model:                Ship the POC with the partner model (Option A), and keep backend-agent /
                      frontend-agent as an explicitly deferred, separately-authorized stage.
Backend impact:       Same as Option A now; the agent contract is designed so a runtime agent can
                      later occupy the same slot as a partner without a UI rewrite.
UX impact:            One actor abstraction with two implementations -- designed once, extended
                      later.
Effort:               MEDIUM now, LOW incremental later.
Risk:                 LOW, provided the actor abstraction is designed for both from the start.
Fidelity:             PARTIAL now, with a clean path to HIGH later.
```

```text
Non-binding recommendation (Claude Code, engineering assessment only):
Option C is PROPOSED. It matches how the work is actually performed today, avoids building two
services whose value is gated on a separate unresolved decision (D-3), and — if the actor
abstraction is specified for both classes up front — costs little to extend later. Option B is
PROPOSED AGAINST as a first step specifically because its value depends on D-3 Option C, which
carries its own security review.
RECOMMENDED FOR PRODUCT OWNER CONSIDERATION. NOT SELECTED.

Product Owner selection:  PENDING
Product Owner conditions: PENDING
```

---

## D-3 — Delivery generation mode

```text
Decision ID:                D-3
Classification:             OPEN_PRODUCT_OWNER_DECISION
Status:                     PRODUCT_OWNER_DECISION_REQUIRED
IMPLEMENTATION_AUTHORIZED:  NO
```

### Observed technical state (agreed by all three partners)

```text
shared/sdk/llm/plan_only_provider.py implements ONLY generate_development_plan.
generate_patch_proposal and generate_test_plan RAISE LLMProviderError BY DESIGN -- its docstring:
  "so a misconfigured caller can never trick the real provider into producing a patch".
get_provider() returns the deterministic mock BY DEFAULT.
agents/development-agent/src/code_generator.py is "deterministic, template-based ... No LLM",
  supporting exactly three families (documentation, demo_api, simple_utility) and returning a
  `blocked` plan for anything it cannot classify.
Codex FE-POC-G3: generation mode / artifact provenance not consistently surfaced.
Claude Design UX-POC-H1: provenance and generation mode must be displayed; explicitly records that
  removing the plan-only restriction is NOT recommended.
```

### Option A — Keep runtime LLM plan-only; Claude Code / Codex generate the implementation

```text
Model:                The runtime plans; external AI partners implement. Artifacts carry explicit
                      provenance ("planned by runtime LLM, implemented by partner X").
Safety:               PRESERVES the deliberate plan-only control unchanged. No new autonomous
                      write capability.
Delivery realism:     HIGH -- real, reviewable software is produced, by partners, through normal
                      source-control review.
Effort:               LOW-MEDIUM (provenance model + display).
Risk:                 LOW.
Dependency:           Pairs naturally with D-2 Option A or C.
```

### Option B — Deterministic templates only

```text
Model:                POC delivery is limited to the three existing template families.
Safety:               HIGHEST -- no LLM output reaches an artifact at all.
Delivery realism:     LOW -- demonstrates the pipeline, not genuine software delivery. Anything
                      outside the three families returns `blocked`.
Effort:               LOWEST -- works today with no new build.
Risk:                 LOW technically; the risk is expectation mismatch if "functional delivery
                      POC" is understood to mean real software.
```

### Option C — Enable autonomous runtime LLM patch/test generation

```text
Model:                Remove the plan-only restriction so the runtime LLM can produce patches and
                      tests autonomously.
Safety:               HIGH-RISK. This deliberately removes an intentional safety control whose
                      stated purpose is to prevent a misconfigured caller from obtaining a patch
                      from the real provider. It would give an autonomous runtime path the ability
                      to author code.
Delivery realism:     HIGHEST in principle.
Effort:               HIGH -- generation, validation, sandboxing, diff policy, review gating, plus
                      the safety work below.
Risk:                 HIGH. Requires at minimum: patch-scope allowlisting, mandatory human review
                      before any merge, isolated execution, prompt-injection consideration, and
                      audit of every generated artifact.
```

```text
Option C classification (mandatory):
  HIGH-RISK
  SEPARATE SECURITY REVIEW REQUIRED
  NOT PART OF NORMAL POC.0

Option C must not be bundled into POC.0 scope as a convenience. If the Product Owner wants it, it
should be its own authorized stage with an independent security review, in the same way RA-1
findings were independently reviewed and closed.
```

```text
Non-binding recommendation (Claude Code, engineering assessment only):
Option A is PROPOSED. It delivers genuinely real software for the POC while leaving the plan-only
safety control fully intact, and it matches how implementation is actually performed on this
project today. Option B is PROPOSED as an acceptable fallback if the Product Owner wants a
zero-new-risk demonstration. Option C is PROPOSED AGAINST for POC.0 and, if wanted, should be
separated into its own security-reviewed stage.
RECOMMENDED FOR PRODUCT OWNER CONSIDERATION. NOT SELECTED.

Product Owner selection:  PENDING
Product Owner conditions: PENDING
```

---

## Decision interaction summary

```text
D-2 and D-3 are coupled: D-2 Option B (build runtime backend/frontend agents) only produces real
software if D-3 Option C (autonomous generation) is also chosen -- which is the high-risk path.
Choosing D-2 Option A or C together with D-3 Option A yields real software with no new autonomous
write capability.

D-1 is independent of D-2/D-3 and can be answered on its own.

Step 66D-ARCH is a SEPARATE prerequisite (not one of these three decisions) for delivery and
acceptance surfaces -- see the consolidated gap register, POC0-DELIVERY.
```

## Boundaries of this package

```text
Decisions made by any partner:        0
Options selected:                     0
Implementation authorized:            NO (D-1, D-2, D-3 all IMPLEMENTATION_AUTHORIZED: NO)
POC scope finalized:                  NO
Step 67POC.0 authorized:              NO
RA-2M / RA-2I0 / RA-3 authorized:     NO
Step 66D-ARCH authorized:             NO
production_executed_true_count:       0
```

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
