# Controlled Workspace Safety (Stage 47)

The workspace operator runs deterministic code generation + local tests in a
tightly constrained sandbox. This document lists the safety rails.

## Workspace root allowlist

* Workspaces are created only under an allowlisted root:
  `/tmp/aiagents-workspaces` (default) or the repo-internal
  `.generated-workspaces/` (gitignored). Override via
  `WORKSPACE_OPERATOR_ALLOWED_ROOTS` (comma-separated).
* `validate_workspace_root` rejects: the empty string, the filesystem root
  `/`, the repo root, any path that would *contain* the repo root, and any
  path not under an allowlisted root.

## Path traversal prevention

* `safe_join` resolves each target with `os.path.realpath` and requires it to
  stay strictly under the validated workspace root. `..` segments, absolute
  paths, and `~` are rejected before joining.

## Symlink escape prevention

* Because `safe_join` resolves symlinks (`realpath`) before the containment
  check, a symlink inside the workspace pointing outside the root cannot be
  used to write outside it.

## No repo root write / no `.git` write / no secret files

* The repo root is never a valid workspace root.
* `is_disallowed_relpath` blocks any path segment named `.git`, `.env`,
  `secrets`, `.ssh`, names like `credentials.json` / `id_rsa` / `.npmrc` /
  `.pypirc` / `.netrc`, and suffixes `.key` / `.pem` / `.p12` / `.secret`.

## Allowed commands

* Only `python -m <module>` for `pytest`, `ruff`, `compileall`, `py_compile`.
* `shell=False` (argv list, never a shell string); no string interpolation
  into a shell; the working directory is pinned to a validated workspace root.

## Command timeout

* Every command runs with a mandatory timeout (default 120s); a timeout is
  classified `error`, never an indefinite hang.

## Output redaction

* All command stdout/stderr is passed through `redact()` (which masks
  GitHub PAT / OpenAI / Slack / AWS / private-key / token patterns and
  truncates) before it is persisted in a summary or artifact.

## No GitHub / PR / deploy / production execution

* `repo_write_enabled`, `github_write_enabled`, `deployment_enabled`,
  `real_llm_enabled`, and `production_executed` all default `false` and are
  surfaced on every result and on `/operations/safety`.
* `workspace.*` and `codegen.*` notification events are on the default
  real-delivery denylist — they never reach a real external channel.

## Generated files are never committed

* `.generated-workspaces/` and the Stage 28 `.workspaces/` roots are
  gitignored; the verifier checks `git status` carries no generated workspace
  files.
