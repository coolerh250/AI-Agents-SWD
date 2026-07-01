# Staging Information Request (Step 64A)

> **Staging only — non-production only. No production action. No production secret. No external write.**

Checklist of information needed from the operator / administrator before Step 64B.

## Known
- **Staging target IP:** `10.0.1.32`
- **Access method:** SSH
- **SSH credential:** to be requested **interactively** by Claude Code / operator at connect
  time — **never stored**, never committed, never printed, never placed in `.env`.
- Deployment source: GitHub `origin/main` (or sync from `10.0.1.31`).

## Still needs operator confirmation
1. **SSH username** for `10.0.1.32`.
2. **Password or key-based access** (key path existence only; never key contents).
3. Whether **sudo** is allowed.
4. Whether **Docker** is already installed.
5. Whether **Docker group** access is available (run docker without sudo).
6. Which **ports** may be exposed for the Admin Console (e.g. `18000`).
7. Whether **browser access** to `10.0.1.32` is available from the operator workstation.
8. Whether **SSH port forwarding** is preferred (vs direct port exposure).
9. Whether **HTTP** is acceptable for the first staging demo (vs requiring TLS).
10. Whether **live GitHub / Slack / LLM integrations remain disabled** (expected: yes).

## General staging questions
- **Host / access:** confirm `10.0.1.32` reachable over SSH; operator account + auth mode.
- **Ports / network:** allowed exposed ports; firewall hints; loopback vs LAN.
- **Auth / session:** operator-session mode for Admin Console mutation pages.
- **DNS / TLS:** whether a staging hostname + certificate is wanted (future).
- **Demo workflow preference:** confirm the SaaS User Management / Create user CRUD API demo.
- **External integrations:** confirm Slack / GitHub / LLM live integrations stay disabled.
- **Staging data retention preference:** how long to keep staging data / demo runs.
- **Staging cleanup preference:** when/how to tear down (no auto-cleanup without operator
  confirmation).

## Step 64B.1 preflight update (resolved / newly known)
- **SSH username:** `itadmin` (confirmed) — key-based access **established** on `10.0.1.32`
  (`agentai-swd-stage`). SSH item 1–2 resolved. Credentials remain interactive/key-only, never
  stored.
- **sudo:** passwordless sudo available (item 3 resolved).
- **Docker:** **NOT installed** on `10.0.1.32` at preflight (items 4–5) → operator must
  authorize a Docker install before Step 64B.2 (no install performed in Step 64B.1).
- Still open: exposed-port confirmation (6), browser reachability (7), SSH-port-forward
  preference (8), HTTP-for-first-demo (9), integrations disabled (10).

## Step 64B.2A host preparation update (resolved / newly known)
- **Docker (items 4–5):** **resolved** — operator authorized host preparation; Docker Engine
  `29.6.1` + Docker Compose v2 `v5.2.0` now installed on `10.0.1.32` (daemon active + enabled;
  `docker` group present; `itadmin` added, effective after reconnect).
- **Access mode (items 8–9):** operator confirmed **SSH local port-forward + HTTP** for the
  first staging demo (`http://localhost:18000/admin`).
- **Integrations (item 10):** operator confirmed live GitHub / Slack / LLM integrations remain
  **disabled / mocked** in staging.
- **Staging volume:** operator confirmed `/data/ai-agents-staging` as the staging volume base
  (created in 64B.2A).
- Still open: exposed-port confirmation beyond loopback (6, default remains loopback + SSH
  port-forward), browser reachability from the operator workstation (7).

---
_Staging only — non-production only. No production action. No production secret. No external write._

<!-- staging-safety: staging-only=true non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false -->
