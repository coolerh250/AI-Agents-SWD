# Real Integration Sandbox Pilot (Stage 32)

> Stage 32 wires the platform's real-Discord and real-GitHub adapters
> behind a strict, end-to-end-tested allowlist. The pilot is opt-in
> at every layer: env vars, per-request payload fields, and the
> ``shared.sdk.real_integration`` guard. The default posture is
> SANDBOX-ONLY and ALL real endpoints refuse with HTTP 409 until the
> operator explicitly enables them.
>
> **Stage 33 update (post Step 31R):** the
> ``notification-worker`` stream consumer now applies a separate
> real-delivery policy in addition to the Stage 32 endpoint guard. See
> [real-discord-delivery-policy.md](real-discord-delivery-policy.md)
> for the allowlist / denylist semantics. The endpoint guard described
> here is unchanged.
>
> **Stage 34 update:** the platform's `audit_logs` table is now backed
> by a tamper-evident hash chain (`audit_integrity_records`) so an
> operator can verify after the fact that no audit row was silently
> mutated. The chain is built automatically as audit rows land; an
> existing audit_logs table can be backfilled with
> `scripts/backfill_audit_integrity.sh`. See
> [tamper-evident-audit.md](tamper-evident-audit.md). The pilot
> guards and refusals described in this document are unchanged.

## Scope

Stage 32 covers exactly:

1. **Real Discord test channel** — one dedicated test guild + test
   channel, one bot token, one (optional) role.
2. **Real GitHub sandbox repo** — one dedicated sandbox repo, one
   fine-grained PAT scoped to it, files only under
   ``docs/github-real-test/``.

Stage 32 does **not** cover:

- Real LLM calls (the ``HARD_SAFETY_ACTIONS`` rail still refuses
  ``real_llm_network_call``).
- Production GitHub repo writes — even with the env set, the sandbox
  guard refuses any repo matching ``coolerh250/AI-Agents-SWD`` unless
  the pinned ``GITHUB_TEST_REPO`` carries a ``-sandbox`` / ``_sandbox``
  suffix.
- PR merges, branch-protection changes, releases, deployments, branch
  deletes, GitHub Actions workflow file mutation, or writes to
  ``.github/`` / ``infra/`` / ``migrations/`` / ``apps/`` / ``shared/``
  / ``scripts/`` / ``tests/``.
- Production deploys (``production_executed=true`` counters must stay
  at 0 in every environment).

## Required operator inputs

### Discord

| Variable | Required | Purpose |
|---|---|---|
| ``DISCORD_BOT_TOKEN`` | yes | Bot token for the pilot test bot. Stored only in env / Vault; never in repo, logs, or audit. |
| ``DISCORD_TEST_GUILD_ID`` | yes | The pinned guild every real call must target. |
| ``DISCORD_TEST_CHANNEL_ID`` | yes | The pinned channel every real call must target. |
| ``DISCORD_ALLOWED_ROLE_ID`` | optional | If present, every real-events caller must carry this role id. |
| ``RUN_REAL_DISCORD_TEST`` | yes | Literal string ``"true"`` (every other value keeps the guard refusing). |

### GitHub

| Variable | Required | Purpose |
|---|---|---|
| ``GITHUB_TOKEN`` | yes | Fine-grained PAT scoped to ``GITHUB_TEST_REPO`` ONLY. Must NOT carry ``Administration``, ``Workflows``, or ``Secrets`` write. |
| ``GITHUB_TEST_REPO`` | yes | Pinned sandbox repo (e.g. ``coolerh250/AI-Agents-SWD-sandbox``). MUST NOT equal the canonical production repo unless it carries a ``-sandbox`` / ``_sandbox`` suffix. |
| ``RUN_REAL_GITHUB_TEST`` | yes | Literal string ``"true"``. |

> The operator-input check script (``scripts/check_real_integration_inputs.sh``)
> reads each variable and prints PRESENT/ABSENT + length only. The
> value is never printed.

## Running in skipped mode (default test cluster)

This is the default on every machine that has not been given the env
vars. Every real-mode test exits with ``SKIPPED: PASS`` and the
master script ends ``REAL_INTEGRATION_PILOT_VERIFY: PASS``.

```bash
./scripts/check_real_integration_inputs.sh
./scripts/verify_real_discord_pilot.sh
./scripts/verify_real_github_sandbox_pilot.sh
./scripts/verify_real_integration_pilot.sh
```

Each script's last line carries the final marker the audit gate
asserts against (``REAL_DISCORD_PILOT_VERIFY: PASS`` /
``REAL_GITHUB_SANDBOX_PILOT_VERIFY: PASS`` /
``REAL_INTEGRATION_PILOT_VERIFY: PASS``).

## Running in real mode (opt-in)

> Real mode does NOT exist on the default test cluster. It is enabled
> by exporting the env vars in an isolated shell, running the verify
> script, and unsetting the env immediately afterwards.

```bash
export DISCORD_BOT_TOKEN=...                # NEVER paste into repo / chat
export DISCORD_TEST_GUILD_ID=...
export DISCORD_TEST_CHANNEL_ID=...
export RUN_REAL_DISCORD_TEST=true

./scripts/verify_real_discord_pilot.sh

unset DISCORD_BOT_TOKEN DISCORD_TEST_GUILD_ID DISCORD_TEST_CHANNEL_ID RUN_REAL_DISCORD_TEST
```

GitHub follows the same pattern with ``GITHUB_TOKEN`` /
``GITHUB_TEST_REPO`` / ``RUN_REAL_GITHUB_TEST``.

## Guards

### Discord -- ``shared.sdk.real_integration.discord.evaluate_real_discord_request``

| # | Check |
|---|---|
| 1 | ``DISCORD_BOT_TOKEN`` present |
| 2 | ``RUN_REAL_DISCORD_TEST=true`` |
| 3 | ``DISCORD_TEST_GUILD_ID`` present |
| 4 | ``DISCORD_TEST_CHANNEL_ID`` present |
| 5 | request ``channel_id`` equals ``DISCORD_TEST_CHANNEL_ID`` |
| 6 | request ``guild_id`` equals ``DISCORD_TEST_GUILD_ID`` (if supplied) |
| 7 | request ``role_id`` equals ``DISCORD_ALLOWED_ROLE_ID`` (if pinned) |
| 8 | ``mode == "controlled_test"`` |
| 9 | ``production_executed`` is the literal ``False`` |

Any failure is HTTP 409 + structured ``safety_guard_result``
(``allowed`` / ``reason`` / ``target_channel`` / ``target_guild`` /
``details``). The token value is never returned, never logged.

### GitHub -- ``shared.sdk.real_integration.github.evaluate_real_github_sandbox_request``

| # | Check |
|---|---|
| 1 | ``GITHUB_TOKEN`` present |
| 2 | ``RUN_REAL_GITHUB_TEST=true`` |
| 3 | ``GITHUB_TEST_REPO`` present |
| 4 | request ``repo`` equals ``GITHUB_TEST_REPO`` |
| 5 | ``repo`` is not the canonical production repo (unless suffixed sandbox) |
| 6 | intent NOT in ``{merge, branch_protection, release, deployment, delete_branch, workflow_secret}`` |
| 7 | ``dry_run`` is the literal ``False`` |
| 8 | branch name starts with ``ai-agents-test/`` |
| 9 | PR title starts with ``[AI-Agents-SWD Test]`` |
| 10 | ``file_path`` does NOT start with any forbidden prefix (``.github/`` / ``infra/`` / ``migrations/`` / ``apps/`` / ``shared/`` / ``scripts/`` / ``tests/`` / ``docs/operations/``) |
| 11 | ``file_path`` starts with ``docs/github-real-test/`` |

The Stage 32 sandbox guard runs **before** the existing Stage 23
``real_guard.evaluate_real_test_request``. A failure of either
returns HTTP 409 + a structured ``safety_guard_result``.

## Audit / Notification

| decision_type | When |
|---|---|
| ``discord_real_test_sent`` | real Discord test message delivered |
| ``discord_real_test_blocked`` | guard refused a real Discord send |
| ``discord_real_task_received`` | real Discord controlled-test event accepted by ``/discord/real/events/test`` |
| ``discord_real_task_blocked`` | guard refused a real Discord task |
| ``github_sandbox_pr_created`` | sandbox-repo PR opened |
| ``github_sandbox_guard_failed`` | Stage 32 pre-guard refused the request |
| ``github_real_test`` / ``github_real_test_blocked`` / ``github_real_test_failed`` | Stage 23 markers retained for backwards compatibility |

| notification event_type | When |
|---|---|
| ``discord.real_test_sent`` | real Discord test message delivered |
| ``discord.real_task_received`` | real Discord task accepted |
| ``github.sandbox_pr.created`` | sandbox-repo PR opened |
| ``github.real_test_pr.created`` | Stage 23 mirror (retained for backwards compatibility) |

Every artifact_refs entry carries ``production_executed=false`` and
``test_mode=true``; ``token`` / ``Authorization`` fields are never
present.

## Operations view

- ``GET /operations/real-integrations`` — combined snapshot (inputs +
  Discord + GitHub + counters + warnings)
- ``GET /operations/real-integrations/discord`` — Discord slice
- ``GET /operations/real-integrations/github`` — GitHub slice
- ``GET /operations/safety`` — booleans:
  ``real_discord_inputs_present`` / ``real_discord_test_enabled`` /
  ``real_discord_target_channel_configured`` /
  ``real_discord_guard_active`` / ``real_github_inputs_present`` /
  ``github_test_repo`` / ``github_sandbox_guard_active`` /
  ``real_llm_enabled`` / ``production_deploy_enabled``.
- ``/operations/summary.real_integration_summary`` — counters for the
  dashboard.

## Rollback / cleanup

If a sandbox PR was opened in real mode and needs to come down:

```bash
gh pr close <number> --delete-branch --repo $GITHUB_TEST_REPO
```

If a Discord test message needs to be retracted:

- Manually delete the message in the Discord client.
- No platform-side delete endpoint is provided (real-Discord writes
  are limited to one POST per call by design).

## No-Go items (must NOT be done in Step 31 or before architect approval)

- Pointing ``GITHUB_TEST_REPO`` at the canonical production repo.
- Granting the PAT any scope other than ``Contents: write`` /
  ``Pull requests: write`` / ``Issues: write`` on the sandbox repo.
- Setting ``ENABLE_REAL_LLM_NETWORK_CALL=true``.
- Manually merging a sandbox PR via the platform; PR merge is a hard
  safety action.
- Re-using the test bot token in any production-bound bot.
- Storing any of these env vars in repo / logs / progress.md /
  README / API response.
