# Cursor WSL and Codex Collaboration Workflow

> Process documentation only. No backend/frontend runtime change. No production action.

This document defines the adopted local development workflow after moving day-to-day
implementation to Cursor with local WSL, while keeping Codex in a repository and GitHub
collaboration role.

## Decision

Adopt Option 1:

```text
Cursor uses local WSL for daily development and local verification.
Codex does not directly attach to Cursor's WSL distro.
Codex collaborates through GitHub branches, shared repo documents, reviews, and Windows-side checks.
```

Reason:

- Cursor can connect to the local `Ubuntu-24.04` WSL distro.
- Codex currently runs under a sandbox user/context that cannot see the same WSL distro.
- WSL distro registration is per Windows user/context.
- Directly sharing one mutable WSL workspace between agents risks collisions in Git state,
  `.venv`, `node_modules`, Docker containers, ports, and generated files.

## Responsibilities

| Actor | Primary environment | Responsibilities |
| --- | --- | --- |
| Cursor | Local `Ubuntu-24.04` WSL | Day-to-day implementation, local Linux commands, frontend tests, Python tests, Docker checks when safe. |
| Codex | Repo workspace and GitHub | Code review, architecture analysis, docs, PR/handoff artifacts, Windows-side frontend checks, non-WSL validation. |
| Remote shared test runtime | Non-production Linux runtime | PR-level integration checks, API/runtime smoke tests, compose/service validation, cross-agent verification. |

## Source of Truth

GitHub remains the source of truth.

Rules:

- Shared deliverables must be committed to the repository and pushed to a branch or Draft PR.
- Local-only notes, WSL scratch files, Cursor workspace settings, logs, screenshots, and generated
  artifacts are not deliverables.
- Do not copy files between Cursor WSL and Codex local workspaces as the primary collaboration path.
  Use Git branches, commits, Draft PRs, and shared docs.
- Do not commit internal hostnames, private URLs, credentials, tokens, `.env` values, SSH aliases,
  or screenshots containing secrets.

## Cursor WSL Workflow

Cursor should use the local WSL distro for implementation work.

Recommended starting point for each task:

```bash
git checkout main
git pull --ff-only origin main
git checkout -b <task-branch>
git status --short --branch
```

Recommended baseline checks:

```bash
cd apps/admin-console
npm ci
npm test
npm run typecheck
npm run build
```

For backend or repository-wide verification:

```bash
cd "$(git rev-parse --show-toplevel)"
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
python3 -m pip install -r apps/orchestrator/requirements.txt
./scripts/run_tests.sh
```

Runtime checks should be coordinated before starting or stopping shared services:

```bash
docker compose -f infra/docker-compose/docker-compose.yml config
```

Do not run destructive runtime commands, volume cleanup, database reset, or service shutdown if
another agent or developer may be using the same WSL/Docker runtime.

## Codex Workflow

Codex should not assume direct WSL access.

Codex may:

- Review code and architecture from the repository workspace.
- Produce or update shared documentation.
- Create branches, commits, pushes, and Draft PRs when explicitly in scope.
- Run Windows-side frontend checks when dependencies and sandbox permissions allow.
- Use the remote shared test runtime for Linux validation when authorized.
- Inspect PRs, diffs, route maps, API clients, frontend tests, and docs.

Codex should not:

- Attempt to attach to Cursor's WSL distro as part of normal development.
- Modify Cursor's WSL workspace directly.
- Stop WSL services, Docker containers, or ports owned by Cursor or another agent.
- Treat Codex's inability to see WSL as a product failure.
- Mark Linux/runtime verification complete based only on Codex Windows checks.

## Handoff Between Cursor and Codex

When Cursor implements work:

1. Cursor commits changes to the task branch.
2. Cursor pushes the branch to GitHub.
3. Cursor records verification results in shared docs when required by the step.
4. Codex reviews the pushed branch/PR, not Cursor's local WSL files.
5. Codex records findings, gaps, or handoff notes in repo paths.

When Codex prepares work for Cursor:

1. Codex creates or updates shared docs in repo paths.
2. Codex pushes a branch or Draft PR if the output must be reviewed.
3. Cursor pulls the branch into WSL.
4. Cursor runs Linux-local verification before implementation continues.

## Verification Ownership

| Verification type | Owner | Environment |
| --- | --- | --- |
| Frontend unit tests | Cursor first, Codex optional | Cursor WSL, Codex Windows if available |
| Frontend build/typecheck | Cursor first, Codex optional | Cursor WSL, Codex Windows if available |
| Python tests | Cursor or remote runtime | Cursor WSL or remote shared test runtime |
| Docker Compose config | Cursor or remote runtime | Cursor WSL or remote shared test runtime |
| Full runtime smoke | Remote runtime preferred | Non-production shared test runtime |
| Product Owner preview | Remote/runtime preview owner | Non-production preview/runtime |
| Security/secret scan | Task owner, reviewed by Codex/Claude Code | WSL or remote runtime |

## Branch and PR Rules

- Start implementation branches from latest `origin/main` unless instructed otherwise.
- Keep branches task-scoped.
- Use Draft PRs for shared review before merge.
- Do not merge without Product Owner or integration owner approval.
- Codex and Cursor should not both push to the same branch at the same time without coordination.
- If both need to work on the same branch, one actor should finish and push before the other pulls.

## Environment Safety

Cursor WSL is a development environment, not production.

Allowed by default:

- `git status`, `git diff`, `git pull --ff-only`, `git checkout -b`.
- `npm test`, `npm run typecheck`, `npm run build`.
- `pytest` and verify scripts that are documented as non-production and non-destructive.
- Docker Compose `config` and read-only inspection commands.

Requires explicit coordination:

- Starting long-running dev servers.
- Starting or stopping Docker Compose services.
- Running migrations against shared test data.
- Resetting databases, Redis streams, volumes, or generated artifacts.
- Any command that writes outside the task workspace.

Forbidden without explicit approval:

- Production deploys or production sync.
- External writes to real integrations.
- Secret extraction or credential sharing.
- Destructive cleanup of shared Docker volumes or WSL workspaces.
- Committing `.env`, tokens, private keys, session files, or local machine-specific config.

## Current Status

```text
Cursor local WSL: usable for daily development after user-side confirmation.
Codex direct WSL visibility: unavailable in current sandbox context.
Adopted collaboration model: Cursor WSL + Codex GitHub/repo collaboration.
Remote shared test runtime: reserved for PR-level integration verification.
```

## Review Triggers

Revisit this workflow if any of the following changes:

- Codex gains direct access to the same WSL distro under the same user context.
- Cursor and Codex need to run concurrent Linux commands against the same workspace.
- Docker runtime validation becomes frequent enough to require a dedicated local or remote runner.
- M1/M2/M4 implementation begins requiring routine full-stack verification.
- A formal CI runner or independent Linux staging environment is introduced.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets in docs, examples, screenshots, or validation evidence._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
