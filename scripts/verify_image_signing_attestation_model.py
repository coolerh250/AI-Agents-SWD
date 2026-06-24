#!/usr/bin/env python3
"""Step 54.3 -- image signing / attestation model verifier.

Marker: IMAGE_SIGNING_ATTESTATION_MODEL_VERIFY: PASS | FAIL
"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
F = ROOT / "infra" / "security" / "image-signing-attestation-model.yaml"

failures: list[str] = []
passes: list[str] = []


def ok(m: str) -> None:
    passes.append(m)
    print(f"  [PASS] {m}")


def bad(m: str) -> None:
    failures.append(m)
    print(f"  [FAIL] {m}")


def main() -> int:
    if not F.is_file():
        bad(f"missing {F}")
        print("IMAGE_SIGNING_ATTESTATION_MODEL_VERIFY: FAIL")
        return 1
    s = (yaml.safe_load(F.read_text(encoding="utf-8")) or {}).get("signingAttestation", {})
    if not s:
        bad("signingAttestation section missing")
        print("IMAGE_SIGNING_ATTESTATION_MODEL_VERIFY: FAIL")
        return 1
    ok("signing / attestation model present")

    for k in (
        "signingConfigured",
        "attestationConfigured",
        "privateKeyCommitted",
        "signingPerformed",
        "attestationGenerated",
        "attestationUploaded",
        "productionReady",
    ):
        if s.get(k) is not False:
            bad(f"{k} must be false")
    if not [f for f in failures if "must be false" in f]:
        ok("signing/attestation disabled; no key committed; nothing signed/uploaded")

    if s.get("status") != "model_only":
        bad("status must be model_only")
    else:
        ok("status model_only")

    # guard: no signing key file committed anywhere in the repo
    import subprocess  # nosec

    tracked = subprocess.run(
        ["git", "ls-files"], cwd=ROOT, capture_output=True, text=True
    ).stdout.split()
    keyish = [
        f for f in tracked if f.endswith((".key", "cosign.key", ".pem")) or "cosign" in f.lower()
    ]
    if keyish:
        bad(f"signing key-like files committed: {keyish[:3]}")
    else:
        ok("no signing key / cosign key committed")

    print(f"\n=== Summary: {len(passes)}/{len(passes) + len(failures)} checks passed ===")
    if failures:
        print("IMAGE_SIGNING_ATTESTATION_MODEL_VERIFY: FAIL")
        return 1
    print("IMAGE_SIGNING_ATTESTATION_MODEL_VERIFY: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
