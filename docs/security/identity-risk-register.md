# Identity Risk Register (Step 52.1 / Stage 54A)

Source: [identity-risk-register.yaml](../../infra/identity/identity-risk-register.yaml).

| Risk | Current state | Severity | Follow-up |
| --- | --- | --- | --- |
| test-local auth not production-grade | accepted for test | high | 52.2 / 52.3 |
| production OIDC disabled | fail-closed; abstraction added (52.2), still disabled/unconfigured | high | 52.3 |
| production secret store absent | not configured | high | 53 |
| session key rotation not productionized | model added (52.3), still gap | medium/high | 53 |
| group→role mapping absent | engine + policy added (52.3), unconfigured (placeholder fixtures only) | high | production auth |
| platform_admin naming confusion | controlled; authorization-decision model documents platform_admin ≠ infrastructure admin | medium | — |
| no MFA signal | external IdP future | medium | 52.2 |
| no device posture | future | medium | later |
| no production break-glass model | model added (52.3), disabled pending production approval | high | 60 |
| session cleanup / concurrency / forced logout gaps | cleanup utility + models added (52.3); concurrency/forced-logout enforcement deferred | medium | production auth |

## Step 52.4 (Stage 54D) — Step 52 closed

Step 52 closes as **modeled, fail-closed, not enabled**. A read-only identity
posture surface ([identity-posture-visibility.md](identity-posture-visibility.md))
aggregates the risks above and exposes them via `/operations/identity/*` +
`/operations/safety` + the Admin Console Identity Posture view — observation
only, no mutation. All high/medium risks above remain open and gated on Step 53
(production secret store) and Step 60 (production approval identity chain);
production identity is not declared ready.
| no production approval identity chain | absent | high | 60 |
