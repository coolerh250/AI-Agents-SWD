# Role Mapping Policy (Step 52.3)

Status: **engine exists; production mapping unconfigured.** Sources:
[role-mapping-policy.yaml](../../infra/identity/role-mapping-policy.yaml),
[role_mapping.py](../../shared/sdk/identity/role_mapping.py).

## Engine

`map_identity_to_role(claims, rules)` resolves OIDC-style group claims to a
backend role using **only explicit rules**, and denies by default:

* missing `sub` / `email` / unverified email / missing groups → deny;
* no matching group → deny (`unknown_user=True`, role `None`);
* a matching explicit rule → that role.

`IdentityClaims` carries no `role` / `is_admin` field, so a token role claim is
structurally impossible to honour. There is no default role and no auto-provision.

## Policy

`enabled: false`, `configured: false`, `rules: []`, `defaultRole: none`,
`unknownUserBehavior: deny`, `frontendRoleAuthority: false`. All four roles
(viewer/reviewer/operator/platform_admin) require an explicit mapping. Forbidden:
wildcard groups, default operator, default platform_admin, token-role-claim
authority, auto-provisioning.

## Fixtures

A SAFE non-production fixture
([role-mapping-safe-fixture.yaml](../../infra/identity/test-fixtures/role-mapping-safe-fixture.yaml))
maps placeholder groups (`group-viewer-placeholder`, …) only. `validate_rules`
rejects wildcard groups and disallowed roles. **No real group IDs** are
committed. Production status: not ready (no real group mapping configured).
