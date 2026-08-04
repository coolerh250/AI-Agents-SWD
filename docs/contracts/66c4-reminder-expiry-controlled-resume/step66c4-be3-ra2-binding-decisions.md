# Step 66C.4-BE3-RA-2 — Identity and Secret Binding Decisions

> **Product Owner binding decision record. It records decisions the Product Owner made and formally
> accepted. It does NOT authorize implementation. No identity was created, no secret read or
> written, no OIDC integration performed, no Vault deployed or configured, no Kubernetes
> environment created, no credential provisioned, no runtime/backend/frontend change made, no
> migration applied, no deployment performed, no feature gate activated, no resume or replay
> executed. `production_executed_true_count: 0`.**

```text
DOCUMENT_STATUS:
CANONICAL / BINDING

DECISION_AUTHORITY:
Product Owner

DECISION_DATE:
2026-08-04

RECORDED_BY:
Claude Code (Step 66C.4-BE3-RA-2M1), acting as recorder only

CANONICAL_CONTEXT:
main 44ab32c   (Step 66SYNC.1 PASS / CLOSED / CANONICALIZED)

PLANNING_SOURCE_COMMIT:
efa396dee6512d6f15b3fd079df87d2c70ee0c77
(planning/66c4-be3-ra2-identity-secret-decision)

RA2_D01_D12:
RESOLVED / BINDING

RA2_C01_C06:
RESOLVED / BINDING

RA2_IMPLEMENTATION:
NOT STARTED / NOT AUTHORIZED
```

## Relationship to the RA-2 planning evidence

The RA-2 current-state inventory, threat and trust analysis, decision package and implementation
stage decomposition were produced while every decision was still open. Those documents record
`PENDING` and `PRODUCT_OWNER_DECISION_REQUIRED`, and `Decided by Claude Code: 0`. That was true when
written, and they are imported unchanged. The Product Owner accepted the decisions **after** that
planning work completed, on 2026-08-04, and only this record makes those selections canonical.

Where this record and a planning document disagree about decision status, this record governs; the
planning document remains valid as the record of state at analysis time. The option analysis these
decisions were made against is
`docs/contracts/66c4-reminder-expiry-controlled-resume/be3-ra2-identity-secret-provisioning-decision-package.md`.

---

## RA2-D01 — Human operator identity source

```text
STATUS:    RESOLVED / BINDING
SELECTION: Enterprise OIDC using the existing enterprise Identity Provider.
```

```text
D01-R1  Human operator identity comes from the existing enterprise Identity Provider via OIDC.
D01-R2  No specific vendor, tenant, or production issuer is selected at this stage.
D01-R3  Selecting the concrete issuer is deferred to the implementation stage that needs it and
        requires its own Product Owner authorization.
```

Observed state this replaces: no verifiable human operator identity exists. `task_api.py::_authenticate`
takes both the actor identifier and the role verbatim from client-supplied headers, so a caller can
self-declare an administrative role.

---

## RA2-D02 — Operator session and API authentication

```text
STATUS:    RESOLVED / BINDING
SELECTION: OIDC Authorization Code Flow with PKCE, plus a backend-managed server-side session.
```

Prohibited:

```text
browser-stored bearer token
client-asserted authenticated user
request-header identity
```

```text
D02-R1  Operator authentication uses Authorization Code Flow with PKCE.
D02-R2  The session is server-side and backend-managed.
D02-R3  No token may be stored in the browser as the authentication credential.
D02-R4  No request header may assert who the authenticated user is.
```

---

## RA2-D03 — Operator role and scope source (authorization source of truth)

```text
STATUS:    RESOLVED / BINDING
SELECTION: Platform-owned RBAC is the authorization source of truth.
```

The Identity Provider may supply only:

```text
identity
provisioning input
group / claim input
```

```text
D03-R1  Platform-owned RBAC decides authorization.
D03-R2  An IdP claim is never, by itself, a platform authorization.
D03-R3  IdP groups and claims may feed provisioning, not entitlement evaluation.
```

---

## RA2-D04 — Service Identity mechanism

```text
STATUS:    RESOLVED / BINDING
SELECTION: Kubernetes projected ServiceAccount OIDC for the first shared activation environment.

SPIFFE / SPIRE:
DEFERRED
```

```text
D04-R1  Workload identity uses projected ServiceAccount OIDC tokens.
D04-R2  No static shared service credential may act as a shared runtime identity.
D04-R3  SPIFFE/SPIRE is deferred, not rejected, and would need its own decision.
```

Observed state this replaces: no Service Identity authenticator exists. `is_service_identity=True`
appears at 16 test-only call sites and zero production sites, leaving the service-identity policy
branch unreachable in production.

---

## RA2-D05 — Policy Authority authentication

```text
STATUS:    RESOLVED / BINDING
SELECTION: Policy Authority uses the same projected workload OIDC model.

Existing HMAC mechanism:
LOCAL / TEST ONLY -- DISABLED IN SHARED RUNTIME
```

```text
D05-R1  Policy Authority authenticates with projected workload OIDC in shared runtime.
D05-R2  The existing HMAC mechanism is permitted for local and test use only.
D05-R3  A long-lived HMAC bearer secret must never be the primary identity mechanism in shared
        runtime.
```

The existing mechanism is capability-confined and dual-key rotatable, but it is a long-lived bearer
secret read directly from the process environment, and it is configured in no environment today.

---

## RA2-D06 — Secret backend

```text
STATUS:    RESOLVED / BINDING
SELECTION: HashiCorp Vault, non-dev, as the authoritative secret backend for the first shared
           environment.

Vault authentication:
Kubernetes workload identity

GCP Secret Manager:
DEFERRED
```

```text
D06-R1  Vault in non-dev mode is the authoritative secret backend.
D06-R2  Vault authenticates workloads via Kubernetes workload identity.
D06-R3  Exactly one authoritative secret backend per environment (see RA2-C01).
D06-R4  GCP Secret Manager is deferred, not rejected.
```

Observed state this replaces: the effective secret backend is environment variables
(`SECRET_PROVIDER` defaults to `"env"`); Vault runs only as `server -dev`; `infra/vault/` holds only
a `.gitkeep`; no `kind: Secret` template exists.

---

## RA2-D07 — Secret delivery mechanism

```text
STATUS:    RESOLVED / BINDING AT ARCHITECTURAL BOUNDARY
SELECTION: Read-only file delivery through the SecretRef abstraction, using Vault Agent or CSI.
```

Prohibited:

```text
shared runtime environment-variable secret delivery
```

```text
D07-R1  Secrets reach workloads as read-only files through the SecretRef abstraction.
D07-R2  Environment-variable secret delivery is prohibited in shared runtime.
D07-R3  **Vault Agent versus CSI is NOT selected.** That choice is deferred to RA-2I4P
        (non-production Kubernetes and Vault readiness planning) and must not be made in RA-2M.
```

This is the one architecture choice inside the RA-2 decision set that remains open. It is not an
open *Product Owner* decision — it is an implementation-planning choice assigned to a named future
stage.

---

## RA2-D08 — Provisioning owner and workflow

```text
STATUS:    RESOLVED / BINDING
SELECTION: GitOps-controlled provisioning, with Platform Security approval, Enterprise IAM
           ownership of IdP configuration, and two-person approval for privileged access.
```

```text
D08-R1  Identity and secret provisioning is GitOps-controlled.
D08-R2  Platform Security approves provisioning changes.
D08-R3  Enterprise IAM owns Identity Provider configuration.
D08-R4  Privileged access requires two-person approval.
D08-R5  No single runtime agent may create a privileged identity or a secret policy by itself.
```

---

## RA2-D09 — Rotation and revocation (credential lifecycle)

```text
STATUS:    RESOLVED / BINDING
SELECTION: Credential-specific lifecycle controls.
```

At minimum:

```text
short TTL
renewal
bounded overlap
session invalidation
workload disablement
Vault lease revocation
```

```text
D09-R1  Each credential type has its own lifecycle controls.
D09-R2  A single generic rotation policy may not stand in for per-type controls.
D09-R3  Revocation must be effective, not merely scheduled: session invalidation, workload
        disablement and Vault lease revocation are required capabilities.
```

---

## RA2-D10 — Break-glass identity

```text
STATUS:    RESOLVED / BINDING
SELECTION: Dedicated human break-glass identity.
```

Required:

```text
hardware MFA
time-limited access
incident record
explicit audit trail
```

Prohibited:

```text
production approval bypass
anonymous emergency identity
shared break-glass account
```

```text
D10-R1  Break-glass is a dedicated, named human identity.
D10-R2  Hardware MFA is required.
D10-R3  Access is time-limited and tied to an incident record with an explicit audit trail.
D10-R4  Break-glass never bypasses production approval.
```

---

## RA2-D11 — First runtime-validation environment

```text
STATUS:    RESOLVED / BINDING
SELECTION: A dedicated, isolated non-production Kubernetes namespace/environment.
```

```text
D11-R1  The first identity and secret validation environment is non-production and isolated.
D11-R2  Production must not serve as the first validation environment.
```

---

## RA2-D12 — Initial activation identity boundary

```text
STATUS:    RESOLVED / BINDING
SELECTION: Phased validation is allowed. Activation is not allowed until the complete chain is
           validated.
```

The complete chain:

```text
Operator Identity
  -> Platform RBAC
    -> Policy Authority
      -> Service Identity
        -> Audit
```

```text
D12-R1  Phased validation of individual components is permitted.
D12-R2  Activation requires the entire chain above to be validated end to end.
D12-R3  API-only validation, or validation of a single component, is not activation and must not
        be described as activation.
```

---

## Additional binding security conditions

```text
RA2-C01  Each environment may have exactly one authoritative secret backend.

RA2-C02  A request-provided actor or role is never an authorization identity and never an
         authoritative audit identity.

RA2-C03  Shared runtime must not use a static shared Service Identity secret.

RA2-C04  Shared runtime must not use Vault dev mode, a root token, or a static Vault token as
         workload authentication.

RA2-C05  BE3 resume and replay execution must not run until the RA-2R combined independent
         security review is complete.

RA2-C06  Every implementation stage requires separate Product Owner authorization.
```

## Deferred decisions

```text
Vault Agent versus CSI secret delivery
  -> deferred by D07-R3 to RA-2I4P. Not a Product Owner decision; an implementation-planning
     choice assigned to a named stage.

SPIFFE / SPIRE workload identity
  -> deferred by D04-R3. Would require its own decision.

GCP Secret Manager as secret backend
  -> deferred by D06-R4. Constrained by RA2-C01 (one authoritative backend per environment).

Concrete IdP vendor, tenant and production issuer
  -> deferred by D01-R2 / D01-R3 to the implementation stage that needs it.
```

## Prohibited implications

None of the following is true, and none may be inferred from this record:

```text
RA-2 decisions are already on main                    -- FALSE (this record is on a PR branch)
OIDC is implemented                                   -- FALSE
Vault is deployed                                     -- FALSE
Service Identity is active                            -- FALSE
Policy Authority workload identity is active          -- FALSE
A shared environment is ready                         -- FALSE
Resume/replay is enabled                              -- FALSE
Any implementation stage is authorized                -- FALSE
The existing HMAC mechanism is approved for shared runtime -- FALSE
Vault Agent or CSI has been chosen                    -- FALSE
```

## Implementation sequence

Recorded as an **APPROVED EXECUTION SEQUENCE**, which is **NOT IMPLEMENTATION AUTHORIZATION**.

```text
RA-2M
  -> RA-2I0
    -> RA-2I4P
      -> RA-2I4A
        -> RA-2I4B
          -> RA-2I1
            -> RA-2I3
              -> RA-2I2
                -> RA-2I5
                  -> RA-2I6
                    -> RA-2R
                      -> RA-3
```

```text
RA-2I0   Backend-independent authentication and secret hardening. Decision-independent.
         Expected scope: Policy Authority credential via SecretRef; no ephemeral fallback for the
         shared runtime session key; a test/shared authentication interlock; actor and role headers
         fail closed in shared runtime.

RA-2I4P  Non-production Kubernetes and Vault readiness plan. Must decide: dedicated namespace or
         cluster boundary; Vault location, HA, storage, TLS, seal and backup; the Kubernetes auth
         mount; ServiceAccounts; NetworkPolicy; GitOps ownership; and Vault Agent versus CSI.

RA-2I4A  Secret and workload identity templates and code, with no shared deployment.

RA-2I4B  Isolated non-production provisioning. CRITICAL STAGE -- requires its own separate
         authorization.

RA-2I1   Operator OIDC and platform RBAC.

RA-2I3   Policy Authority workload OIDC.

RA-2I2   Service Identity authenticator. Must follow RA-2I3.

RA-2I5   Credential lifecycle and break-glass controls.

RA-2I6   Identity audit and Admin visibility.

RA-2R    Combined independent security review. BE3 resume/replay execution must not begin before
         RA-2R passes (RA2-C05).

RA-3     Follows RA-2R.
```

This sequence supersedes the stage decomposition proposed in
`docs/handoffs/66c4-reminder-expiry-controlled-resume/be3-ra2-implementation-stage-decomposition.md`
in one respect: the proposal's single `RA-2I4` stage is split into `RA-2I4P` (readiness planning),
`RA-2I4A` (templates and code, no deployment) and `RA-2I4B` (isolated non-production provisioning).
The proposal document is imported unchanged and remains the analysis behind the sequence.

## Implementation authorization status

```text
RA2_PLANNING:           COMPLETE
RA2_DECISIONS:          RESOLVED / BINDING
RA2_CANONICALIZATION:   PREPARED FOR MERGE
RA2_IMPLEMENTATION:     NOT STARTED / NOT AUTHORIZED

RA2I0:    NOT AUTHORIZED
RA2I4P:   NOT AUTHORIZED
RA2I4A:   NOT AUTHORIZED
RA2I4B:   NOT AUTHORIZED
RA2I1:    NOT AUTHORIZED
RA2I3:    NOT AUTHORIZED
RA2I2:    NOT AUTHORIZED
RA2I5:    NOT AUTHORIZED
RA2I6:    NOT AUTHORIZED
RA2R:     NOT AUTHORIZED
RA3:      NOT AUTHORIZED

BE3_RESUME_REPLAY:              DISABLED
PRODUCTION_EXECUTED_TRUE_COUNT: 0
```

## Activation boundary

```text
Phased validation:  ALLOWED
Activation:         NOT ALLOWED until Operator Identity -> Platform RBAC -> Policy Authority
                    -> Service Identity -> Audit is validated end to end (D12).
Resume/replay:      NOT ALLOWED until RA-2R passes (RA2-C05).
```

A complete decision set is not an implementation plan and is not an activation. Deciding *what* the
identity and secret architecture will be does not authorize building it, provisioning it, or turning
it on.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
