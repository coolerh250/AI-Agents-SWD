# Release Governance — Policy (Step 60)

- Model: `infra/release/release-governance-policy.yaml`
- SDK: `shared/sdk/release_governance/policy.py`
- Verifier: `scripts/verify_release_governance_policy.py` → `RELEASE_GOVERNANCE_POLICY_VERIFY`

Defines the controlled, **non-production** release & deployment governance boundary. It
integrates delivery / work-item / sandbox-draft-PR / runtime / GitOps / security /
approval evidence into a governance decision — it does **not** deploy, sync, merge,
push, or release. **Production stays blocked.**

## Toggles (all false)
`allowProductionDeploy`, `allowAutoPromotion`, `allowGitHubMerge`, `allowTagCreation`,
`allowReleaseCreation`, `allowImagePush`, `allowRegistryLogin`,
`allowArgoCDProductionSync`. `productionReady` is always false;
`requireHumanApprovalForProduction` is true. These read straight from the committed YAML
so they cannot silently drift true in code.

## Environments
- `defaultEnvironment: nonprod`; `allowedEnvironments: [dev, test, nonprod]`.
- `forbiddenEnvironments: [production, prod]` — a production target is always rejected.

## Invariants
- Governance visibility is **not** a production gate active.
- No auto-promotion.
- A draft PR is not a release approval; a delivery-package-ready is not a production
  approval; a security baseline PASS is not a production approval.
