# Canonical Source-of-Truth Precedence

> **Index and precedence record only. No runtime, frontend, backend, API, database, workflow,
> deployment, migration, secret, or feature-gate change. `production_executed_true_count: 0`.**

Established by Step 66SYNC.1-M1. When two documents in this repository disagree about program
state, decision status, or authorization status, the higher tier governs.

## Precedence order

```text
1. Product Owner accepted binding decisions
2. Current canonical program-state addendum
3. Final reconciliation package
4. Partner acknowledgements and evidence
5. Historical snapshots
6. Planning proposals
```

## Tier contents (current)

```text
Tier 1 -- Product Owner accepted binding decisions
  docs/handoffs/program-sync/step66sync1-poc-scope-binding-decisions.md
    D-1, D-2, D-3 RESOLVED / BINDING; binding conditions B-01..B-12.

Tier 2 -- Current canonical program-state addendum
  docs/alignment/66-project-completion/master/partner-synchronized-program-state-20260804.md

Tier 3 -- Final reconciliation package (2396c6c)
  docs/alignment/66-project-completion/master/partner-synchronized-program-state-20260803.md
  docs/handoffs/program-sync/step66sync1-final-partner-acknowledgement.md
  docs/handoffs/program-sync/step66sync1-final-context-discrepancy-register.md
  docs/handoffs/program-sync/step66sync1-poc-scope-decision-package.md
  docs/handoffs/program-sync/step66sync1-poc0-consolidated-gap-register.md

Tier 4 -- Partner acknowledgements and evidence
  Claude Code   828ea90  step66sync1-claude-code-acknowledgement.md
                         step66sync1-context-discrepancy-register.md
                         step66sync1-poc-backend-readiness-matrix.md
                         partner-context-snapshot-20260803.md
  Codex         78aa4ee  step66sync1-codex-acknowledgement.md
                         step66sync1-codex-frontend-gap-register.md
  Claude Design 65c93a1  step66sync1-claude-design-acknowledgement.md
                         step66sync1-claude-design-ux-gap-register.md
                         docs/design/ai-agent-team-functional-poc-control-center-spec.md
  plus the four docs/test/ evidence records.

Tier 5 -- Historical snapshots
  Everything under docs/alignment/66-project-completion/master/ predating this record, including
  the master plan, its source-of-truth record, and the milestone/gate/ownership documents.

Tier 6 -- Planning proposals
  docs/handoffs/.../be3-ra2-implementation-stage-decomposition.md and comparable stage-decomposition
  or option documents. Proposals only.
```

## Known precedence resolutions

```text
Decision status
  Tier 3 and Tier 4 artifacts record OPEN_PRODUCT_OWNER_DECISIONS: 3. That was true at
  reconciliation time and those documents are preserved unchanged. Tier 1 supersedes: D-1, D-2 and
  D-3 are RESOLVED / BINDING as of 2026-08-04, and open decisions from Step 66SYNC.1 are 0.

Screen count
  The specification (Tier 4, 65c93a1, §7.1-7.15) is authoritative at 15 screens. Any 14-name
  summary is superseded.

66D
  Step 66D-ARCH / 66D-DESIGN / 66D implementation slices are canonical stage identifiers already on
  main. They were confirmed, not renamed.
```

## What must not be treated as source of truth

```text
A conversation summary or completion report      -- never authoritative; evidence must be committed.
A design option (including the two POC.0 IA      -- non-binding until a Product Owner selects it.
  options)
A partner recommendation                         -- advisory only.
A planning proposal or stage decomposition       -- proposal only; confers no authorization.
```

None of the above may be written up as authorized implementation. Authorization exists only where a
Product Owner authorization record says so explicitly.

## RA-2 identity and secret precedence (Step 66C.4-BE3-RA-2M1)

The same six-tier order applies to the RA-2 identity and secret decision set:

```text
1. Product Owner binding decisions
   docs/contracts/66c4-reminder-expiry-controlled-resume/step66c4-be3-ra2-binding-decisions.md
     RA2-D01..RA2-D12 RESOLVED / BINDING; conditions RA2-C01..RA2-C06.

2. Current RA-2 canonical state addendum
   docs/alignment/66-project-completion/master/step66c4-be3-ra2-current-state-20260804.md

3. RA-2 binding decision record's implementation sequence
   RA-2M -> RA-2I0 -> RA-2I4P -> RA-2I4A -> RA-2I4B -> RA-2I1 -> RA-2I3 -> RA-2I2
        -> RA-2I5 -> RA-2I6 -> RA-2R -> RA-3.
   An APPROVED EXECUTION SEQUENCE, not an implementation authorization.

4. Historical RA-2 planning evidence (planning source efa396d, imported unchanged)
   docs/security/be3-ra2-current-state-identity-secret-inventory.md
   docs/security/be3-ra2-identity-secret-threat-and-trust-analysis.md
   docs/contracts/66c4-.../be3-ra2-identity-secret-provisioning-decision-package.md
   docs/handoffs/66c4-.../be3-ra2-implementation-stage-decomposition.md
   docs/test/step66c4-be3-ra2-identity-secret-decision-evidence.md
   docs/alignment/66-project-completion/master/next-executable-stage-sequence.md

5. Partner recommendations                -- advisory only
6. Conversation summaries                 -- never authoritative
```

Known precedence resolutions for RA-2:

```text
Decision status
  Tier 4 records every decision as PENDING / PRODUCT_OWNER_DECISION_REQUIRED with
  "Decided by Claude Code: 0". That was true at analysis time and is preserved unchanged.
  Tier 1 supersedes: RA2-D01..D12 are RESOLVED / BINDING as of 2026-08-04.

RA-2 test count
  next-executable-stage-sequence.md (Tier 4) states "79 tests passed". That figure is wrong.
  The authoritative count is 100 passed / 0 skipped / 0 failed, per the RA-2 evidence record
  and per re-running the test file. Tier 2 §6 carries the correction.

Implementation sequence
  The Tier 4 stage decomposition proposes a single RA-2I4. Tier 1 splits it into RA-2I4P,
  RA-2I4A and RA-2I4B; Tier 1 governs.

Vault Agent versus CSI
  NOT selected at any tier. Assigned to RA-2I4P. It is an implementation-planning choice,
  not an open Product Owner decision.
```

A planning recommendation is never an implementation authorization. Neither the decision record nor
this precedence index authorizes any RA-2 implementation stage.
RA-2I0 through RA-2R and RA-3 are all NOT AUTHORIZED, and each requires its own separate Product
Owner authorization (RA2-C06).

## Step 66D delivery decision model precedence (Step 66D-ALIGN1)

```text
Tier 1 -- Product Owner binding decisions
  docs/contracts/66d-delivery-acceptance/step66d-delivery-decision-model-binding-decisions.md
    66D-D01..66D-D04 RESOLVED / BINDING, 2026-08-04.

Tier 1 supporting registry
  docs/contracts/66d-delivery-acceptance/step66d-canonical-terminology-registry.md
  docs/handoffs/66d-delivery-acceptance/step66d-canonical-conflict-supersession-matrix.md
```

**The 66D-D01..D04 binding decision record supersedes conflicting active terminology without
rewriting historical evidence.** Active canonical documents were edited to remove the contradiction;
partner specifications and gap registers were annotated with append-only supersession notes and
their original text left byte-for-byte intact.

Known precedence resolutions for Step 66D:

```text
Decision vocabulary
  The master-plan family described a 6-action gate; the Claude Design specification said
  "Product Owner decision (only these three)". Both were right about different layers. 66D-D01
  governs: six Review Gate Actions AND three Product Owner Final Decisions, as separate contracts.
  Neither prior statement is discarded; each is scoped.

Delivery lifecycle
  The earlier rule that acceptance must not appear in the delivery lifecycle at all is superseded
  by 66D-D02: delivery review status MAY project the current effective decision, while the
  authoritative history is a separate immutable, supersedable ProductOwnerDecision record.

Anchor
  66D-D03 governs: execution and artifact lineage is project -> work item -> workflow -> run;
  human review and TASK_ROLES authorization anchor on delivery_review_task_id. Binding decision
  D-1 is preserved -- the Task surface is still not the Agent execution source of truth.

Entity naming
  66D-D04 governs: the legacy DeliveryPackage (Step 47/49 Platform Ops evidence object) is
  preserved unchanged; the new human-acceptance aggregate is DeliverySubmission.

Annotated partner evidence
  docs/design/ai-agent-team-functional-poc-control-center-spec.md
  docs/handoffs/program-sync/step66sync1-claude-design-ux-gap-register.md
  docs/handoffs/program-sync/step66sync1-poc0-consolidated-gap-register.md
    Each carries an append-only "Supersession note -- Step 66D-ALIGN1" section. The content above
    each note's marker is unchanged from its Step 66SYNC.1 source blob and stays Tier 4 evidence.
```

Resolving the vocabulary conflict is not a contract freeze. Step 66D-ARCH remains NOT AUTHORIZED,
as do Step 66D-DESIGN and every Step 66D implementation slice.

## Autonomous Team architecture precedence (AT-M1)

```text
Tier 1 -- Product Owner binding decisions
  docs/contracts/autonomous-team/at-binding-decisions.md
    AT-D01..AT-D05 RESOLVED / BINDING.

Tier 1 supporting registry
  docs/contracts/autonomous-team/at-canonical-terminology-registry.md
  docs/contracts/autonomous-team/at-capability-state-registry.json
  docs/decisions/at-m1-architecture-decisions.md   AT-ADR-01..08
```

**AT-D01..AT-D05 govern the CURRENT TARGET ARCHITECTURE of the autonomous-team middle journey —
how agents obtain a shared goal, discuss, plan, decompose, divide work, execute, verify, debug and
re-run.** This is a scoped precedence, not a global supersession. AT-M1 does not rewrite historical
documents and does not displace Step 66 or 66D architecture outside the middle journey.

Scoped relationships:

```text
AT-D01  Execution source of truth
  PRESERVES binding decision D-1 (66SYNC.1) and 66D-D03 execution lineage:
  project -> work item -> workflow -> run remains the execution anchor, and the Task surface is
  still NOT the Agent execution source of truth.

AT-D02  Agent principal model
  ADDS ActorPrincipal / AgentProfile / ProjectTeamMembership as a SEPARATE agent-identity layer.
  Does NOT replace the six human TASK_ROLES in shared/sdk/tasks/rbac.py, which stay the human
  authorization contract, unmodified.

AT-D03  Collaboration model
  SUPERSEDES, as target architecture, the template/simulated discussion in
  shared/sdk/agent_discussion/ (deterministic_template contribution strings). The existing module
  is retained as a fixture, not deleted. Redis stream dispatch is not discussion.

AT-D04  Planning, delegation and replanning
  SUPERSEDES, as target architecture, the template planner (shared/sdk/project_planning/
  task_graph.py literals), static work-item dispatch (shared/sdk/work_items/dispatcher.py plus its
  policy YAML, demoted to fallback/policy seed) and linear LangGraph routing
  (apps/orchestrator/src/workflow.py). All are retained; none is deleted by AT-M1.

AT-D05  Middle-journey design amendment
  SCOPED amendment of the 66D-DESIGN middle journey only. Delivery and Acceptance boundaries are
  PRESERVED in full.
```

Explicitly preserved, NOT superseded by the AT family:

```text
66D Delivery Review and the six Review Gate Actions
ProductOwnerDecision and the three Product Owner Final Decisions
66D-D01..66D-D05 and ADR-66D-01..10
Delivery / Acceptance boundaries and the DeliverySubmission aggregate
Safety, evidence, cost and external-action contracts
Human TASK_ROLES authorization (six human roles)
Binding decision D-1 (66SYNC.1)
Step 66C.4 clarification expiry contract -- AT-D09 remains OPEN / DEFERRED and is NOT decided here
```

```text
AT-M1 canonical status:  CLOSED / CANONICAL on main.
                         PR #29 MERGED; reviewed stage head c80350e, merge commit db4e7a7.
                         These decisions are the target-architecture authority for the middle
                         journey and are canonical on main.
PR #28:                  HOLD / PRESERVE / NON-CANONICAL -- future AT-M7 input, not a dependency
                         of AT-M1..AT-M6.
```

## Current authorization status

```text
POC implementation:  NOT STARTED / NOT AUTHORIZED
Step 66D-ARCH:       NOT STARTED / NOT AUTHORIZED
Step 67POC.0:        NOT STARTED / NOT AUTHORIZED
RA-2M:               NOT STARTED / NOT AUTHORIZED
BE3 resume/replay:   DISABLED
AT-M2..AT-M8:        NOT AUTHORIZED
PCP-V2.1:            REQUIRED BEFORE AT-M2
```

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
