# Secret Access Boundary (Step 53)

Source: [secret-access-boundary.yaml](../../infra/secrets/secret-access-boundary.yaml).

* Frontend cannot access a secret; Admin Console cannot display one.
* Backend may reference secret **metadata** only; secret value access is
  **disabled** this stage.
* Production secret reads require a future store provider.
* Audit records metadata only; verifiers scan for leaks.
* Operators, `platform_admin`, and break-glass **cannot** read secret values.
