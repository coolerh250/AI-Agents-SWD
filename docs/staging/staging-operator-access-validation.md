# Staging Operator Access Validation (Step 64C)

> **Staging only — non-production only. No production action. No production secret. No external write.**
> **No public exposure — SSH local port-forward + HTTP only.**

Validation of the operator access path to the staging Admin Console on `10.0.1.32`
(`agentai-swd-stage`).

## Approved access method
SSH local port-forward + HTTP (operator-confirmed preference). Port `18000` on the host is
bound to `127.0.0.1` only; it is **never exposed on the LAN or publicly** in this stage.

```bash
ssh -i ~/.ssh/ai-agents-staging/staging_10_0_1_32 -L 18000:127.0.0.1:18000 itadmin@10.0.1.32
```

Then open in the operator browser:

```text
http://localhost:18000/admin
```

## End-to-end validation performed by Claude Code
From a client host holding the staging key, a fresh tunnel was opened and torn down:
- Tunnel `-L 18000:127.0.0.1:18000` established (exit 0, `ExitOnForwardFailure=yes`).
- Through the tunnel: `http://localhost:18000/health` → **200**;
  `http://localhost:18000/admin` → **200** (title "Admin Console v0 — read-only");
  `http://localhost:18000/operations/safety` → **200**.
- Tunnel closed afterward; local port `18000` freed (no lingering forward).

This proves the port-forward access **mechanism** works end-to-end from a client workstation.

## Operator workstation confirmation — CONFIRMED
The operator has **confirmed** they can open the read-only Admin Console page from their own
workstation through the approved SSH local port-forward path (`http://localhost:18000/admin`),
result: read-only Admin Console page opened successfully. Marker is now full **PASS**. Access
method: SSH local port-forward + HTTP; public exposure: none; production action: none;
`production_executed_true_count=0`.

## Access alternatives if the operator cannot use the current key
- **Option A (recommended):** operator generates their own SSH keypair and installs the public
  key in `itadmin@10.0.1.32`'s `authorized_keys`; private key stays on the operator workstation.
- **Option B:** operator uses their existing approved SSH access to `10.0.1.32`.
- **Option C:** temporary internal-only direct port exposure — only if later explicitly
  authorized (not done here).
- **Option D (future):** reverse proxy / DNS / TLS termination.

Current approved method remains **SSH port-forward + HTTP**; no public exposure unless
explicitly authorized.

## Credential / safety notes
Key-based SSH only; **no password** used or exposed; SSH private key never printed / committed /
stored; `.env.staging.local` never printed. No production action; `production_executed_true_count=0`.

---
_Staging only — non-production only. No production action. No production secret. No external write._

<!-- staging-safety: staging-only=true non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
