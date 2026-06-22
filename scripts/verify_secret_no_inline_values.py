#!/usr/bin/env python3
"""Step 53 -- no-inline-secret-values verifier (NO value access).

Scans the secret-management + infra surface for committed secret/token shapes
(JWT, private key, client secret literal, password/token literal, kubeconfig,
GitHub/ArgoCD token, registry auth, DB URL with password, webhook URL). The
tests/ + SDK scan is scoped to this stage's files so unrelated stages'
intentional redaction fixtures are not flagged; detector modules holding pattern
fragments are excluded.

Marker: SECRET_NO_INLINE_VALUES_VERIFY: PASS | FAIL
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))  # noqa: E402

from shared.sdk.secrets_foundation import find_committed_secret  # noqa: E402

# (directory, glob) -- infra scanned fully; SDK/API/tests/docs scoped to Step 53.
SCAN = [
    (ROOT / "infra" / "secrets", "**/*"),
    (ROOT / "infra" / "identity", "**/*"),
    (ROOT / "infra" / "kubernetes", "**/*"),
    (ROOT / "infra" / "gitops", "**/*"),
    (ROOT / "shared" / "sdk" / "secrets_foundation", "*.py"),
    (ROOT / "apps" / "orchestrator" / "src", "secret_posture_api.py"),
    (ROOT / "tests", "test_secret_*.py"),
    (ROOT / "docs" / "security", "secret-*.md"),
    (ROOT / "docs" / "operations", "secret-*.md"),
]
# Detector modules legitimately contain pattern fragments; the pre-existing
# secrets-provider tests + leak-scanner test (other stages) carry intentional
# redaction fixtures and are out of the Step 53 surface.
EXCLUDE = {
    ROOT / "shared" / "sdk" / "secrets_foundation" / "secret_redaction.py",
    ROOT / "shared" / "sdk" / "secrets_foundation" / "secret_ref.py",
    ROOT / "tests" / "test_secret_leak_scanner.py",
    ROOT / "tests" / "test_secret_provider.py",
    ROOT / "tests" / "test_secret_provider_selection.py",
}
EXTS = {".yaml", ".yml", ".md", ".py", ".json", ".tpl", ".txt"}

failures: list[str] = []


def main() -> int:
    scanned = 0
    for base, pattern in SCAN:
        if not base.is_dir():
            continue
        for p in sorted(base.glob(pattern)):
            if not p.is_file() or p in EXCLUDE:
                continue
            if p.suffix not in EXTS or "__pycache__" in p.parts:
                continue
            scanned += 1
            for r in find_committed_secret(p.read_text(encoding="utf-8", errors="ignore")):
                failures.append(f"{p.relative_to(ROOT)}: {r}")

    if failures:
        for f in failures[:40]:
            print(f"  [FAIL] {f}")
        print(f"\n=== Scanned {scanned} files; {len(failures)} inline-secret hits ===")
        print("SECRET_NO_INLINE_VALUES_VERIFY: FAIL")
        return 1
    print(f"  [PASS] no inline secret/token values in {scanned} scanned files")
    print("SECRET_NO_INLINE_VALUES_VERIFY: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
