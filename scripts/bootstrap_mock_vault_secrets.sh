#!/usr/bin/env bash
# Stage 26 mock-vault bootstrap.
#
# Generates ``infra/runtime/.mock-vault-secrets.local.json`` from the
# placeholder-only template ``infra/runtime/mock-vault-secrets.example.json``,
# substituting a random 32-char base64 password for POSTGRES_PASSWORD.
#
# The output file is:
#   * gitignored (see .gitignore)
#   * chmod 600
#   * staging-validation only — never contains a real GitHub / Discord
#     token. The template ships placeholder strings for those fields
#     and this script does not overwrite them.
#
# Re-runs are idempotent: if the local file already exists the script
# refuses to overwrite it unless ``ALLOW_OVERWRITE=true``. Re-bootstrap
# during rotation testing by setting the env var or removing the file
# first.
set -uo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TEMPLATE="${MOCK_VAULT_TEMPLATE:-${REPO_ROOT}/infra/runtime/mock-vault-secrets.example.json}"
OUT="${MOCK_VAULT_SECRETS_FILE:-${REPO_ROOT}/infra/runtime/.mock-vault-secrets.local.json}"

echo "### bootstrap_mock_vault_secrets: $(date '+%Y-%m-%d %H:%M:%S %Z')"
echo "  template = $TEMPLATE"
echo "  out      = $OUT"

if [ ! -f "$TEMPLATE" ]; then
  echo "BOOTSTRAP_MOCK_VAULT_SECRETS: FAIL (template missing)"
  exit 1
fi

if [ -f "$OUT" ] && [ "${ALLOW_OVERWRITE:-false}" != "true" ]; then
  echo "  $OUT already exists — refusing to overwrite"
  echo "  set ALLOW_OVERWRITE=true to regenerate (rotation testing)"
  echo "BOOTSTRAP_MOCK_VAULT_SECRETS: SKIP"
  exit 0
fi

# 32 random bytes -> base64 -> trim padding/newlines. Same shape used
# by generate_staging_env.sh so the rotation smoke can predict it.
gen_password() {
  python3 - <<'PY'
import base64, os, sys
sys.stdout.write(base64.b64encode(os.urandom(32)).decode().rstrip("="))
PY
}

NEW_PASS="$(gen_password)"
if [ -z "$NEW_PASS" ]; then
  echo "BOOTSTRAP_MOCK_VAULT_SECRETS: FAIL (password generation failed)"
  exit 1
fi

mkdir -p "$(dirname "$OUT")"

python3 - "$TEMPLATE" "$OUT" "$NEW_PASS" <<'PY'
import json
import sys
from pathlib import Path

template_path = Path(sys.argv[1])
out_path = Path(sys.argv[2])
new_password = sys.argv[3]

try:
    data = json.loads(template_path.read_text(encoding="utf-8"))
except Exception as exc:
    sys.stderr.write(f"template parse failed: {exc}\n")
    sys.exit(1)
if not isinstance(data, dict):
    sys.stderr.write("template is not a JSON object\n")
    sys.exit(1)

# Strip the comment field; the mock provider treats every value as a
# secret candidate and we don't want a stray "_comment" key in the
# kv namespace.
data.pop("_comment", None)

data["POSTGRES_PASSWORD"] = new_password
# Leave the GitHub / Discord / Alertmanager placeholders intact — the
# bootstrap script must not synthesise token-shaped values. Only the DB
# password is fabricated because the staging compose REQUIRES one for
# postgres to start.

out_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
PY

chmod 600 "$OUT" 2>/dev/null || true

echo "  wrote $(stat -c '%a %n' "$OUT" 2>/dev/null || ls -l "$OUT")"
echo "BOOTSTRAP_MOCK_VAULT_SECRETS: PASS"
