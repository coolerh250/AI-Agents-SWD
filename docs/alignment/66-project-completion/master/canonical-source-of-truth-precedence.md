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

## Current authorization status

```text
POC implementation:  NOT STARTED / NOT AUTHORIZED
Step 66D-ARCH:       NOT STARTED / NOT AUTHORIZED
Step 67POC.0:        NOT STARTED / NOT AUTHORIZED
RA-2M:               NOT STARTED / NOT AUTHORIZED
BE3 resume/replay:   DISABLED
```

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
