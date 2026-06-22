# Secret Lifecycle Model (Step 53)

Source: [secret-lifecycle-model.yaml](../../infra/secrets/secret-lifecycle-model.yaml).

Model only. Stages: request → approval → provisioning → reference registration →
rotation → emergency rotation → revocation → audit → post-rotation verification →
decommission. Production secret lifecycle requires approval.

Secret **values never** traverse the repo, audit, Admin Console, logs, or test
fixtures. A rotation record stores metadata only — never a value.
