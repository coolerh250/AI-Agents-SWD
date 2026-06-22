#!/usr/bin/env python3
"""Step 53 -- secret reference schema verifier (NO value access).

Validates the reference-only SecretRef: no inline value field, disabled store
supported, disabled store not production-ready, name/key required for a
configured ref, and bad fixtures (inline value) rejected.

Marker: SECRET_REFERENCE_SCHEMA_VERIFY: PASS | FAIL
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))  # noqa: E402

from shared.sdk.secrets_foundation import SecretRef, validate_ref_dict  # noqa: E402

failures: list[str] = []
passes: list[str] = []


def ok(m: str) -> None:
    passes.append(m)
    print(f"  [PASS] {m}")


def bad(m: str) -> None:
    failures.append(m)
    print(f"  [FAIL] {m}")


def main() -> int:
    fields = set(SecretRef.model_fields)
    if {"value", "secret", "token", "password"} & fields:
        bad("SecretRef must not define a value/secret/token/password field")
    else:
        ok("SecretRef carries no inline value field")

    disabled = SecretRef(store="disabled", name="", key="", required=True)
    if disabled.configured or disabled.production_ready:
        bad("disabled store ref must be unconfigured + not production-ready")
    else:
        ok("disabled store supported; not configured; not production-ready")

    # configured-but-not-production-allowed ref is not production-ready
    cfg = SecretRef(store="vault_ref", name="app", key="k", required=True, production_allowed=False)
    if cfg.production_ready:
        bad("production_allowed=false ref must not be production-ready")
    else:
        ok("name/key configured but production_allowed=false -> not production-ready")

    # bad fixtures: inline value rejected by the field validator
    jwt = "eyJ" + "a" * 20 + "." + "b" * 20 + "." + "c" * 20
    try:
        SecretRef(store="vault_ref", name="x", key=jwt)
        bad("inline JWT value not rejected")
    except Exception:
        ok("inline JWT value rejected by SecretRef validator")

    if validate_ref_dict({"name": "ok", "value": "x" * 12}):
        ok("validate_ref_dict rejects a 'value' field")
    else:
        bad("validate_ref_dict must reject an inline value field")

    print(f"\n=== Summary: {len(passes)}/{len(passes) + len(failures)} checks passed ===")
    if failures:
        print("SECRET_REFERENCE_SCHEMA_VERIFY: FAIL")
        return 1
    print("SECRET_REFERENCE_SCHEMA_VERIFY: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
