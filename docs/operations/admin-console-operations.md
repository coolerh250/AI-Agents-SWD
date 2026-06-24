# Admin Console Operations (Stage 50)

Read-only aggregate API + static serving for Admin Console v0. Everything here
is GET-only with no side effects.

## Static serving

The console is served by the orchestrator at **`/admin`** via a `StaticFiles`
mount (`apps/orchestrator/src/main.py`). It prefers `admin_console_static/dist`
(a built Vite bundle, copied into the image if present) and falls back to
`admin_console_static/index.html` (the committed zero-build static console). The
orchestrator Dockerfile copies `apps/admin-console/static/` into the image as
`admin_console_static/`, so `/admin` always responds.

No new docker-compose service and no Node runtime are required at runtime.

## Aggregate read-only endpoints

```
GET /operations/admin-console/overview
GET /operations/admin-console/projects
GET /operations/admin-console/projects/{project_id}
GET /operations/admin-console/latest-delivery-state
GET /operations/admin-console/safety-summary
GET /operations/admin-console/regression-summary
```

Each aggregates existing stores / `/operations/*` helpers defensively (a failing
source degrades to a safe default). They perform no DB / Redis write, trigger no
agent / build / delivery / approval, and contain no secrets or chain-of-thought.
The router exposes only GET/HEAD routes (asserted by
`tests/test_admin_console_no_side_effects.py`).

## /operations/safety fields (Stage 50)

`admin_console_enabled`, `admin_console_read_only` (true),
`admin_console_operator_actions_enabled` (false),
`admin_console_write_api_enabled` (false),
`admin_console_secret_redaction_enabled` (true).

## Feature flag

`ENABLE_ADMIN_CONSOLE` (default true) toggles `admin_console_enabled`. The
read-only / no-write / no-operator-action invariants are constant and not
env-toggleable in v0.

## Build (optional, when npm available)

```bash
cd apps/admin-console
npm install
npm run typecheck
npm run build     # -> apps/admin-console/static/dist (gitignored)
npm test
```

If npm is unavailable, the zero-build static fallback at `/admin` is used and
`verify_admin_console_v0.sh` runs deterministic source-level checks instead of a
build — the full platform regression remains unaffected.

## Verify + smokes

- `scripts/verify_admin_console_v0.sh` — Scenarios A–G. Marker:
  `ADMIN_CONSOLE_V0_VERIFY: PASS`. Scenario G chains
  `verify_delivery_package_acceptance_gate.sh` → full regression.
- `check_runtime_state.sh` smokes 230–242 cover service / build inputs / static
  serve / aggregate endpoints / read-only guard / no-secret / no-chain-of-thought
  / no-operator-action / no-write-API.

## Step 52.4 — read-only identity posture (Stage 54D)

13 GET-only `/operations/identity/*` endpoints + 35 `/operations/safety`
identity fields surface the Step 52 identity foundation (modeled, fail-closed,
not enabled). The Admin Console adds a read-only **Identity Posture** view
(`/identity`). No login/callback/token/connect/role-mapping-mutation/break-glass
endpoint or button; production identity not enabled. See
[identity-operations-api.md](../security/identity-operations-api.md) and
[identity-foundation-verification.md](identity-foundation-verification.md).

13 GET-only `/operations/secrets/*` endpoints back the read-only **Secret
Posture** view (`/secrets`); 17 GET-only `/operations/security/*` endpoints + 20
`/operations/safety` security/supply-chain fields back the read-only **Security /
Supply Chain** view (`/security`, Step 54.1). Neither view renders any mutation
control (no reveal/upload/run-scan/connect/configure/create-PR/push-image/gate).
See [security-supply-chain-verification.md](security-supply-chain-verification.md).

The Security view also renders a read-only **Local Scan Toolchain Baseline** section (Step
54.2) backed by `GET /operations/security/scans/status` (9 GET-only scan endpoints + 16
`/operations/safety` scan fields); no run-scan / upload / connect / configure control. Live scan
status degrades to `not_run` (runtime reports are never committed / not in the image). See
[security-scan-toolchain-verification.md](security-scan-toolchain-verification.md).

13 GET-only `/operations/security/{sbom,images}/*` endpoints + container/SBOM `/operations/safety`
fields back the read-only **SBOM / Image Digest / Container Security** section (Step 54.3) in the
Security view; no generate-SBOM / pull / scan / login / push / sign / attest control; SBOM /
image-policy status degrades to `not_run`. See
[sbom-container-security-verification.md](sbom-container-security-verification.md).
