#!/usr/bin/env bash
# AT-M3.6B.2 -- complete the Vault runtime readiness procedure without exposing the operator token.
#
#     scripts/complete_vault_runtime_readiness.sh --operator-token-file /dev/shm/vault-operator-token.XXXXXX
#
# WHY THIS SCRIPT EXISTS. The readiness procedure needs Vault operator authority for four things --
# read the loaded policy, confirm the KV mount, revoke a superseded runtime token, mint a new one --
# and the assistant driving the procedure must not come into possession of that authority as a
# value. Pasting a root token into a chat transcript is not undoable. So the operator writes the
# token into a private file, hands over ONLY THE PATH, and this script reads it into a shell
# variable that never leaves the process.
#
# WHAT THIS SCRIPT WILL NEVER DO, and what the tests in
# tests/test_at_m3_6b_2_operator_handoff.py hold it to:
#
#   * print, log, echo, hash, measure or otherwise render the operator token, the runtime token, or
#     the value of any field stored in Vault;
#   * write the operator token anywhere -- not into .env, not into compose, not into a container,
#     not into the repository, not into a log;
#   * touch the real Anthropic credential. This slice finishes with the placeholder installed and
#     the reasoning rail non-callable, and every check below is written to keep it that way.
#
# It prints names, booleans, counts and Vault status fields. Its output is safe to paste.
#
# Non-production only. No production action.

set -uo pipefail

MOUNT="${VAULT_KV_MOUNT:-secret}"
KV_PATH="${VAULT_KV_PATH:-aiagents/test-runtime}"
FIELD="ANTHROPIC_API_KEY"
SENTINEL="PLACEHOLDER_DO_NOT_COMMIT_REAL_VALUE"
POLICY_NAME="aiagents-runtime-read"
TOKEN_PERIOD="768h"

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE_DIR="${REPO_ROOT}/infra/docker-compose"
COMPOSE_FILE="${COMPOSE_DIR}/docker-compose.yml"
ENV_FILE="${COMPOSE_DIR}/.env"
VERIFY_SH="${REPO_ROOT}/scripts/verify_vault_runtime_readiness.sh"

OPERATOR_TOKEN_FILE=""
KEEP_TOKEN_FILE=no

while [ "$#" -gt 0 ]; do
  case "$1" in
    --operator-token-file) OPERATOR_TOKEN_FILE="${2:-}"; shift 2 ;;
    --keep-token-file)     KEEP_TOKEN_FILE=yes; shift ;;
    -h|--help)             sed -n '2,26p' "${BASH_SOURCE[0]}"; exit 0 ;;
    *) printf 'unknown argument: %s\n' "$1" >&2; exit 2 ;;
  esac
done

fail_hard() {
  printf '\nCOMPLETION: BLOCKED -- %s\n' "$1"
  printf 'operator_token_file_removed=%s\n' "${TOKEN_FILE_REMOVED:-no}"
  exit 1
}

step() { printf '\n== %s\n' "$1"; }
ok()   { printf '  ok    %s\n' "$1"; }
info() { printf '  --    %s\n' "$1"; }

TOKEN_FILE_REMOVED=no

# --- 1. validate the operator-token file, before reading a byte of it -----------------------------
# Each check answers "could this file be something other than what the operator intended". A
# symlink can point back into the repository; a group- or world-readable file has already been
# disclosed; a file inside the working tree is one `git add -A` away from being committed.
step "operator token file"

[ -n "${OPERATOR_TOKEN_FILE}" ] || fail_hard "--operator-token-file is required"
[ -e "${OPERATOR_TOKEN_FILE}" ] || fail_hard "operator token file does not exist"
[ -L "${OPERATOR_TOKEN_FILE}" ] && fail_hard "operator token file is a SYMLINK -- refusing to follow it"
[ -f "${OPERATOR_TOKEN_FILE}" ] || fail_hard "operator token file is not a regular file"

file_mode="$(stat -c '%a' "${OPERATOR_TOKEN_FILE}" 2>/dev/null)"
file_uid="$(stat -c '%u' "${OPERATOR_TOKEN_FILE}" 2>/dev/null)"
[ "${file_mode}" = "600" ] || fail_hard "operator token file mode is ${file_mode}, expected 600"
[ "${file_uid}" = "$(id -u)" ] || fail_hard "operator token file is owned by another user"

token_file_real="$(readlink -f "${OPERATOR_TOKEN_FILE}")"
case "${token_file_real}" in
  "${REPO_ROOT}"/*) fail_hard "operator token file is INSIDE the repository working tree" ;;
esac

ok "path is a regular non-symlink file, mode 600, owned by the caller, outside the repository"
case "${token_file_real}" in
  /dev/shm/*) ok "resides in /dev/shm (tmpfs -- never written to disk)" ;;
  *)          info "not in /dev/shm; it is on a disk-backed filesystem, so remove it promptly" ;;
esac

# Read it here and nowhere else. `$(<file)` strips the trailing newline; `tr -d` removes the rest
# of any whitespace an editor may have added. From this line on the value exists only as
# ${OPERATOR_TOKEN}, is passed to Vault through an environment variable of a child process, and is
# never expanded into any string this script prints.
OPERATOR_TOKEN="$(tr -d '[:space:]' < "${OPERATOR_TOKEN_FILE}")"
[ -n "${OPERATOR_TOKEN}" ] || fail_hard "operator token file is empty"
ok "operator token loaded into this process (value not rendered)"

# --- vault invocation helpers ----------------------------------------------------------------
# `exec -T -e VAULT_TOKEN` hands the value to the container through the environment; it never
# appears in argv, so it is absent from `ps` output on the host.
vault_as() {
  local token="$1"; shift
  VAULT_TOKEN="${token}" docker compose -f "${COMPOSE_FILE}" exec -T -e VAULT_TOKEN vault "$@"
}
op()  { vault_as "${OPERATOR_TOKEN}" "$@"; }
rt()  { vault_as "${RUNTIME_TOKEN:-}" "$@"; }

# --- 2. canonical Vault state ---------------------------------------------------------------------
step "vault server posture"

status_json="$(op vault status -format=json 2>/dev/null)"
[ -n "${status_json}" ] || fail_hard "vault status unreachable -- is the vault service running?"

initialized="$(printf '%s' "${status_json}" | jq -r '.initialized')"
sealed="$(printf '%s' "${status_json}" | jq -r '.sealed')"
storage="$(printf '%s' "${status_json}" | jq -r '.storage_type // "unknown"')"
printf '  --    initialized=%s sealed=%s storage=%s\n' "${initialized}" "${sealed}" "${storage}"
[ "${initialized}" = "true" ] || fail_hard "vault is not initialized"
[ "${sealed}" = "false" ]     || fail_hard "vault is SEALED -- unseal it first (runbook step 3)"
[ "${storage}" = "file" ]     || fail_hard "storage backend is '${storage}', expected 'file'"

# Confirm the supplied credential really carries operator authority, rather than failing four
# checks later with a confusing "permission denied".
op_policies="$(op vault token lookup -format=json 2>/dev/null | jq -r '.data.policies | join(",")')"
[ -n "${op_policies}" ] || fail_hard "the supplied token cannot look itself up -- it is not an operator token"
printf '  --    operator token policies=%s\n' "${op_policies}"

step "KV engine"
kv_version="$(op vault secrets list -format=json 2>/dev/null | jq -r ".\"${MOUNT}/\".options.version // empty")"
printf '  --    mount=%s/ kv_version=%s\n' "${MOUNT}" "${kv_version:-none}"
[ "${kv_version}" = "2" ] || fail_hard "no KV v2 engine at ${MOUNT}/ -- runbook step 4"
ok "KV v2 confirmed authoritatively (sys/mounts, with operator authority)"

# --- 3. the policy is exactly the one line, and nothing else ---------------------------------------
step "policy ${POLICY_NAME}"

policy_text="$(op vault policy read "${POLICY_NAME}" 2>/dev/null)"
[ -n "${policy_text}" ] || fail_hard "policy ${POLICY_NAME} is not loaded -- runbook step 4"

# Strip comments and blank lines, then collapse whitespace, so the comparison is about the grant
# and not about formatting.
policy_norm="$(printf '%s\n' "${policy_text}" \
  | sed 's/#.*$//' \
  | tr -s '[:space:]' ' ' \
  | sed 's/^ //; s/ $//')"
policy_expected="path \"${MOUNT}/data/${KV_PATH}\" { capabilities = [\"read\"] }"

printf '  --    normalized: %s\n' "${policy_norm}"
if [ "${policy_norm}" = "${policy_expected}" ]; then
  ok "policy is exactly: read, on ${MOUNT}/data/${KV_PATH}, and nothing else"
else
  printf '  --    expected:   %s\n' "${policy_expected}"
  fail_hard "loaded policy is not equivalent to the committed least-privilege grant"
fi

for forbidden in create update patch delete list sudo destroy deny; do
  case "${policy_norm}" in
    *"\"${forbidden}\""*) fail_hard "policy grants capability '${forbidden}'" ;;
  esac
done
case "${policy_norm}" in
  *'*'*|*'+'*)                     fail_hard "policy contains a wildcard path" ;;
  *'"sys/'*|*'"auth/'*|*'"identity/'*) fail_hard "policy reaches an administrative path" ;;
  *'metadata/'*)                   fail_hard "policy grants metadata access the provider never uses" ;;
esac
ok "no wildcard, no write/delete/list/sudo, no sys|auth|identity, no metadata"

# --- 4. the canonical secret, by NAME, and the placeholder as a BOOLEAN ----------------------------
step "canonical secret ${MOUNT}/${KV_PATH}"

secret_json="$(op vault read -format=json "${MOUNT}/data/${KV_PATH}" 2>/dev/null)"
[ -n "${secret_json}" ] || fail_hard "canonical path is not readable with operator authority -- runbook step 5"

names="$(printf '%s' "${secret_json}" | jq -r '.data.data | keys[]' 2>/dev/null | tr '\n' ' ')"
printf '  --    field names: %s\n' "${names}"
printf '%s' "${names}" | grep -qw "${FIELD}" || fail_hard "field name ${FIELD} is absent"
ok "field=${FIELD} present (NAME only)"

# jq compares the stored value against the sentinel INSIDE jq and emits only true/false. The value
# is never interpolated into a shell variable, an argument list, or this script's output.
placeholder_intact="$(printf '%s' "${secret_json}" \
  | jq -r --arg f "${FIELD}" --arg s "${SENTINEL}" '(.data.data[$f] // "") == $s')"
printf '  --    placeholder_intact=%s\n' "${placeholder_intact}"
if [ "${placeholder_intact}" != "true" ]; then
  fail_hard "the canonical field no longer holds the readiness placeholder. This slice is NOT authorized to provision a real credential; restore the placeholder or escalate."
fi
ok "placeholder still installed -- the credential remains not present and the rail non-callable"

# --- 5. superseded runtime tokens -----------------------------------------------------------------
# Revoke ONLY what can be positively identified as a token carrying this policy. "Not the root
# token" is not an identification: this Vault is shared with whatever else the operator has been
# doing, and revoking an unidentified accessor is an outage looking for somewhere to happen.
step "existing runtime tokens"

revoked=0
unidentified=0
accessors="$(op vault list -format=json auth/token/accessors 2>/dev/null | jq -r '.[]' 2>/dev/null)"
if [ -z "${accessors}" ]; then
  info "accessor listing unavailable with this token -- skipping hygiene, NON_BLOCKING"
else
  while IFS= read -r accessor; do
    [ -n "${accessor}" ] || continue
    acc_policies="$(op vault token lookup -accessor -format=json "${accessor}" 2>/dev/null \
      | jq -r '.data.policies | join(",")' 2>/dev/null)"
    if [ -z "${acc_policies}" ]; then
      unidentified=$((unidentified + 1))
      continue
    fi
    case ",${acc_policies}," in
      *",${POLICY_NAME},"*)
        if op vault token revoke -accessor "${accessor}" >/dev/null 2>&1; then
          revoked=$((revoked + 1))
        fi
        ;;
    esac
  done <<EOF
${accessors}
EOF
fi
printf '  --    superseded_runtime_tokens_revoked=%s\n' "${revoked}"
printf '  --    unidentified_accessors_left_alone=%s (NON_BLOCKING -- later hygiene)\n' "${unidentified}"

# --- 6. mint ONE scoped runtime token --------------------------------------------------------------
step "mint runtime token"

RUNTIME_TOKEN="$(op vault token create \
  -policy="${POLICY_NAME}" -no-default-policy -period="${TOKEN_PERIOD}" -field=token 2>/dev/null)"
[ -n "${RUNTIME_TOKEN}" ] || fail_hard "token creation failed"
case "${RUNTIME_TOKEN}" in
  *[[:space:]]*) fail_hard "token creation returned unexpected output" ;;
esac
ok "one runtime token minted: policy=${POLICY_NAME}, -no-default-policy, period=${TOKEN_PERIOD}"
info "value not rendered"

rt_policies="$(rt vault token lookup -format=json 2>/dev/null | jq -r '.data.policies | join(",")')"
if [ -n "${rt_policies}" ]; then
  printf '  --    runtime token policies=%s\n' "${rt_policies}"
  case ",${rt_policies}," in
    *,root,*) fail_hard "the minted token carries the ROOT policy" ;;
  esac
else
  info "self-lookup refused -- expected with -no-default-policy"
fi

# --- 7. ALLOW before DENY --------------------------------------------------------------------------
step "runtime token capability (allow first)"

rt_json="$(rt vault read -format=json "${MOUNT}/data/${KV_PATH}" 2>/dev/null)"
rt_names="$(printf '%s' "${rt_json}" | jq -r '.data.data | keys[]' 2>/dev/null | tr '\n' ' ')"
if [ -z "${rt_names}" ]; then
  echo "  FAIL  runtime_canonical_read=FAIL"
  fail_hard "the new runtime token cannot read the canonical path -- stopping before injection"
fi
echo "runtime_canonical_read=PASS"
printf 'field=%s\n' "${FIELD}"
printf '  --    field names: %s\n' "${rt_names}"

step "runtime token restrictions (only meaningful now the read has passed)"
deny_failures=0
assert_denied() {
  local label="$1"; shift
  if "$@" >/dev/null 2>&1; then
    printf '  FAIL  %s=ALLOWED\n' "${label}"
    deny_failures=$((deny_failures + 1))
  else
    printf '  ok    %s=DENIED\n' "${label}"
  fi
}
assert_denied write         rt vault kv patch -mount="${MOUNT}" "${KV_PATH}" READINESS_PROBE=deny-me
assert_denied delete        rt vault kv metadata delete -mount="${MOUNT}" "${KV_PATH}"
assert_denied unrelated     rt vault read "${MOUNT}/data/aiagents/some-other-secret"
assert_denied metadata_path rt vault read "${MOUNT}/metadata/${KV_PATH}"
assert_denied sys_policy    rt vault read sys/policy
assert_denied token_create  rt vault token create -policy="${POLICY_NAME}"
[ "${deny_failures}" -eq 0 ] || fail_hard "${deny_failures} unauthorized action(s) were permitted"

# --- 8. inject the runtime token through the existing compose mechanism -----------------------------
# infra/docker-compose/.env is the repository's one env-injection mechanism; this adds no second
# one. The operator token is NOT written here, and neither is any Anthropic material.
step "inject runtime token into ${ENV_FILE##*/}"

umask 077
tmp_env="$(mktemp "${COMPOSE_DIR}/.env.tmp.XXXXXX")"
if [ -f "${ENV_FILE}" ]; then
  grep -v '^[[:space:]]*VAULT_TOKEN=' "${ENV_FILE}" > "${tmp_env}" || true
fi
printf 'VAULT_TOKEN=%s\n' "${RUNTIME_TOKEN}" >> "${tmp_env}"
mv "${tmp_env}" "${ENV_FILE}"
chmod 600 "${ENV_FILE}"

printf '  --    mode=%s\n' "$(stat -c '%a' "${ENV_FILE}")"
[ "$(stat -c '%a' "${ENV_FILE}")" = "600" ] || fail_hard ".env is not mode 600"

if git -C "${REPO_ROOT}" ls-files --error-unmatch "${ENV_FILE}" >/dev/null 2>&1; then
  fail_hard ".env is TRACKED by git -- refusing to leave a token in a tracked file"
fi
ok ".env is untracked and mode 600"
info "keys present: $(cut -d= -f1 "${ENV_FILE}" | tr '\n' ' ')"

for forbidden_key in ANTHROPIC_API_KEY VAULT_ROOT_TOKEN VAULT_UNSEAL_KEY; do
  if grep -q "^[[:space:]]*${forbidden_key}=" "${ENV_FILE}"; then
    fail_hard ".env contains ${forbidden_key}, which must never be written there"
  fi
done
ok "no Anthropic key, root token or unseal key in .env"

# --- 9. force-recreate the orchestrator -------------------------------------------------------------
# VAULT_TOKEN is an ENVIRONMENT change. `docker compose restart` restarts the existing container
# with the environment it was CREATED with, so it would restart the orchestrator with the old
# token and report success. The container has to be replaced.
step "force-recreate orchestrator (environment change)"

if ! docker compose -f "${COMPOSE_FILE}" up -d --force-recreate orchestrator 2>&1 | tail -5; then
  fail_hard "orchestrator did not come up"
fi

state=unknown
for _ in $(seq 1 30); do
  cid="$(docker compose -f "${COMPOSE_FILE}" ps -q orchestrator 2>/dev/null)"
  if [ -n "${cid}" ]; then
    state="$(docker inspect -f '{{.State.Status}}' "${cid}" 2>/dev/null)"
    [ "${state}" = "running" ] && break
  fi
  sleep 2
done
printf '  --    container replaced (not restarted): id changed to %s\n' "${cid:0:12}"
printf '  --    orchestrator state=%s\n' "${state:-unknown}"
[ "${state}" = "running" ] || fail_hard "orchestrator is not running"

# --- 10. value-free runtime configuration proof -------------------------------------------------------
step "runtime configuration (names and booleans only)"

oc() { docker compose -f "${COMPOSE_FILE}" exec -T orchestrator "$@"; }

config_failures=0
for pair in \
  "SECRET_PROVIDER=vault" \
  "VAULT_ADDR=http://vault:8200" \
  "VAULT_KV_MOUNT=${MOUNT}" \
  "VAULT_KV_PATH=${KV_PATH}" \
  "REASONING_PROVIDER=anthropic" \
  "REASONING_MODEL=claude-sonnet-5" \
  "REASONING_LIVE_NETWORK_ENABLED=false" ; do
  key="${pair%%=*}"
  want="${pair#*=}"
  got="$(oc printenv "${key}" 2>/dev/null | tr -d '\r')"
  if [ "${got}" = "${want}" ]; then
    printf '  ok    %s=%s\n' "${key}" "${got}"
  else
    printf '  FAIL  %s=%s (expected %s)\n' "${key}" "${got:-<unset>}" "${want}"
    config_failures=$((config_failures + 1))
  fi
done

# Presence only. The container reports whether the variable is non-empty; the value never crosses
# the container boundary.
token_present="$(oc sh -c '[ -n "${VAULT_TOKEN:-}" ] && echo yes || echo no' 2>/dev/null | tr -d '\r')"
printf '  --    VAULT_TOKEN present=%s\n' "${token_present}"
[ "${token_present}" = "yes" ] || config_failures=$((config_failures + 1))

anthropic_in_env="$(oc sh -c '[ -n "${ANTHROPIC_API_KEY:-}" ] && echo yes || echo no' 2>/dev/null | tr -d '\r')"
printf '  --    ANTHROPIC_API_KEY in orchestrator environment=%s (must be no)\n' "${anthropic_in_env}"
[ "${anthropic_in_env}" = "no" ] || config_failures=$((config_failures + 1))

[ "${config_failures}" -eq 0 ] || fail_hard "${config_failures} runtime configuration check(s) failed"

# --- 11. the canonical SecretProvider code path -------------------------------------------------------
# Not a re-implementation of the read: `provider_from_env` is what the runtime itself calls, and the
# point is to prove THAT path resolves to Vault rather than falling back to os.environ.
step "canonical SecretProvider"

provider_out="$(oc python - <<'PY' 2>&1
import json

from shared.sdk.secrets.provider import provider_from_env

provider = provider_from_env()
names = provider.list_available_secrets()
print(json.dumps({
    "provider_class": type(provider).__name__,
    "provider": provider.status.get("provider"),
    "mount": provider.status.get("mount"),
    "path": provider.status.get("path"),
    "names": sorted(names),
    "get_secret_present": provider.get_secret("ANTHROPIC_API_KEY").present,
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
printf '  --    provider=%s mount=%s path=%s\n' \
  "$(printf '%s' "${provider_json}" | jq -r '.provider')" \
  "$(printf '%s' "${provider_json}" | jq -r '.mount')" \
  "$(printf '%s' "${provider_json}" | jq -r '.path')"
printf '  --    list_available_secrets=%s\n' "$(printf '%s' "${provider_json}" | jq -c '.names')"
printf '  --    get_secret("%s").present=%s\n' "${FIELD}" "$(printf '%s' "${provider_json}" | jq -r '.get_secret_present')"
printf '  --    has_secret("%s")=%s\n' "${FIELD}" "$(printf '%s' "${provider_json}" | jq -r '.has_secret')"

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
check_json '.provider' 'vault' 'provider=vault'
check_json '.mount' "${MOUNT}" "mount=${MOUNT}"
check_json '.path' "${KV_PATH}" "path=${KV_PATH}"
check_json ".names | index(\"${FIELD}\") != null" 'true' "list_available_secrets contains ${FIELD}"
# The placeholder is installed, so the NAME is visible and the CREDENTIAL is absent. Both, at once,
# is the whole readiness claim.
check_json '.get_secret_present' 'false' "get_secret(${FIELD}).present=false (placeholder -- expected)"
check_json '.has_secret' 'false' "has_secret(${FIELD})=false (non-callable -- expected)"
[ "${provider_failures}" -eq 0 ] || fail_hard "${provider_failures} SecretProvider check(s) failed"

# --- 12. the readiness script, through the compose mechanism ------------------------------------------
step "scripts/verify_vault_runtime_readiness.sh --from-compose-env"
if bash "${VERIFY_SH}" --from-compose-env; then
  readiness=PASS
else
  readiness=FAIL
fi

# --- 13. surrender the operator authority --------------------------------------------------------------
step "operator token file"
if [ "${readiness}" = "PASS" ] && [ "${KEEP_TOKEN_FILE}" = "no" ]; then
  if rm -f "${OPERATOR_TOKEN_FILE}"; then
    TOKEN_FILE_REMOVED=yes
    ok "operator token file removed"
  fi
else
  info "retained: operator authority may still be needed"
fi
unset OPERATOR_TOKEN RUNTIME_TOKEN

printf '\noperator_token_file_removed=%s\n' "${TOKEN_FILE_REMOVED}"
printf 'VAULT_RUNTIME_READINESS: %s\n' "${readiness}"
[ "${readiness}" = "PASS" ] || exit 1
echo "COMPLETION: PASS"
