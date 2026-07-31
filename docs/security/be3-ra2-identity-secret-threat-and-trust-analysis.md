# Step 66C.4-BE3-RA-2 — Identity and Secret Threat and Trust Analysis

> **Analysis document only. Derived from the code-verified inventory in
> `be3-ra2-current-state-identity-secret-inventory.md` at canonical main `c1db4cc`. NO identity
> created or modified, NO secret read or written, NO exploit executed, NO runtime action.
> `production_executed_true_count: 0`.**

## Scope statement

This analysis covers the identity and secret trust boundaries that BE3 runtime activation would
depend on. It is **not** a claim that Zero Trust is implemented, designed, or approached. The
current architecture is explicitly **pre-Zero-Trust**: the primary human-operator surface accepts
an unverified client-asserted role, and no workload authenticates itself to any other workload.

Severity uses: `CRITICAL` (direct path to unauthorized production-effect or full identity
compromise), `HIGH` (privilege escalation or credential compromise with meaningful blast radius),
`MEDIUM` (weakens containment/forensics but is not directly exploitable into production effect).

Every "current control" statement below cites the code-verified state, and every "control gap" is
a genuine gap — not a hypothetical.

---

## 10. Trust-boundary model (text form)

### 10.1 Intended boundary chain

```text
[ Human Operator ]
      |  (B1) Identity Provider / Session Boundary
      v
[ Authenticated Operator Session ]
      |  (B2) Operator API Boundary
      v
[ Operator API / Admin Console ]
      |  (B3) Policy / Approval Boundary
      v
[ Authorization + Production-Approval Decision ]
      |  (B4) Durable Authorization Record Boundary
      v
[ Durable Authorization (DB, expiring, scope-bound) ]
      |  (B5) Service Identity Boundary
      v
[ Runtime Consumer / Executor ]
      |  (B6) Evidence Boundary
      v
[ Audit Evidence ]
```

### 10.2 Separately-labelled authorities (must never collapse into one "admin token")

```text
[ Trusted Policy Authority ]
      -> authenticated capability (dedicated header + server-configured principal id)
      -> authorize / reject decision ONLY (cannot request, cancel, consume, or approve production)
      -> durable authorization record

[ Secret Backend ]
      -> authenticated workload
      -> scoped credential delivery
      -> rotation / revocation
```

The design intent — three distinct authorities (human operator, policy authority, service
identity), each with a disjoint capability set — is correctly reflected in
`authorization_policy.evaluate`. The gap is entirely in *authentication*, not in *authorization
design*.

### 10.3 Actual boundary status at `c1db4cc`

```text
B1  Identity Provider / Session      ABSENT for production. Surface A has no session at all;
                                     Surface B has a real session carrying a fixed pseudo-identity.
B2  Operator API                     PRESENT but trusts client-asserted actor AND role headers.
B3  Policy / Approval                PARTIAL. Policy Authority boundary is real and strong.
                                     Production-approval GRANT boundary has no entry point at all.
B4  Durable Authorization            PRESENT and strong (expiring, scope-bound, exactly-null-safe
                                     team/project matching, extensively tested).
B5  Service Identity                 ABSENT. No authenticator; the policy branch is unreachable in
                                     production.
B6  Evidence                         PARTIAL. Evidence is written durably; nothing delivers or
                                     surfaces it (no activated relay, no console surface).
```

**The chain is broken at both ends.** B1 (who is the human?) and B5 (which workload is calling?)
are the two missing boundaries, and they are exactly the two that RA-2's decisions must resolve.

---

## 11. Threat register

### T-01 — Operator impersonation via client-asserted actor header

```text
Threat:              Any client reaching the BE3 operator API declares an arbitrary X-Task-Actor
                     and is treated as that operator.
Affected identity:   Human operator
Attack path:         Attacker reaches the orchestrator with TASK_API_TEST_AUTH_ENABLED=true ->
                     sends X-Task-Actor: <victim-operator-id>, X-Task-Role: <any TASK_ROLE> ->
                     creates/cancels resume or replay requests attributed to the victim.
Current control:     TASK_API_TEST_AUTH_ENABLED is false by default (fail-closed 403), and all
                     four BE3 feature gates default false. Network exposure is bound to localhost
                     in the compose file.
Control gap:         There is no authentication factor of any kind on this surface. The control is
                     "the feature is off", not "the caller is verified".
Severity:            CRITICAL (if the surface is ever enabled in a shared runtime)
Required decision:   RA2-D01, RA2-D02
Candidate mitigation:Replace _authenticate with an IdP-backed session/token validator; make the
                     audited actor the verified subject claim, never a header.
Future evidence:     A test proving a forged X-Task-Actor is rejected when the production
                     authenticator is active; an audit record whose actor is provably the verified
                     subject.
```

### T-02 — Privilege escalation via client-asserted role header

```text
Threat:              A caller self-declares X-Task-Role: platform_admin and obtains administrative
                     capability without any server-side entitlement check.
Affected identity:   Human operator (role/entitlement)
Attack path:         Same as T-01, but the payoff is the role rather than the identity: the role
                     is validated only for MEMBERSHIP in TASK_ROLES (task_api.py:76), never for
                     whether this actor is entitled to it.
Current control:     None beyond the feature gate. Membership validation does not constrain WHO
                     may claim a role.
Control gap:         No binding between actor id and permitted roles anywhere in the codebase.
Severity:            CRITICAL
Required decision:   RA2-D03
Candidate mitigation:Derive role exclusively from a verified IdP claim or a platform-owned RBAC
                     record keyed to the verified subject; reject any role transported in a
                     request header.
Future evidence:     A test proving a header-supplied role is ignored/rejected while the verified
                     claim governs.
```

### T-03 — Operator and approver identity collision (separation-of-duties defeat)

```text
Threat:              The two-person control on replay (distinct requester and approver) is
                     defeated because one party can present as both.
Affected identity:   Human operator + approver
Attack path:         With T-01 available, a single actor issues the request as actor-A and the
                     approval as actor-B. The two-person rule compares principal ids that the same
                     caller fully controls.
Current control:     The distinct-approver rule itself is correctly implemented and well tested at
                     the data/authorization layer.
Control gap:         The rule compares UNVERIFIED identifiers, so its guarantee is only as strong
                     as B1 -- which is absent.
Severity:            CRITICAL
Required decision:   RA2-D01, RA2-D03, RA2-D12
Candidate mitigation:Verified subject binding, plus (optionally) an approval-time re-authentication.
Future evidence:     A test proving two distinct verified sessions are required and one session
                     cannot satisfy both roles.
```

### T-04 — Service identity spoofing

```text
Threat:              An unauthorized process claims to be the Service Identity to consume
                     authorizations and trigger execution.
Affected identity:   Service Identity
Attack path:         Not currently exploitable -- because no authenticator exists and no consumer
                     exists, there is nothing to spoof. The threat is entirely FORWARD-LOOKING:
                     whichever mechanism RA2-D04 selects becomes the spoofing target.
Current control:     Structural -- the capability does not exist (§6).
Control gap:         The absence is the gap: any future consumer must not be built on a static
                     shared secret, or this becomes immediately exploitable.
Severity:            HIGH (forward-looking, becomes CRITICAL if implemented with a static secret)
Required decision:   RA2-D04
Candidate mitigation:Workload-bound, audience-scoped, short-lived credentials (projected token,
                     SPIFFE, mTLS, or signed short-lived JWT) rather than a bearer shared secret.
Future evidence:     A test proving a caller without a valid workload credential is denied consume.
```

### T-05 — Confused deputy via the orchestrator

```text
Threat:              The orchestrator, holding privileged credentials, performs a
                     consume/execute action on behalf of a caller who is not entitled to it.
Affected identity:   Service Identity / orchestrator
Attack path:         A future consumer authenticates to a downstream system with its own service
                     credential while acting on request data whose origin was never verified
                     (T-01). The downstream system sees a trusted service, not the real requester.
Current control:     The durable authorization record carries scope (team/project) and is checked
                     with exact null-safe equality -- a genuine and effective control.
Control gap:         Nothing propagates the ORIGINAL operator identity to the execution step for
                     re-verification; the authorization record is trusted wholesale once written.
Severity:            HIGH
Required decision:   RA2-D04, RA2-D12
Candidate mitigation:Carry the verified requester subject into the authorization record and
                     re-check it at consume time; keep service credentials audience-scoped so they
                     cannot be replayed against unintended downstreams.
Future evidence:     A test proving a consume bound to team/project A cannot execute against B even
                     with a valid service credential.
```

### T-06 — Shared-secret reuse across environments

```text
Threat:              The same Policy Authority capability value is used in dev, test, and a shared
                     runtime; compromise in the weakest environment grants authority in all.
Affected identity:   Policy Authority
Attack path:         An operator copies a working env-var block between environments (the default
                     delivery mechanism is environment variables, §8) -- the fastest way to make
                     it "work" is to reuse the value.
Current control:     None technical. No environment binding, no audience claim, no issuer.
Control gap:         The credential is an opaque string with no environment or audience scoping;
                     nothing detects or prevents reuse.
Severity:            HIGH
Required decision:   RA2-D05, RA2-D06, RA2-D11
Candidate mitigation:Per-environment credentials issued by a backend that cannot serve another
                     environment's namespace; audience/issuer claims that fail closed cross-env.
Future evidence:     Evidence that a credential minted for the validation environment is rejected
                     elsewhere.
```

### T-07 — Credential replay

```text
Threat:              A captured Policy Authority capability header is replayed indefinitely.
Affected identity:   Policy Authority
Attack path:         Any party observing one authorize/reject request (a proxy, a log with header
                     capture, a debugging session) obtains a bearer value that never expires.
Current control:     Constant-time comparison, length bound, non-echo in logs/audit/response, and
                     dedicated-header-only sourcing -- all real and correctly implemented.
Control gap:         The value is a BEARER secret: no nonce, no timestamp, no request signature,
                     no expiry. Capture once, use forever until rotated.
Severity:            HIGH
Required decision:   RA2-D05, RA2-D09
Candidate mitigation:Short-lived signed tokens (exp/aud/iss) or request signing over method, path,
                     body hash, and timestamp.
Future evidence:     A test proving a captured credential fails after its TTL or outside its
                     audience.
```

### T-08 — Credential theft from process environment

```text
Threat:              Secrets in environment variables are exposed via crash dumps, /proc, debug
                     endpoints, subprocess inheritance, or container introspection.
Affected identity:   All (Policy Authority, DB, Vault token, all service credentials)
Attack path:         Environment variables are the DEFAULT and effective delivery mechanism
                     (SECRET_PROVIDER defaults to "env"); BE3's own credential path reads
                     os.environ directly and does NOT use SecretRef, so its value is not even
                     protected by the platform's redaction wrapper against stray repr/str.
Current control:     Strong redaction exists for values that DO go through SecretRef /
                     redact_mapping / the BE3 audit-payload forbidden-value scanners; the BE3
                     migration CLI (RA-1) proved a strict no-leak output contract.
Control gap:         The BE3 identity credential path bypasses the secrets SDK entirely; every
                     child process inherits the environment; no runtime-fetch alternative is wired.
Severity:            HIGH
Required decision:   RA2-D06, RA2-D07
Candidate mitigation:File-mounted or runtime-fetched short-lived credentials; route every BE3
                     credential read through SecretRef; never place identity credentials in the
                     process environment of a shared runtime.
Future evidence:     Evidence that no identity credential appears in the process environment of the
                     validation runtime.
```

### T-09 — Secret leakage into logs, errors, or audit payloads

```text
Threat:              A credential reaches an operator-visible log line, exception, or audit row.
Affected identity:   All
Attack path:         An unhandled exception echoing a DSN or header; an audit payload built from
                     raw request data.
Current control:     GENUINELY STRONG and the most mature control in this analysis: BE3 audit
                     payload builders scan for forbidden markers (password/secret/token/dsn=/
                     postgres://); the policy-authority value is never logged or echoed; RA-1C/D
                     hardened the migration CLI to a single-JSON, whole-message-collapse redaction
                     contract with regex-based secret-shape detection.
Control gap:         Coverage is per-call-site rather than enforced centrally; a NEW code path
                     (e.g. a future authenticator) does not automatically inherit it.
Severity:            MEDIUM
Required decision:   RA2-D07 (delivery choice affects exposure surface)
Candidate mitigation:A central logging filter plus a required SecretRef type at every credential
                     boundary.
Future evidence:     A negative test asserting no credential-shaped value appears in any log,
                     error, or audit row for the new authentication paths.
```

### T-10 — Cross-team / cross-project credential use

```text
Threat:              A credential valid for one team/project is used to act on another's data.
Affected identity:   Human operator + Service Identity
Attack path:         Present the same credential with a different team_id/project_id in the body.
Current control:     STRONG at the data layer -- exact null-safe team/project equality with
                     cross-tenant masking (404 rather than 403), independently re-verified at
                     BE3-R and BE3-R-FC.
Control gap:         Scope is supplied by the CALLER and validated against the record, not derived
                     from the credential. A credential is not itself scope-bound.
Severity:            MEDIUM (well contained by the record-level check; would be HIGH without it)
Required decision:   RA2-D03, RA2-D04
Candidate mitigation:Bind team/project scope into the credential claims and intersect it with the
                     requested scope, denying any request outside the credential's own scope.
Future evidence:     A test proving a scope-bound credential cannot act outside its scope even when
                     the request body asks it to.
```

### T-11 — Stale credential after role removal

```text
Threat:              An operator who has left the team or lost a role continues to act.
Affected identity:   Human operator
Attack path:         No revocation exists on Surface A (stateless headers). On Surface B a session
                     can be revoked, but the identity is fixed so the concept barely applies.
Current control:     Durable authorizations carry expires_at, which bounds the damage window for
                     already-granted authorizations.
Control gap:         No role-change propagation, no session invalidation on entitlement change, no
                     revocation on the header surface at all.
Severity:            HIGH
Required decision:   RA2-D03, RA2-D09
Candidate mitigation:Short session/token TTLs plus entitlement re-evaluation per request; explicit
                     revocation on role change.
Future evidence:     A test proving a revoked entitlement denies within the stated propagation SLA.
```

### T-12 — Rotation race

```text
Threat:              A credential rotation causes either an outage (callers still using the old
                     value) or an extended window where a compromised old value stays valid.
Affected identity:   Policy Authority; Admin Console session key
Attack path:         Rotate without overlap -> in-flight callers fail. Rotate with an unbounded
                     overlap -> a stolen old value stays usable indefinitely.
Current control:     Policy Authority implements a proper dual-key overlap (current + previous) --
                     a good design.
Control gap:         The overlap window is UNBOUNDED (no expiry on the _PREVIOUS slot; it stays
                     valid until an operator manually clears it) and there is no operational
                     procedure requiring clearance. The Admin Console session key has NO overlap
                     mechanism at all, so rotating it invalidates every live session at once.
Severity:            MEDIUM
Required decision:   RA2-D09
Candidate mitigation:Bound the overlap window with an explicit expiry; add a dual-key window to
                     the session key; alert while a previous-slot credential remains configured.
Future evidence:     A rotation rehearsal showing zero failed requests and a bounded, auto-expiring
                     overlap.
```

### T-13 — Revocation delay

```text
Threat:              A known-compromised credential remains accepted while the fix propagates.
Affected identity:   All
Attack path:         Revocation today = edit configuration + (for env-var delivery) restart every
                     consumer. No push invalidation exists.
Current control:     Fail-closed behaviour once the value is actually cleared.
Control gap:         Propagation time is unbounded and unmeasured; env-var delivery generally
                     requires a restart; there is no revocation list or check-on-use.
Severity:            HIGH
Required decision:   RA2-D07, RA2-D09
Candidate mitigation:Short TTLs so revocation is bounded by expiry; a backend supporting immediate
                     lease revocation; a documented and tested propagation SLA.
Future evidence:     A revocation rehearsal measuring actual propagation time against the SLA.
```

### T-14 — Break-glass abuse

```text
Threat:              An emergency-access path is used for routine work, or is left enabled.
Affected identity:   Human operator (elevated)
Attack path:         n/a today -- no break-glass credential exists in code or configuration.
Current control:     Structural absence. (docs/security/break-glass-model.md describes a MODEL;
                     no implementation exists, consistent with the reading rule in the inventory.)
Control gap:         There is also no emergency path at all, which is itself an operational risk
                     once a shared runtime exists.
Severity:            MEDIUM (forward-looking; becomes HIGH if implemented without controls)
Required decision:   RA2-D10
Candidate mitigation:Time-boxed, MFA-gated, approval-gated, fully audited, auto-expiring elevation
                     with mandatory post-use rotation and automatic incident creation.
Future evidence:     Evidence that a break-glass grant auto-expires and raises an incident record.
```

### T-15 — Policy Authority compromise

```text
Threat:              Whoever holds the capability can authorize any resume within scope.
Affected identity:   Policy Authority
Attack path:         Obtain the capability (T-07/T-08) plus the principal id -> authorize resumes.
Current control:     EXCELLENT capability confinement: is_policy_authority restricts the actor to
                     authorize/reject ONLY -- it can never request, cancel, consume, or touch the
                     independent production-approval gate. The production-effect path additionally
                     requires a SEPARATE production approval that this authority cannot grant.
                     This is real defence in depth and it materially bounds the blast radius.
Control gap:         The credential is a long-lived bearer secret with no expiry (T-07) and the
                     paired principal id arrives in an unverified header (T-01).
Severity:            HIGH (bounded to authorize/reject by the capability confinement)
Required decision:   RA2-D05
Candidate mitigation:Replace the bearer secret with a short-lived, audience-bound, workload-issued
                     credential; verify the principal id independently of the client header.
Future evidence:     A test proving a compromised policy-authority credential still cannot grant a
                     production approval or consume an authorization.
```

### T-16 — Service identity used as human identity (and the converse)

```text
Threat:              Machine and human identities become interchangeable, destroying accountability
                     and separation of duties.
Affected identity:   All
Attack path:         A human uses the service credential to act (untraceable to a person), or a
                     service is registered as a TASK_ROLE human operator to pass RBAC.
Current control:     The Actor model separates the two flags explicitly and the policy evaluates
                     machine flags BEFORE TASK_ROLES membership; the policy-authority principal is
                     documented as "an internal service account, never a human Operator's own
                     actor id".
Control gap:         Nothing ENFORCES that separation at provisioning time: the same header-based
                     mechanism carries both, and no registry marks an identifier as human-only or
                     machine-only.
Severity:            HIGH
Required decision:   RA2-D01, RA2-D04, RA2-D08
Candidate mitigation:Disjoint issuers/namespaces for human and workload identities; a provisioning
                     rule that a workload identity can never be granted a human TASK_ROLE.
Future evidence:     A test proving a workload credential cannot satisfy a human-role action and
                     vice versa.
```

### T-17 — Test credential reaching a shared runtime

```text
Threat:              A test-mode flag or fixed test identity is enabled in a shared environment.
Affected identity:   All
Attack path:         TASK_API_TEST_AUTH_ENABLED=true or ADMIN_CONSOLE_TEST_AUTH_ENABLED=true set
                     in a shared runtime -> the fixed "operator-test" identity, or arbitrary
                     header-asserted identities, become live.
Current control:     Both default to false and fail closed; Admin Console test auth is FORCED off
                     whenever production auth is enabled (auth.py lines 62-63) -- a genuinely good
                     interlock.
Control gap:         No equivalent interlock exists for TASK_API_TEST_AUTH_ENABLED: nothing forces
                     it off in a production-like environment, and nothing alerts if it is on.
Severity:            HIGH
Required decision:   RA2-D11, RA2-D12
Candidate mitigation:Mirror the Admin Console interlock onto the task/BE3 surface; add a startup
                     assertion that refuses to boot with test auth enabled outside dev/test; add a
                     posture alert.
Future evidence:     A test proving the service refuses to start with test auth enabled under a
                     production-like environment marker.
```

### T-18 — Dev/test/production identity crossover

```text
Threat:              One identity or credential namespace spans environments.
Affected identity:   All
Attack path:         Same as T-06, generalised to all identities; the mock-vault JSON file and
                     env-file patterns make copying trivial.
Current control:     Environment separation is procedural today, not technical.
Severity:            MEDIUM
Required decision:   RA2-D06, RA2-D11
Candidate mitigation:Per-environment issuers and namespaces; environment claim in every credential.
Future evidence:     Evidence of distinct issuer/namespace per environment.
```

### T-19 — Credential exposure through the Admin Console

```text
Threat:              A console view or posture API discloses secret material.
Affected identity:   All
Attack path:         A posture/report endpoint renders configuration including secret values.
Current control:     STRONG and deliberate: posture surfaces are explicitly booleans/enums/status
                     only; identity_posture_api is read-only with no mutation; the secrets provider
                     exposes list_available_secrets returning NAMES ONLY, never values; SecretRef
                     renders ***REDACTED***; a dedicated secret_posture surface exists.
Control gap:         Same as T-09 -- the guarantee is per-call-site discipline rather than a
                     structurally enforced type boundary.
Severity:            MEDIUM
Required decision:   RA2-D07
Future evidence:     A negative test asserting no posture/report endpoint can emit a secret value.
```

### T-20 — Unauthorized provisioning

```text
Threat:              An unauthorized party (including an automated agent) creates or alters an
                     identity or credential.
Affected identity:   All
Attack path:         No provisioning workflow, owner, approval requirement, or audit exists today,
                     so any party with configuration access effectively provisions identity.
Current control:     None (nothing to control -- no provisioning system exists).
Control gap:         Complete: no defined owner, no two-person control, no audit trail for identity
                     or credential creation.
Severity:            HIGH
Required decision:   RA2-D08
Candidate mitigation:A named human provisioning owner, two-person control for authority-bearing
                     credentials, full audit, and an explicit prohibition on any runtime agent
                     provisioning its own authority.
Future evidence:     An audit record for every identity/credential creation, with approver.
```

---

## 12. Severity roll-up

```text
CRITICAL (3):  T-01 operator impersonation
               T-02 role escalation via header
               T-03 operator/approver collision (two-person control defeat)

HIGH (10):     T-04 service identity spoofing (forward-looking)
               T-05 confused deputy
               T-06 shared-secret reuse across environments
               T-07 credential replay
               T-08 credential theft from process environment
               T-11 stale credential after role removal
               T-13 revocation delay
               T-15 policy authority compromise
               T-16 service/human identity conflation
               T-17 test credential reaching a shared runtime
               T-20 unauthorized provisioning

MEDIUM (6):    T-09 secret leakage into logs/audit
               T-10 cross-team credential use
               T-12 rotation race
               T-14 break-glass abuse (forward-looking)
               T-18 dev/test/production crossover
               T-19 exposure through Admin Console
```

(Count note: the HIGH list contains 11 entries; T-04 and T-14 are forward-looking threats whose
severity is conditional on the mechanism chosen in RA2-D04 / RA2-D10.)

## 13. Principal trust gaps (the shortest honest summary)

```text
GAP-1  No verifiable human identity. Every "who did this" claim on the BE3 surface is a
       client-supplied string. This single gap is the root cause of T-01, T-02, T-03, and it
       undermines the two-person control that the replay path depends on.

GAP-2  No workload identity. No process can prove what it is to any other process. The service
       identity authorization branch is unreachable in production, so the entire execution half of
       BE3 has no authenticated caller (T-04, T-05, T-16).

GAP-3  Bearer secrets with no lifetime. The one real authority credential (Policy Authority) is a
       long-lived opaque bearer string delivered via environment variables, outside the platform's
       own secrets abstraction (T-06, T-07, T-08, T-13, T-15).

GAP-4  No provisioning, rotation-window, or revocation operations. Rotation exists as a mechanism
       for one credential but has no bounded window; revocation has no propagation guarantee; no
       one owns provisioning at all (T-11, T-12, T-13, T-20).
```

## 14. Explicit non-claims

```text
Zero Trust:                     NOT achieved, NOT designed, NOT approached. Stated explicitly.
Identity readiness:             NOT claimed.
Secret backend selection:       NOT made -- see the decision package.
Any mitigation above:           PROPOSED / NON-BINDING candidate only; none is implemented,
                                scheduled, or authorized by this stage.
```

The existing controls that this analysis credits as genuinely strong — capability confinement of
the Policy Authority, exact null-safe scope matching with cross-tenant masking, the audit-payload
forbidden-value scanners, the RA-1 CLI redaction contract, the Admin Console test/production auth
interlock, and the fail-closed default of every gate — are real and materially reduce blast radius.
They do not substitute for the four gaps above.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
