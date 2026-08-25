# AT-D17 — data-driven decision discovery and future authority bootstrap

> **Product Owner decision record. Authorizes implementing bounded, convention-based decision
> discovery to replace the hard-coded decision-id map, and typed per-decision authority for
> decisions recorded after AT-D16. Authorizes no acceptance/merge of this or any implementation,
> no production action, no external action, no AT-M3.2 implementation and no PCP remediation.
> `production_executed_true_count: 0`.**

```text
AT-D17:                      RESOLVED / BINDING
Recorded_on:                 2026-08-25
Recorded_by:                 Product Owner
Canonical_main_at_decision:  5a04ec1c67453c4d90b525e94402b9515fbec0bf
Depends_on:                  AT-D16 (docs/decisions/at-d16-multi-milestone-changeset-registry.md)
```

## 1. What this record is for

AT-GOV-DECISION-DISCOVERY-REBASELINE-1 found that AT-D16's live-guard registry, while sound on
every axis two rounds of adversarial validation exercised, cannot scale: `scripts/successor_lifecycle.py`
resolved a decision id to its file through `_DECISION_RECORD_PATHS`, a Python dict enumerating
exactly six ids. Every future milestone -- authorized, by this repository's own unbroken
convention, under its own freshly-numbered decision -- would require first editing that dict, an
edit which itself trips a separate historical stage's frozen-scope guard, which would in turn need
its own acceptance, which would need its own decision, recursing without bound.

This record authorizes replacing that map with discovery driven entirely by repository data: the
set of `docs/decisions/*.md` files and their own anchored identity lines, so that landing a new,
reviewed decision file on canonical `main` is itself the act of registering it -- no shared
mechanism code is touched to make a future id knowable.

## 2. What is authorized

```text
Bounded, convention-based decision discovery over exactly docs/decisions/*.md -- non-recursive,
  repository-fixed, regular files only, symlinks excluded, no caller/PM/registry-supplied path
  ever reaches the filesystem.

Decision identity read from an anchored ^AT-D<n>: <status> line in the file's own text, never
  from the filename (AT-D11's own file, at-m2-authorization.md, already breaks any
  filename-based convention on purpose).

Removal of _DECISION_RECORD_PATHS and any equivalent enumeration of individual decision ids in
  Python -- no dict, list, match/case, if/elif chain, or id-specific regex.

Typed, per-decision, self-contained authority for every decision discovered after AT-D16:
  AUTHORIZES_IMPLEMENTATION and AUTHORIZES_ACCEPTANCE_MERGE are distinct fields and distinct
  authorization slots; a decision granting one never satisfies the other.

Generalized reviewed-changeset discovery: any decision discovered after AT-D16 may optionally
  carry its own REGISTERED_CHANGESET_* table, unioned with AT-D16's own AT_D16_CHANGESET_* table
  by milestone; a milestone registered by more than one decision, or twice within one decision,
  with disagreeing values receives no exemption from either -- never a union, never a pick.

Focused, adversarial governance tests proving the above, including synthetic future decisions
  registered through data only.
```

## 3. What is explicitly NOT authorized

```text
Acceptance or merge of AT-D16's implementation           NOT AUTHORIZED by this record
Acceptance or merge of THIS (AT-D17) implementation       NOT AUTHORIZED by this record --
                                                            requires its own future decision
Self-registration of either implementation as reviewed    NOT AUTHORIZED -- explicitly deferred,
  content                                                   see section 5
Production action                                          NOT AUTHORIZED -- unchanged
Production authorization                                   NOT GRANTED -- unchanged
M3.6B / real external LLM calls                             NOT AUTHORIZED -- unchanged
AT-M3.2 .. AT-M3.6A implementation                          NOT STARTED by this record
AT-M4                                                        NOT AUTHORIZED
PCP remediation                                              NOT AUTHORIZED by this record
```

## 4. Binding rules

```text
AT-D17-R01  AT-D16's own AT_D16_CHANGESET_* table (section 5 of that record) remains the sole,
            unmodified, canonical source for the AT-M2 and AT-M3.1 reviewed-changeset entries.
            This record adds nothing to that table and edits no line of AT-D16.

AT-D17-R02  AT-D16's own authority index (AT_D16_AUTHORITY_AT_D11/13/14/15) is frozen exactly as
            AT-D16 recorded it: a closed grandfather for those four ids only. It does not grow.
            No decision recorded after AT-D16, including this one, is ever added to it -- a
            decision recorded after AT-D16 carries its own typed authority fields instead.

AT-D17-R03  This record supersedes AT-D16-R08's clause naming AT-D16 "the sole canonical source
            ... of which decision authorizes which milestone" -- but ONLY for decisions recorded
            after AT-D16. AT-D16-R08 is not edited, is not falsified as a record of what AT-D16
            said, and remains the operative rule for the four grandfathered ids under R02. A later
            authorization supersedes an earlier position without rewriting the record of it, the
            same rule this repository already applies to AT-M1's `AT_M2: NOT AUTHORIZED` line and
            to AT-D11 relative to it.

AT-D17-R04  Decision identity is content, not filename. An id claimed by more than one file, or a
            single file claiming more than one distinct id, resolves to no authority for any id
            involved in that ambiguity. Every other, unambiguous id remains independently usable.

AT-D17-R05  A decision's typed authority slot (AUTHORIZES_IMPLEMENTATION or
            AUTHORIZES_ACCEPTANCE_MERGE) is checked by exact list membership against the field of
            that exact name. A decision's own prose is never searched for a milestone's name --
            the AT-D14-mentions-"AT-M2"-without-authorizing-it failure AT-D16-REMEDIATION-1 closed
            for the two existing milestones must never be able to recur for a future one.

AT-D17-R06  A reviewed-changeset entry a future decision registers is exempt only under the same
            controls AT-D16 already established and two rounds of validation already proved:
            exact value binding against the discovering decision's own table (no ancestry-plausible
            substitute), the PM snapshot mirroring those values exactly, real-commit and ancestry
            checks, and per-milestone conflict failing closed rather than unioning.

AT-D17-R07  Neither this implementation nor AT-D16's remains self-registered as reviewed content
            by this record. Until a separate, future Product Owner decision accepts one or both and
            registers its exact validated commit, historical and live governance guards may
            correctly continue to show `scripts/successor_lifecycle.py`'s own changes as
            unreviewed drift. That is fail-closed behavior working as designed, not a defect to be
            patched around with a path allowlist, a premature self-registration, or a reused
            decision id standing in for a real acceptance authority.
```

## 4a. Typed structured authority

```text
AUTHORIZES_IMPLEMENTATION: AT-GOV-DECISION-DISCOVERY-1
```

This is AT-D17's own typed authority declaration, in the shape every decision recorded after
AT-D16 must use (AT-D17-R05): implementation authorization for the milestone identity
`AT-GOV-DECISION-DISCOVERY-1` -- the bounded-discovery mechanism and typed-authority rework this
record covers -- and nothing else. This record carries no `AUTHORIZES_ACCEPTANCE_MERGE` field: it
grants implementation authority only, exactly as section 3 states.

## 5. Future acceptance is a separate decision

Exactly as AT-M2's implementation (AT-D11) and merge (AT-D13) were separate decisions, and AT-M3.1's
implementation (AT-D14) and acceptance/merge (AT-D15) were separate decisions, this record
authorizes implementation only. A future decision -- expected to be the next in sequence -- is
required before either AT-D16's or this record's own implementation may be registered as reviewed,
and must itself be discovered the same way every decision after AT-D16 now is: no edit to
`scripts/successor_lifecycle.py` to make it knowable.

## 6. What this decision does NOT do

```text
Does NOT amend AT-D11 through AT-D16
Does NOT move or reinterpret SUCCESSOR_AUTHORIZED_CHANGESET_END
Does NOT grow AT-D16's frozen authority index
Does NOT accept or merge this implementation, or AT-D16's
Does NOT register any content as reviewed
Does NOT authorize AT-M3.2 .. AT-M3.6A implementation to begin
Does NOT grant production authorization -- NOT GRANTED, unchanged
Does NOT retire, reduce or reclassify any PCP or governance debt
Does NOT relax TASK_ROLES, RBAC, policy or approval
```

## 7. Validation policy

```text
AT_D17_VALIDATION_ROUNDS_PERMITTED:   2
AT_D17_VALIDATION_ROUNDS_USED:        0
```

Bounded remediation policy applies: Validation 1 -> at most one remediation -> Validation 2, no
Validation 3. AT-D16's own, separate, closed Validation 1/2 cycle is not reopened by this record.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
