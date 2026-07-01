# Staging Admin Console Access Evidence (Step 64B.2B)

> **Staging only — non-production only. No production action. No production secret. No external write.**

Evidence that the Admin Console is reachable on the staging runtime (`10.0.1.32`,
`agentai-swd-stage`, deployed commit `f43e163`), plus the operator access instruction.

## Host-local reachability (on 10.0.1.32)
- `GET http://127.0.0.1:18000/health` → **200**.
- `GET http://127.0.0.1:18000/admin` → **307** redirect → `http://127.0.0.1:18000/admin/`.
- `GET http://127.0.0.1:18000/admin/` → **200**, 56 KB HTML, page title
  **"Admin Console v0 — read-only"** (React root renders).
- `GET http://127.0.0.1:18000/operations/safety` → **200**.

The Admin Console host port `18000` is bound to **loopback only** (`127.0.0.1:18000`); it is
not exposed on the LAN.

## Operator access method — SSH local port-forward + HTTP
First staging demo access is via **SSH local port-forward** (operator-confirmed preference),
no public port exposure:

```bash
ssh -i ~/.ssh/ai-agents-staging/staging_10_0_1_32 -L 18000:127.0.0.1:18000 itadmin@10.0.1.32
```

Then open in the operator's browser:

```text
http://localhost:18000/admin
```

## Operator URL
- `http://localhost:18000/admin` (through the SSH tunnel above).

## Pages expected
The Admin Console v0 is **read-only** for viewing; operator-session model + CSRF apply to any
mutation pages (covered in the Step 64C Admin Console exposure stage). Expected navigation
includes the operations / safety / readiness / audit views served by the orchestrator.

## Step 64C update — port-forward validated end-to-end
The SSH local port-forward path was validated from a client host: a fresh
`-L 18000:127.0.0.1:18000` tunnel was opened, `localhost:18000/health` → 200,
`localhost:18000/admin` → 200 ("Admin Console v0 — read-only"),
`localhost:18000/operations/safety` → 200; the tunnel was then torn down and local port 18000
freed. **Operator workstation access: confirmed** — the operator opened the read-only Admin
Console page successfully from their own workstation (marker now full **PASS**). See
[staging-operator-access-validation.md](staging-operator-access-validation.md),
[staging-admin-console-exposure-report.md](staging-admin-console-exposure-report.md), and the
page inventory [staging-admin-console-page-inventory.md](staging-admin-console-page-inventory.md).

## Credential / safety notes
- Access is over key-based SSH; **no password** is used or exposed; the SSH private key is
  never printed / committed / stored.
- No port is exposed publicly; HTTP (no TLS) is acceptable for the first staging demo only.
- No production action; `production_executed_true_count=0`.

---
_Staging only — non-production only. No production action. No production secret. No external write._

<!-- staging-safety: staging-only=true non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false runtime-deployment=staging-only live-integrations=disabled demo-workflow-executed=false -->
