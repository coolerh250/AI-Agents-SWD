# Identity Posture Visibility (Step 52.4)

Status: **modeled, fail-closed, NOT enabled.** The Step 52 identity foundation
(52.1 inventory/boundary + 52.2 OIDC abstraction + 52.3 session hardening / role
mapping) is now aggregated into a **read-only** posture surface.

## SDK

`shared/sdk/identity_posture/` (read-only, no network, no secrets):

| Module | Purpose |
|---|---|
| `collector.py` | Reads the committed Step 52.1/52.2/52.3 identity YAMLs and derives the posture; a missing source yields `status: unknown` (never a fake PASS). |
| `models.py` | Status enum: `modeled_fail_closed_not_enabled` / `failed` / `unknown` — there is **no** `production_identity_ready` / `oidc_enabled` status. |
| `report_builder.py` | Per-section views for the read-only API. |
| `safety.py` | Flat `/operations/safety` identity fields. |
| `redaction.py` | Secret / token / raw-email / GUID guard (reuses the Step 52.2 detector). |

The committed summary `infra/identity/identity-posture-summary.yaml` is anti-drift
tested (committed == rebuilt) and copied into the orchestrator image.

## Posture (current)

`status: modeled_fail_closed_not_enabled`, `productionIdentityReady: false`,
`productionAuthEnabled: false`. OIDC: abstraction present, not configured/enabled,
no discovery/JWKS fetch, no callback, no token exchange. Session: hardened, no raw
token, cleanup available, concurrency not enforced, key rotation not
production-ready. Role mapping: engine present, unconfigured, unknown user deny,
default role none, no platform_admin auto-grant. Break-glass: disabled.
platform_admin has no infrastructure authority; human acceptance ≠ deployment.

See [identity-operations-api.md](identity-operations-api.md),
[identity-safety-fields.md](identity-safety-fields.md), and
[identity-foundation-integrated-baseline.md](identity-foundation-integrated-baseline.md).
No production identity readiness is declared.
