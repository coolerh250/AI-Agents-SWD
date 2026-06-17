# Kubernetes Workspace Storage Model (Step 51.2C1 / Stage 53D)

## Finding: workspace is per-pod, NOT a shared filesystem

The four workspace components — `development-agent`, `qa-agent`,
`workspace-operator-agent`, `mini-delivery-pilot-agent` — each write under
`/tmp/aiagents-workspaces` (or `tempfile` → `/tmp`) **inside their own pod**.

* Each agent is the **sole writer** of its own scratch.
* The mini-delivery pilot runs controlled workspace execution **in-process** —
  there is no cross-pod filesystem handoff.
* Agents exchange state via **PostgreSQL / in-process**, not a shared volume.

Therefore **no ReadWriteMany volume is required** for the current behaviour.

## Strategy chosen: D — Ephemeral controlled workspace

Dev/Test (and staging/prod placeholders) keep the existing `/tmp` `emptyDir`:

* Restart-discarded; **not** delivery-durable.
* Does **not** represent production storage.
* Persistence is **not** solved (`persistenceSolved: false`).

The other candidate strategies were evaluated and recorded as **disabled
placeholders**, not adopted:

* **B — Shared RWX existingClaim**: `enabled=false`, `existingClaim=""`,
  `accessMode=ReadWriteMany`. Inert; no claim generated; no real storage class.
  Production cannot render it as deployable without a real existing claim.
* **C — External object/artifact store**: endpoint blank, disabled, no
  credential, no egress policy.

## Remaining blocker

Durable / cross-restart workspaces (if ever required) need either an RWX
existing claim or an object store. Both are **future** decisions; today the
honest state is ephemeral per-pod. Recorded in
[storage-ownership-catalog.yaml](../../infra/kubernetes/storage-ownership-catalog.yaml)
under `workspace-scratch.futureTarget`.

`accessModeRequirement` for the active workspace is therefore **none** (no claim),
and `validate-values.yaml` blocks `productionConfigured=true` unless a non-sample
existing RWX claim is supplied.
