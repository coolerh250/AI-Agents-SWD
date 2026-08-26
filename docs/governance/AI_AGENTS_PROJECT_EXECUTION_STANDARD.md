# AI Agents Project Execution Standard

> **Process documentation only. No backend/frontend runtime change. No production action.**

The binding, shared execution standard for every partner on this project — Product Owner, ChatGPT
Architect/PM, Claude Code, Claude Design, Codex, and any future partner. It states how work is
scoped, what may block product development, when to stop, and how partners signal disagreement to
each other.

It is **process memory, not a mechanism.** It adds no verifier, no registry, no discovery, no
authority resolution and no runtime. It is enforced by partners reading it and by the Product
Owner, not by code that validates other code.

```text
STANDARD_ID:        AI-AGENTS-PROJECT-EXECUTION-STANDARD
STANDARD_VERSION:   1
RECORDED_ON:        2026-08-26
ORIGIN:             AT-PROJECT-LOGIC-REVIEW-1 -- whole-project forensic postmortem
INSTALLED_BY_STAGE: AT-PROJECT-MEMORY-INSTALL-CLAUDE-1
STATUS:             ACTIVE / BINDING PROCESS MEMORY
```

## 1. Why this exists

An independent read-only forensic review of the repository on 2026-08-26 ("The Governance
Deadlock") found that the project had drifted from building an autonomous AI agents team into
maintaining a self-referential governance subsystem.

```text
PRIMARY CAUSE      Architect/PM governance design over-expansion
SECONDARY CAUSE    Claude Code implementation and validation gaps
CLAUDE MISUNDERSTANDING   PARTIAL -- contributing, not primary
```

The structural failure was specific. Completed stages carried "this stage introduced no
implementation" assertions asked as a diff from a frozen baseline **to current HEAD**. That is
correct while a stage is live and false forever after: every later, legitimately authorized
milestone violates an expired historical assertion by construction.

Instead of retiring or freezing those expired assertions, the project repeatedly generalized the
machinery that exempts work from them:

```text
historical stage guard
  -> successor exemption window
    -> live runtime denylist
      -> reviewed-changeset registry
        -> exact provenance/authority binding
          -> decision discovery
            -> canonical freeze
```

Each layer needed an authority the previous layer could not supply, and the project had **no finite
explicit root of trust** to terminate the chain. The AT-D16 and AT-D17 branches demonstrated the
resulting deadlock: authority required presence on canonical `main`, presence on `main` required a
merge, and the merge required the very guards the mechanism existed to satisfy.

**The lesson this standard encodes:** when a control cannot be satisfied without inventing another
control, the answer is to retire the original assertion, not to build the next layer.

## 2. Product North Star

The product exists to build one thing:

```text
Goal
  -> Team Formation
    -> Discussion
      -> Planning
        -> Delegation
          -> Reasoning
            -> Execution
              -> Verification
                -> Failure Diagnosis
                  -> Replanning
                    -> Retry
                      -> Delivery
```

**Governance exists to protect this product. Governance must not become the product.** Any
governance work that cannot name the product risk it protects is, by that fact, not protecting the
product.

## 3. Minimal Blocking Governance Kernel

Only a control protecting a concrete P0/P1 risk blocks product development by default. These eight
are the kernel:

```text
PES-K1  Production authorization
PES-K2  Human approval boundaries
PES-K3  External network / model / action authorization
PES-K4  Secrets and credential exposure
PES-K5  Destructive and irreversible actions
PES-K6  Audit integrity and anti-tamper
PES-K7  Security and authorization boundary (RBAC, TASK_ROLES, policy)
PES-K8  Canonical-main safety -- unreviewed content must not reach main
```

The kernel restates, and does not replace, the hard restrictions in
`.agents/skills/security-governance/SKILL.md`. Where the two are read together, the SKILL file's
restrictions remain in force exactly as written; this section states which of them are *blocking of
product work* and which merely require authorization before a specific act.

### 3a. Every claimed blocker must be justified

A partner asserting that something blocks product development states all four, in the claim itself:

```text
PROTECTED_RISK      which of PES-K1..K8 it protects, named exactly
SEVERITY            P0 | P1 | P2 | P3
FAILURE_IMPACT      the concrete consequence if the control is absent, not a category
WHY_STOP_NOW        why product development cannot continue while this is open
```

If no P0/P1 risk can be identified, the **default disposition is `NON_BLOCKING`**, and the item is
classified as one of:

```text
PRE_PRODUCTION      real, must be closed before production authorization, does not gate a
                      non-production milestone
INFORMATIONAL       worth reporting and tracking; gates nothing
HISTORICAL_ONLY     evidence about a period that has ended; gates nothing going forward
```

**A failing test is not automatically a blocker.** Classify the risk first, then decide. "This test
currently fails" is an observation; "this failure means an unauthorized production action is
reachable" is a blocker.

## 4. Non-blocking by default

Unless a specific, stated P0/P1 impact is proven, none of the following may block a future product
milestone:

```text
PES-N1  Historical "this stage changed no implementation" assertions
PES-N2  Historical frozen-scope guards over closed stages
PES-N3  PCP / meta-governance measurement consistency and staleness
PES-N4  Verifier and meta-verifier self-consistency
PES-N5  Stale governance evidence and narrative counts
PES-N6  Governance-report completeness
PES-N7  Any control whose only purpose is proving another governance artifact
```

**Historical assertions are evaluated against their own reviewed stage boundary, never against
future HEAD.** A closed stage's scope claim is evidence about a period that ended. It needs no live
authority to remain true, and it acquires no new meaning from commits made after the stage closed.

This does not weaken any live control. A runtime denylist, a security boundary check, or any
PES-K1..K8 control is *not* a historical assertion and keeps scanning current state, forever.

## 5. Role contract

This section is the governance/blocking view of the roles. It is additive to, and does not replace,
`docs/process/role-responsibility-matrix.md`, which remains authoritative for day-to-day delivery
ownership.

### Product Owner

```text
Owns   product direction; canonical transition approval; genuine risk acceptance;
       production and external authorization; final acceptance
```

### ChatGPT — Architect / PM

```text
Owns   product critical path; architecture; blocker severity; STOP/GO; roadmap;
       whether a governance control is worth doing at all
```

Blocker severity is this role's call and must be exercised against section 3a — not inherited from
whichever test happens to be red.

### Claude Code — Implementer

```text
Owns   real repository truth; bounded implementation; real Git and runtime evidence; tests;
       transparent reporting of what was and was not verified
```

Claude Code **must challenge or STOP rather than implement** when a request would create recursive
governance. Implementing a request that trips section 7 is a failure of this role even when the
implementation itself is correct.

### Codex — Implementer (assigned surfaces)

```text
Owns   its assigned implementation surfaces
Must   independently flag any conflict with the Product North Star, the Minimal Governance
         Kernel, or real lifecycle behavior
```

### Independent Validator

```text
Validates an already-approved design.
```

If validation finds an **architecture or design-premise** failure rather than an implementation
defect, it returns:

```text
DESIGN_FINDING / DESIGN_REVIEW_REQUIRED
```

and stops. It does **not** invent another remediation layer inside the validation round. This is
the specific failure that produced the AT-D16/AT-D17 deadlock: two validation rounds returned
architectural findings, and both were implemented as code inside the round, under a budget with no
capacity left to check whether the new design was sound.

## 6. Execution lifecycle

```text
DESIGN REVIEW
  -> IMPLEMENTATION
    -> INDEPENDENT IMPLEMENTATION VALIDATION
      -> PRODUCT OWNER ACCEPTANCE
        -> PRE-PRODUCTION COMPLIANCE
```

```text
An implementation report is a CLAIM.
Independently reproduced evidence is PROOF.
```

Load-bearing acceptance properties must be tested against the **real** repository, the **real** Git
lifecycle, and the **real** runtime lifecycle. Synthetic fixtures are legitimate and often
necessary, but they are **insufficient alone** wherever they differ materially from the real
operating lifecycle.

The concrete failure this rule prevents: AT-D16/AT-D17 shipped 70 passing tests built on synthetic
Git repositories in which decision records are written once and never amended. The real project
amends decision records in place as a matter of policy. The mechanism was therefore permanently
non-functional in the real repository while every one of its own tests passed.

**A governance mechanism's acceptance criterion is an assertion evaluated in the real repository at
the candidate tip — not a count of passing unit tests.**

## 7. Mandatory STOP rules

STOP immediately if **any** of these hold:

```text
PES-S1  A control begins validating its own validator.
PES-S2  Fixing a control requires modifying the authority that legitimizes that same fix.
PES-S3  The same root problem is about to create a third governance or meta layer.
PES-S4  Synthetic fixture behavior differs materially from actual Git, runtime or deployment
          lifecycle.
PES-S5  No finite explicit root of trust exists.
PES-S6  Governance work is blocking product work without a concrete P0/P1 safety risk.
PES-S7  Validation finds a DESIGN premise defect rather than an implementation defect.
PES-S8  Preserving an invariant requires a growing exception list.
PES-S9  A historical assertion is being applied permanently to future HEAD with no active
          safety reason.
```

These are additive to `docs/process/stop-conditions.md`, which remains in force. That document
covers conflicts between prompt, `main`, decisions, authorization and secrets. This section covers
**governance recursion** specifically, which that document did not previously address.

### After STOP

```text
Do NOT add another mechanism.
Record the evidence, reproduced.
Classify the risk: P0 | P1 | P2 | P3.
Recommend one of: REDESIGN | RETIRE | DEFER | HISTORICAL_ONLY | PRE_PRODUCTION.
Escalate to the ChatGPT Architect/PM, and to the Product Owner where authorization is involved.
```

Reporting a STOP is not a failure. Proceeding past one silently is.

## 8. GOVERNANCE_DRIFT_ALERT

Whenever this standard is violated, or is likely to be violated by the work about to be done, the
partner emits exactly this block:

```text
GOVERNANCE_DRIFT_ALERT

RULE_VIOLATED:
EVIDENCE:
RISK_CLASS: P0 | P1 | P2 | P3
PRODUCT_IMPACT:
RECOMMENDATION: STOP | DEFER | PRE_PRODUCTION | HISTORICAL_ONLY | CONTINUE
PO_DECISION_REQUIRED: YES | NO
CROSS_PARTNER_NOTE:
```

**This alert is not a refusal to work. It is a coordination signal.** `RECOMMENDATION: CONTINUE` is
a valid outcome: the alert can record that drift was considered, evidenced, and judged acceptable.
What is not acceptable is proceeding without surfacing it.

## 9. Cross-partner responsibility

Claude Code and Codex share this standard. Claude Design and any future partner do too.

If any partner encounters an `AGENTS.md`, a handoff, an implementation, a prompt, or a test
expectation that contradicts this standard, it must **not silently adopt the contradiction**. It
raises `GOVERNANCE_DRIFT_ALERT` and lets the Architect/PM or Product Owner resolve it.

The obligation is symmetric. Claude Code must expect Codex to challenge Claude-side output on the
same grounds, and must treat such a challenge as a legitimate coordination signal rather than an
obstruction.

```text
No partner has authority to silently redefine the shared execution standard.
```

Changing this standard requires an explicit Product Owner decision recorded under
`docs/decisions/`, exactly as any other binding project decision.

## 10. Current project disposition

Preserved here as current process memory, as of 2026-08-26:

```text
AT_D16_AT_D17_BRANCHES:   FAILED / NONCANONICAL EXPERIMENTS
                            not candidates for further remediation or merge unless a future
                            explicit Product Owner reset decision changes this
PM_RECOMMENDATION:        Option B -- Minimal Governance Kernel + Product/Governance Decoupling
AT_M3_2:                  IMPLEMENTATION-AUTHORIZED under AT-D14
PRODUCT_RESUMPTION:       after the reset reconciliation is approved and executed
```

Still **not** authorized, unchanged by this standard:

```text
Production action / production authorization    NOT AUTHORIZED / NOT GRANTED
AT-M3.6B -- real external model or network call NOT AUTHORIZED
AT-M4                                            NOT AUTHORIZED unless separately authorized
Unrelated PCP remediation                        NOT AUTHORIZED
```

This standard authorizes no milestone, retires no registered governance debt, reclassifies no
recorded decision, and grants no production or external authorization. It is a process record.
`production_executed_true_count: 0`.

## 11. Relationship to existing documents

This is the single authoritative statement of the rules above. It does not duplicate or supersede
the documents below; where a reader needs detail, these remain the place to find it.

| Document | Relationship |
| --- | --- |
| `docs/process/stop-conditions.md` | Still in force. Section 7 is additive: governance recursion. |
| `docs/process/role-responsibility-matrix.md` | Still authoritative for delivery ownership. Section 5 is the governance/blocking view. |
| `docs/process/source-of-truth-policy.md` | Unchanged and still authoritative. |
| `docs/process/partner-handoff-standard.md` | Unchanged. A handoff still follows it. |
| `.agents/skills/security-governance/SKILL.md` | Unchanged. Section 3 states which restrictions block *product work*. |
| `.agents/skills/shared-context/SKILL.md` | Unchanged preflight. This standard is read alongside it. |
| `docs/governance/AI_AGENTS_PM_STATE.md` | Records live project position; references this standard. |
| `docs/governance/project-control-plane-v2.md` | Unchanged. Its measurement controls are PES-N3 — pre-production, not product-blocking. |
| `CLAUDE.md` (repo root) | Bootstrap pointer only. Never a copy of this file. |

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
