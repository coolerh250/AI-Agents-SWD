# Release Governance — Rollback Requirement Model (Step 60)

- Model: `infra/release/rollback-requirement-model.yaml`
- SDK: `shared/sdk/release_governance/rollback.py`
- Verifier: `scripts/verify_rollback_requirement_model.py` → `ROLLBACK_REQUIREMENT_MODEL_VERIFY`

A release candidate is not ready for operator review without a rollback plan + rollback
evidence.

## Required plan fields
`rollback_owner`, `rollback_trigger`, `rollback_steps`, `rollback_validation`.

## Invariants
- A missing rollback plan **blocks readiness** (`rollback_plan` is in the readiness
  required-evidence set).
- Defining a rollback plan does **not** trigger a rollback.
- Production rollback is a **future phase only**.
