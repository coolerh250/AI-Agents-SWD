# Project Control Plane v2

> **Governance artifact only. No backend/frontend runtime change. No production action.**

PCP-v2 is how this project is driven when no single session can hold its history. It extends, and
does not replace, [the source-of-truth policy](../process/source-of-truth-policy.md) and
[the context guard protocol](../process/context-guard-protocol.md).

The problem it solves: a project whose control state lives in a conversation dies with the
conversation. Every stage that begins by re-reading a transcript pays for the whole history again
and still inherits whatever the transcript got wrong.

## 1. Source-of-truth hierarchy

```text
1  GitHub canonical main          engineering source of truth
2  PM State Snapshot              derived project-control truth  (AI_AGENTS_PM_STATE.md)
3  persistent assistant memory    durable principles and decisions only
4  conversation history           convenience context, never required
```

A lower tier never overrides a higher one. When tiers disagree the answer is not "prefer the
newer" or "prefer the more detailed" — it is **stop and reconcile downward from `main`**.

## 2. Durable versus volatile

Persistent memory **should** hold: durable operating principles, binding Product Owner decisions,
long-lived architectural constraints, the authorization model, stable workflow rules.

Persistent memory **must not** be the sole authority for: the canonical SHA, any test or check
count, any path count, pull-request state, the current stage or gate, the current blocker, or any
execution evidence. Those are volatile. They are recovered from canonical sources and reconciled,
every time.

The failure this prevents is specific: a confidently remembered SHA or test count that was true
three stages ago reads exactly like a currently true one.

## 3. Delta prompt / stage contract

A stage prompt transmits a **delta**, not a history:

```text
STAGE FINGERPRINT     the small set of facts the stage depends on, stated as values
DELTA                 what changed since, and what this stage must do
INVARIANT             the property that must hold when the stage is done
DOMAIN                where the invariant must hold, stated as a set, not as examples
GATE                  G1 | G2 | G3
PASS CRITERIA         what makes it done, checkable without the author present
```

Known instances of a defect are **evidence**, never the specification. A defect written as a list
of instances gets fixed exactly at those instances, and the next review finds instance n+1. This
project has paid that cost repeatedly.

## 4. Stage capsule

A stage reports a compact state-transition capsule, not a narrative: measured truth with the
measurement, blockers, advisories, safety state, and the next stage. Numbers appear only if they
were measured in that stage.

## 5. Risk-adaptive gates

```text
G1  documentation / evidence
G2  contract / verifier / governance
G3  runtime / schema / security / infra / canonical merge / high risk
```

The stage owner sets the gate. An implementer **may recommend escalation and may not
self-authorize a lower one**. Discovering mid-stage that the work needs a higher gate is a
stop-and-report condition, not a judgment call.

## 6. Pre-authorized repair window

Remediation of the same invariant, in the same domain, at the same risk may proceed without new
Product Owner authorization when all of the following hold:

- no architecture decision changes
- no security boundary changes
- no Product Owner decision is introduced
- no scope or risk expansion occurs

Outside that window, authorization is required first.

## 7. Independent closure

Bounded remediation is closed by a **focused independent audit** of the specific invariant, run
without access to the implementer's reasoning. A full architecture review is not repeated for a
bounded fix.

The reviewer must derive its own counts. An audit that accepts the implementer's numbers is not
independent, and this project has had reviewers report figures that did not survive reproduction.

## 8. Product Owner gates

Explicit authorization is always required for: a binding product or architecture decision, merge
authorization, any production or external irreversible action, and any scope or risk authorization
outside the repair window above.

## 9. Root-defect memory model

Project control tracks the **root defect class and its invariant**, not a list of finding IDs.
Finding IDs are evidence of an instance; they are not the unit of memory.

A defect specification has this shape:

```text
INVARIANT                    the property, stated over a domain
DOMAIN                       the full set it must hold over
KNOWN INSTANCES              explicitly marked NON-EXHAUSTIVE
ADVERSARY MODEL              the shapes an attacker or a careless author would use
POSITIVE CONTROLS            what must keep passing, so the fix cannot be "reject everything"
CLOSURE PROOF                how closure is demonstrated against the invariant, not the instances
RISK GATE                    G1 | G2 | G3
```

Worked example from this repository's own history, recorded because the shape repeated seven
times: an invariant about structured governance carriers was fixed first by enumerating forbidden
state words, then by enumerating permitted key characters. Both fixes passed their own reviews.
Neither removed the enumeration; each relocated it. Closure came only from a fix stated over the
domain — a key is whatever precedes the first colon — and from a test asserting the probe
vocabulary appears nowhere in the implementation.

## 10. Self-consistency invariants

These are machine-checked by `scripts/verify_pcp_v2_control_plane.py`.

```text
I1  a NOT AUTHORIZED stage cannot simultaneously be the current implementation
I2  a HOLD / NON-CANONICAL artifact cannot be a current canonical dependency
I3  an OPEN / DEFERRED decision cannot be represented as downstream BINDING truth
I4  with no production authorization, the production execution count must remain 0
I5  a MERGED pull request must be ancestry-reconcilable with canonical main
I6  a CLOSED / CANONICAL milestone must have canonical evidence and ancestry
I7  the next stage must satisfy its roadmap prerequisites
```

I7 currently means: AT-M2 requires PCP-V2.1 to have passed. Until then AT-M2 is NOT AUTHORIZED.

## 11. What BLOCKERS: NONE means

It does not mean "the stage author did not notice a blocker". For the governance domain it means
all three of these, and it is machine-checked:

```text
1  the APPLICABLE governance verification set was executed
   -- derived, never nominated: every verifier that computes its own changed-path set against
      live HEAD, because those are exactly the ones an incoming path can break
2  every MEASURED failure appears in the registered-debt list, by EXACT identity
   -- verifier:<file> and test:<nodeid>; a family or a module is not an identity
3  the measurement is FRESH
   -- invalidated as soon as any governance artifact changes after it was taken
```

```text
NEW_UNREGISTERED = MEASURED_FAILURE_IDS - REGISTERED_DEBT_IDS
NEW_UNREGISTERED non-empty  ->  BLOCKERS may not be NONE  ->  GOVERNANCE_REGRESSION
```

Both halves of this were learned the hard way. A stage nominated four sentinels and missed the one
that broke; the derived set later found a third site that the nomination had also missed. And debt
recorded at family granularity let a new failure hide behind an existing advisory that shared its
verifier family — the register said BLOCKERS: NONE while two governance verifiers were failing on
canonical main.

### 11a. Where the measurement runs, and what may count

Both of the above assume the measurement describes canonical main. It did not. The measurement ran
in the operator's own working tree, so three verifiers that read a gitignored `.runtime/` directory
passed here and failed in a clean checkout of the same commit — with a byte-identical authority
digest. `BLOCKERS: NONE` was a property of one workstation.

```text
CANONICAL_MEASUREMENT = F(canonical_commit, canonical_authority_inputs, measurement_policy)

not                   F(canonical_commit, whatever_happens_to_exist_locally, ambient_environment)
```

So a canonical measurement runs in a disposable clean checkout of the canonical commit under a
sanitized environment, and every measured identity resolves to one of three states:

```text
REPO_DETERMINISTIC     every input it actually read is canonical tracked repository state
                       -> participates in debt reconciliation

ENVIRONMENT_DEPENDENT  its truth needs an input a clean checkout cannot contain
                       -> reported with the exact input, and NOT registered as repository debt.
                          Repository debt means a known canonical governance failure; it must not
                          come to mean "this machine had no runtime evidence"

UNKNOWN                its inputs could not be observed, so their authority is unestablished
                       -> BLOCKS. Never mapped to either neighbour: calling it environment-
                          dependent would silently exclude it, and calling it deterministic would
                          silently adopt the workstation's answer
```

Admissibility is decided by **observing what a module actually reads**, not by inspecting how it is
written, and what counts as non-canonical is decided by `git check-ignore` rather than by any list
kept here. Both choices are deliberate. A path can be spelled an unbounded number of ways, and
every previous attempt to classify governance modules by their text — stage family, ref spelling,
command form, executable name — was defeated by a spelling nobody anticipated. What a process opens
is decidable regardless of spelling, and the repository already declares which paths it will never
carry.

## 12. Two classes of fact, two authority models

Not every fact in the snapshot has a Git source, and pretending otherwise produced a real
contradiction: the packet said never to take a stage from the snapshot alone, while the stage
verdicts existed nowhere else.

```text
ENGINEERING VOLATILE FACT      any SHA, PR state, merge state, ancestry, path or test count,
                               measured failure identity
  authority   canonical main. The snapshot is a cache and is never sufficient.
  recovery    verify against git / GitHub / a canonical engineering artifact, every time.

PM CONTROL-PLANE FACT          independent review verdict, acceptance outcome, PM authorization,
                               gate disposition, stage position
  authority   the PM State Snapshot MAY be authoritative, but only when all four hold:
                the field is structured and versioned, not narrative prose;
                its provenance fields are internally consistent;
                the snapshot itself reconciles against engineering truth;
                no higher tier contradicts it.
  recovery    read the structured field, then check those four conditions.
```

A PM control-plane fact recorded only as prose is not authoritative at all. The distinction is
between *a fact that has an engineering source and must be checked against it* and *a fact whose
only possible source is the control plane* — never a licence for narrative to become truth.

## 13. Memory drift gate

The drift gate reconciles the PM State Snapshot against canonical engineering truth and
distinguishes two failure modes:

```text
STALENESS   the snapshot's main SHA is an ancestor of current main
            tolerated, reported, does not stop work

DRIFT       a stable/binding fact disagrees with canonical truth, or the snapshot names a commit
            unknown to the repository or not an ancestor of main
            PM_STATE_CONFLICT -- stop
```

On conflict the system stops. It does not silently prefer whichever source is more convenient,
which is the specific behaviour that makes a stale snapshot dangerous rather than merely wrong.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
