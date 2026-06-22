#!/usr/bin/env python3
"""Step 52.3 -- session hardening verifier (source-level, NO network).

Validates the session hardening catalog + cleanup/concurrency/forced-logout/
key-rotation models: raw token never persisted, hardened cookie, production
secret store required, current session key NOT production-ready, key file not
committed.

Marker: SESSION_HARDENING_VERIFY: PASS | FAIL
"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
IDENT = ROOT / "infra" / "identity"
sys.path.insert(0, str(ROOT))  # noqa: E402

failures: list[str] = []
passes: list[str] = []


def ok(m: str) -> None:
    passes.append(m)
    print(f"  [PASS] {m}")


def bad(m: str) -> None:
    failures.append(m)
    print(f"  [FAIL] {m}")


def load(name: str) -> dict:
    return yaml.safe_load((IDENT / name).read_text(encoding="utf-8"))


def main() -> int:
    required = [
        "session-hardening-catalog.yaml",
        "session-concurrency-policy.yaml",
        "forced-logout-model.yaml",
        "session-key-rotation-model.yaml",
    ]
    for n in required:
        if not (IDENT / n).is_file():
            bad(f"missing file: {n}")
    if not failures:
        ok("session hardening catalog + concurrency + forced-logout + key-rotation present")

    h = load("session-hardening-catalog.yaml")["sessionHardening"]
    if h["persistence"]["rawTokenPersisted"] is not False:
        bad("rawTokenPersisted must be false")
    if h["persistence"]["tokenHashAlgorithm"] != "sha256":
        bad("token hash algorithm must be sha256")
    if h["cookie"]["httpOnly"] is not True:
        bad("cookie httpOnly must be true")
    if h["cookie"]["sameSite"] != "Strict":
        bad("cookie SameSite must be Strict")
    if h["cookie"]["secureRequiredInProduction"] is not True:
        bad("secureRequiredInProduction must be true")
    if h["cleanup"]["required"] is not True:
        bad("cleanup must be required")
    if not failures:
        ok(
            "raw token not persisted; sha256 hash; HttpOnly/SameSite=Strict/secure-in-prod; cleanup required"
        )

    # cleanup SDK module exists and is importable
    try:
        from shared.sdk.identity import plan_cleanup  # noqa: F401

        ok("session cleanup utility present (shared.sdk.identity.plan_cleanup)")
    except Exception as e:  # noqa: BLE001
        bad(f"session cleanup utility missing: {e}")

    kr = load("session-key-rotation-model.yaml")["sessionKeyRotation"]
    if kr["required"] is not True or kr["productionSecretStoreRequired"] is not True:
        bad("key rotation must be required + require a production secret store")
    if kr["status"] != "model_only":
        bad("key rotation status must be model_only")
    krc = load("session-key-rotation-model.yaml")["constraints"]
    if krc["currentKeyProductionReady"] is not False:
        bad("current session key must NOT be production-ready")
    if krc["keyFileCommitted"] is not False:
        bad("key file must not be committed (flag)")
    if not [f for f in failures if "key" in f.lower()]:
        ok(
            "key rotation model_only; production secret store required; current key not production-ready"
        )

    # forced logout + concurrency models declare not-production-ready
    fl = load("forced-logout-model.yaml")["status"]
    cc = load("session-concurrency-policy.yaml")["status"]
    if fl["productionReady"] is not False or cc["productionReady"] is not False:
        bad("forced logout + concurrency must declare productionReady=false")
    else:
        ok("forced logout + concurrency models present, production-ready=false")

    # session signing key file must not be committed/tracked
    gi = (
        (ROOT / ".gitignore").read_text(encoding="utf-8") if (ROOT / ".gitignore").is_file() else ""
    )
    key_file = ROOT / ".runtime" / "admin-console-session-key"
    if ".runtime" in gi:
        ok(".runtime session key path is gitignored (key file not committed)")
    elif not key_file.exists():
        ok("no committed session key file present")
    else:
        bad("session key file present and .runtime not gitignored")

    print(f"\n=== Summary: {len(passes)}/{len(passes) + len(failures)} checks passed ===")
    if failures:
        print("SESSION_HARDENING_VERIFY: FAIL")
        return 1
    print("SESSION_HARDENING_VERIFY: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
