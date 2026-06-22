#!/usr/bin/env python3
"""Step 53 -- secret rotation model verifier (model only, NO real rotation).

Marker: SECRET_ROTATION_MODEL_VERIFY: PASS | FAIL
"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SDIR = ROOT / "infra" / "secrets"
REQUIRED_SECRETS = {
    "session_signing_key",
    "audit_hmac_keyring",
    "oidc_client_secret",
    "database_credential",
    "redis_credential",
    "backup_encryption_key",
    "github_credential",
    "argocd_repo_credential",
    "registry_credential",
    "llm_api_key",
    "notification_webhook",
}

failures: list[str] = []
passes: list[str] = []


def ok(m: str) -> None:
    passes.append(m)
    print(f"  [PASS] {m}")


def bad(m: str) -> None:
    failures.append(m)
    print(f"  [FAIL] {m}")


def main() -> int:
    f = SDIR / "secret-rotation-model.yaml"
    if not f.is_file():
        bad("missing secret-rotation-model.yaml")
        print("SECRET_ROTATION_MODEL_VERIFY: FAIL")
        return 1
    data = yaml.safe_load(f.read_text(encoding="utf-8"))
    rot = data["rotation"]

    if rot["required"] is not True or rot["productionStoreRequired"] is not True:
        bad("rotation must be required + require a production store")
    if rot["status"] != "model_only":
        bad("rotation status must be model_only (no real rotation)")
    if (
        rot["emergencyRotation"]["required"] is not True
        or rot["emergencyRotation"]["approvalRequired"] is not True
    ):
        bad("emergency rotation must be required + approval-required")
    if not failures:
        ok("rotation model_only; production store required; emergency rotation approval-required")

    covered = {p.get("secretKey") for p in data.get("secretRotationPlans", [])}
    if not REQUIRED_SECRETS <= covered:
        bad(f"rotation plans missing: {sorted(REQUIRED_SECRETS - covered)}")
    else:
        ok(f"rotation plans cover all {len(REQUIRED_SECRETS)} critical secret types")

    for p in data.get("secretRotationPlans", []):
        if p.get("productionStoreRequired") is not True:
            bad(f"{p.get('secretKey')}: rotation plan must record production store dependency")
    if not [x for x in failures if "rotation plan must record" in x]:
        ok("every rotation plan records the production store dependency")

    print(f"\n=== Summary: {len(passes)}/{len(passes) + len(failures)} checks passed ===")
    if failures:
        print("SECRET_ROTATION_MODEL_VERIFY: FAIL")
        return 1
    print("SECRET_ROTATION_MODEL_VERIFY: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
