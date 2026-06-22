# Identity Authorization Decision Model (Step 52.3)

Source: [identity-authorization-decision-model.yaml](../../infra/identity/identity-authorization-decision-model.yaml).

Authorization is an ordered chain of **distinct** decisions; none short-circuits
a later one:

1. **authentication** → authenticated identity (test-local today; OIDC disabled).
2. **role mapping** → role from explicit group rules (unknown user deny).
3. **RBAC** → role's allowed action set (backend-authoritative).
4. **policy engine** → per-action policy gate (Step 50).
5. **confirmation** → one-time confirmation (not a permission grant).
6. **idempotency** → client correlation key (not authorization).
7. **audit** → records identity/role/action; `production_executed=false`.
8. **final authorization** → the result.

## Separations (each is enforced as a distinct boundary)

* Role mapping ≠ RBAC.
* RBAC ≠ policy approval.
* Confirmation ≠ permission.
* Human acceptance ≠ deployment approval.
* `platform_admin` ≠ infrastructure admin.

Production actions require a **future production approval gate** and are **not
currently executable**.
