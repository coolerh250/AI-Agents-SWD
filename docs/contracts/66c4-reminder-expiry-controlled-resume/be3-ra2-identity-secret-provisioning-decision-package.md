# Step 66C.4-BE3-RA-2 — Identity and Secret Provisioning Decision Package

> **Product Owner decision package. Every item below is PROPOSED / NON-BINDING and awaits an
> explicit Product Owner decision. Claude Code has NOT selected an identity provider, a secret
> backend, a delivery mechanism, a provisioning owner, or a validation environment, and has NOT
> marked any option as selected, approved, binding, or canonical. NO identity was created or
> modified, NO secret was read, written, or rotated, NO Vault/Kubernetes/IAM change occurred, NO
> deployment, NO activation. `production_executed_true_count: 0`.**

Evidence base:
`docs/security/be3-ra2-current-state-identity-secret-inventory.md` (code-verified inventory) and
`docs/security/be3-ra2-identity-secret-threat-and-trust-analysis.md` (threat/trust analysis), both
derived from canonical main `c1db4cc`.

## Reading the `Recommended assessment` field

Each decision carries a `Recommended assessment`. Per §26 these are **PROPOSED / RECOMMENDED FOR PO
CONSIDERATION / NON-BINDING** engineering assessments supplied so the Product Owner has an informed
starting point. They are explicitly **not** decisions, and the `Product Owner selection` field is
left `PENDING` on every item without exception. Where an option is called *unacceptable*, that is a
security assessment about a pattern (with its reason stated), not a decision about the platform.

---

## RA2-D01 — Human operator identity source

```text
Decision ID:          RA2-D01
Decision:             What is the authoritative source of a human operator's identity?
Current gap:          None exists. The BE3 surface accepts an unverified X-Task-Actor header; the
                      Admin Console authenticates a single fixed pseudo-identity "operator-test"
                      in test_local mode only. Root cause of threats T-01, T-02, T-03 (all
                      CRITICAL). See inventory §5.
Option A:             Enterprise OIDC / existing IdP. Identity assurance high; MFA inherited from
                      the IdP; group/role claims available; sessions and revocation managed
                      centrally; stable audit subject. Requires an IdP to exist and a client
                      registration to be provisioned. The repo already contains an OIDC config
                      validator, claim contract, and provider interface (all fail-closed, no
                      network) that this option would implement against.
Option B:             Reverse-proxy asserted identity (proxy authenticates, forwards a trusted
                      header). Lower app-side complexity; centralises authN at the edge. Depends
                      ENTIRELY on the app being unreachable except through the proxy -- otherwise
                      it degrades to exactly today's forgeable-header model.
Option C:             Internal operator account database (platform-owned users + credentials).
                      No external dependency; full control; works identically on-prem and on GCP.
                      But the platform then owns password storage, MFA, lockout, reset, and
                      breach response -- a large, security-sensitive surface to build and maintain.
Option D:             Static API token per operator. Simple. UNACCEPTABLE for shared activation:
                      no MFA, no expiry, no revocation propagation, weak audit binding, and a
                      long-lived bearer credential per human (T-07, T-11, T-13).
Unacceptable:         Option D as the identity source for any shared runtime; continuing to trust
                      an unverified client-supplied actor header (the current state).
Security impact:      Closes GAP-1; directly addresses the three CRITICAL threats and restores the
                      integrity of the two-person replay control.
Operational impact:   A/B introduce an external dependency in the login path (availability and
                      clock-skew considerations). C introduces ongoing credential-management duty.
On-prem impact:       A works if an on-prem IdP exists; B works well on-prem; C always works.
GCP impact:           A maps cleanly to Cloud Identity / Workforce Identity Federation; B maps to
                      IAP; C is portable but duplicates what the platform already provides.
Cost/lock-in:         A: low cost if an IdP exists, moderate coupling to it (mitigated by the
                      existing provider abstraction). B: low cost, coupling to the proxy/ingress.
                      C: highest build+maintenance cost, lowest external lock-in.
Recommended assessment: NON-BINDING -- Option A is PROPOSED as the primary candidate where an
                      enterprise IdP already exists, because it resolves MFA, revocation, and role
                      claims in one step and the codebase already anticipates it. Option B is
                      PROPOSED as a pragmatic interim ONLY IF network-path exclusivity can be
                      technically guaranteed and verified. RECOMMENDED FOR PO CONSIDERATION.
Prerequisites:        An IdP endpoint and client registration (A); a guaranteed-exclusive ingress
                      path (B); a credential-storage design and review (C).
Rollback/revocation:  A/B: disable the integration -> operator surface fails closed (unchanged from
                      today's default-off posture). C: disable accounts.
Product Owner selection:   PENDING
Product Owner conditions:  PENDING
Status: PRODUCT_OWNER_DECISION_REQUIRED
```

---

## RA2-D02 — Operator session and API authentication

```text
Decision ID:          RA2-D02
Decision:             How is an authenticated operator session established, carried, and ended for
                      both the Admin Console and the BE3 operator APIs?
Current gap:          Two unrelated models. Surface A (BE3/task APIs) has NO session -- every
                      request is independently header-asserted. Surface B (Admin Console) has a
                      real HMAC-signed HttpOnly SameSite=strict 30-minute revocable session with
                      CSRF, but a fixed identity and a signing key with no rotation overlap that
                      may fall back to an ephemeral in-memory value. Inventory §5.1-5.2.
Option A:             OIDC authorization-code + PKCE, establishing a server-side session cookie.
                      Best fit for browser-based console use; PKCE protects the code exchange;
                      refresh and logout flow from the IdP.
Option B:             Secure server-side session only (extend the existing Stage-52 session to
                      carry a real authenticated subject). Reuses working, tested machinery (CSRF,
                      TTL, revocation, sha256-only storage) and is the smallest delta -- but still
                      requires RA2-D01 to supply the subject.
Option C:             Short-lived bearer access token (JWT) for API clients, validated per request
                      with issuer/audience/expiry checks. Best fit for non-browser/API callers;
                      no cookie/CSRF concerns; requires key distribution and clock-skew tolerance.
Option D:             Reverse-proxy asserted identity per request (no app session at all).
Unacceptable:         Continuing header-asserted identity on the BE3 surface; any session whose
                      signing key is an ephemeral in-memory value in a shared runtime; a session
                      with no expiry or no revocation path.
Must be covered:      session timeout; refresh; logout; revocation; CSRF; SameSite policy; API
                      token audience; issuer verification; clock skew; replay prevention.
Security impact:      Determines the durability of the T-01/T-03 fix and bounds T-11 (stale
                      credential) via TTL.
Operational impact:   A hybrid (A/B for the console, C for API callers) is likely -- browser and
                      machine callers have genuinely different needs.
On-prem impact:       All viable on-prem. GCP impact: A/C map to standard managed patterns.
Cost/lock-in:         B lowest (reuses existing code); A moderate; C moderate (key management).
Recommended assessment: NON-BINDING -- a COMBINATION is PROPOSED: Option A+B for the browser
                      console (OIDC login establishing the existing server-side session), and
                      Option C for programmatic/API callers, with a single shared subject/claims
                      model so both surfaces resolve to the same verified identity rather than
                      remaining two disconnected trust models. RECOMMENDED FOR PO CONSIDERATION.
Prerequisites:        RA2-D01; a managed signing key (RA2-D06/D07) to replace the ephemeral-key
                      fallback; a bounded rotation window for the session key (RA2-D09).
Rollback/revocation:  Revoke sessions server-side (already supported: active/expired/revoked);
                      disable the integration -> fail closed.
Product Owner selection:   PENDING
Product Owner conditions:  PENDING
Status: PRODUCT_OWNER_DECISION_REQUIRED
```

---

## RA2-D03 — Operator role and scope source

```text
Decision ID:          RA2-D03
Decision:             Where do an operator's role and team/project scope come from?
Current gap:          The role arrives in the X-Task-Role header and is validated ONLY for
                      membership in TASK_ROLES (task_api.py:76) -- never for whether this actor is
                      entitled to it. Any caller may claim platform_admin. Threat T-02, CRITICAL.
Option A:             IdP groups/claims map to TASK_ROLES. Central administration; role changes
                      follow joiner/mover/leaver processes automatically. Requires the IdP to
                      model platform-specific roles, and propagation is bounded by token lifetime.
Option B:             Platform-owned RBAC records keyed to the verified subject. Full control of
                      platform-specific semantics (reviewer_approver, two-person rules,
                      team/project binding); immediate propagation; but the platform owns the
                      administration surface and its own audit.
Option C:             Hybrid -- IdP supplies verified identity and coarse group membership; the
                      platform owns fine-grained role and team/project scope binding, intersecting
                      the two and denying anything not permitted by BOTH.
Option D:             Request-provided role (the current state).
Unacceptable:         Option D -- explicitly and unconditionally. A role transported in a client
                      request is not an entitlement; it is an assertion by the party being
                      authorized. This pattern must not survive into any shared activation.
Must be covered:      TASK_ROLES reuse; reviewer_approver; platform_admin; operator;
                      team/project binding; separation of duties; role-change propagation.
Security impact:      Closes the second CRITICAL threat and is a precondition for the two-person
                      replay control to mean anything (T-03).
Operational impact:   A depends on IdP group hygiene; B needs an admin UI/API and its own RBAC;
                      C needs both but fails safe by intersection.
On-prem/GCP impact:   All portable; A depends on the chosen IdP's group model.
Cost/lock-in:         B/C higher build cost; A higher coupling to IdP group structure.
Recommended assessment: NON-BINDING -- Option C is PROPOSED. The platform already owns genuinely
                      platform-specific concepts (exact null-safe team/project scoping,
                      distinct-approver rules) that a generic IdP group model represents poorly,
                      while identity assurance belongs in the IdP. Intersecting both fails closed.
                      RECOMMENDED FOR PO CONSIDERATION.
Prerequisites:        RA2-D01; a role-mapping configuration (the repo already contains
                      role-mapping models and a fail-closed validator to build against).
Rollback/revocation:  Remove the mapping/record -> the operator loses the role and requests fail
                      closed.
Product Owner selection:   PENDING
Product Owner conditions:  PENDING
Status: PRODUCT_OWNER_DECISION_REQUIRED
```

---

## RA2-D04 — Service Identity mechanism

```text
Decision ID:          RA2-D04
Decision:             How does a workload prove it is the Service Identity entitled to consume an
                      authorization and execute?
Current gap:          No authenticator exists. 16 test-only construction sites, ZERO in apps/ or
                      shared/sdk/; the is_service_identity policy branch is unreachable in
                      production. Inventory §6. Threats T-04, T-05, T-16.
Option A:             Kubernetes ServiceAccount projected OIDC tokens. Short-lived, automatically
                      rotated, audience-bound, no secret to store. BUT: requires Kubernetes, and
                      today the chart sets automountServiceAccountToken=false with no
                      Role/RoleBinding, and the platform actually runs on Docker Compose -- so
                      this option has NO substrate today.
Option B:             SPIFFE/SPIRE workload identity. Platform-agnostic (works on-prem, VMs, K8s,
                      GCP); short-lived automatically-rotated SVIDs; strong workload attestation;
                      mTLS or JWT-SVID. Cost: a new control-plane component to run and operate.
Option C:             mTLS with managed certificates. Strong, well-understood, no bearer token to
                      steal; works anywhere. Cost: certificate lifecycle management (issuance,
                      renewal, revocation/CRL/OCSP) and per-service trust configuration.
Option D:             Signed short-lived service JWT (issuer/audience/expiry, asymmetric key).
                      Simplest to implement inside the existing FastAPI stack; portable; bounded
                      lifetime limits replay. Cost: the platform must own key custody, rotation,
                      and an issuing path.
Option E:             Static shared secret.
Unacceptable:         Option E as a long-term shared-runtime mechanism -- an unbounded bearer
                      credential reproduces every weakness of T-06/T-07/T-08/T-13 for the very
                      identity that gates execution. It must not be the long-term answer.
Must be covered:      on-prem support; GCP support; Kubernetes dependency; rotation; revocation;
                      audience binding; service-name binding; team/project scope; consumer
                      authentication; operational complexity.
Security impact:      Closes GAP-2 and is a hard precondition for any execution-path activation.
Operational impact:   A ties activation to a Kubernetes migration. B adds a control plane. C adds
                      PKI operations. D adds key custody but no new infrastructure.
On-prem impact:       B/C/D work on-prem; A does not without Kubernetes.
GCP impact:           A maps to GKE Workload Identity; B/C/D all work; D can later federate.
Cost/lock-in:         D lowest immediate cost and lowest lock-in; B highest capability and highest
                      operational cost; A lowest cost ONLY IF Kubernetes is already the target.
Recommended assessment: NON-BINDING -- Option D is PROPOSED as the pragmatic first mechanism
                      because it requires no new infrastructure and no Kubernetes migration, and
                      it can be introduced behind the existing authorization boundary; Option B is
                      PROPOSED as the stronger long-term target if the platform commits to a
                      workload-identity control plane. Option A is PROPOSED only if and when the
                      platform actually runs on Kubernetes. RECOMMENDED FOR PO CONSIDERATION.
Prerequisites:        A key custody decision (RA2-D06/D07); a decision on whether Kubernetes is the
                      target runtime (interacts with RA2-D11).
Rollback/revocation:  Disable the consumer; revoke the signing key / SVID / certificate -> consume
                      fails closed (the execution path is already gated and defaults off).
Product Owner selection:   PENDING
Product Owner conditions:  PENDING
Status: PRODUCT_OWNER_DECISION_REQUIRED
```

---

## RA2-D05 — Policy Authority authentication

```text
Decision ID:          RA2-D05
Decision:             How does the automated policy/safety authority authenticate when it
                      authorizes or rejects a resume?
Current gap:          A rotatable static shared secret in a dedicated header, paired with an actor
                      id that arrives in an UNVERIFIED client header. Configured in no environment
                      (zero matches for BE3_RESUME_POLICY_AUTHORITY in infra/), so it is
                      unconditionally fail-closed today. Inventory §7. Threats T-07, T-15.
Existing strengths
to preserve:          constant-time comparison; dedicated-header-only sourcing; no short-circuit;
                      uniform 403; never logged/echoed; dual-key rotation slots; fixed role label;
                      capability confinement to authorize/reject ONLY (cannot request, cancel,
                      consume, or grant production approval). Any replacement MUST retain all of
                      these -- especially the capability confinement, which is the single most
                      effective blast-radius control currently in the system.
Option A:             Workload OIDC (the policy engine presents a projected/federated token).
                      Short-lived, audience-bound, no stored secret. Requires the substrate from
                      RA2-D04 Option A.
Option B:             mTLS identity -- the authority is identified by its client certificate.
                      No bearer token to replay; strong binding; needs PKI.
Option C:             Signed short-lived service JWT (issuer/audience/expiry/subject). Bounded
                      replay window; no new infrastructure; aligns with RA2-D04 Option D.
Option D:             Rotatable HMAC/shared secret (the current mechanism, hardened): add expiry,
                      bound the rotation overlap window, and route it through the secrets SDK.
Unacceptable:         Treating the CURRENT configured secret as a completed formal identity;
                      pairing any credential with a principal id that is still read from an
                      unverified client header; an unbounded-lifetime bearer credential in a shared
                      runtime.
Must be covered:      principal identity; capability claim; credential form; audience; issuer;
                      expiration; rotation; revocation; dual-key overlap; request signature or
                      token validation; failure behaviour (must remain fail-closed).
Security impact:      Bounds T-07 (replay) and T-15 (authority compromise) by lifetime and
                      audience rather than by rotation discipline alone.
Operational impact:   D is the smallest change and preserves a working mechanism; A/B/C align the
                      authority with whatever RA2-D04 chooses, avoiding two parallel schemes.
On-prem/GCP impact:   C/D fully portable; A depends on Kubernetes/federation; B needs PKI.
Cost/lock-in:         D lowest; C low; B moderate (PKI); A tied to RA2-D04-A.
Recommended assessment: NON-BINDING -- Option C is PROPOSED so the Policy Authority and the Service
                      Identity share ONE workload-credential scheme rather than two, with Option D
                      PROPOSED as an acceptable hardened interim (add expiry + bounded overlap +
                      SecretRef routing) if a decision on RA2-D04 is deferred. The principal id
                      must in all cases be derived from the verified credential, not from a client
                      header. RECOMMENDED FOR PO CONSIDERATION.
Prerequisites:        RA2-D04 (to avoid divergent schemes); RA2-D06/D07 for credential delivery.
Rollback/revocation:  Clear the credential/key -> the authority path fails closed immediately, as
                      it does today.
Product Owner selection:   PENDING
Product Owner conditions:  PENDING
Status: PRODUCT_OWNER_DECISION_REQUIRED
```

---

## RA2-D06 — Secret backend

```text
Decision ID:          RA2-D06
Decision:             Which system is the authoritative store for runtime secrets?
Current gap:          The effective backend is ENVIRONMENT VARIABLES (SECRET_PROVIDER defaults to
                      "env"). Vault runs only as `server -dev` (in-memory, auto-unsealed, root
                      token, data lost on restart) and infra/vault/ holds only a .gitkeep. A real
                      Vault KV v2 client exists but authenticates with a STATIC token and is not
                      the default. No Kubernetes Secret template exists. Inventory §8.
Option A:             HashiCorp Vault with workload authentication (AppRole/Kubernetes/JWT auth --
                      not a static root token). Strong: dynamic secrets, leases, immediate
                      revocation, rich policies, audit device. Already partially coded against.
                      Cost: run Vault properly (persistent storage, seal/unseal, HA, backup).
Option B:             GCP Secret Manager with workload identity. Managed HA/DR, IAM-integrated,
                      versioned, audited. Cost: GCP-specific; weak fit for an on-prem-first
                      deployment; a cross-environment story is needed.
Option C:             Kubernetes Secret + encryption-at-rest. Simple if Kubernetes is the target.
                      But: base64 not encryption by default, namespace-wide exposure risk, weak
                      rotation story, and there is no Kubernetes runtime today.
Option D:             External Secrets Operator / Secrets Store CSI abstraction over A or B.
                      Decouples the application from the backend and eases later migration; adds
                      an operator/driver to run; still requires a real backend underneath.
Option E:             Environment-file delivery (the de facto current state).
Unacceptable:         Option E for shared activation -- local/dev only. Also unacceptable: Vault
                      `server -dev` as a shared-runtime backend, and any static root-token
                      authentication path.
Must be covered:      on-prem support; GCP support; HA/DR; audit; rotation; revocation; access
                      policies; bootstrap complexity; vendor lock-in; operational ownership.
Security impact:      Determines whether T-08 (env exposure), T-13 (revocation delay), and T-06
                      (cross-env reuse) are structurally fixable or only procedurally managed.
Operational impact:   A is the largest operational commitment but the most capable on-prem; B is
                      the least operational work but only on GCP; D adds indirection but preserves
                      optionality.
On-prem impact:       A strongest; B weak; C only with Kubernetes; D follows its backend.
GCP impact:           B strongest; A fully workable; D fine.
Cost/lock-in:         A: operational cost, low vendor lock-in (self-hosted). B: low operational
                      cost, high provider lock-in. D: mitigates lock-in at the cost of a component.
Recommended assessment: NON-BINDING -- Option A is PROPOSED where on-prem is the primary target,
                      because the platform is already on-prem/Compose today, a Vault KV v2 client
                      already exists in the codebase, and Vault's lease/revocation model directly
                      addresses the revocation-delay gap. Option D is PROPOSED as a wrapper IF
                      the Product Owner wants to preserve a future move to Option B. The bootstrap
                      secret (how the workload authenticates to the backend at all) must be
                      designed explicitly under whichever option is chosen.
                      RECOMMENDED FOR PO CONSIDERATION.
Prerequisites:        A decision on the primary target environment (interacts with RA2-D11); an
                      operational owner (RA2-D08).
Rollback/revocation:  Revoke the backend role/policy -> credential issuance stops and dependent
                      paths fail closed.
Product Owner selection:   PENDING
Product Owner conditions:  PENDING
Status: PRODUCT_OWNER_DECISION_REQUIRED
```

---

## RA2-D07 — Secret delivery mechanism

```text
Decision ID:          RA2-D07
Decision:             How does a secret reach the process that needs it?
Current gap:          Environment variables, read directly via os.environ. BE3's own credential
                      path does NOT use the platform's SecretProvider/SecretRef wrapper, so it
                      lacks even the redaction protection the platform already offers. Threat T-08.
Option A:             Environment variables. Simplest; universally supported. Weaknesses: visible
                      to child processes and introspection, cannot rotate without restart, easily
                      copied between environments.
Option B:             Read-only mounted files. Avoids process-environment exposure; can be updated
                      in place to enable rotation without restart (if the app re-reads); file
                      permissions provide a real boundary. The existing session-key loader already
                      uses a key-FILE pattern, so this is partially precedented.
Option C:             CSI-mounted secrets (driver-managed files). Option B plus backend-managed
                      lifecycle and automatic rotation. Requires Kubernetes + the CSI driver.
Option D:             Vault Agent / sidecar templating credentials to a file or memory. Automatic
                      renewal and revocation propagation; no application change beyond re-reading.
                      Adds a sidecar per workload.
Option E:             Runtime API fetch (the app authenticates to the backend and fetches on
                      demand, caching briefly). Most control and the best rotation/revocation
                      story; requires a bootstrap credential and careful cache/failure handling.
Option F:             Short-lived credential issuance (the app receives a lease/TTL credential and
                      renews). Best security posture; highest implementation complexity.
Unacceptable:         Environment-variable delivery of authority-bearing identity credentials in a
                      shared runtime; any delivery path that bypasses SecretRef-style redaction.
Must be covered:      process-environment exposure; rotation without restart; filesystem exposure;
                      application complexity; auditability; failure behaviour; secret lifetime.
Security impact:      Directly determines T-08 exposure and the achievable revocation SLA (T-13).
Operational impact:   B is a small delta from today; D/E/F progressively increase capability and
                      complexity.
On-prem/GCP impact:   A/B/D/E portable; C requires Kubernetes.
Cost/lock-in:         B lowest; D moderate (sidecar ops); E/F highest build cost.
Recommended assessment: NON-BINDING -- Option B is PROPOSED as the near-term mechanism (it removes
                      identity credentials from the process environment with minimal change and is
                      already precedented by the session-key file loader), with Option D or F
                      PROPOSED as the target once RA2-D06 is settled, because rotation-without-
                      restart and bounded lease revocation are what actually close T-12/T-13.
                      Independently of the option chosen, routing every BE3 credential read through
                      the existing SecretRef wrapper is PROPOSED as a low-cost hardening step.
                      RECOMMENDED FOR PO CONSIDERATION.
Prerequisites:        RA2-D06.
Rollback/revocation:  Remove the mount/lease -> the dependent path fails closed.
Product Owner selection:   PENDING
Product Owner conditions:  PENDING
Status: PRODUCT_OWNER_DECISION_REQUIRED
```

---

## RA2-D08 — Provisioning owner and workflow

```text
Decision ID:          RA2-D08
Decision:             Who may request, approve, provision, revoke, and rotate identities and
                      credentials, and through what workflow?
Current gap:          Nothing exists -- no owner, no workflow, no approval, no audit for identity
                      or credential creation. Anyone with configuration access effectively
                      provisions identity. Threat T-20 (HIGH).
Option A:             Human Platform Administrator performs provisioning manually against a
                      documented runbook. Simple, immediate, clear accountability. Cost: manual,
                      error-prone at scale, and the audit trail depends on discipline.
Option B:             GitOps-controlled provisioning (identity/credential REFERENCES in git,
                      values in the backend). Reviewable, versioned, auditable by construction,
                      supports two-person control via PR review. The repo already has a GitOps
                      structure and secret-reference files that fit this model. Cost: a strict
                      rule that no secret VALUE ever enters git.
Option C:             Dedicated Identity Provisioning Service. Best automation and consistency;
                      significant build and its own privileged identity to protect.
Option D:             External enterprise IAM team owns provisioning. Strong separation of duties
                      and existing enterprise controls; slower turnaround; depends on such a team.
Unacceptable:         Any runtime agent -- including any AI agent in this platform -- creating or
                      modifying its own authority identity or credentials. This must be an
                      explicit, standing prohibition regardless of which option is chosen.
Must be covered:      who may request; who may approve; who may provision; who may revoke; who may
                      rotate; two-person control; audit evidence; emergency handling.
Security impact:      Closes T-20 and is a precondition for trustworthy rotation (T-12) and
                      revocation (T-13).
Operational impact:   A is available immediately; B adds review latency but strong evidence; C/D
                      are larger organizational commitments.
On-prem/GCP impact:   All portable.
Cost/lock-in:         A lowest; B low (structure already present); C highest; D organizational.
Recommended assessment: NON-BINDING -- Option A combined with Option B is PROPOSED: a named human
                      Platform Administrator is accountable, while references/policies are managed
                      through GitOps so that two-person control and audit come from PR review,
                      with secret VALUES never in git. The prohibition on agent self-provisioning
                      is PROPOSED as unconditional. RECOMMENDED FOR PO CONSIDERATION.
Prerequisites:        A named accountable owner; RA2-D06 (what is being provisioned into).
Rollback/revocation:  Revert the reference change and revoke the credential in the backend.
Product Owner selection:   PENDING
Product Owner conditions:  PENDING
Status: PRODUCT_OWNER_DECISION_REQUIRED
```

---

## RA2-D09 — Rotation and revocation

```text
Decision ID:          RA2-D09
Decision:             What are the credential lifetimes, rotation cadence, overlap rules, and
                      revocation propagation guarantees?
Current gap:          The Policy Authority has a genuine dual-key overlap but the overlap window is
                      UNBOUNDED (the previous slot stays valid until manually cleared, with no
                      procedure requiring it). The Admin Console session key has NO overlap at all
                      and may silently fall back to an ephemeral value. No revocation propagation
                      guarantee exists anywhere. Threats T-11, T-12, T-13.
Required distinctions (these are four different operations and must not be conflated):
  rotation    -- issue a new credential while the identity continues to exist and remain valid
  revocation  -- invalidate a specific credential immediately, before its natural expiry
  expiration  -- a credential becomes invalid by the passage of its own TTL, with no action taken
  disable identity -- the principal itself is deactivated; all its credentials cease to be usable
Option A:             Long-lived credentials with scheduled manual rotation. Lowest effort; leaves
                      T-07/T-13 essentially unmitigated.
Option B:             Short TTL with automatic renewal (lease model). Revocation becomes bounded by
                      TTL even without push invalidation; strongest practical posture; requires a
                      backend that issues leases (RA2-D06).
Option C:             Moderate TTL plus an explicit revocation list checked on use. Immediate
                      revocation without very short TTLs; adds a check-on-use dependency.
Must be covered:      credential TTL; rotation frequency; dual-key overlap (and its BOUND);
                      revocation propagation target (an explicit SLA); compromise response;
                      consumer reload behaviour; session invalidation; audit events; rollback to a
                      prior credential.
Security impact:      Converts revocation from "eventually, if someone restarts everything" into a
                      measurable guarantee.
Operational impact:   B requires consumers to handle renewal and transient backend unavailability.
On-prem/GCP impact:   All portable; B depends on the RA2-D06 backend's lease support.
Cost/lock-in:         A lowest cost/highest residual risk; B highest capability.
Recommended assessment: NON-BINDING -- Option B is PROPOSED as the target, with three specific
                      near-term hardening steps PROPOSED regardless of the eventual backend:
                      (1) bound the Policy Authority previous-slot overlap with an explicit expiry
                      and alert while it remains populated; (2) add a dual-key overlap to the
                      Admin Console session key and remove the silent ephemeral-key fallback for
                      any shared runtime; (3) define and publish an explicit revocation-propagation
                      SLA that can actually be rehearsed and measured.
                      RECOMMENDED FOR PO CONSIDERATION.
Prerequisites:        RA2-D06, RA2-D07.
Rollback/revocation:  This decision IS the rollback/revocation design.
Product Owner selection:   PENDING
Product Owner conditions:  PENDING
Status: PRODUCT_OWNER_DECISION_REQUIRED
```

---

## RA2-D10 — Break-glass identity

```text
Decision ID:          RA2-D10
Decision:             Is there an emergency access path, and under what controls?
Current gap:          No break-glass credential or path exists in code or configuration. The
                      absence is currently safe (nothing to abuse) but becomes an operational risk
                      once a shared runtime exists and the normal identity path can fail.
                      Threat T-14.
Option A:             Dedicated emergency human identity, normally disabled. Clear and auditable;
                      must be protected as strongly as any administrative account.
Option B:             Time-limited elevated role granted to an existing verified identity. No
                      separate credential to store; inherits MFA and audit from the normal path;
                      requires the normal identity path to be available (so it does not help if
                      the IdP itself is down).
Option C:             Offline recovery credential (sealed, split, or stored out-of-band). Works
                      even when the IdP is unavailable; highest custody burden and highest abuse
                      potential if mishandled.
Option D:             No break-glass capability. Simplest and safest against abuse; accepts that
                      an identity-system outage means no operator access at all.
Must be covered:      storage; MFA; approval; maximum duration; scope; audit; post-use rotation;
                      incident creation; production restrictions.
Security impact:      A poorly controlled break-glass path is a standing privilege-escalation
                      route; a missing one is an availability and incident-response risk.
Operational impact:   B is the lightest to operate; C demands a custody procedure and periodic
                      verification.
On-prem/GCP impact:   All portable.
Cost/lock-in:         D zero; B low; A moderate; C highest.
Recommended assessment: NON-BINDING -- Option B is PROPOSED as the primary path (time-limited
                      elevation of an already-verified identity, MFA-gated, approval-gated,
                      auto-expiring, fully audited, with mandatory post-use rotation and automatic
                      incident creation), and Option D is PROPOSED as entirely acceptable for the
                      FIRST validation environment specifically, where the blast radius is small
                      and a disposable environment can simply be rebuilt. NO break-glass credential
                      may be created by this stage or by any implementation stage without its own
                      explicit authorization. RECOMMENDED FOR PO CONSIDERATION.
Prerequisites:        RA2-D01, RA2-D03, RA2-D08.
Rollback/revocation:  Auto-expiry plus mandatory post-use rotation.
Product Owner selection:   PENDING
Product Owner conditions:  PENDING
Status: PRODUCT_OWNER_DECISION_REQUIRED
```

---

## RA2-D11 — First runtime-validation environment

```text
Decision ID:          RA2-D11
Decision:             Which environment hosts the first runtime validation of any BE3 identity or
                      execution capability?
Current gap:          Undecided. RA-P raised it; it remains open. It gates RA-1's Gates 1/2/6 as
                      well (which runtime hosts the first shared migration apply/rollback).
Option A:             Fresh isolated ephemeral environment created per validation run. Smallest
                      blast radius; strongest credential/database isolation; perfectly repeatable;
                      trivially destroyed. This is exactly the pattern every RA-1 stage already
                      used successfully. Cost: bootstrap effort each run; least realistic.
Option B:             Dedicated non-production namespace/stack, persistent. More realistic and
                      supports multi-operator scenarios; needs its own credentials and lifecycle
                      management.
Option C:             Shared internal test stack with an isolated database and isolated
                      credentials. Most realistic to the eventual target; but shares a host and
                      network with other work, so isolation depends on configuration discipline
                      rather than construction.
Option D:             A future staging environment. Most realistic; does not exist today (staging
                      was decommissioned), so this option defers validation until it is rebuilt.
Must be covered:      blast radius; credential isolation; database isolation; network isolation;
                      observability; rollback; repeatability; operator access; secret bootstrap.
Security impact:      Determines the consequences of any identity/authorization defect found during
                      first validation, and bounds T-17 (test credentials in a shared runtime).
Operational impact:   A is proven and cheap to repeat; C reuses existing infrastructure but
                      requires care to avoid contaminating other work.
On-prem/GCP impact:   A/B/C all available on-prem today; D depends on a rebuild decision.
Cost/lock-in:         A lowest cost, lowest realism; D highest realism, highest prerequisite cost.
Recommended assessment: NON-BINDING -- Option A is PROPOSED for the FIRST validation of each new
                      identity capability (matching the proven RA-1 isolated-ephemeral pattern),
                      with Option B PROPOSED as the follow-on for genuinely multi-operator
                      scenarios that a single-purpose ephemeral environment cannot represent.
                      Option C is PROPOSED as acceptable only with a separate database, separate
                      credentials, and an explicit non-contamination check. NO environment is
                      created, selected, or modified by this stage.
                      RECOMMENDED FOR PO CONSIDERATION.
Prerequisites:        RA2-D06/D07 (how credentials are bootstrapped into it).
Rollback/revocation:  Destroy the environment (A/B); for C, revoke credentials and restore the
                      isolated database.
Product Owner selection:   PENDING
Product Owner conditions:  PENDING
Status: PRODUCT_OWNER_DECISION_REQUIRED
```

---

## RA2-D12 — Initial activation identity boundary

```text
Decision ID:          RA2-D12
Decision:             How much of the identity chain must be real before the FIRST activation is
                      permitted?
Current gap:          Undecided. Determines the scope and ordering of every implementation stage.
Option A:             API-only operator identity validation. Activate only the request/read paths
                      with a real operator identity; no policy authority, no service identity, no
                      execution. Smallest scope; proves RA2-D01/D02/D03 in a real runtime.
                      Dependency: RA-8 (RBAC verification) becomes meaningful for the first time.
                      Risk: lowest -- no execution path is reachable.
Option B:             Policy Authority authentication only. Adds a real authorizing authority
                      without any consumer. Proves RA2-D05. Dependency: RA-8/RA-9 (audit evidence
                      for authorize/reject transitions). Risk: low-moderate -- authorizations
                      become real records but nothing consumes them.
Option C:             Service Identity consumer authentication only. Adds a real consumer.
                      Dependency: RA-10 (runtime E2E) becomes partially exercisable. Risk: HIGH --
                      this is the first point at which an execution path can actually run, and it
                      is unsafe to reach before the operator identity that authorizes it is real.
Option D:             End-to-end operator -> authority -> service identity chain. Dependency:
                      RA-8, RA-9, RA-10, and RA-11 (Product Owner deployment authorization) all at
                      once. Risk: CRITICAL -- the full production-effect path becomes reachable in
                      a single step, with no intermediate validation.
Dependency/risk mapping required by §23:
  RA-8  (resume/replay RBAC verified)  -- meaningful under A; required under B/C/D
  RA-9  (audit evidence verified)      -- partially under A; required under B/C/D
  RA-10 (runtime E2E)                  -- not reachable under A/B; partial under C; full under D
  RA-11 (PO deployment authorization)  -- always required; non-delegable; required at every option
Unacceptable:         Reaching Option C or D while the operator identity source remains a
                      client-asserted header -- that would make a real execution path reachable
                      behind an unverifiable requester (T-01 + T-03 + T-05 compounding).
Security impact:      Controls whether a defect found during activation can produce a real effect.
Operational impact:   A/B are rehearsable repeatedly at low cost; D is effectively one-shot.
Recommended assessment: NON-BINDING -- a STRICTLY INCREMENTAL ordering A -> B -> C -> D is PROPOSED,
                      with an explicit Product Owner gate between each step, because each stage
                      makes the next one's failures observable while the execution path is still
                      unreachable. Option D as a first step is PROPOSED AGAINST.
                      RECOMMENDED FOR PO CONSIDERATION.
Prerequisites:        RA2-D01 through RA2-D05 at minimum for anything beyond Option A.
Rollback/revocation:  Every BE3 feature gate is read fresh from the environment on every call, so
                      flipping a gate back to false takes effect immediately with no restart
                      ordering hazard (verified at RA-P and unchanged).
Product Owner selection:   PENDING
Product Owner conditions:  PENDING
Status: PRODUCT_OWNER_DECISION_REQUIRED
```

---

## 24. RA-P open-decision carry-forward (all 11 items, none dropped)

Every one of the 11 open decisions recorded in `be3-runtime-activation-readiness-plan.md` §7 is
carried forward and classified. Mapping deviations from the suggested mapping are justified.

```text
RA-P 1. Production approval grant-path owner
        -> REQUIRES_RA2_PO_DECISION  (primary: RA2-D08, with RA2-D01/D03 for who may grant)
        Rationale: matches the suggested mapping. Note the inventory confirms
        grant_production_approval has ZERO production callers and no endpoint, so this is both a
        provisioning-owner decision AND a build item (see RA-2I6 in the decomposition).

RA-P 2. Production approval visibility (where an approver sees requests)
        -> DEFERRED_TO_RA6  (Admin Console evidence/visibility surface)
        Rationale: matches the suggested mapping -- a product/UI surface decision, not an identity
        mechanism decision. It does, however, depend on RA2-D01/D03 for who may see what.

RA-P 3. Canonical operator identity source
        -> RESOLVED_BY_RA2_PO_DECISION  (RA2-D01, with RA2-D02 and RA2-D03)
        Rationale: matches the suggested mapping; this is RA-2's central decision.

RA-P 4. Service Identity mechanism
        -> RESOLVED_BY_RA2_PO_DECISION  (RA2-D04)
        Rationale: matches the suggested mapping.

RA-P 5. Policy Authority secret delivery
        -> RESOLVED_BY_RA2_PO_DECISION  (RA2-D05, with RA2-D06 and RA2-D07)
        Rationale: matches the suggested mapping. Split deliberately: D05 decides the
        AUTHENTICATION form, D06/D07 decide the STORAGE and DELIVERY -- conflating them is what
        produced the current env-var-shared-secret state.

RA-P 6. First-validation environment
        -> RESOLVED_BY_RA2_PO_DECISION  (RA2-D11)
        Rationale: matches the suggested mapping. Also gates RA-1's Gates 1/2/6.

RA-P 7. Allowed validation events (synthetic-only vs real-but-low-stakes)
        -> DEFERRED_TO_RA7  (runtime validation planning)
        Rationale: matches the suggested mapping -- depends on the environment chosen in RA2-D11
        but is a validation-design decision, not an identity decision.

RA-P 8. Operation cap during initial validation
        -> DEFERRED_TO_RA7
        Rationale: matches the suggested mapping; same reasoning as item 7.

RA-P 9. Abort threshold for validation
        -> DEFERRED_TO_RA7
        Rationale: matches the suggested mapping; same reasoning as item 7.

RA-P 10. Admin Console evidence required before activation is complete
        -> DEFERRED_TO_RA6
        Rationale: matches the suggested mapping; pairs with item 2.

RA-P 11. Initial activation boundary (API only / command path / replay path)
        -> RESOLVED_BY_RA2_PO_DECISION  (RA2-D12)
        Rationale: matches the suggested mapping. Elevated in importance by the inventory: because
        no execution consumer exists at all, the activation boundary also determines how much NEW
        implementation is required before activation is even possible.

Cross-cutting item recorded by RA-P §8 (not one of the 11, carried forward so it is not lost):
        whether to activate BE2's poller/relay as a BE3 prerequisite, or build a narrower
        BE3-scoped audit-delivery path
        -> DEFERRED_TO_RA9_RA11  (materially affects sequencing; not an identity decision)
```

```text
Carry-forward integrity check:
  RA-P open items: 11        carried forward: 11        dropped: 0        silently defaulted: 0
  RESOLVED_BY_RA2_PO_DECISION: 5   (items 3, 4, 5, 6, 11)
  REQUIRES_RA2_PO_DECISION:    1   (item 1)
  DEFERRED_TO_RA6:             2   (items 2, 10)
  DEFERRED_TO_RA7:             3   (items 7, 8, 9)
  DEFERRED_TO_RA9_RA11:        1   (cross-cutting BE2 poller/relay item, additional to the 11)
```

---

## 25. Decision summary table (for direct Product Owner reply)

```text
ID       Decision                              Primary options            Status
RA2-D01  Human operator identity source        IdP / proxy / internal DB  PRODUCT_OWNER_DECISION_REQUIRED
RA2-D02  Operator session & API authN          OIDC+PKCE / session / JWT  PRODUCT_OWNER_DECISION_REQUIRED
RA2-D03  Operator role & scope source          IdP claims / platform / hybrid  PRODUCT_OWNER_DECISION_REQUIRED
RA2-D04  Service Identity mechanism            projected / SPIFFE / mTLS / JWT PRODUCT_OWNER_DECISION_REQUIRED
RA2-D05  Policy Authority authentication       workload OIDC / mTLS / JWT / HMAC PRODUCT_OWNER_DECISION_REQUIRED
RA2-D06  Secret backend                        Vault / GCP SM / K8s / ESO PRODUCT_OWNER_DECISION_REQUIRED
RA2-D07  Secret delivery mechanism             env / file / CSI / agent / API PRODUCT_OWNER_DECISION_REQUIRED
RA2-D08  Provisioning owner & workflow         human / GitOps / service / IAM PRODUCT_OWNER_DECISION_REQUIRED
RA2-D09  Rotation & revocation                 long-lived / short TTL / revocation list PRODUCT_OWNER_DECISION_REQUIRED
RA2-D10  Break-glass identity                  dedicated / time-limited / offline / none PRODUCT_OWNER_DECISION_REQUIRED
RA2-D11  First validation environment          ephemeral / namespace / shared / staging PRODUCT_OWNER_DECISION_REQUIRED
RA2-D12  Initial activation identity boundary  API / authority / service / E2E PRODUCT_OWNER_DECISION_REQUIRED

Total decisions: 12        Awaiting Product Owner: 12        Decided by Claude Code: 0
```

## 26. Rejected unsafe patterns (assessment, not decision)

```text
Request-provided role as an entitlement                     -- currently present; must not persist
Unverified client-asserted actor id as audit identity       -- currently present; must not persist
Static shared secret as the long-term Service Identity      -- must not become the mechanism
Vault `server -dev` as a shared-runtime secret backend      -- development convenience only
Static root-token authentication to a secret backend        -- must not be the workload auth path
Environment-variable delivery of authority credentials      -- local/dev only
Ephemeral in-memory session signing key in a shared runtime -- silent fallback must be removed
Unbounded dual-key rotation overlap                         -- must be bounded and alerted
Any runtime agent provisioning its own authority/credential -- unconditional prohibition
Treating the currently configured Policy Authority secret
  as a completed formal identity                            -- explicitly rejected
```

## 27. Boundaries of this package

```text
Claude Code has NOT selected, approved, or made binding any identity provider, secret backend,
delivery mechanism, provisioning owner, rotation policy, break-glass design, validation
environment, or activation boundary. Every `Product Owner selection` field is PENDING. Every
recommendation is labelled PROPOSED / RECOMMENDED FOR PO CONSIDERATION / NON-BINDING. No
implementation stage has been started. No identity exists that did not exist before this stage,
and no secret was read, written, or rotated.
```

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
