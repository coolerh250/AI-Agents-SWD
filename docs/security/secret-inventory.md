# Secret Inventory (Step 53)

Source: [secret-inventory.yaml](../../infra/secrets/secret-inventory.yaml).

References only — no real secret value. All 15 categories are covered: identity,
session, csrf, database, redis, backup, audit, gitops, kubernetes, github,
registry, llm, notification, storage, break_glass.

Invariants enforced by `SECRET_INVENTORY_VERIFY`:

* every production secret: `productionConfigured=false`, `secretStoreRequired=true`;
* every secret: `valueStoredInRepo=false`, an `owner`, and `references`;
* dev/test ephemeral secrets (session key, trust-auth DB) are marked
  non-production; the dev mock-vault is dev-only / not a production store.
