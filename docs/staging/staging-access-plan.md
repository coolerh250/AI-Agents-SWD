# Staging Access Plan (Step 64A)

> **Staging only — non-production only. No production action. No production secret. No external write.**

How an operator reaches the staging Admin Console + APIs on the staging target.

## Staging target
- **Staging target host:** `10.0.1.32` · **Access method:** SSH
- **Credential handling:** interactive only — Claude Code / operator supplies the SSH
  username and password-or-key method at connect time. Credentials are **never stored**,
  never committed, never written to `.env`, never printed; if an SSH key is used only its
  *path existence* is noted, never its contents. On failure only the error *type* is
  reported, never the credential.

## Operator access methods (ranked)
1. **SSH local port-forward (recommended first demo):**
   `ssh -L 18000:127.0.0.1:18000 <user>@10.0.1.32`, then browse `http://localhost:18000/admin`.
   Keeps the staging port on loopback; no LAN exposure.
2. **Direct internal IP / port:** `http://10.0.1.32:18000/admin` if the operator confirms the
   port may be exposed on the staging LAN.
3. **Reverse proxy (future):** nginx/Caddy in front of `18000` for a friendlier host/path.
4. **DNS / TLS (future, out of scope):** a staging hostname + certificate — needs more
   environment info + operator authorization.

## Internal IP / port option
Admin Console: `10.0.1.32:18000/admin`. Read-only operations APIs under the same origin
(`/operations/*`, `/health`).

## SSH port-forwarding option
Preferred for the first demo (no inbound port opened). Operator runs the `-L` forward from
their workstation; HTTP is acceptable for the first staging demo (operator to confirm).

## Reverse proxy option
Optional later: terminate HTTP(S) at a proxy and route `/admin` + `/operations/*`. Not
required for Step 64B.

## DNS / TLS future option
A staging DNS name + TLS cert is a future enhancement (Option C). Out of Step 64A/64B scope.

## Authentication / session assumptions
Admin Console pages are read-only visibility; controlled mutations (operator console, review
requests) reuse the existing operator auth + CSRF + audit. Staging assumes the existing
non-production operator-session model; no production auth/IdP is introduced.

## Access risks
Exposing `18000` on a shared LAN; weak operator-session assumptions; HTTP (no TLS) for the
first demo. Mitigations: prefer SSH port-forward, keep loopback binding, defer TLS to a
future option. See [staging-risk-and-safety-plan.md](staging-risk-and-safety-plan.md).

## Required operator confirmation
SSH username; password vs key-based access; whether sudo is allowed; whether Docker is
installed + group access; which ports may be exposed; browser reachability of `10.0.1.32`;
SSH-port-forward preference; HTTP acceptable for first demo; live GitHub/Slack/LLM remain
disabled. See [staging-information-request.md](staging-information-request.md).

---
_Staging only — non-production only. No production action. No production secret. No external write._

<!-- staging-safety: staging-only=true non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false -->
