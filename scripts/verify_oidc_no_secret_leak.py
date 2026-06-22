#!/usr/bin/env python3
"""Step 52.2 -- OIDC no-secret-leak verifier (NO network).

Scans the OIDC surface for committed credential / token shapes: JWTs, client
secrets, access/refresh/ID tokens, private keys, real IdP issuers, tenant/group
GUIDs, OAuth codes, bearer tokens and real emails. Field names, placeholders,
empty strings and ``example.*`` documentation hosts are allowed.

Marker: OIDC_NO_SECRET_LEAK_VERIFY: PASS | FAIL
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))  # noqa: E402

from shared.sdk.identity import find_secret_like  # noqa: E402

# OIDC surface introduced by this stage. tests/ is scoped to test_oidc_*.py so
# that unrelated stages' intentional redaction fixtures are not flagged.
SCAN_GLOBS = [
    (ROOT / "infra" / "identity", "*"),
    (ROOT / "docs" / "security", "oidc-*.md"),
    (ROOT / "shared" / "sdk" / "identity", "*"),
    (ROOT / "tests", "test_oidc_*.py"),
]
# The detector module legitimately contains pattern fragments; exclude it.
EXCLUDE = {ROOT / "shared" / "sdk" / "identity" / "oidc_redaction.py"}
EXTS = {".yaml", ".yml", ".md", ".py"}

failures: list[str] = []


def main() -> int:
    scanned = 0
    for d, pattern in SCAN_GLOBS:
        if not d.is_dir():
            continue
        for p in sorted(d.rglob(pattern)):
            if p.suffix not in EXTS or not p.is_file() or p in EXCLUDE:
                continue
            if "__pycache__" in p.parts:
                continue
            scanned += 1
            reasons = find_secret_like(p.read_text(encoding="utf-8"))
            for r in reasons:
                failures.append(f"{p.relative_to(ROOT)}: {r}")

    if failures:
        for f in failures:
            print(f"  [FAIL] {f}")
        print(f"\n=== Scanned {scanned} files; {len(failures)} secret-like hits ===")
        print("OIDC_NO_SECRET_LEAK_VERIFY: FAIL")
        return 1
    print(f"  [PASS] no secret/token-shaped values in {scanned} scanned files")
    print("OIDC_NO_SECRET_LEAK_VERIFY: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
