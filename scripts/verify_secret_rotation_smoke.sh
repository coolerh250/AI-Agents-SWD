#!/usr/bin/env bash
# Stage 26 secret rotation smoke.
#
# Drives the SDK-layer rotation contract without touching any service:
#   1. Bootstrap an isolated mock-vault file (under a tmp dir).
#   2. Write version A.
#   3. Build a MockVaultSecretProvider against the file and read version A.
#   4. Rewrite the file with version B.
#   5. Call provider.reload() and read version B.
# A PASS means the provider re-reads on demand and never echoes a
# value to stdout — the script prints provider STATUS only (booleans).
#
# This script does NOT touch Vault, GitHub, Discord, or any service.
set -uo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

echo "### verify_secret_rotation_smoke: $(date '+%Y-%m-%d %H:%M:%S %Z')"

tmpfile=$(mktemp -t mock-vault.XXXXXX.json)
trap 'rm -f "$tmpfile"' EXIT
chmod 600 "$tmpfile" 2>/dev/null || true

REPO_ROOT="$REPO_ROOT" python3 - "$tmpfile" <<'PY'
import json
import os
import sys
from pathlib import Path

repo_root = Path(__file__).resolve()
# We're invoked from `python3 - tmpfile` so the script body's __file__
# is the synthetic stdin entry; resolve repo root via env instead.
repo_root = Path(os.environ.get("REPO_ROOT") or os.getcwd()).resolve()
sys.path.insert(0, str(repo_root))

from shared.sdk.secrets import MockVaultSecretProvider  # noqa: E402

tmpfile = Path(sys.argv[1])

# version A
version_a = {"POSTGRES_PASSWORD": "rotation-smoke-A", "GITHUB_TOKEN": "placeholder-A"}
tmpfile.write_text(json.dumps(version_a), encoding="utf-8")

provider = MockVaultSecretProvider(path=tmpfile)
ref_a = provider.get_secret("POSTGRES_PASSWORD")
if not ref_a.present:
    print("ROTATION_VERSION_A: FAIL")
    sys.exit(1)
print("ROTATION_VERSION_A: PASS")

# version B
version_b = {"POSTGRES_PASSWORD": "rotation-smoke-B", "GITHUB_TOKEN": "placeholder-B"}
tmpfile.write_text(json.dumps(version_b), encoding="utf-8")

provider.reload()
ref_b = provider.get_secret("POSTGRES_PASSWORD")
if not ref_b.present:
    print("ROTATION_VERSION_B: FAIL (provider did not pick up new value)")
    sys.exit(1)

# Compare reveal-handles WITHOUT printing either value. We only echo
# the booleans + a "changed" flag.
changed = ref_a.reveal() != ref_b.reveal()
print(f"ROTATION_VERSION_B: PASS  changed_between_versions={changed}")

if not changed:
    print("ROTATION_DELTA: FAIL")
    sys.exit(1)
print("ROTATION_DELTA: PASS")

# Status must NOT contain secret values
status = provider.status
for v in status.values():
    if isinstance(v, str) and (
        "rotation-smoke-A" in v or "rotation-smoke-B" in v
    ):
        print("ROTATION_STATUS_LEAK: FAIL")
        sys.exit(1)
print("ROTATION_STATUS_LEAK: PASS")
PY
rc=$?
if [ "$rc" -ne 0 ]; then
  echo "SECRET_ROTATION_SMOKE: FAIL (rc=$rc)"
  exit 1
fi

echo
echo "SECRET_ROTATION_SMOKE: PASS"
