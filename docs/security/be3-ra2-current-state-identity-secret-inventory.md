# Step 66C.4-BE3-RA-2 — Current-State Identity and Secret Inventory

> **Inventory document only. Every classification below is derived from a directly inspected code
> path or committed configuration file at canonical main `c1db4cc`, never from a document title or
> a class/schema name. NO identity was created or modified, NO secret was read, written, or
> rotated, NO Vault/Kubernetes/IAM command was executed, NO deployment or activation occurred.
> `production_executed_true_count: 0`.**

## Reading rule applied throughout

A capability counts as present only when a **production code path** (`apps/` or `shared/sdk/`,
excluding `tests/`) actually performs it at runtime. Three distinctions are enforced everywhere:

```text
a defined dataclass field         != an authenticator that populates it
a declared configuration mode     != an implementation that serves that mode
a test-helper construction        != a runtime call site
a documented design (docs/*.md)   != a wired code path
```

`docs/security/` already contains an extensive family of identity/OIDC/break-glass design
documents. Those describe **planned** design. This inventory deliberately re-derives everything
from code, and where a document's title suggests a capability that the code does not implement,
the code classification wins and the divergence is called out.

---

## 5. Operator identity inventory

### 5.1 The two independent operator authentication surfaces

The platform has **two separate, unrelated operator authentication mechanisms**. They do not share
an identity, a session, a role source, or a trust model. Any operator identity decision must
account for both.

#### Surface A — BE3 / task operator APIs (header-asserted)

```text
Code path:      apps/orchestrator/src/task_api.py::_authenticate  (lines 62-78)
Used by:        task_api, workroom API, operations_resume_api (_operator, line 110-112),
                operations_replay_api (_operator, line 95)
Gate:           TASK_API_TEST_AUTH_ENABLED must be exactly "true"; unset/false -> 403 for every
                request (fail-closed, no non-test path exists)
Identity claim: X-Task-Actor request header, taken verbatim
Role claim:     X-Task-Role request header, checked only for membership in TASK_ROLES
Session:        NONE -- every request is independently header-authenticated; no session object,
                no login, no logout, no revocation
Verification:   none -- no signature, no token, no issuer, no expiry, no audience
```

The module's own docstring states it plainly: *"Fail-closed test-only auth
(TASK_API_TEST_AUTH_ENABLED + X-Task-Actor/X-Task-Role headers) stands in for a real
identity/session model -- documented gap."*

**Consequence (security-material):** on this surface the caller's **role is entirely
client-asserted**. Any client that can reach the API while `TASK_API_TEST_AUTH_ENABLED=true` may
declare `X-Task-Role: platform_admin` and be treated as a platform administrator. There is no
server-side binding between an actor id and the role it is permitted to claim. This is precisely
the "request-provided role" pattern that decision RA2-D03 is required to classify as
unacceptable — and it is the **current** state, not a hypothetical option.

#### Surface B — Admin Console operator actions (signed session)

```text
Code path:      apps/orchestrator/src/operator_actions_api.py (login line 157, logout line 195)
                shared/sdk/operator_actions/auth.py     (mode resolution)
                shared/sdk/operator_actions/session.py  (HMAC-SHA256 signed token)
                shared/sdk/operator_actions/csrf.py     (CSRF issue/verify)
                shared/sdk/operator_actions/rbac.py     (highest_role)
Gate:           ADMIN_CONSOLE_AUTH_MODE must be "test_local_signed_session" AND
                ADMIN_CONSOLE_TEST_AUTH_ENABLED true AND
                ADMIN_CONSOLE_PRODUCTION_AUTH_ENABLED false
Identity claim: TEST_OPERATOR_IDENTITY -- the fixed literal "operator-test" (auth.py line 21)
Session:        real signed session cookie "admin_console_session"; HttpOnly, SameSite=strict;
                DB stores only sha256(token); TTL 1800s (30 min); explicit logout endpoint
Verification:   HMAC-SHA256 signature + expiry, hmac.compare_digest, fail-closed on any decode error
```

This surface is materially stronger than Surface A: it has a real signed session, CSRF protection,
a confirmation nonce, idempotency, a policy gate, and an audited action catalog. But it
authenticates **exactly one hardcoded pseudo-identity** (`operator-test`). It cannot represent two
different humans, and it therefore cannot support separation of duties.

`AUTH_MODE_OIDC` is a *recognised* mode string, but `resolve_auth_config` enables operator actions
only under `AUTH_MODE_TEST_LOCAL` (auth.py lines 66-69). Setting mode to `oidc` yields
`operator_actions_enabled=False` — i.e. selecting the production mode currently **disables** the
console rather than authenticating anyone.

### 5.2 Session signing key handling

```text
Code path:  shared/sdk/operator_actions/session.py::_resolve_secret (lines 30-43)
Resolution: ADMIN_CONSOLE_SESSION_KEY_FILE -> ".runtime/admin-console-session-key" ->
            "/tmp/aiagents-admin-console-session-key" -> ephemeral secrets.token_bytes(32)
Rotation:   NONE -- a single active key, no previous-key overlap, no rotation window
Fallback:   an in-memory ephemeral key is generated silently when no key file exists
```

Two gaps follow directly. First, the default search path includes a shared-temp location, which is
not an acceptable key location for a shared multi-operator runtime. Second, and unlike the Policy
Authority capability (§7, which *does* implement a `_PREVIOUS` rotation slot), the session signing
key has **no dual-key overlap**, so any rotation invalidates every live session at once.

### 5.3 Per-entrypoint operator identity matrix

| Entrypoint | AuthN | Identity source | Role source | Session | CSRF | Revocation | Audit actor |
|---|---|---|---|---|---|---|---|
| Admin Console UI (`/admin`, static mount) | none itself | delegates to Surface B | — | cookie | n/a | via session revoke | `operator-test` |
| Admin Console operator actions | Surface B | fixed `operator-test` | `rbac.highest_role` | yes (30 min) | yes | yes (status active/expired/revoked) | fixed identity |
| Task API (`/tasks`) | Surface A | `X-Task-Actor` header | `X-Task-Role` header | none | none | none | header value |
| Workroom / clarification API | Surface A | `X-Task-Actor` header | `X-Task-Role` header | none | none | none | header value |
| Resume request API (`/operations/resume-requests`) | Surface A + gate | `X-Task-Actor` header | `X-Task-Role` header | none | none | none | header value |
| Resume authorize/reject | Policy Authority (§7) | server-configured principal id | fixed `policy_authority` label | none | none | rotate capability | principal id |
| Replay request API (`/operations/replay-requests`) | Surface A + gate | `X-Task-Actor` header | `X-Task-Role` header | none | none | none | header value |
| Production approval grant/revoke | **no endpoint exists** | — | — | — | — | — | — |
| Identity/secret/security posture APIs | read-only reporting | n/a | n/a | n/a | n/a | n/a | n/a |
| Migration CLI (`scripts/run_platform_migrations.py`) | none (operator-run) | OS user | n/a | n/a | n/a | n/a | not audited |

### 5.4 Mandatory answers required by §5

```text
Q: 目前是否存在正式 operator authenticator？
A: NO. Two mechanisms exist; both are explicitly test-gated. Surface A is header-asserted with no
   verification of any kind. Surface B is a genuine signed session but authenticates a single
   hardcoded pseudo-identity. Neither can establish who a real human operator is.

Q: 目前是否只相信 request payload/header？
A: For Surface A -- YES, entirely: both the actor id AND the role come from client-supplied
   headers, unverified. For Surface B -- NO: the session cookie is HMAC-verified server-side, but
   the identity it carries is a fixed constant rather than an authenticated human.

Q: 目前是否存在 Admin Console session？
A: YES, technically -- a real HMAC-signed, HttpOnly, SameSite=strict, 30-minute, revocable session
   with CSRF protection exists (Surface B). But it is reachable only in test_local mode and always
   carries the same fixed identity, so it provides session mechanics without identity assurance.

Q: 目前是否存在可驗證的人類 operator identity？
A: NO. No code path anywhere validates a human credential against any authority. There is no
   password check, no MFA, no token validation, no IdP call, no certificate check. The OIDC
   provider abstraction exists but every live operation raises OidcDisabledError (§8.2).
```

---

## 6. Service Identity inventory

### 6.1 Repo-wide call-site census (re-counted at `c1db4cc`)

```text
Search term: is_service_identity=True
  tests/     16 call sites
  apps/       0 call sites
  shared/     0 call sites
  scripts/    0 call sites

All references to is_service_identity in production code (apps/ + shared/), complete list:
  shared/sdk/tasks/authorization_policy.py:50   docstring text
  shared/sdk/tasks/authorization_policy.py:56   field declaration, default False
  shared/sdk/tasks/authorization_policy.py:106  policy CONSUMER -- `if actor.is_service_identity:`
```

**Divergence from RA-P noted:** the RA-P readiness plan recorded 12 test call sites; the count at
`c1db4cc` is **16**. The increase comes from test suites added in later BE3-R1/R2 stages. The
qualitative conclusion is unchanged and now re-verified independently: **zero production call
sites.**

### 6.2 What this means structurally

`authorization_policy.py:106` is a *decision* branch — it restricts a service identity to
consume-only actions. It is only reachable if some caller constructs an `Actor` with
`is_service_identity=True`. Every `Actor` construction in production code is:

```text
apps/orchestrator/src/operations_replay_api.py:95   Actor(principal_id=ctx.actor, role=ctx.role)
apps/orchestrator/src/operations_resume_api.py:112  Actor(principal_id=ctx.actor, role=ctx.role)
apps/orchestrator/src/operations_resume_api.py:175  Actor(..., is_policy_authority=True)
```

None sets `is_service_identity`. It therefore defaults to `False` on every production-constructed
Actor, which makes the service-identity branch of `authorization_policy.evaluate`
**unreachable in any production path today**.

### 6.3 Per-path record for the service-identity-dependent operations

```text
Path: authorized dead-event replay execution
  caller:              NONE -- replay_service.execute_authorized_replay (replay_service.py:431)
                       has zero production callers; the only apps/ mention is a docstring in
                       operations_replay_api.py:13 stating it is deliberately NOT exposed
  callee:              replay_service.execute_authorized_replay
  credential source:   none exists
  verification:        none exists
  expiration:          n/a          rotation: n/a          scope binding: n/a
  replay protection:   n/a          revocation: n/a
  audit identity:      would be actor.principal_id, but no authenticator produces one

Path: resume execution command preparation
  caller:              NONE -- resume_service.prepare_execution (resume_service.py:373) has zero
                       production callers; operations_resume_api.py:12 documents it as not exposed
  (all other fields: as above -- no credential, no verification, no rotation, no revocation)

Path: DESTINATION_ORCHESTRATOR_COMMAND outbox consumption
  consumer:            NONE anywhere in the repository (independently re-confirmed)
```

### 6.4 Required explicit statement

```text
Current state: NO REAL SERVICE IDENTITY AUTHENTICATOR EXISTS.

The authorization POLICY that would govern a service identity is implemented and well tested. The
AUTHENTICATOR that would resolve a real caller into that identity does not exist in any form --
not stubbed, not disabled-by-flag, not partially wired. This is a build-new-capability gap, not a
configuration gap.
```

No mTLS, SPIFFE/SPIRE, workload-identity, projected-token, signed-service-JWT, or client-credential
verification code exists anywhere in `apps/` or `shared/sdk/`.

---

## 7. Policy Authority inventory

### 7.1 Implemented mechanism (this one *is* real code)

```text
Code path: apps/orchestrator/src/operations_resume_api.py::_policy_authority (lines 158-175)
```

The mechanism is genuinely well built, and this inventory credits it as such:

```text
Principal identity:  X-Task-Actor must EXACTLY equal BE3_RESUME_POLICY_AUTHORITY_PRINCIPAL_ID
                     (_configured_policy_authority_principal, line 125-128). Unset -> "" -> can
                     never match (fail-closed).
Capability claim:    dedicated header X-Resume-Policy-Authority; never read from body, query
                     string, or the general X-Task-Role header
Credential form:     opaque shared-secret string compared with hmac.compare_digest (line 153) --
                     constant-time, never `==`
Dual-key rotation:   YES -- BE3_RESUME_POLICY_AUTHORITY_CAPABILITY plus
                     ..._CAPABILITY_PREVIOUS, both accepted during a rotation window
                     (_configured_capabilities, lines 131-141)
Length bound:        oversized (>256 char) or empty values rejected before any comparison
No short-circuit:    principal_ok and capability_ok are BOTH always evaluated (lines 171-173), so
                     failure timing cannot distinguish which check failed
Uniform failure:     every failure raises the identical 403 "policy_authority_required"
Non-echo:            the presented value is never logged, audited, or returned
Role handling:       resolved Actor carries the fixed label _POLICY_AUTHORITY_ROLE, never the
                     caller's own X-Task-Role; is_policy_authority=True restricts it in
                     authorization_policy.evaluate to authorize/reject only -- it can never
                     request, cancel, consume, or touch the production-approval gate
```

### 7.2 Required answers under §7

```text
Q: Policy Authority 目前如何證明 caller 身分？
A: By two co-required facts: (1) the actor id asserted in X-Task-Actor equals a server-configured
   principal id, and (2) a shared secret presented in a dedicated header matches a
   server-configured value in constant time. Note (1) inherits Surface A's weakness entirely --
   the actor id itself is an unverified client-supplied header, so the *only* real secret-bearing
   factor is (2).

Q: 是否只是 static shared secret？
A: Effectively yes -- a rotatable static shared secret. There is no issuer, no audience, no
   expiry, no signature over the request, and no binding to a workload.

Q: secret 從哪裡載入？
A: Directly from os.environ (lines 128, 138-140). It does NOT use the platform's own
   shared/sdk/secrets SecretProvider or SecretRef redaction wrapper -- operations_resume_api.py
   imports neither. The credential therefore lives in the raw process environment with no
   SecretRef protection against accidental repr/str/audit exposure.

Q: 是否有 dual-key rotation？
A: YES -- current + previous capability slots are both honoured, which is a genuinely good design
   and notably better than the Admin Console session key (§5.2), which has none.

Q: 是否支援 revocation？
A: Only coarsely -- clearing/replacing the env var revokes the capability, but this requires a
   configuration change and (for most delivery mechanisms) a process restart. There is no
   per-credential revocation list and no immediate propagation mechanism.

Q: credential 遺失時是否 fail closed？
A: YES. Unset principal id -> "" -> principal_ok False. Unset capabilities -> empty tuple ->
   _capability_matches returns False. Every failure path denies.

Q: request-controlled role 是否完全不可影響 authority？
A: YES -- confirmed by code. The resolved Actor's role is hardcoded to _POLICY_AUTHORITY_ROLE and
   authorization_policy.evaluate branches on is_policy_authority BEFORE any TASK_ROLES check.
   An operator cannot reach policy-authority powers by manipulating X-Task-Role. This specific
   escalation path is genuinely closed.
```

### 7.3 Provisioning state

```text
grep -rn "BE3_RESUME_POLICY_AUTHORITY" infra/   -> zero matches
```

No compose file, Helm values file, GitOps manifest, or secret-reference file sets any of the three
variables. The mechanism is therefore **unconditionally fail-closed in every environment that
exists today**, and no real automated policy/safety engine process exists that would present these
credentials. The `apps/policy-engine/` service is a separate component and is not wired to this
capability.

---

## 8. Secret backend inventory

Classification vocabulary is the one required by §8.

### 8.1 Backend-by-backend classification

```text
HashiCorp Vault -- DEV_ONLY
  Evidence: infra/docker-compose/docker-compose.yml lines 30-38 --
              image: hashicorp/vault:1.17
              command: server -dev
              VAULT_DEV_LISTEN_ADDRESS: 0.0.0.0:8200
              ports: 127.0.0.1:8200:8200
  `server -dev` means: in-memory storage, auto-unsealed, a well-known root token, all data lost on
  restart. This is a development convenience, NOT a production-grade Vault integration.
  infra/vault/ contains ONLY a .gitkeep -- there are zero Vault policies, roles, auth-method
  configurations, or templates in the repository.

Vault KV v2 client code -- IMPLEMENTED_NOT_ACTIVE
  Evidence: shared/sdk/secrets/provider.py::VaultKvSecretProvider (lines 169+, 207+) reads KV v2
  over HTTP using VAULT_ADDR + VAULT_TOKEN, wrapping the token in SecretRef so a stray repr/str
  renders ***REDACTED***. Real code, but: authenticates with a STATIC TOKEN (no AppRole, no
  Kubernetes auth, no workload identity), and is not the default provider.

Environment variables -- IMPLEMENTED_AND_ACTIVE (the de facto backend)
  Evidence: shared/sdk/secrets/provider.py::provider_from_env line 446 --
              choice = (snapshot.get("SECRET_PROVIDER") or "env").strip().lower()
  "env" is the DEFAULT. Every BE3 identity credential bypasses this abstraction entirely and reads
  os.environ directly (§7.2).

Mock-vault file provider -- DEV_ONLY
  Evidence: MockVaultSecretProvider reads a local JSON file generated by
  scripts/bootstrap_mock_vault_secrets.sh; infra/runtime/mock-vault-secrets.example.json is an
  EXAMPLE file only. Explicitly described in-code as intended for validation, and gitignored.

Kubernetes Secret -- ABSENT
  Evidence: no `kind: Secret` template exists in infra/kubernetes/charts/ai-agents-platform/.
  The chart renders ConfigMaps, Deployments, Services, NetworkPolicies, PVCs, ServiceAccounts and
  batch jobs -- but no Secret object.

Kubernetes ServiceAccount -- TEMPLATE_ONLY
  Evidence: infra/kubernetes/charts/.../templates/serviceaccounts.yaml. Per its own header:
  "automountServiceAccountToken defaults to false -- no Role/RoleBinding/ClusterRole is created
  here". Therefore NO projected service-account token is available to any workload, which means
  option A of RA2-D04 (projected OIDC tokens) has no substrate today.

Helm / Kubernetes as a running platform -- TEMPLATE_ONLY
  Evidence: infra/helm/ contains only .gitkeep. The chart exists and is referenced by
  infra/gitops/argocd/applications/dev.yaml, but the platform actually runs on Docker Compose;
  RA-P separately recorded that the internal test runtime has no kubectl/helm/kubeconfig.

External Secrets Operator / Secrets Store CSI -- ABSENT
  Evidence: no ExternalSecret or SecretProviderClass manifest anywhere in infra/.

GCP Secret Manager -- REFERENCED_NOT_IMPLEMENTED
  Evidence: exactly one occurrence repo-wide --
  shared/sdk/secrets_foundation/secret_ref.py:21 lists "gcp_secret_manager_ref" as a permitted
  reference TYPE in a schema. No client, no API call, no configuration.

Secret reference/metadata foundation -- IMPLEMENTED_AND_ACTIVE (as documentation-of-record)
  Evidence: infra/secrets/*.yaml (16 files: inventory, classification, ownership catalog, rotation
  model, lifecycle model, access boundary, audit model, redaction policy, usage mapping, plus
  per-domain reference files). These are reference/metadata models. They contain secret NAMES and
  policy statements -- correctly, no secret values. They describe intended handling; they do not
  themselves deliver any secret.

GitHub Actions secrets -- REFERENCED_NOT_IMPLEMENTED for runtime purposes
  Relevant to CI only; not a runtime credential-delivery path for BE3.
```

### 8.2 OIDC implementation status (checked because many `docs/security/oidc-*.md` files exist)

```text
shared/sdk/identity/ -- 803 lines across 10 modules, all of them config validation, policy
  evaluation, redaction, role-mapping models, and session-cleanup planning.

shared/sdk/identity/oidc_provider.py -- INTERFACE ONLY. Verbatim from the module:
  "Every operation that would require an external IdP -- discovery, JWKS fetch,
   authorization-code exchange, ID-token validation -- raises OidcDisabledError in this step.
   There is NO concrete provider that talks to a network."
  fetch_discovery / fetch_jwks / exchange_code / validate_id_token -- each raises
  OidcDisabledError unconditionally (lines 35-45).

Wiring check: the only production importers of shared.sdk.identity are
  shared/sdk/identity_posture/redaction.py   (uses find_secret_like for redaction)
  shared/sdk/secrets_foundation/secret_redaction.py (same)
NO request-authentication path imports it. identity_posture_api.py is a read-only POSTURE
REPORTING surface ("NO login/callback/authorize/token/logout, NO role-mapping mutation").
```

**Conclusion:** the OIDC design corpus is thorough and the fail-closed validators are real, but
there is **no OIDC authentication capability** in the running system.

### 8.3 Required distinctions restated

```text
Vault dev mode (`server -dev`, in-memory, auto-unseal, root token)
  IS NOT
production-grade Vault integration (persistent storage, sealed, auth methods, policies, audit
  device, HA) -- of which the repository contains none.

Kubernetes ServiceAccount template (automount disabled, no RoleBinding)
  IS NOT
workload identity or secret rotation -- there is no projected token, no IdP trust relationship,
  and no rotation mechanism of any kind.
```

---

## 9. Consolidated current-state summary

```text
Operator authentication (human):        NOT_IMPLEMENTED for production (two test-gated surfaces)
Operator role/scope source:             CLIENT-ASSERTED HEADER on the BE3 surface (unacceptable
                                        pattern, present today)
Operator session:                       IMPLEMENTED_NOT_ACTIVE (real mechanics, fixed identity,
                                        test-local mode only, no key rotation)
Service Identity authenticator:         NOT_IMPLEMENTED (0 production call sites; policy branch
                                        unreachable in production)
Policy Authority authentication:        IMPLEMENTED_NOT_ACTIVE (strong mechanism, rotatable,
                                        fail-closed; configured in NO environment; bypasses the
                                        secrets SDK and reads os.environ directly)
Production approval grant path:         NOT_IMPLEMENTED (service functions exist, zero callers,
                                        no endpoint)
Resume/replay execution callers:        NOT_IMPLEMENTED (zero production callers)
Secret backend (effective):             ENVIRONMENT VARIABLES (default provider "env")
Secret backend (aspirational, coded):   Vault KV v2 via static token -- IMPLEMENTED_NOT_ACTIVE
Secret backend (dev):                   Vault server -dev, mock-vault JSON file
Kubernetes/Helm/CSI/External Secrets:   TEMPLATE_ONLY or ABSENT
GCP Secret Manager:                     REFERENCED_NOT_IMPLEMENTED (one schema string)
Runtime credential provisioning:        NONE -- no provisioning workflow, owner, or automation
                                        exists for any BE3 identity or credential
```

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
