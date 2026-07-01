# Staging Admin Console Exposure Report (Step 64C)

> **Staging only — non-production only. No production action. No production secret. No external write.**
> **No public exposure — access is via SSH local port-forward only. Live integrations disabled/mocked.**

Overall result: **PASS**. The staging Admin Console on `10.0.1.32` (`agentai-swd-stage`) is
reachable and browsable via the SSH local port-forward access path; the port-forward was
validated end-to-end from a client host holding the staging key, and the **operator has
confirmed** they can open the read-only Admin Console page from their own workstation through
the approved SSH port-forward path (`http://localhost:18000/admin`).

## Runtime status (re-validated)
- **Target host:** `10.0.1.32`; repo `/data/ai-agents-staging/AI-Agents-SWD` at `f43e163`.
- **Runtime:** running — **22/22 containers** (`docker compose -p aiagents-staging … ps`).
- `GET /health` → **200**; `GET /admin` → 307 → `/admin/` → **200** ("Admin Console v0 —
  read-only"); `GET /operations/safety` → **200**, `production_executed_true_count=0`.

## Operator access path
- **Method:** SSH local port-forward + HTTP (loopback-only; **no public exposure**).
- **Command:**
  `ssh -i ~/.ssh/ai-agents-staging/staging_10_0_1_32 -L 18000:127.0.0.1:18000 itadmin@10.0.1.32`
- **Operator URL:** `http://localhost:18000/admin`
- **End-to-end validation:** a fresh SSH `-L 18000:127.0.0.1:18000` tunnel was established from a
  client host; through it `localhost:18000/health` → 200, `localhost:18000/admin` → 200
  ("Admin Console v0 — read-only"), `localhost:18000/operations/safety` → 200. The tunnel was
  torn down afterward and local port 18000 freed. **Operator workstation access: confirmed** —
  the operator opened the read-only Admin Console page successfully. See
  [staging-operator-access-validation.md](staging-operator-access-validation.md).

## Read-only API dependencies (probed on host, all 200)
`/operations/summary`, `/operations/agents`, `/operations/safety`, `/operations/metrics/overview`,
`/operations/readiness/overview`, `/operations/readiness/controlled-rollout/policy`,
`/operations/release/overview`, `/operations/dr/overview`,
`/operations/github/sandbox-draft-pr/safety`, `/operations/runtime/kubernetes/baseline`,
`/operations/security/foundation`, `/operations/identity/posture`, `/operations/secrets/foundation`.
Full page → route → API mapping: [staging-admin-console-page-inventory.md](staging-admin-console-page-inventory.md).

## Mutation gating (non-destructive check)
Operator mutation is gated in staging. An unauthenticated `POST /operations/readiness/operator-review-requests`
returned HTTP 200 with an application-level **`status=policy_blocked`, `reason=operator_actions_disabled`,
`production_executed=false`** — **no record was created**, and the safety counters
(`production_executed_true_count`, `deployment_environment_production_count`) stayed 0. Operator
actions are disabled by default in staging; mutation pages cannot change runtime/production state.

## Safety endpoint summary
- `production_executed_true_count = 0`; `deployment_environment_production_count = 0`;
  `workflow_production_executed_true_count = 0`.
- `github_external_write_enabled=false`, `real_github_test_enabled=false`;
  `discord_external_send_enabled=false`; LLM live disabled/mocked.

## Known gaps
See [staging-admin-console-known-gaps.md](staging-admin-console-known-gaps.md) (operator
workstation confirmation pending; per-page endpoints not all individually probed; Vault
dev/mock-vault; HTTP-only; no screenshots committed).

## Explicit statements
- **No public exposure** — port `18000` is loopback-only; access is via SSH tunnel only.
- **No production action / secret / external write; live integrations disabled/mocked.**
- `production_executed_true_count=0`. **Claude Code does not decide production readiness.**

---
_Staging only — non-production only. No production action. No production secret. No external write._

<!-- staging-safety: staging-only=true non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
