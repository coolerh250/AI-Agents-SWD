# Step 66C.4-BE3-RA-2 — Identity and Secret Current State, 2026-08-04

> **Current-state addendum. It does not modify or replace the RA-2 planning evidence, which remains
> valid as the record of state at analysis time. No identity created, no secret read or written, no
> OIDC integration, no Vault deployment or configuration, no Kubernetes environment created, no
> credential provisioned, no runtime/backend/frontend change, no migration, no deployment, no
> feature-gate activation, no resume or replay execution.
> `production_executed_true_count: 0`.**

```text
Canonical main baseline:
44ab32c

Planning source:
efa396d   (planning/66c4-be3-ra2-identity-secret-decision)

Binding decision record:
docs/contracts/66c4-reminder-expiry-controlled-resume/step66c4-be3-ra2-binding-decisions.md

RA-2 decision package:
CANONICALIZED IN THIS PR
```

## 1. What changed

The Product Owner resolved RA2-D01 through RA2-D12 and accepted the six binding security conditions
RA2-C01 through RA2-C06 on 2026-08-04. Nothing else changed: no code, configuration, environment,
credential, or runtime state. Every technical finding in the RA-2 inventory and threat analysis is
still current.

```text
RA2_PLANNING:           COMPLETE
RA2_DECISIONS:          RESOLVED / BINDING
RA2_CANONICALIZATION:   PREPARED FOR MERGE
RA2_IMPLEMENTATION:     NOT STARTED / NOT AUTHORIZED
```

## 2. Current technical state — nothing is implemented

Each line below was code-verified during RA-2 and is unchanged by the decisions.

```text
Operator production authentication:
NOT IMPLEMENTED
  apps/orchestrator/src/task_api.py::_authenticate reads both the actor identifier and the role
  verbatim from client headers; the role is validated only for membership in the known set. A
  caller can self-declare an administrative role. D01/D02/D03 decide the replacement; none is built.

Service Identity production authentication:
NOT IMPLEMENTED
  is_service_identity=True appears at 16 test-only call sites and 0 production sites, so the
  service-identity policy branch is unreachable in production. D04 decides the mechanism.

Policy Authority workload OIDC:
NOT IMPLEMENTED
  The existing mechanism is capability-confined and dual-key rotatable, but it is a long-lived
  bearer secret read directly from the process environment, and it is configured in no environment.
  D05 makes it local/test only and selects projected workload OIDC for shared runtime.

Authoritative non-dev Vault:
NOT DEPLOYED
  SECRET_PROVIDER defaults to "env"; Vault runs only as `server -dev`; infra/vault/ contains only a
  .gitkeep. D06 selects non-dev Vault with Kubernetes workload identity.

Shared secret delivery:
NOT IMPLEMENTED
  No kind: Secret template exists; ServiceAccounts are template-only with automount disabled.
  D07 selects read-only file delivery via SecretRef; Vault Agent versus CSI stays open for RA-2I4P.

OIDC integration:
NOT IMPLEMENTED
  oidc_provider.py is interface-only; every live operation raises OidcDisabledError.

Dedicated non-production Kubernetes environment:
NOT PROVISIONED
  D11 selects an isolated non-production namespace/environment; none exists.

Resume/replay execution:
DISABLED
  All four BE3 gates default false. RA2-C05 forbids execution before RA-2R.

RA-2R:
NOT STARTED

production_executed_true_count:
0
```

`grant_production_approval`, `execute_authorized_replay` and `prepare_execution` still have zero
production callers.

## 3. Threat posture

The RA-2 threat and trust analysis registered 20 threats — 3 CRITICAL, 11 HIGH, 6 MEDIUM — and
explicitly disclaimed Zero Trust. The binding decisions choose the architecture intended to address
them; **none of the threats is mitigated yet**, because nothing has been implemented. The register
stays open and is the input to RA-2R.

## 4. Decision status versus implementation status

```text
Decisions resolved:      12 of 12 (RA2-D01 .. RA2-D12)
Binding conditions:      6 of 6   (RA2-C01 .. RA2-C06)
Architecture choices still open: 1 -- Vault Agent versus CSI, assigned to RA-2I4P (not a Product
                                     Owner decision)
Implementation stages authorized: 0 of 11
Threats mitigated:       0
Environments provisioned: 0
Credentials provisioned:  0
```

## 5. Authorization state

```text
RA-2I0:   NOT AUTHORIZED     RA-2I3:  NOT AUTHORIZED     RA-2I6:  NOT AUTHORIZED
RA-2I4P:  NOT AUTHORIZED     RA-2I2:  NOT AUTHORIZED     RA-2R:   NOT AUTHORIZED
RA-2I4A:  NOT AUTHORIZED     RA-2I5:  NOT AUTHORIZED     RA-3:    NOT AUTHORIZED
RA-2I4B:  NOT AUTHORIZED

RA-2 implementation:  NOT STARTED / NOT AUTHORIZED
Deployment:           none
Shared migration:     none applied
Runtime action:       none
Secret access:        none
External action:      none
BE3 feature gates:    all four unchanged, default false
```

## 6. Known defect in an imported planning index

`docs/alignment/66-project-completion/master/next-executable-stage-sequence.md` is imported
unchanged from `efa396d` and states that the RA-2 stage ran "79 tests passed". That figure is
wrong. The authoritative count is **100 passed / 0 skipped / 0 failed**, recorded in
`docs/test/step66c4-be3-ra2-identity-secret-decision-evidence.md` and re-derived in this stage by
running `tests/test_step66c4_be3_ra2_identity_secret_decision.py`, which reports 100 passed.

The index file was left unchanged deliberately: it is historical planning evidence, and this stage
does not rewrite history to correct it. The correction belongs in this higher-precedence
current-state record. That file's RA-2 paragraph also records the decisions as `PENDING`, which was
true when written and is superseded by the binding decision record.

## 7. Source-of-truth precedence for RA-2

```text
1. Product Owner binding decisions
   docs/contracts/66c4-reminder-expiry-controlled-resume/step66c4-be3-ra2-binding-decisions.md
2. Current RA-2 canonical state addendum
   this document
3. RA-2 binding decision record's implementation sequence
4. Historical RA-2 planning evidence
   the inventory, threat analysis, decision package, stage decomposition and evidence record
5. Partner recommendations
6. Conversation summaries -- never authoritative
```

A planning recommendation is never an implementation authorization.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
