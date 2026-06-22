# Identity Foundation Verification (Step 52.4)

How to verify the Step 52 identity foundation on the test server (10.0.1.31).
Verifier scripts import the identity SDK (pydantic), so run them under the
project venv (`.venv/bin/python`), not bare `python3`.

## Combined (recommended)

```bash
PYTHON=.venv/bin/python PATH="$PWD/.venv/bin:$PATH" \
  bash scripts/verify_identity_foundation_baseline.sh
```

Expected: `IDENTITY_FOUNDATION_BASELINE_VERIFY: PASS` (chains Step 52.1/52.2/52.3
baselines + the three Step 52.4 verifiers + tests + guards).

## Individual

```bash
.venv/bin/python scripts/verify_identity_operations_visibility.py   # IDENTITY_OPERATIONS_VISIBILITY_VERIFY
.venv/bin/python scripts/verify_admin_console_identity_posture.py   # ADMIN_CONSOLE_IDENTITY_POSTURE_VERIFY
.venv/bin/python scripts/verify_identity_safety_fields.py           # IDENTITY_SAFETY_FIELDS_VERIFY
```

The live verifiers require the orchestrator (`http://localhost:8000`) and a
rebuilt orchestrator image (the posture summary is copied in via the Dockerfile).

## Prior-stage + regression

```bash
bash scripts/verify_admin_console_v1_operator_actions.sh
bash scripts/verify_kubernetes_helm_argocd_baseline.sh
bash scripts/run_full_regression.sh --full --json-report
```

Must NOT run: OIDC discovery, JWKS fetch, IdP login, OAuth callback, token
exchange, kubectl, argocd, helm install/upgrade, production auth, production
action.
