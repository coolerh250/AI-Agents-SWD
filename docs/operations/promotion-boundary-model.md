# Release Governance — Promotion Boundary Model (Step 60)

- Model: `infra/release/promotion-boundary-model.yaml`
- Verifier: `scripts/verify_promotion_boundary_model.py` → `PROMOTION_BOUNDARY_MODEL_VERIFY`

Defines the allowed promotion path:

```
dev → test → nonprod → operator_review
operator_review → production   (allowed: false — future production phase only)
```

## Invariants
- Production promotion is **forbidden** (the `operator_review → production` transition is
  `allowed: false` and `requiresFutureProductionPhase: true`).
- Auto-promotion is **forbidden** (no transition has `auto: true`).
- Step 60 adds **no** production route and **no** deploy action.
- A future production phase requires separate explicit approval.
