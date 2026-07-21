# Codex to Cursor Environment Readiness

Purpose: define the minimum reproducible verification baseline before moving day-to-day
development from Codex to Cursor.

This is a process and environment handoff only. It does not authorize runtime code changes,
deployment, production action, external integration changes, credential sharing, or secret
storage.

## Summary

Cursor should be treated as a new developer workstation until it proves the same verification
commands can run from a clean checkout. The product architecture does not need to be re-reviewed
only because the IDE changes, but the execution environment does need a reproducibility check.

Recommended result before Cursor starts implementation: `READY_WITH_GAPS`.

Current gaps are environmental:

- Python is not available in the current Codex host shell, so backend and cross-cutting pytest
  verification cannot be reproduced there.
- Docker is not available in the current Codex host shell, so local compose runtime verification
  cannot be reproduced there.
- PowerShell blocks direct `npm` script invocation in the current Codex host shell; `npm.cmd`
  works.
- Vite/Vitest can fail under restricted filesystem sandbox permissions even when the same commands
  pass in a normal developer shell.

## Source of Truth

Cursor should begin from the GitHub source of truth, not from local Codex scratch state.

Minimum checkout procedure:

```bash
git checkout main
git pull --ff-only origin main
git status --short --branch
```

Branch rules:

- Create a fresh task branch from latest `origin/main` unless a Product Owner or engineering lead
  gives an explicit branch name.
- Do not base new implementation on local-only Codex files.
- Do not commit local scratch folders, generated build metadata, logs, screenshots, credentials,
  `.env` files, or machine-specific settings.

Known local-only items to ignore unless separately reviewed:

- `.tools/`
- `docs/product/platform-progress-admin-console-proposal.md`

## Required Tooling

### Frontend

Cursor must support:

- Node.js compatible with the Admin Console dependency set.
- npm command execution from `apps/admin-console`.
- Vite, Vitest, TypeScript, React, and React Router from the committed package lock.

Observed Codex frontend baseline:

| Tool | Observed result |
| --- | --- |
| Node.js | `v24.15.0` |
| npm | `11.12.1` via `npm.cmd` |
| Admin Console tests | 17 test files passed, 137 tests passed |
| Admin Console typecheck | Passed |
| Admin Console build | Passed |

Recommended Cursor check:

```bash
cd apps/admin-console
npm ci
npm test
npm run typecheck
npm run build
```

On Windows PowerShell, if direct `npm` is blocked by execution policy, use:

```powershell
npm.cmd test
npm.cmd run typecheck
npm.cmd run build
```

### Python and Backend Verification

Cursor must support:

- Python 3.12 compatible with `pyproject.toml`.
- A repo-local virtual environment.
- Dependencies from `requirements.txt` and `apps/orchestrator/requirements.txt`.
- `pytest`, `pytest-asyncio`, `ruff`, `black`, and `mypy`.

Recommended setup:

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
python3 -m pip install -r apps/orchestrator/requirements.txt
./scripts/run_tests.sh
```

The repository already provides `scripts/lib/verify_env.sh` for verification scripts. Cursor should
prefer that helper for stage verification because it resolves `.venv`, avoids host dependency leaks,
and avoids printing secret values.

### Docker Runtime

Cursor needs Docker only when validating integration/runtime behavior.

Required capability:

- Docker Engine and Docker Compose v2.
- Ability to run the local/test compose runtime.
- Ability to bind local service ports.
- Ability to run shell scripts under a Linux-compatible shell.

Recommended runtime checks:

```bash
docker compose -f infra/docker-compose/docker-compose.yml config
docker compose -f infra/docker-compose/docker-compose.yml up -d
docker compose -f infra/docker-compose/docker-compose.yml ps
./scripts/init_local_runtime.sh
./scripts/check_runtime_state.sh
docker compose -f infra/docker-compose/docker-compose.yml down
```

Use only a non-production test runtime. Do not place hostnames, addresses, tokens, passwords, or
private URLs in committed handoff notes.

## Verification Baseline

Cursor should reproduce these baseline commands before accepting implementation work:

| Area | Command | Expected baseline |
| --- | --- | --- |
| Git state | `git status --short --branch` | Clean except explicitly known local-only files |
| Frontend install | `npm ci` from `apps/admin-console` | Completes without lockfile drift |
| Frontend tests | `npm test` from `apps/admin-console` | Passes current Vitest suite |
| Frontend typecheck | `npm run typecheck` from `apps/admin-console` | Passes |
| Frontend build | `npm run build` from `apps/admin-console` | Passes |
| Python tests | `./scripts/run_tests.sh` | Passes or reports documented runtime skips |
| Compose config | `docker compose -f infra/docker-compose/docker-compose.yml config` | Valid |
| Runtime state | `./scripts/check_runtime_state.sh` | Passes against non-production runtime |
| Whitespace | `git diff --check` | Passes |
| Secret scan | Project-approved scanner or grep-based fallback | No committed secrets |

If Cursor cannot run the Python or Docker baseline locally, use the shared test runtime and record
which commands were verified there. Do not mark backend/runtime validation complete based only on
frontend checks.

## Current Codex Verification Notes

Commands that passed in the current Codex environment:

```text
apps/admin-console: npm.cmd test
apps/admin-console: npm.cmd run typecheck
apps/admin-console: npm.cmd run build
```

Command behavior observed:

- Direct `npm` invocation from PowerShell failed because script execution was disabled.
- `npm.cmd` avoided that Windows-specific wrapper issue.
- `npm test` and `npm run build` failed inside restricted filesystem sandbox permissions because
  Vite/Vitest could not read required config paths.
- The same frontend test and build commands passed when run with normal filesystem permissions.
- Python and Docker commands were not available in the current host shell.

This means Cursor should validate from a normal developer terminal, not from a restricted shell that
prevents Vite, Vitest, Docker, or Python from reading required workspace files.

## Environment Variables and Secrets

Cursor setup may require environment variables for local/test services, but no secret values should
be committed or pasted into shared documents.

Rules:

- Keep `.env` files untracked.
- Use documented variable names without values in handoff notes.
- Use redacted examples only.
- Never store API tokens, passwords, session cookies, private keys, webhook secrets, or provider
  credentials in source control.
- Keep test-role local storage limited to non-secret frontend simulation state until production auth
  replaces it.

## Cursor-Specific Risks

1. Auto-formatting can create unrelated diffs.
   - Disable broad format-on-save until the repository formatting standard is confirmed.

2. Line endings can drift between Windows and Linux.
   - Check `git diff --check` and review staged files before commit.

3. Cursor may run commands from the wrong working directory.
   - Frontend commands must run from `apps/admin-console`; repo-wide Python scripts run from the
     repository root.

4. Generated build metadata can appear after `tsc -b`.
   - Do not commit generated metadata unless a task explicitly changes it.

5. Python dependencies can leak from the host.
   - Prefer `.venv` and `scripts/lib/verify_env.sh`.

6. Docker runtime validation can accidentally point at the wrong environment.
   - Use only non-production runtime configuration and verify safety flags before running mutable
     checks.

7. GitHub CLI credentials may be present locally.
   - Use them only for branch, push, and Draft PR work authorized by the task; do not extract or
     document credentials.

## Cursor Preflight Checklist

Before Cursor starts implementation:

- [ ] Fresh checkout from latest `origin/main`.
- [ ] Clean branch created for the task.
- [ ] `apps/admin-console/npm ci` completes without lockfile drift.
- [ ] Frontend `npm test`, `npm run typecheck`, and `npm run build` pass.
- [ ] Python `.venv` is created and `./scripts/run_tests.sh` runs or has documented skips.
- [ ] Docker Compose config validates.
- [ ] Non-production runtime health check passes when runtime work is needed.
- [ ] `git diff --check` passes.
- [ ] Secret scan passes.
- [ ] Cursor settings do not auto-format unrelated files.
- [ ] Known local-only files remain untracked and are not included in commits.

## Recommended First Cursor Task

Run a no-runtime-code readiness PR before feature work:

1. Clean checkout and branch from latest `origin/main`.
2. Install frontend and Python dependencies.
3. Run frontend tests, typecheck, and build.
4. Run Python and runtime verification where available.
5. Document any environment gaps in `docs/handoffs/`.

Only after that should Cursor take implementation work.
