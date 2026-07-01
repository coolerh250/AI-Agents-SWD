# Operator Safety Check Guide (Step 64E)

> **Staging only — non-production only. No production action. No production secret. No external write.**

How an operator confirms the **staging** safety posture. Read via the Safety Posture page
(`/safety`) or the `GET /operations/safety` endpoint (through the SSH tunnel). All checks are
read-only.

## How to read the safety endpoint
Through the tunnel: `http://localhost:18000/operations/safety` (or the Safety Posture page).
Confirm each of the following.

| Check | Expected value | Field |
|---|---|---|
| No production execution | `0` | `production_executed_true_count` |
| No production deployment env | `0` | `deployment_environment_production_count` |
| No production workflow execution | `0` | `workflow_production_executed_true_count` |
| Production deploy disabled | not enabled | (no production deploy toggle true) |
| Production sync disabled | not enabled | (no production sync toggle true) |
| Production secret absent | mock-vault / dev | `SECRET_PROVIDER=mock-vault` |
| Live GitHub write disabled | `false` | `github_external_write_enabled` |
| Real GitHub test disabled | `false` | `real_github_test_enabled` |
| Live Slack/Discord send disabled | `false` | `discord_external_send_enabled` |
| Discord token absent | `false` | `discord_has_token` |
| Live LLM call disabled/mocked | 0 LLM interactions | LLM interactions count |
| External write disabled | none | (no external write) |
| Public exposure absent | loopback + SSH tunnel only | port 18000 bound `127.0.0.1` |

## Note on `github_has_token`
`github_has_token=true` may appear, but it is a **sandbox/mock** token from the mock-vault
fixture. Because `github_external_write_enabled=false` and `real_github_test_enabled=false`, **no
live GitHub write can occur.** This is a limitation, not a live integration.

## Green result
The staging safety posture is green when `production_executed_true_count=0` and all live-write
toggles are false. This is the current state.

## If a check is not green
Do not attempt a fix or bypass. Record the field + value and escalate per
[operator-access-troubleshooting.md](operator-access-troubleshooting.md).

## Safety
No production action; no production secret; live integrations disabled/mocked; no public
exposure; `production_executed_true_count=0`.

---
_Staging only — non-production only. No production action. No production secret. No external write._

<!-- staging-safety: staging-only=true non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
