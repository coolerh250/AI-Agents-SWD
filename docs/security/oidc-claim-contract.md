# OIDC Claim Contract (Step 52.2)

`infra/identity/oidc-claim-contract.yaml` (`oidc-claim-contract-v1`) defines the
claims a future production ID token must provide. No real claim is processed in
this step.

## Required claims

| Claim | Field | Notes |
|---|---|---|
| subject | `sub` | required, immutable |
| email | `email` | required, verified required |
| email verified | `email_verified` | required |
| groups | `groups` | required, mapping not configured |

Optional: `name`, `preferred_username`.

## Authority rules

* `frontendRoleAuthority: false` — the browser/frontend can never assert a role.
* `forbiddenClaimsAsAuthority: [role, is_admin, platform_admin]` — a token's
  `role` / `is_admin` / `platform_admin` claim is **never** authoritative. Roles
  derive only from a backend-configured group→role mapping (deferred to 52.3).
* `unknownUserBehavior: deny` — an unmapped user is denied, never given a
  default role.

`groups` may become the future role-mapping input, but mapping is not
implemented here. See [oidc-role-mapping-contract.yaml] and
[test-vs-production-auth-boundary.md](test-vs-production-auth-boundary.md).
