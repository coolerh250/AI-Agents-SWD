# AT-D18 — project governance reset & minimal governance kernel

> **Product Owner decision record. Adopts Option B — Minimal Governance Kernel plus
> product/governance decoupling — dispositions the AT-D16/AT-D17 branches as failed noncanonical
> experiments, and restores the product critical path at AT-M3.2. Authorizes no production action,
> no external action, no AT-M3.2 implementation start, no AT-M4 and no PCP remediation.
> `production_executed_true_count: 0`.**

```text
AT-D18:                      RESOLVED / BINDING
Recorded_on:                 2026-08-26
Recorded_by:                 Product Owner
Canonical_main_at_decision:  5a04ec1c67453c4d90b525e94402b9515fbec0bf
Depends_on:                  AT-D14 (docs/decisions/at-d14-at-m3-live-reasoning-authorization.md)
Origin:                      AT-PROJECT-LOGIC-REVIEW-1 -- whole-project forensic postmortem
Standard:                    docs/governance/AI_AGENTS_PROJECT_EXECUTION_STANDARD.md
```

## 1. What this record is for

An independent read-only forensic review on 2026-08-26 found that this project had drifted from
building an autonomous AI agents team into maintaining a self-referential governance subsystem.
Historical stage assertions — "this stage introduced no implementation", asked as a diff from a
frozen baseline to **current HEAD** — were left permanently live, so every later, legitimately
authorized milestone violated an expired assertion by construction. Each time this fired, the
project generalized the exemption machinery rather than retiring the expired assertion, and the
resulting chain had no finite root of trust and did not terminate.

This record is the Product Owner's reset. It reduces governance rather than extending it, and it
adds no mechanism: no verifier, no registry, no decision discovery, no canonical activation, no
meta-governance runtime.

## 2. What is decided

```text
AT-D18-R01  Option B is adopted: a Minimal Governance Kernel plus product/governance decoupling.
            Governance exists to protect the product and does not become the product.

AT-D18-R02  The AT-D16 and AT-D17 implementation branches are FAILED / NONCANONICAL GOVERNANCE
            EXPERIMENTS and are NOT FOR MERGE, unless a future explicit Product Owner decision
            changes that disposition.

AT-D18-R03  Historical, frozen-scope and meta-governance controls do NOT automatically block
            future product milestones. Such a control may block only when concrete evidence
            shows a P0/P1 safety risk.

AT-D18-R04  The Minimal Blocking Governance Kernel is limited to exactly these eight:
              production authorization
              human approval boundaries
              external model / network / action authorization
              secrets and credentials
              destructive and irreversible actions
              audit integrity and anti-tamper
              security and authorization boundaries
              canonical-main safety

AT-D18-R05  Every claimed blocker must identify PROTECTED_RISK, SEVERITY, FAILURE_IMPACT and
            WHY_STOP_NOW. Where no P0/P1 risk exists the default disposition is NON_BLOCKING,
            classified as PRE_PRODUCTION, INFORMATIONAL or HISTORICAL_ONLY.

AT-D18-R06  Historical assertions are evaluated against their own reviewed stage boundary, never
            against future HEAD.

AT-D18-R07  The project execution lifecycle is:
              DESIGN REVIEW -> IMPLEMENTATION -> INDEPENDENT IMPLEMENTATION VALIDATION
                -> PRODUCT OWNER ACCEPTANCE -> PRE-PRODUCTION COMPLIANCE

AT-D18-R08  An architecture or design-premise finding returns DESIGN_REVIEW_REQUIRED. It must
            NOT be repaired by recursively adding another governance layer inside a validation
            round.

AT-D18-R09  ChatGPT, Claude Code and Codex emit GOVERNANCE_DRIFT_ALERT, in the format the shared
            standard defines, when work contradicts that standard.

AT-D18-R10  Product development may resume after Reset-0 canonical reconciliation.

AT-D18-R11  AT-M3.2 remains implementation-authorized under AT-D14. No new Product Owner
            implementation authorization is required for it unless its architecture, security or
            authorization boundary materially expands.

AT-D18-R12  This record does not authorize deleting historical evidence. Failed governance
            experiments and historical reports may remain in the repository as evidence, but must
            not remain Product Critical Path blockers without a P0/P1 risk.
```

## 3. What is NOT authorized

```text
Production action                    NOT AUTHORIZED -- unchanged, no path to one is added
Production authorization             NOT GRANTED -- unchanged
AT-M3.6B / real external model or    NOT AUTHORIZED -- unchanged from AT-D14/AT-D15
  network call
External model credentials           NOT AUTHORIZED
AT-M4                                NOT AUTHORIZED unless separately authorized
AT-M3.2 implementation start         NOT STARTED by this record -- AT-D14 already authorizes the
                                       work; this record neither grants nor withholds that
                                       authority and does not itself begin it
Unrelated PCP remediation            NOT AUTHORIZED by this record
AT-D16 / AT-D17 remediation or merge NOT AUTHORIZED -- see AT-D18-R02
Deleting historical evidence         NOT AUTHORIZED -- see AT-D18-R12
Weakening any kernel control         NOT AUTHORIZED -- AT-D18-R04's eight controls are unchanged
                                       in strength; this record changes only what may block
                                       product work, never what is enforced
```

## 4. What this decision does NOT do

```text
Does NOT amend AT-D01 through AT-D15
Does NOT rewrite or falsify any historical decision record or stage report
Does NOT retire, reduce or reclassify any registered PCP or governance debt
Does NOT disposition HAZARD_AT_M1_DENYLIST or HAZARD_AT_M3_LIVE_DENYLIST -- both stay as
   recorded in AI_AGENTS_PM_STATE.md section 8; under AT-D18-R03 they block no product
   milestone by default, which is a classification, not a retirement
Does NOT introduce a verifier, registry, discovery mechanism or canonical activation
Does NOT grant production authorization -- NOT GRANTED, unchanged
Does NOT relax TASK_ROLES, RBAC, policy or approval
Does NOT configure GitHub branch protection or CI -- deferred to a later minimal-kernel
   hardening stage
```

## 5. Relationship to the shared standard

`docs/governance/AI_AGENTS_PROJECT_EXECUTION_STANDARD.md` is the single authoritative statement of
the operating rules this record adopts. This decision is the Product Owner authority behind that
standard; the standard is where the detail lives. `CLAUDE.md` and `AGENTS.md` at the repository
root are thin bootstrap pointers to it and must never become copies of it.

Changing the standard requires a future decision recorded here, exactly as this one was.

## 6. Root of trust — recorded state, not a claim

The postmortem found no finite explicit root of trust outside repository content. This record does
not create one, and deliberately does not claim one exists:

```text
GITHUB_BRANCH_PROTECTION:  UNVERIFIED -- not determinable from the local environment
REQUIRED_REVIEW:           UNVERIFIED -- not determinable from the local environment
CI_WORKFLOWS:              NONE -- .github/workflows/ does not exist in this repository
COMMIT_SIGNING:            NOT IN USE -- process-memory commits are unsigned
```

Establishing those primitives is a later minimal-kernel hardening stage and is explicitly out of
scope here (section 3).

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
