# Identity Trust Boundary Model (Step 52.1 / Stage 54A)

Source: [identity-boundary-model.yaml](../../infra/identity/identity-boundary-model.yaml).

| Boundary | Trusted | Authority |
| --- | --- | --- |
| Browser | no | cannot store tokens |
| Admin Console frontend | partial | may initiate, **may not authorize** |
| Backend session | yes | validates identity (signature + expiry) |
| Policy engine | yes | authorizes the action |
| Approval engine | yes | governs human approval |
| Audit service | yes | records identity (no raw token/secret/CoT) |
| External IdP | future | **disabled** |
| Kubernetes / ArgoCD | future | **disabled** |

## Invariants

Frontend cannot self-authorize · roles are backend-authoritative · session
validated backend-side · CSRF / confirmation / idempotency are **not**
authorization · audit is **not** approval · **human acceptance is not
deployment** · **platform_admin is not infrastructure admin** · the production
IdP is untrusted because disabled.
