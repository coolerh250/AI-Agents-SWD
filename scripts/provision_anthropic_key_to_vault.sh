#!/usr/bin/env bash
# AT-M3.6B.2 -- provision the real Anthropic API key into Vault without exposing it.
#
#     scripts/provision_anthropic_key_to_vault.sh \
#       --secret-file /dev/shm/anthropic-api-key.XXXXXX \
#       --operator-token-file /dev/shm/vault-operator-token.XXXXXX
#
# WHY THIS SCRIPT EXISTS. AT-D30 authorizes writing a real, non-production Anthropic API key into
# the already-validated Vault rail, and nothing else -- not reading it, not validating it, not
# calling Anthropic with it. The assistant driving this procedure must not come into possession of
# the credential as a value at any point. So the Product Owner writes it into a private file, hands
# over ONLY THE PATH, and this script reads it into a shell variable that never leaves the process
# and is streamed to Vault on stdin.
#
# WHAT THIS SCRIPT WILL NEVER DO, and what the tests in
# tests/test_at_m3_6b_2_real_anthropic_secret_provisioning.py hold it to:
#
#   * accept the key or the operator token via a command-line flag or an inherited environment
#     variable -- both are file-path-only interfaces;
#   * print, log, echo, hash, measure, or otherwise render either credential, or the resulting
#     ANTHROPIC_API_KEY value now stored in Vault;
#   * put either credential into argv passed to a child process -- both travel through a child
#     process's environment (docker compose exec -e) or stdin, never as a CLI argument;
#   * use `vault kv put` on the canonical path -- ANTHROPIC_API_KEY is one field of a shared secret,
#     and `put` would delete every other field there; this script uses `vault kv patch` only;
#   * enable REASONING_LIVE_NETWORK_ENABLED, call Anthropic, or otherwise exercise the credential
#     it just wrote. Provisioning and using a credential are different risks -- this script performs
#     only the first, and refuses to run at all if the live gate is already open;
#   * force-recreate the orchestrator container. Only a Vault secret VALUE changes here, not the
#     runtime's environment, so `docker compose restart` is correct and `--force-recreate` is not
#     used, matching the runbook's "Restart or recreate?" table.
#
# It prints names, booleans, counts and Vault status fields. Its output is safe to paste.
#
# Non-production only. No production action. No Anthropic call of any kind.

set -uo pipefail

MOUNT="${VAULT_KV_MOUNT:-secret}"
KV_PATH="${VAULT_KV_PATH:-aiagents/test-runtime}"
FIELD="ANTHROPIC_API_KEY"
SENTINEL="PLACEHOLDER_DO_NOT_COMMIT_REAL_VALUE"

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE_DIR="${REPO_ROOT}/infra/docker-compose"
COMPOSE_FILE="${COMPOSE_DIR}/docker-compose.yml"

SECRET_FILE=""
OPERATOR_TOKEN_FILE=""

while [ "$#" -gt 0 ]; do
  case "$1" in
    --secret-file)         SECRET_FILE="${2:-}"; shift 2 ;;
    --operator-token-file) OPERATOR_TOKEN_FILE="${2:-}"; shift 2 ;;
    -h|--help)              sed -n '2,34p' "${BASH_SOURCE[0]}"; exit 0 ;;
    *) printf 'unknown argument: %s -- this script accepts file paths only, never a key value\n' "$1" >&2; exit 2 ;;
  esac
done

fail_hard() {
  printf '\nPROVISIONING: BLOCKED -- %s\n' "$1"
  printf 'source_file_removed=%s\n' "${SOURCE_FILE_REMOVED:-no}"
  printf 'operator_token_file_removed=%s\n' "${TOKEN_FILE_REMOVED:-no}"
  exit 1
}
step() { printf '\n== %s\n' "$1"; }
ok()   { printf '  ok    %s\n' "$1"; }
info() { printf '  --    %s\n' "$1"; }

SOURCE_FILE_REMOVED=no
TOKEN_FILE_REMOVED=no

# --- 0. refuse the interfaces this script explicitly does not support -----------------------------
step "interface guard"
if [ -n "${ANTHROPIC_API_KEY:-}" ]; then
  fail_hard "ANTHROPIC_API_KEY is set in this shell's environment -- this script accepts the key ONLY as a file path via --secret-file, never via environment"
fi
ok "no ANTHROPIC_API_KEY in this process's inherited environment"

# --- 1. validate both opaque files, before reading a byte of either --------------------------------
# Each check answers "could this file be something other than what its owner intended". A symlink
# can point back into the repository; a group- or world-readable file has already been disclosed; a
# file inside the working tree is one `git add -A` away from being committed.
validate_opaque_file() {
  local f="$1" label="$2"
  [ -n "${f}" ] || fail_hard "--${label}-file is required"
  [ -e "${f}" ] || fail_hard "${label} file does not exist"
  [ -L "${f}" ] && fail_hard "${label} file is a SYMLINK -- refusing to follow it"
  [ -f "${f}" ] || fail_hard "${label} file is not a regular file"
  local mode uid real
  mode="$(stat -c '%a' "${f}" 2>/dev/null)"
  uid="$(stat -c '%u' "${f}" 2>/dev/null)"
  [ "${mode}" = "600" ] || fail_hard "${label} file mode is ${mode}, expected 600"
  [ "${uid}" = "$(id -u)" ] || fail_hard "${label} file is owned by another user"
  real="$(readlink -f "${f}")"
  case "${real}" in
    "${REPO_ROOT}"/*) fail_hard "${label} file is INSIDE the repository working tree" ;;
  esac
  ok "${label} file: regular, non-symlink, mode 600, owned by the caller, outside the repository"
  case "${real}" in
    /dev/shm/*) ok "${label} file resides in /dev/shm (tmpfs -- never written to disk)" ;;
    *)          info "${label} file is not in /dev/shm; it is disk-backed, so remove it promptly" ;;
  esac
}

step "secret file (real Anthropic API key)"
validate_opaque_file "${SECRET_FILE}" "secret"

step "operator token file (Vault write authority)"
validate_opaque_file "${OPERATOR_TOKEN_FILE}" "operator-token"

# Read here and nowhere else. `$(<file)` strips the trailing newline; `tr -d` removes the rest of
# any whitespace an editor may have added. From this line on the value exists only as
# ${ANTHROPIC_KEY} / ${OPERATOR_TOKEN}, is passed to Vault through a child process's environment or
# stdin, and is never expanded into any string this script prints.
ANTHROPIC_KEY="$(tr -d '[:space:]' < "${SECRET_FILE}")"
[ -n "${ANTHROPIC_KEY}" ] || fail_hard "secret file is empty"
ok "secret loaded into this process (value not rendered)"

OPERATOR_TOKEN="$(tr -d '[:space:]' < "${OPERATOR_TOKEN_FILE}")"
[ -n "${OPERATOR_TOKEN}" ] || fail_hard "operator token file is empty"
ok "operator token loaded into this process (value not rendered)"

vault_as() {
  local token="$1"; shift
  VAULT_TOKEN="${token}" docker compose -f "${COMPOSE_FILE}" exec -T -e VAULT_TOKEN vault "$@"
}
op() { vault_as "${OPERATOR_TOKEN}" "$@"; }

# --- 2. canonical Vault state, with operator authority ----------------------------------------------
step "vault server posture"
status_json="$(op vault status -format=json 2>/dev/null)"
[ -n "${status_json}" ] || fail_hard "vault status unreachable -- is the vault service running?"
initialized="$(printf '%s' "${status_json}" | jq -r '.initialized')"
sealed="$(printf '%s' "${status_json}" | jq -r '.sealed')"
storage="$(printf '%s' "${status_json}" | jq -r '.storage_type // "unknown"')"
printf '  --    initialized=%s sealed=%s storage=%s\n' "${initialized}" "${sealed}" "${storage}"
[ "${initialized}" = "true" ] || fail_hard "vault is not initialized"
[ "${sealed}" = "false" ]     || fail_hard "vault is SEALED -- unseal it first"
[ "${storage}" = "file" ]     || fail_hard "storage backend is '${storage}', expected 'file'"

op_policies="$(op vault token lookup -format=json 2>/dev/null | jq -r '.data.policies | join(",")')"
[ -n "${op_policies}" ] || fail_hard "the supplied token cannot look itself up -- it is not an operator token"
printf '  --    operator token policies=%s\n' "${op_policies}"
ok "vault initialized, unsealed, operator authority confirmed"

# --- 3. current field state -- must still be the placeholder before this script writes anything -----
# The comparison happens server-side inside jq; the value crosses this script's stdout only as a
# boolean, never as itself.
step "current field state (${MOUNT}/${KV_PATH})"
secret_json="$(op vault read -format=json "${MOUNT}/data/${KV_PATH}" 2>/dev/null)"
[ -n "${secret_json}" ] || fail_hard "canonical path is not readable with operator authority"

names="$(printf '%s' "${secret_json}" | jq -r '.data.data | keys[]' 2>/dev/null | tr '\n' ' ')"
printf '  --    field names before write: %s\n' "${names}"

current_is_placeholder="$(printf '%s' "${secret_json}" \
  | jq -r --arg f "${FIELD}" --arg s "${SENTINEL}" '(.data.data[$f] // "") == $s')"
printf '  --    current_is_placeholder=%s\n' "${current_is_placeholder}"
if [ "${current_is_placeholder}" != "true" ]; then
  fail_hard "the canonical field does not currently hold the placeholder -- refusing to overwrite an existing non-placeholder value without explicit operator confirmation outside this script"
fi
ok "current field is the placeholder -- safe to provision"

# --- 4. live-gate guard, immediately before the write -----------------------------------------------
step "live-gate guard (immediately before write)"
live_gate="$(docker compose -f "${COMPOSE_FILE}" exec -T orchestrator printenv REASONING_LIVE_NETWORK_ENABLED 2>/dev/null | tr -d '\r')"
printf '  --    REASONING_LIVE_NETWORK_ENABLED=%s\n' "${live_gate:-<unset>}"
if [ "${live_gate}" = "true" ]; then
  fail_hard "REASONING_LIVE_NETWORK_ENABLED=true -- refusing to write the real credential while the live gate is open"
fi
ok "live gate is false -- safe to write"

# --- 5. the write: PATCH, value on stdin, never argv -------------------------------------------------
step "vault kv patch (value on stdin, never argv)"
if printf '%s' "${ANTHROPIC_KEY}" | VAULT_TOKEN="${OPERATOR_TOKEN}" docker compose -f "${COMPOSE_FILE}" \
    exec -T -e VAULT_TOKEN vault vault kv patch -mount="${MOUNT}" "${KV_PATH}" "${FIELD}=-" >/dev/null 2>&1
then
  printf 'vault_write=PASS\n'
else
  printf 'vault_write=FAIL\n'
  unset ANTHROPIC_KEY
  fail_hard "vault kv patch failed"
fi
unset ANTHROPIC_KEY

# --- 6. post-write: field present, unrelated fields preserved, placeholder gone ----------------------
step "post-write field state"
post_json="$(op vault read -format=json "${MOUNT}/data/${KV_PATH}" 2>/dev/null)"
[ -n "${post_json}" ] || fail_hard "post-write read failed"

post_names="$(printf '%s' "${post_json}" | jq -r '.data.data | keys[]' 2>/dev/null | tr '\n' ' ')"
printf '  --    field names after write: %s\n' "${post_names}"
printf '%s' "${post_names}" | grep -qw "${FIELD}" || fail_hard "field ${FIELD} missing after write"
ok "field=${FIELD} present"

for prior_name in ${names}; do
  printf '%s' "${post_names}" | grep -qw "${prior_name}" \
    || fail_hard "pre-existing field ${prior_name} was lost by the write -- patch should never do this"
done
ok "every field present before the write is still present after it"

field_still_placeholder="$(printf '%s' "${post_json}" \
  | jq -r --arg f "${FIELD}" --arg s "${SENTINEL}" '(.data.data[$f] // "") == $s')"
if [ "${field_still_placeholder}" = "true" ]; then
  fail_hard "field still reads as the placeholder after patch -- the write did not take effect"
fi
ok "field no longer reads as the placeholder"

unset OPERATOR_TOKEN

# --- 7. restart (secret-value-only change -- NOT --force-recreate) -----------------------------------
step "restart orchestrator (secret value only; environment unchanged)"
if ! docker compose -f "${COMPOSE_FILE}" restart orchestrator 2>&1 | tail -5; then
  fail_hard "orchestrator restart failed"
fi

health=unknown
for _ in $(seq 1 30); do
  health="$(docker inspect -f '{{.State.Health.Status}}' aiagents-test-orchestrator-1 2>/dev/null)"
  [ "${health}" = "healthy" ] && break
  sleep 2
done
printf '  --    orchestrator health=%s\n' "${health:-unknown}"
[ "${health}" = "healthy" ] || fail_hard "orchestrator is not healthy after restart"
ok "orchestrator restarted and healthy"

# --- 8. canonical SecretProvider, post-restart, through the actual deployed code path -----------------
step "canonical SecretProvider (post-restart)"
provider_out="$(docker compose -f "${COMPOSE_FILE}" exec -T orchestrator python - <<'PY' 2>&1
import json
from shared.sdk.secrets.provider import provider_from_env

provider = provider_from_env()
print(json.dumps({
    "provider_class": type(provider).__name__,
    "provider": provider.status.get("provider"),
    "mount": provider.status.get("mount"),
    "path": provider.status.get("path"),
    "names": sorted(provider.list_available_secrets()),
    "present": provider.get_secret("ANTHROPIC_API_KEY").present,
    "has_secret": provider.has_secret("ANTHROPIC_API_KEY"),
}))
PY
)"
provider_json="$(printf '%s' "${provider_out}" | tail -n 1)"
if ! printf '%s' "${provider_json}" | jq -e . >/dev/null 2>&1; then
  printf '%s\n' "${provider_out}"
  fail_hard "the canonical SecretProvider probe did not return JSON"
fi

printf '  --    provider_class=%s\n' "$(printf '%s' "${provider_json}" | jq -r '.provider_class')"
printf '  --    names=%s\n' "$(printf '%s' "${provider_json}" | jq -c '.names')"
printf '  --    present=%s has_secret=%s\n' \
  "$(printf '%s' "${provider_json}" | jq -r '.present')" \
  "$(printf '%s' "${provider_json}" | jq -r '.has_secret')"

provider_failures=0
check_json() {
  local expr="$1" want="$2" label="$3"
  local got; got="$(printf '%s' "${provider_json}" | jq -r "${expr}")"
  if [ "${got}" = "${want}" ]; then
    printf '  ok    %s\n' "${label}"
  else
    printf '  FAIL  %s (got %s)\n' "${label}" "${got}"
    provider_failures=$((provider_failures + 1))
  fi
}
check_json '.provider_class' 'VaultKvSecretProvider' 'provider_class=VaultKvSecretProvider'
check_json ".names | index(\"${FIELD}\") != null" 'true' "list_available_secrets contains ${FIELD}"
check_json '.present' 'true' "present=true (the real key is now readable)"
check_json '.has_secret' 'true' "has_secret=true (the credential is now callable at the SecretProvider layer)"
[ "${provider_failures}" -eq 0 ] || fail_hard "${provider_failures} SecretProvider check(s) failed"

# --- 9. live gate re-confirmed, still false ------------------------------------------------------------
step "live gate re-confirmed (post-restart)"
live_gate_post="$(docker compose -f "${COMPOSE_FILE}" exec -T orchestrator printenv REASONING_LIVE_NETWORK_ENABLED 2>/dev/null | tr -d '\r')"
printf '  --    REASONING_LIVE_NETWORK_ENABLED=%s\n' "${live_gate_post:-<unset>}"
[ "${live_gate_post}" = "false" ] || fail_hard "live gate is not false after restart"
ok "live gate remains false -- credential present but system remains non-callable externally"

# --- 10. surrender both credentials -------------------------------------------------------------------
step "consume-once handoff"
if rm -f "${SECRET_FILE}"; then
  SOURCE_FILE_REMOVED=yes
  ok "secret file removed"
fi
if rm -f "${OPERATOR_TOKEN_FILE}"; then
  TOKEN_FILE_REMOVED=yes
  ok "operator token file removed"
fi

printf '\nsource_file_removed=%s\n' "${SOURCE_FILE_REMOVED}"
printf 'operator_token_file_removed=%s\n' "${TOKEN_FILE_REMOVED}"
printf 'vault_write=PASS\n'
echo "PROVISIONING: PASS"
