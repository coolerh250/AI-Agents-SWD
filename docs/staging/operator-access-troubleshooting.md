# Operator Access Troubleshooting (Step 64E)

> **Staging only — non-production only. No production action. No production secret. No external write.**

Troubleshooting for operator access to the **staging** Admin Console (`10.0.1.32`). Collect
only **non-secret** diagnostics; never print or share secrets, `.env.staging.local`, tokens, or
private keys.

## SSH tunnel cannot connect
- Confirm you can reach the host: `ssh -i ~/.ssh/ai-agents-staging/staging_10_0_1_32 itadmin@10.0.1.32 'echo ok'`.
- Confirm the key is installed in `itadmin@10.0.1.32`'s `authorized_keys` (or use your own key —
  see [staging-operator-access-validation.md](staging-operator-access-validation.md)).
- Check network reachability to `10.0.1.32:22`.

## `localhost:18000` already in use
- Another tunnel/process holds the local port. Either close the stray tunnel, or forward to a
  different local port: `-L 18080:127.0.0.1:18000` and browse `http://localhost:18080/admin`.
- On Windows, a leftover `ssh.exe` can hold port 18000; identify it with `netstat -ano | find "18000"`
  and stop that PID.

## Admin Console does not load
- Confirm the tunnel session is still open.
- Check `http://localhost:18000/health` returns `200`.
- Try `http://localhost:18000/admin/` (with trailing slash); `/admin` 307-redirects to it.
- Clear the browser cache / try a private window.

## Health check fails
- On the host: `docker compose -p aiagents-staging -f infra/docker-compose/docker-compose.staging.yml --env-file infra/runtime/.env.staging.local ps`
  and confirm the orchestrator is `running (healthy)`.
- If a service is unhealthy, record the service name + status; do **not** rebuild images or
  install dependencies (out of scope) — escalate.

## Browser cache issue
- Hard-refresh (`Ctrl-Shift-R`) or use a private/incognito window.

## Runtime service unhealthy
- Read logs (non-secret) for the affected service:
  `docker compose … logs --tail=100 <service>`. Record the error class; do not paste secrets.
- A single-service restart (if clearly needed) is `docker compose … restart <service>` — but
  prefer to record + escalate rather than change runtime state.

## How to collect safe diagnostic information
- HTTP status codes (`/health`, `/admin`, `/operations/safety`).
- `docker compose … ps` output (service states).
- Selected **non-secret** safety fields (e.g. `production_executed_true_count`).

## What NOT to collect / share
- `.env.staging.local` contents, any password, token, private key, or kubeconfig.
- Raw logs that may contain secrets (scrub first, or share only summaries).

## Escalation
Record the symptom + non-secret evidence and escalate. Do not bypass auth, expose ports
publicly, or mutate production.

---
_Staging only — non-production only. No production action. No production secret. No external write._

<!-- staging-safety: staging-only=true non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
