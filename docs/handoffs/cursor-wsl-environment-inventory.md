# Cursor WSL Environment Inventory

Purpose: document the current observable WSL state from Codex, identify what is still unknown,
and recommend how Cursor should use a WSL environment that may already be shared by other local
developer agents.

This is read-only environment analysis. It does not authorize installing packages, stopping
processes, changing WSL settings, changing Docker state, modifying runtime code, or sharing secrets.

## Observed From Codex

Codex attempted a read-only WSL preflight from the current Windows host context.

Observed result:

| Check | Result |
| --- | --- |
| `wsl.exe --list --verbose` | Failed: WSL reported as not installed or unavailable in this Codex context. |
| `wsl.exe --status` | Failed with the same WSL unavailable result. |
| `wsl.exe uname -a` | Failed with the same WSL unavailable result. |
| `\\wsl$` filesystem access | No distribution listing available from this context. |
| Windows `wsl.exe` binary | Present. |
| Docker CLI on Windows host | Not found from this context. |
| SSH CLI on Windows host | Present. |
| Cursor CLI path indicator | Present in PATH. |

Interpretation:

- Codex can see the Windows `wsl.exe` binary, but cannot see a usable WSL distribution from its
  current execution context.
- This does not prove WSL is absent on the physical machine. It only proves the current Codex
  process cannot use or inspect it.
- If other local developer agents are already using WSL, they are likely running from a different
  user/session/context or from a WSL integration path that Codex cannot directly observe.

## Current Unknowns

These must be checked from inside the actual WSL environment used by Cursor or the other local
developer agents:

- Distribution name and version.
- Whether systemd is enabled.
- CPU, memory, disk availability.
- Whether Docker is local inside WSL or provided by Docker Desktop integration.
- Running containers, compose projects, ports, and volumes.
- Existing project checkouts and branch state.
- Existing local agents, editors, language servers, background watchers, and dev servers.
- Python, Node, npm, GitHub CLI, and shell tool versions.
- Whether repo dependencies are installed inside WSL.
- Whether any uncommitted work or local-only files exist in the WSL checkout.
- Whether ports required by Admin Console or platform services are already occupied.

## Safe WSL Inventory Commands

Run these from the real WSL terminal. Do not paste secrets or full private environment values into
shared documents.

### System

```bash
hostname
cat /etc/os-release
uname -a
whoami
pwd
df -h
free -h
nproc
```

### Toolchain

```bash
git --version
node --version
npm --version
python3 --version
docker --version
docker compose version
gh --version
```

### Repository

```bash
git rev-parse --show-toplevel
git remote -v
git status --short --branch
git branch --show-current
git log -1 --oneline
```

When sharing results, redact private remote URLs if any are not public.

### Running Processes

```bash
ps -eo pid,ppid,user,stat,comm,args --sort=comm | grep -Ei 'cursor|claude|codex|node|npm|vite|vitest|python|pytest|docker|compose|uvicorn|fastapi|redis|postgres' | grep -v grep
```

Share only process names, ports, and repo-relative working context. Do not share command arguments
that contain tokens, cookies, webhook URLs, or secrets.

### Ports

```bash
ss -ltnp
```

If output includes sensitive process arguments, summarize manually:

```text
3000/tcp - frontend dev server
5173/tcp - Vite dev server
8000/tcp - orchestrator/API
5432/tcp - postgres
6379/tcp - redis
```

### Docker

```bash
docker ps --format 'table {{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}'
docker compose ls
docker volume ls
docker network ls
```

Do not run `docker compose down`, remove volumes, prune images, or restart services during inventory.

### Frontend Baseline

```bash
cd apps/admin-console
npm ci
npm test
npm run typecheck
npm run build
```

### Python Baseline

```bash
cd "$(git rev-parse --show-toplevel)"
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
python3 -m pip install -r apps/orchestrator/requirements.txt
./scripts/run_tests.sh
```

If the WSL environment is shared, do not recreate `.venv` if another agent is actively using it.
Create an isolated task-specific venv path or clone instead.

## Usage Options

### Option A: Use Existing Shared WSL

Best when the WSL environment is stable, already has dependencies, and only one agent is actively
running verification at a time.

Advantages:

- Lowest setup cost.
- Closest to Cursor's likely local workflow.
- Good for fast frontend checks and small docs-only or UI-only tasks.

Risks:

- Other agents may have active watchers, dev servers, containers, or uncommitted files.
- Shared `.venv`, `node_modules`, Docker volumes, and ports can cause non-reproducible results.
- A destructive command could interrupt another agent's work.

Recommended guardrails:

- Use a separate repo clone for Codex/Cursor handoff work.
- Use branch-specific working directories.
- Do not reuse another agent's `.venv` for backend verification.
- Do not stop Docker containers unless the owner confirms they are idle.
- Record which commands were run and whether other agents were active.

### Option B: Use Existing WSL With Isolated Per-Agent Workspace

Best default if WSL is shared by multiple local agents.

Pattern:

```text
WSL distro shared
  ~/work/ai-agent-swd-cursor/     Cursor workspace
  ~/work/ai-agent-swd-claude/     Other local agent workspace
  ~/work/ai-agent-swd-codex/      Codex verification workspace, if needed
```

Advantages:

- Keeps setup cost low while avoiding most Git and dependency collisions.
- Allows each agent to keep its own `.venv`, `node_modules`, branches, and generated files.
- Still uses the same OS, Docker Engine, and network behavior.

Risks:

- Docker containers and ports remain shared.
- Host-level package changes still affect every workspace.
- Disk usage increases.

Recommended guardrails:

- Use unique compose project names when running Docker Compose.
- Use explicit ports or document when shared ports are occupied.
- Keep `.env` files local and untracked per workspace.
- Push shared outputs to GitHub rather than relying on cross-workspace local files.

### Option C: Create Independent Linux Environment

Best when repeatable CI-like validation, destructive tests, or long-running runtime checks are
needed.

Advantages:

- Cleanest reproducibility.
- Can be reset without disrupting local agents.
- Better for full Docker runtime, database migration, recovery, security, and end-to-end testing.

Risks:

- Higher setup and maintenance cost.
- Needs separate GitHub access, package mirrors, Docker, disk, and monitoring.
- Can become another environment to debug if not managed as CI/staging.

Recommended use:

- Not necessary for immediate Cursor frontend work.
- Strongly recommended before broader M1/M2/M4 integration work becomes routine.
- Required if agents need to run potentially disruptive compose, migration, restore, or long-running
  verification cycles.

## Recommendation

Use the existing WSL only after confirming its real state from inside WSL.

Recommended order:

1. Run the safe WSL inventory commands from the actual Cursor-accessible WSL terminal.
2. If other agents are active, use the same WSL distro but create an isolated per-agent repo clone
   and per-agent `.venv`.
3. Use WSL for daily Cursor development and fast frontend/backend verification.
4. Use the remote shared test runtime only for PR-level integration checks.
5. Add an independent Linux environment later for CI-like, destructive, long-running, or
   production-readiness validation.

Operational recommendation: do not let Codex directly use the shared WSL until Codex can see the
same WSL distribution and an owner confirms it will not collide with other active agents. For now,
Codex should treat WSL as an external environment and consume summarized inventory results through
shared repo docs or user-provided output.

## Readiness Decision

Current decision: `WSL_NOT_READY_FOR_CODEX_DIRECT_USE`.

Reason:

- Codex cannot currently enumerate or enter the WSL distribution.
- Other agents may already be using the WSL environment.
- The actual WSL process, Docker, port, and repo state are unknown.

Target decision after inventory:

```text
READY_FOR_CURSOR_DAILY_DEV
READY_FOR_PR_PREFLIGHT
NOT_READY_FOR_SHARED_RUNTIME_RESET
```

This target means Cursor can use WSL for ordinary development, but runtime resets, Docker cleanup,
database reset, and long-running integration tests should remain gated by explicit coordination.
