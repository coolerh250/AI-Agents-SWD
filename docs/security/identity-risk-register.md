# Identity Risk Register (Step 52.1 / Stage 54A)

Source: [identity-risk-register.yaml](../../infra/identity/identity-risk-register.yaml).

| Risk | Current state | Severity | Follow-up |
| --- | --- | --- | --- |
| test-local auth not production-grade | accepted for test | high | 52.2 / 52.3 |
| production OIDC disabled | fail-closed | high | 52.2 |
| production secret store absent | not configured | high | 53 |
| session key rotation not productionized | gap | medium/high | 52.3 / 53 |
| group→role mapping absent | gap | high | 52.3 |
| platform_admin naming confusion | controlled | medium | 52.3 |
| no MFA signal | external IdP future | medium | 52.2 |
| no device posture | future | medium | later |
| no production break-glass model | absent | high | later |
| no production approval identity chain | absent | high | 60 |
