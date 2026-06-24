# Registry Credential Boundary (Step 54.3)

Source: [infra/security/registry-credential-boundary.yaml](../../infra/security/registry-credential-boundary.yaml).

Registry credentials are referenced via the Step 53 secret store only and never committed. No
registry login, no image push, no image pull-with-credential this stage. A future Kubernetes
image pull secret / ArgoCD image access would be a Step 53 `SecretRef` (store=disabled today).
Production registry access disabled; `productionReady: false`. Ties to
[secret-management-foundation.md](secret-management-foundation.md). Covered by
`tests/test_registry_credential_boundary.py`.
