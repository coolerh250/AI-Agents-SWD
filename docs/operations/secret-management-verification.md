# Secret Management Verification (Step 53)

Run on the test server (10.0.1.31). Verifier scripts import the secrets SDK
(pydantic) — run under the project venv (`.venv/bin/python`), not bare python3.

## Combined (recommended)

```bash
PYTHON=.venv/bin/python PATH="$PWD/.venv/bin:$PATH" \
  bash scripts/verify_secret_management_foundation_baseline.sh
```

Expected: `SECRET_MANAGEMENT_FOUNDATION_BASELINE_VERIFY: PASS` (chains the Step 51
+ Step 52 integrated baselines + the nine secret verifiers + targeted tests +
safety posture).

## Individual

```bash
.venv/bin/python scripts/verify_secret_inventory.py            # SECRET_INVENTORY_VERIFY
.venv/bin/python scripts/verify_secret_reference_schema.py     # SECRET_REFERENCE_SCHEMA_VERIFY
.venv/bin/python scripts/verify_secret_store_abstraction.py    # SECRET_STORE_ABSTRACTION_VERIFY
.venv/bin/python scripts/verify_secret_no_inline_values.py     # SECRET_NO_INLINE_VALUES_VERIFY
.venv/bin/python scripts/verify_secret_rotation_model.py       # SECRET_ROTATION_MODEL_VERIFY
.venv/bin/python scripts/verify_secret_redaction_policy.py     # SECRET_REDACTION_POLICY_VERIFY
.venv/bin/python scripts/verify_secret_operations_visibility.py   # SECRET_OPERATIONS_VISIBILITY_VERIFY
.venv/bin/python scripts/verify_admin_console_secret_posture.py   # ADMIN_CONSOLE_SECRET_POSTURE_VERIFY
.venv/bin/python scripts/verify_secret_safety_fields.py        # SECRET_SAFETY_FIELDS_VERIFY
```

The live verifiers require the orchestrator (`http://localhost:8000`) and a
rebuilt orchestrator image (the catalogs are copied in via the Dockerfile).

Must NOT run: secret store connect, read/write/rotate secret, kubectl, argocd,
helm install/upgrade, OIDC discovery, JWKS fetch, production auth/action.
