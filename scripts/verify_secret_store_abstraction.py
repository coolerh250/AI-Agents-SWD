#!/usr/bin/env python3
"""Step 53 -- secret store abstraction verifier (NO value access, NO network).

Validates the provider interface exists, read_secret_value raises, no external
provider connection, the disabled production store config exists with
read/write/rotation all false and production-ready false.

Marker: SECRET_STORE_ABSTRACTION_VERIFY: PASS | FAIL
"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SDIR = ROOT / "infra" / "secrets"
SDK = ROOT / "shared" / "sdk" / "secrets_foundation"
sys.path.insert(0, str(ROOT))  # noqa: E402

from shared.sdk.secrets_foundation import (  # noqa: E402
    DisabledSecretStoreProvider,
    SecretRef,
    SecretStoreProvider,
    SecretValueAccessDisabledError,
)

failures: list[str] = []
passes: list[str] = []


def ok(m: str) -> None:
    passes.append(m)
    print(f"  [PASS] {m}")


def bad(m: str) -> None:
    failures.append(m)
    print(f"  [FAIL] {m}")


def main() -> int:
    if not isinstance(DisabledSecretStoreProvider(), SecretStoreProvider):
        bad("DisabledSecretStoreProvider must satisfy the SecretStoreProvider protocol")
    else:
        ok("provider interface present (SecretStoreProvider protocol)")

    prov = DisabledSecretStoreProvider()
    ref = SecretRef(store="disabled", name="", key="")
    md = prov.get_secret_metadata(ref)
    if md.production_ready or md.configured:
        bad("disabled ref metadata must be unconfigured / not production-ready")
    else:
        ok("metadata read works and carries no value")
    try:
        prov.read_secret_value(ref)
        bad("read_secret_value must raise")
    except SecretValueAccessDisabledError:
        ok("read_secret_value raises SecretValueAccessDisabledError")

    # no external provider connection in the SDK
    blob = "\n".join(p.read_text(encoding="utf-8") for p in SDK.glob("*.py"))
    for line in blob.splitlines():
        s = line.strip()
        if s.startswith(
            (
                "import requests",
                "import httpx",
                "import aiohttp",
                "from requests",
                "from httpx",
                "from aiohttp",
                "import hvac",
            )
        ):
            bad(f"secret SDK imports an external client: {s}")
    if not [f for f in failures if "external client" in f]:
        ok("secret SDK performs no external provider connection")

    store = yaml.safe_load(
        (SDIR / "production-secret-store-disabled-config.yaml").read_text(encoding="utf-8")
    )["productionSecretStore"]
    for k in (
        "enabled",
        "configured",
        "readSecretValuesEnabled",
        "writeSecretValuesEnabled",
        "rotationEnabled",
        "productionReady",
    ):
        if store[k] is not False:
            bad(f"disabled store {k} must be false")
    if store["provider"] != "disabled" or store["failClosed"] is not True:
        bad("disabled store must be provider=disabled, failClosed=true")
    if not [f for f in failures if "disabled store" in f]:
        ok(
            "production secret store disabled: provider=disabled, read/write/rotation/ready all false"
        )

    print(f"\n=== Summary: {len(passes)}/{len(passes) + len(failures)} checks passed ===")
    if failures:
        print("SECRET_STORE_ABSTRACTION_VERIFY: FAIL")
        return 1
    print("SECRET_STORE_ABSTRACTION_VERIFY: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
