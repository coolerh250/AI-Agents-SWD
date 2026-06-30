#!/usr/bin/env python3
"""Step 63A -- production credential readiness verifier.

Marker: PRODUCTION_CREDENTIAL_READINESS_VERIFY: PASS | FAIL
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from shared.sdk.controlled_rollout import loaders  # noqa: E402

MARKER = "PRODUCTION_CREDENTIAL_READINESS_VERIFY"
failures: list[str] = []


def bad(m: str) -> None:
    failures.append(m)
    print(f"  [FAIL] {m}")


def main() -> int:
    c = loaders.load("credentials")
    if c.get("reads_credential_values") is not False:
        bad("must not read credential values")
    if c.get("creates_credentials") is not False:
        bad("must not create credentials")
    if c.get("exposes_secret") is not False:
        bad("must not expose secret")
    # References record only configured booleans -- never a value.
    for ref in c.get("references", []):
        if set(ref.keys()) - {"name", "configured"}:
            bad(f"credential reference carries unexpected fields (possible value leak): {ref}")
    missing = loaders.missing_credential_refs()
    if not missing:
        bad("expected production credential references to be not_configured")

    if failures:
        print(f"{MARKER}: FAIL")
        return 1
    print(
        f"  [OK] credential readiness: {len(missing)} refs missing; no value read/created/exposed"
    )
    print(f"{MARKER}: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
