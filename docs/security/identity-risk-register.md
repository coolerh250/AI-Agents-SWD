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
| no production approval identity chain | absent | high | 60 |
