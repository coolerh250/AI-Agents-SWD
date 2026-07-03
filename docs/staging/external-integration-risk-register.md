# External Integration Risk Register (Step 65B)

> **Staging only — non-production only. No production action. No production secret. No external write.**
> **Risk register / planning only — no integration enabled in this stage.**

Risks for enabling the in-scope staging external integrations (GitHub / notification / LLM / secret
backend), with likelihood, impact, mitigation, owner, and acceptance status.

| # | Risk | Likelihood | Impact | Mitigation | Owner | Acceptance |
|---|---|---|---|---|---|---|
| 1 | Secret value leaked (chat/repo/logs) | Low | High | out-of-band delivery to staging secret backend only; existence-only records; secret scan; never print `.env.staging.local` | Operator + Claude Code | Open |
| 2 | Live write to a production GitHub repo | Low | High | sandbox repo only; `GITHUB_DRY_RUN` kill switch; forbid merge/release/tag/protected-branch; verify target | Operator | Open |
| 3 | Notification to a production channel / real user | Low | High | test channel only; `[STAGING]` prefix; `RUN_REAL_DISCORD_TEST` kill switch; forbid DMs/customer sends | Operator | Open |
| 4 | LLM key misuse / unbounded spend | Med | High | non-prod key; bounded quota; per-run cap; `LLM_PROVIDER=mock` fallback; revoke | Operator | Open |
| 5 | Production key/data accidentally used | Low | High | non-production resources only; forbid production key/data; verify before enable | Operator | Open |
| 6 | LLM output triggers an unintended action | Med | High | human review + policy gates; no external write from LLM output alone; `production_executed_true_count=0` | Operator + Claude Code | Open |
| 7 | Integration left enabled after validation | Med | Med | kill switch per step; `/operations/safety` re-check returns `*_enabled=false` | Claude Code | Open |
| 8 | Scope creep to deferred integrations (registry/cloud) | Low | Med | deferred register; separate authorized step required | Operator | Open |
| 9 | Treating integration validation as production readiness | Low | High | acceptance criteria exclude production readiness | Operator | Open |
| 10 | Rate-limit / quota exhaustion disrupts staging | Low | Low | bounded sends/calls; single controlled action first | Claude Code | Open |

## Posture
Planning only. No integration enabled, no secret created, no external write, no runtime change, no
production action; `production_executed_true_count=0`.

---
_Staging only — non-production only. No production action. No production secret. No external write._

<!-- staging-safety: staging-only=true non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
