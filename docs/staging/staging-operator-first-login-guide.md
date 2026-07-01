# Staging Operator First-Login Guide (Step 64C)

> **Staging only — non-production only. No production action. No production secret. No external write.**

A step-by-step guide for an operator to reach and browse the staging Admin Console on
`10.0.1.32` (`agentai-swd-stage`) for the first time. This is a **staging** system; nothing
here performs a production action.

## Prerequisites
- SSH access to `itadmin@10.0.1.32` (key-based). If you do not have the session key, create
  your own keypair and have your public key installed in `authorized_keys` — see
  [staging-operator-access-validation.md](staging-operator-access-validation.md) (Option A/B).
- A local web browser.

## Step 1 — open the SSH local port-forward tunnel
From your workstation:

```bash
ssh -i ~/.ssh/ai-agents-staging/staging_10_0_1_32 -L 18000:127.0.0.1:18000 itadmin@10.0.1.32
```

Leave this session open. It forwards your local `localhost:18000` to the staging
orchestrator's loopback `127.0.0.1:18000` on the host. (If your local port 18000 is busy,
use e.g. `-L 18080:127.0.0.1:18000` and browse `localhost:18080` instead.)

## Step 2 — open the Admin Console
In your browser:

```text
http://localhost:18000/admin
```

You should see **"Admin Console v0 — read-only"**. `/admin` redirects to `/admin/`.

## Step 3 — browse the read-only pages
Use the navigation to open, for example: Overview (`/`), Safety Center (`/safety`),
Operational Metrics (`/metrics`), Production Readiness (`/production-readiness`), Controlled
Rollout Review (`/controlled-rollout-review`), Release Governance (`/release-governance`),
Backup/DR (`/backup-dr`), Sandbox GitHub (`/sandbox-github`), Runtime Baseline (`/runtime`).
Full list: [staging-admin-console-page-inventory.md](staging-admin-console-page-inventory.md).

Newly-bootstrapped staging shows **empty states** on data pages (no projects / work items
yet) — this is expected until the Step 64D demo seed.

## Step 4 — what you can and cannot do
- **Read-only viewing** is available across pages.
- **Operator mutations are disabled in staging** — actions return `policy_blocked` /
  `operator_actions_disabled` and change nothing. No production action is possible.

## Step 5 — finish
Close the browser tab and press `Ctrl-D` / `exit` in the SSH session to close the tunnel.
Port `18000` is released locally.

## Safety
- Access is via SSH tunnel only; the port is **not exposed publicly**.
- Live GitHub / Slack / LLM integrations are disabled/mocked; no production action;
  `production_executed_true_count=0`.

---
_Staging only — non-production only. No production action. No production secret. No external write._

<!-- staging-safety: staging-only=true non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
