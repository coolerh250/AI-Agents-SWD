# Break-glass Model (Step 52.3)

Status: **defined, disabled.** Source:
[break-glass-model.yaml](../../infra/identity/break-glass-model.yaml).

There is **no** break-glass login route, **no** admin button, and **no**
automatic platform_admin break-glass access. The verifier scans `apps/` and
`shared/sdk/` to confirm no break-glass route exists.

## Future requirements (all required, none implemented)

Production identity, a separate approval, a time-bound session, a recorded
reason, audit, and a post-incident review.

## Prohibitions

Break-glass can never be test-local, can never bypass audit, and can never
auto-grant Kubernetes / ArgoCD / GitHub / production-deploy access.

Break-glass depends on the future production approval model (**Step 60**) and
stays disabled until then.
