# Test Environment Reset & Deployment Report (Step 66A.0)

> **Non-production only. No production action. No production secret. No production data.**
> **Test runtime on `10.0.1.31` reset and redeployed as the Step 66 development environment.**

## 1. Host verification

- Host: `10.0.1.31`, hostname `aiagent-swd`, confirmed via `hostname` + `ip addr` (`inet 10.0.1.31`).
- Repo: `/home/itadmin/AI-Agents-SWD` at `4e1b184` (= `origin/main`); `git pull --ff-only` =
  **Already up to date**. This is the intended test/development environment.

## 2. State before reset

- `aiagents-test` compose project: **32 defined services**, all containers **Exited (255)** ~7 days
  ago — a stale / broken test runtime (matches §4.6 "stale, inconsistent, or polluted by previous
  runs").
- Unrelated leftovers (left untouched — not part of `aiagents-test`, avoid touching unrelated
  projects): `aiagents-smoke-control-plane` (`kindest/node` Kubernetes-in-Docker node, binds only
  `6443→127.0.0.1`), `cadvisor` (healthy).
- Port `8000` (orchestrator health) was **free** before deploy.
- Uncommitted files were runtime artifacts only (`source/dr-reports/`, `source/regression-reports/`),
  disposable; canonical evidence preserved in git.

## 3. Reset (scoped to `aiagents-test`)

```
docker compose -p aiagents-test \
  -f infra/docker-compose/docker-compose.yml \
  down --volumes --remove-orphans
```

- After reset: **0 containers, 0 volumes** for `aiagents-test`.
- No unscoped prune; no `rm -rf`; unrelated docker projects untouched.
- Staging secret residue found on the test host removed (no contents printed):
  `infra/runtime/.env.staging.local`, `infra/runtime/.mock-vault-secrets.local.json` (both
  untracked).

## 4. Deployment (latest test runtime)

```
docker compose -f infra/docker-compose/docker-compose.yml config -q   # config OK
docker compose -f infra/docker-compose/docker-compose.yml up -d
```

- Repo already at latest `origin/main` (`4e1b184`); test runtime uses **Vault dev-mode** (in-memory,
  ephemeral) and Postgres `trust` auth — **no repository secrets required**, and external
  integrations are **disabled by default** (no GitHub/Discord/Anthropic tokens present).
- Result: **27/27 containers running, none problematic** (no `exited` / `unhealthy` / `restarting`).
- (32 defined − 27 running = profile-gated optional services not started under the default profile.)
- Note: images correspond to the current HEAD `4e1b184`; a full `--build` image refresh is
  **deferred to the first Step 66B implementation deploy** (which rebuilds the affected services
  anyway). This is a preparation baseline, not a production build.

## 5. Smoke validation

| Check | Result |
| --- | --- |
| `docker compose config -q` | OK |
| Containers running | 27/27, none problematic |
| Orchestrator `/health` | `{"service":"orchestrator","status":"ok"}` |
| `/operations/safety` reachable | yes |
| `production_executed_true_count` | 0 |

Full safety detail in `test-runtime-safety-validation.md`.

## 6. Blocker status

- No blocker. Test environment prepared and healthy. Marker eligible for **PASS** (not
  `PASS_WITH_GAPS`).

## 7. Plain statements (for verifier)

- Test runtime deployment completed on the verified test host 10.0.1.31.
- production_executed_true_count=0 on the test runtime.
- No production action occurred.
- No unscoped docker prune was used.
- No workflow was executed for product behavior.

---
_Non-production only. No production action. No production data._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
