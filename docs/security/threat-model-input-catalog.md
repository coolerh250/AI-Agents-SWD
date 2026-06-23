# Threat Model Input Catalog (Step 54.1)

Source of truth: [infra/security/threat-model-input-catalog.yaml](../../infra/security/threat-model-input-catalog.yaml).

Enumerates the inputs a future threat model (**Step 54.4**) must cover. `required: true`,
`configured: false`, `requiredBeforeProductionGate: true`. No threat model is produced here.

- **Assets:** admin console, operator actions, identity/OIDC, secret management, runtime
  operations, GitOps, workspace operator, future GitHub PR flow, future Kubernetes runtime,
  backup/restore, LLM integration, notification (Slack/email), future Google Drive.
- **Trust boundaries:** operator→console, console→operations API, orchestrator→siblings,
  platform→{IdP, secret store, GitHub, cluster, LLM, notification channels} (future where noted).
- **Entrypoints, data flows, external integrations** are likewise catalogued.
- References the Step 51 runtime, Step 52 identity, and Step 53 secret summaries.

Generation deferred to **Step 54.4**.
