# AT-D16 — multi-milestone live-guard changeset registry

> **Product Owner decision record. Generalizes the live-guard reviewed-content exemption from a
> single AT-M2-only changeset into a multi-milestone registry, and registers AT-M2's and AT-M3.1's
> own already-reviewed content as its first two entries. Authorizes no production action, no
> external action, no AT-M3.2 implementation start and no PCP remediation.
> `production_executed_true_count: 0`.**

```text
AT-D16:                      RESOLVED / BINDING
Recorded_on:                 2026-08-24
Recorded_by:                 Product Owner
Canonical_main_at_decision:  5a04ec1c67453c4d90b525e94402b9515fbec0bf
Depends_on:                  AT-D11 (docs/decisions/at-m2-authorization.md),
                              AT-D12 (docs/decisions/at-d12-successor-freeze-amendment.md),
                              AT-D13 (docs/decisions/at-d13-at-m2-merge-authorization.md),
                              AT-D14 (docs/decisions/at-d14-at-m3-live-reasoning-authorization.md),
                              AT-D15 (docs/decisions/at-d15-at-m3-1-acceptance-and-merge-authorization.md)
```

## 1. What this record is for

`docs/governance/AI_AGENTS_PM_STATE.md` section 8 records `HAZARD_AT_M3_LIVE_DENYLIST: OPEN /
DISPOSITION REQUIRED`: `scripts/successor_lifecycle.py`'s live guard
(`live_guard_changed_paths`) recognises only one reviewed changeset,
`SUCCESSOR_AUTHORIZED_CHANGESET_END`, scoped by its own field documentation to AT-M2 specifically.
AT-M3.1 is the first later milestone to add genuinely new, AT-D14/AT-D15-authorized,
Validation-1/2-passed content under the same protected paths (`shared/`, `migrations/`), and the
single-value mechanism cannot recognise it as reviewed — reproduced directly:
`test_live_guard_does_not_misfire_on_at_m2s_own_authorized_work` (which the mechanism's own
AT-D12 test suite already carries) fails on current `main`, listing AT-M3.1's own
`shared/sdk/agent_reasoning/*` and `migrations/037_*` files as unexplained offenders.

This record is the disposition the hazard note asks for — analogous to what AT-D12 did for the
historical-freeze conflict at AT-M2's own transition — naming a general mechanism rather than a
one-off relaxation, exactly as AT-D11 required for the "no implementation" guards it closed.

## 2. What is authorized

```text
Generalize the live-guard reviewed-content exemption from one scalar changeset end into an
ordered, additive, per-milestone registry.

Register, as the registry's first two entries, content already authorized and validated by prior
binding decisions -- no new implementation content is authorized by this record:

  AT-M2    authorization AT-D11, merge/acceptance AT-D13,
           implementation_end 9c002e06029a682f586013671e8cb30ed1a475f4 (unchanged from the
           existing SUCCESSOR_AUTHORIZED_CHANGESET_END scalar)

  AT-M3.1  authorization AT-D14, merge/acceptance AT-D15,
           implementation_end 1ba197a91867e77a9fa2256289b2766317b51b41 (the Validated_candidate
           tip AT-D15 names, not a later docs/bookkeeping commit)

Update scripts/successor_lifecycle.py's live-guard exemption logic to consult the registry.

Add the governance records and tests needed to prove the model.
```

## 3. What is NOT authorized

```text
Production action                 NOT AUTHORIZED -- unchanged, no path to one is added
Production authorization          NOT GRANTED -- unchanged
M3.6B / real external LLM calls   NOT AUTHORIZED -- unchanged from AT-D14/AT-D15
External model credentials        NOT AUTHORIZED
AT-M3.2 .. AT-M3.6A implementation  NOT STARTED by this record -- AT-D14 already authorizes their
                                     eventual implementation; this record neither grants nor
                                     withholds that authority and does not itself clear them to
                                     begin -- see AI_AGENTS_PM_STATE.md section 2/5a for that gate
AT-M4                              NOT AUTHORIZED
PCP remediation                    NOT AUTHORIZED by this record
Blanket path allowlists            NOT AUTHORIZED -- exemption stays per-path, per-content-hash,
                                     never by path membership alone
Weakening any HEAD-relative guard  NOT AUTHORIZED -- live_guard_changed_paths keeps diffing to
                                     current HEAD; no successor boundary ever replaces HEAD as the
                                     scan endpoint
```

## 4. Binding rules

```text
AT-D16-R01  The live-guard reviewed-content registry is additive only. Adding a later milestone's
            entry never edits, removes, or reinterprets an earlier entry. AT-M2's
            SUCCESSOR_AUTHORIZED_CHANGESET_END scalar stays exactly where AT-D13 left it and is
            preserved as AT-M2-only compatibility provenance -- not deleted, not moved, not
            reinterpreted as "latest milestone".

AT-D16-R02  Each registry entry validates independently and fails closed on its own: a missing or
            malformed entry is ignored, never substituted with a wider exemption, and never
            invalidates or widens any other entry.

AT-D16-R03  Exemption is by CONTENT VERSION, not by path. A path is exempt only where its blob at
            current HEAD is byte-identical to its blob at a validated entry's implementation_end.
            A further, later edit to a path a registry entry already covers is a new divergence
            and is caught on its own merits, exactly as before this record.

AT-D16-R04  live_guard_changed_paths keeps scanning baseline..HEAD, always current HEAD. No
            registry entry, present or future, ever caps or replaces that endpoint.

AT-D16-R05  An entry's implementation_end names the last commit whose implementation content was
            itself reviewed/validated -- never a later docs-only or merge-bookkeeping commit.
            Reconciliation commits after that point, on either milestone, never move the entry and
            require no registry update.

AT-D16-R06  This record does not reinterpret or rewrite AT-D11 through AT-D15. Their authorization,
            merge and acceptance scopes stand exactly as recorded.

AT-D16-R07  An unrecognised future milestone (e.g. AT-M3.2 and beyond) has no registry entry under
            this record and therefore no exemption. Adding its entry, when the time comes, needs
            only its own already-required implementation/validation/acceptance decisions to exist
            and be RESOLVED / BINDING -- consistent with this being a mechanical generalization,
            not a new authorization -- but recording it is still a bookkeeping act this record does
            not perform in advance.
```

## 5. Registry entries authorized by this record

```text
AUTHORIZED_CHANGESET_REGISTRY: 2

AUTHORIZED_CHANGESET_1_MILESTONE:            AT-M2
AUTHORIZED_CHANGESET_1_AUTHORIZATION_ID:     AT-D11
AUTHORIZED_CHANGESET_1_MERGE_ID:             AT-D13
AUTHORIZED_CHANGESET_1_BASELINE:             192ebb74ba600f7a53ddf5967a7254a1f7a72fb8
AUTHORIZED_CHANGESET_1_IMPLEMENTATION_END:   9c002e06029a682f586013671e8cb30ed1a475f4

AUTHORIZED_CHANGESET_2_MILESTONE:            AT-M3.1
AUTHORIZED_CHANGESET_2_AUTHORIZATION_ID:     AT-D14
AUTHORIZED_CHANGESET_2_MERGE_ID:             AT-D15
AUTHORIZED_CHANGESET_2_BASELINE:             44cdd6f14333915932428d190b0a3e117d033b6d
AUTHORIZED_CHANGESET_2_IMPLEMENTATION_END:   1ba197a91867e77a9fa2256289b2766317b51b41
```

The canonical, machine-read copy of this table lives in `docs/governance/AI_AGENTS_PM_STATE.md`
section 5b; this copy is the decision-record evidence of what was authorized and must match it.

## 6. What this decision does NOT do

```text
Does NOT amend AT-D11, AT-D12, AT-D13, AT-D14 or AT-D15
Does NOT move or reinterpret SUCCESSOR_AUTHORIZED_CHANGESET_END
Does NOT authorize AT-M3.2 .. AT-M3.6A implementation to begin -- that gate is unaffected by this
   record; see AI_AGENTS_PM_STATE.md section 2
Does NOT grant production authorization -- NOT GRANTED, unchanged
Does NOT retire, reduce or reclassify any PCP or governance debt
Does NOT authorize any blanket path exemption
Does NOT relax TASK_ROLES, RBAC, policy or approval
```

## 7. Validation policy

```text
AT_D16_VALIDATION_ROUNDS_PERMITTED:   2
AT_D16_VALIDATION_ROUNDS_USED:        0
```

Bounded remediation policy applies: Validation 1 -> at most one remediation -> Validation 2, no
Validation 3. AT-M3.2 stays paused until this governance implementation is validated.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
