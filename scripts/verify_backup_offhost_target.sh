#!/usr/bin/env bash
# Stage 51 -- off-host target + readback verification (mock target).
#
# Copies an encrypted artifact to the mock off-host target and verifies the
# readback checksum. Asserts real_cloud_write_performed=false.
#
# Marker: BACKUP_OFFHOST_TARGET_VERIFY: PASS / FAIL
set -uo pipefail
cd "$(dirname "$0")/.."
source "$(dirname "$0")/lib/verify_env.sh" 2>/dev/null || true
PY="${PYTHON:-python3}"
RUNTIME_DIR="${BACKUP_DR_RUNTIME_DIR:-.runtime}/backup-dr"
facts="$RUNTIME_DIR/facts.json"

echo "### verify_backup_offhost_target"
[ -f "$facts" ] || bash scripts/run_encrypted_backup.sh >/dev/null 2>&1 || true

result=$("$PY" - "$facts" <<'PY'
import json, sys, tempfile, os
from pathlib import Path
from shared.sdk.backup_dr.offhost_target import build_mock_offhost_target
from shared.sdk.backup_dr.offhost_transfer import transfer_to_offhost, offhost_gap_closed

facts_path = sys.argv[1]
art = None
if os.path.isfile(facts_path):
    art = json.load(open(facts_path)).get("encrypted_artifact_path")
if not art or not os.path.isfile(art):
    d = Path(tempfile.mkdtemp()); art = str(d / "backup.enc"); Path(art).write_bytes(b"ENC")
os.environ.setdefault("BACKUP_DR_OFFHOST_DIR", tempfile.mkdtemp())
target = build_mock_offhost_target()
tr = transfer_to_offhost(source_path=art, target=target)
print(json.dumps({
    "status": tr.status,
    "readback_verified": tr.readback_verified,
    "real_cloud_write_performed": tr.real_cloud_write_performed,
    "gap_closed": offhost_gap_closed(tr),
}))
PY
)
echo "$result"
ok=$("$PY" -c "import json;d=json.loads('''$result''');print(d['gap_closed'] and not d['real_cloud_write_performed'])" 2>/dev/null)
if [ "$ok" = "True" ]; then echo "BACKUP_OFFHOST_TARGET_VERIFY: PASS"; exit 0; fi
echo "BACKUP_OFFHOST_TARGET_VERIFY: FAIL"; exit 1
