# External Integration User Input Checklist (Step 65B)

> **Staging only — non-production only. No production action. No production secret. No external write.**
> **Planning only — this lists what will be needed later; do NOT provide actual secrets in this stage.**

What the operator will need to provide/confirm for Step 65C–65F. **Do not send any secret value
now** — values are provided out-of-band at 65C and stored only in the staging secret backend.

## Needed later (not now)
| Item | For | Delivery method |
|---|---|---|
| GitHub sandbox repo name / URL | 65D | repo reference (non-production) |
| GitHub sandbox token delivery method | 65D | out-of-band into staging secret backend (never in chat/repo) |
| Notification platform (Slack / Discord / other) | 65E | operator choice |
| Staging channel name or webhook delivery method | 65E | out-of-band into staging secret backend |
| LLM provider | 65F | operator choice |
| LLM staging key delivery method | 65F | out-of-band into staging secret backend |
| LLM quota / budget limit | 65F | numeric limit |
| Preferred secret backend / approved staging secret store | 65C | env path or Vault-like (staging-only) |
| Credential owner | 65C | operator/named owner |
| Rotation owner | 65C | operator/named owner |

## Explicitly NOT to be provided in this stage
- Any actual token, key, webhook secret, or password value.
- Any production repo, channel, key, or secret.
- Any production data.

## Operator authorization required (per step)
- 65C: authorize sandbox credential setup.
- 65D: authorize GitHub sandbox write.
- 65E: authorize staging notification send.
- 65F: authorize LLM key usage + quota.
- 65G/65H: authorize the E2E run and each failure/governance scenario.
- 65I: give the staging functional acceptance verdict.

## Posture
Planning only. No secret requested/created, no integration enabled, no external write, no runtime
change, no production action; `production_executed_true_count=0`.

---
_Staging only — non-production only. No production action. No production secret. No external write._

<!-- staging-safety: staging-only=true non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
