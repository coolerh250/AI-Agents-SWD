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

---
_Staging only — non-production only. No production action. No production secret. No external write._

<!-- staging-safety: staging-only=true non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false -->
