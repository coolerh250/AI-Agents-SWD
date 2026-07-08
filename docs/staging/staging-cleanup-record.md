# Staging Cleanup Record (Step 66A.0)

> **Non-production only. No production action. No production secret. No production data.**
> **Scoped cleanup of the `aiagents-staging` validation runtime on `10.0.1.32` only.**

## 1. Scope & safety

- Host verified: `10.0.1.32` = `agentai-swd-stage` (hostname + `ip addr`).
- All destructive operations scoped to docker compose project **`aiagents-staging`** only.
- **No unscoped prune** was run: no `docker system prune -a`, no `docker volume prune`, no unscoped
  `rm -rf`. No `rm -rf /data`, no `rm -rf /home/itadmin`.
- The staging **repository** at `/data/ai-agents-staging/AI-Agents-SWD` was **not** deleted — it stays
  at `4e1b184` with all Step 65 docs preserved (all changes already committed + pushed to `origin/main`).

## 2. Inventory before cleanup

| Item | Count | Detail |
| --- | --- | --- |
| Containers (`aiagents-staging`) | 22 | all `Up … (healthy)` |
| Networks | 1 | `aiagents-staging_default` |
| Volumes | 5 | `alertmanager-staging-data`, `grafana-staging-data`, `postgres-staging-data`, `prometheus-staging-data`, `tempo-staging-data` |
| Repo HEAD | — | `4e1b184` (clean, = `origin/main`) |

## 3. `down --volumes` authorization (documented per §4.4)

`docker compose down --volumes` was authorized because all of the following held:

- The 5 volumes are **project-scoped to `aiagents-staging`** (matched by
  `label=com.docker.compose.project=aiagents-staging`).
- **No production data** — this is a staging validation environment; production was never deployed
  here.
- **No needed evidence remained only in the DB** — all Step 65 evidence is captured in committed
  `docs/staging/*.md` and `source/progress.md`, already pushed to `origin/main`.
- **All Step 65 docs are committed and pushed** (repo clean at `4e1b184`).

## 4. Cleanup command (scoped)

```
docker compose -p aiagents-staging \
  -f infra/docker-compose/docker-compose.staging.yml \
  --env-file infra/runtime/.env.staging.local \
  down --volumes --remove-orphans
```

## 5. State after cleanup (verified)

| Item | Count |
| --- | --- |
| Containers (`aiagents-staging`) | 0 |
| Networks (`aiagents-staging`) | 0 |
| Volumes (`aiagents-staging`) | 0 |

## 6. Staging secret residue removed (no contents printed)

| File | Tracked? | Action |
| --- | --- | --- |
| `infra/runtime/.env.staging.local` | untracked | removed (`rm -f`), verified gone |
| `infra/runtime/.mock-vault-secrets.local.json` | untracked / gitignored | removed, verified gone |

- **Secret values printed: no.** **Secret values committed: no.**
- `git status --short` on the staging repo after cleanup: clean (0 lines).
- Remaining `.local` residue in `infra/runtime/`: none.

## 7. Secret scan / follow-up

- No secret was echoed to the terminal, log, or commit during cleanup.
- External validation credentials (GitHub sandbox / Discord / Anthropic) used during Step 65:
  **operator should rotate/revoke**; not auto-revoked here; no external provider API called.

## 8. Related test-host runtime cleanup (10.0.1.31 — post-reset, 2026-07-08)

After the 66A.0 reset, a follow-up **Tier 1** cleanup removed obsolete, non-platform Docker artifacts
from the **test host `10.0.1.31`** (not staging). Operator authorized Tier 1 only; `cadvisor` kept.
This was **runtime-only** (no repo change); the `aiagents-test` platform stack was not touched.

Removed (all unrelated to the `aiagents-test` compose project):

| Item | Detail |
| --- | --- |
| `aiagents-smoke-control-plane` container | leftover single-node **kind** (Kubernetes-in-Docker) smoke-test node |
| `kindest/node:v1.31.2` image | 1.49 GB, only used by the removed kind node |
| `kind` docker network | only the kind node was attached |
| kind anonymous volume `455d5f9f…` | removed **by name** (held the kind node fs, ~3.6 GB) |
| `alpine:latest` image | unused (only inactive image) |
| build cache | `docker builder prune -f` (~226 MB) |

Scoped-safety notes:
- The kind volume was removed **by explicit name**, not via `docker volume prune` — after confirming
  the other three anonymous volumes belong to `aiagents-test-redis-1` and `aiagents-test-vault-1`
  (kept, verified intact after cleanup).
- No unscoped docker prune of images/containers/volumes; no `rm -rf`; unrelated `cadvisor` left running.
- Verified after: `aiagents-test` **27/27 healthy**, orchestrator `/health` ok.
- Reclaimed ≈ 5.5 GB (images 6.72→5.03 GB; volumes 3.80→0.18 GB; build cache freed).
- `production_executed_true_count=0` unaffected; no external action; no production action.

## 9. Plain statements (for verifier)

- Staging docker cleanup was scoped to the aiagents-staging project.
- No unscoped docker prune was used.
- Staging secrets were not printed and staging secrets were not committed.
- No production action occurred and no production data was touched.

---
_Non-production only. No production action. No production data._

<!-- staging-safety: staging-only=true non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
