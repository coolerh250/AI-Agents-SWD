#!/usr/bin/env bash
# AT-M3.6B.2 readiness -- value-free verification of the test-runtime Vault rail.
#
# Prints booleans, names, diagnostic CATEGORIES and Vault status fields. It NEVER prints a secret
# value, a prefix or a length -- not the Anthropic key, not the runtime token, not the root token.
# Its output is safe to paste into a report.
#
# Usage, from the compose directory or the repo root:
#
#     VAULT_TOKEN=<scoped runtime token> scripts/verify_vault_runtime_readiness.sh
#     scripts/verify_vault_runtime_readiness.sh --from-compose-env
#
# The token must be the RUNTIME token, not the root token -- the point of the denial checks is that
# a read-only token is actually read-only, and a root token would pass them by being allowed to do
# everything.
#
# TWO ORDERING RULES ARE LOAD-BEARING, and both exist because the first version of this script
# could report PASS while proving nothing:
#
#   1. A MISSING TOKEN IS A HARD FAIL, checked before anything else. Every denial check below is
#      "Vault refused this request". With no token Vault refuses all of them, for the wrong
#      reason, and a script that counted those refusals as passes would certify an unconfigured
#      runtime as ready.
#
#   2. THE CANONICAL READ MUST SUCCEED BEFORE ANY DENIAL COUNTS. The same failure one step further
#      in: a token that is expired, revoked, or scoped to the wrong path is refused everywhere,
#      including where refusal is the desired answer. So the read the runtime actually makes is
#      the gate -- if it fails, the script reports a diagnostic category and stops, rather than
#      collecting five meaningless refusals and calling them a least-privilege proof.

set -uo pipefail

MOUNT="${VAULT_KV_MOUNT:-secret}"
KV_PATH="${VAULT_KV_PATH:-aiagents/test-runtime}"
FIELD="ANTHROPIC_API_KEY"
SENTINEL="PLACEHOLDER_DO_NOT_COMMIT_REAL_VALUE"
COMPOSE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../infra/docker-compose" && pwd)"
ENV_FILE="${COMPOSE_DIR}/.env"

FROM_COMPOSE_ENV=no
for arg in "$@"; do
  case "${arg}" in
    --from-compose-env) FROM_COMPOSE_ENV=yes ;;
    -h|--help) sed -n '2,29p' "${BASH_SOURCE[0]}"; exit 0 ;;
    *) printf 'unknown argument: %s\n' "${arg}" >&2; exit 2 ;;
  esac
done

pass=0
fail=0

ok()   { printf '  ok    %s\n' "$1"; pass=$((pass + 1)); }
bad()  { printf '  FAIL  %s\n' "$1"; fail=$((fail + 1)); }
note() { printf '  --    %s\n' "$1"; }

verdict() {
  echo
  printf 'READINESS_CHECKS passed=%s failed=%s\n' "${pass}" "${fail}"
  if [ "${fail}" -eq 0 ]; then
    echo "VAULT_RUNTIME_READINESS: PASS"
    exit 0
  fi
  echo "VAULT_RUNTIME_READINESS: FAIL"
  exit 1
}

echo "AT-M3.6B.2 VAULT RUNTIME READINESS -- value-free checks"
echo "mount=${MOUNT} path=${KV_PATH} field=${FIELD}"
echo

# --- 0. the token gate ---------------------------------------------------------------------------
# Reading the compose env file is OPT-IN, never automatic: the default consults the environment
# only, so "I forgot the token" is always a FAIL here and never a silent pickup of whatever the
# deployment directory happens to hold.
token_source=none
if [ -n "${VAULT_TOKEN:-}" ] && [ "${VAULT_TOKEN}" != "${SENTINEL}" ]; then
  token_source=environment
elif [ "${FROM_COMPOSE_ENV}" = "yes" ] && [ -r "${ENV_FILE}" ]; then
  # Read the one assignment, in this process, without echoing it and without sourcing a file whose
  # other lines are none of this script's business.
  # \042 and \047 are the double and single quote: an env file may quote the value, and a quote
  # character is not part of a Vault token.
  candidate="$(sed -n 's/^[[:space:]]*VAULT_TOKEN=//p' "${ENV_FILE}" | tail -n 1 | tr -d '\042\047')"
  if [ -n "${candidate}" ] && [ "${candidate}" != "${SENTINEL}" ]; then
    export VAULT_TOKEN="${candidate}"
    token_source=compose_env_file
  fi
  unset candidate
fi

printf '  --    token_source=%s\n' "${token_source}"
if [ "${token_source}" = "none" ]; then
  bad "VAULT_TOKEN is unset, empty or still the placeholder"
  echo "READINESS_DIAGNOSTIC: TOKEN_MISSING_OR_DENIED"
  note "No denial check was run. With no token every Vault request is refused, and counting those"
  note "refusals as passes would certify an unconfigured runtime as ready."
  verdict
fi
ok "a runtime token was supplied"

# Run a vault command inside the compose vault container. stdout/stderr are captured by the caller;
# we never echo a captured value, only decide on it.
v()     { docker compose -f "${COMPOSE_DIR}/docker-compose.yml" exec -T -e VAULT_TOKEN vault "$@"; }
v_err() { docker compose -f "${COMPOSE_DIR}/docker-compose.yml" exec -T -e VAULT_TOKEN vault "$@" 2>&1 >/dev/null; }

# --- 1. server posture ---------------------------------------------------------------------------
status_json="$(v vault status -format=json 2>/dev/null)"
if [ -z "${status_json}" ]; then
  bad "vault status unreachable (container down, or Vault not listening)"
else
  initialized="$(printf '%s' "${status_json}" | jq -r '.initialized')"
  sealed="$(printf '%s' "${status_json}" | jq -r '.sealed')"
  storage="$(printf '%s' "${status_json}" | jq -r '.storage_type // "unknown"')"

  [ "${initialized}" = "true" ] && ok "vault initialized" || bad "vault NOT initialized -- run the bootstrap runbook"
  [ "${sealed}" = "false" ] && ok "vault unsealed" || bad "vault SEALED -- unseal it (manual; there is no auto-unseal)"
  [ "${storage}" = "file" ] && ok "persistent storage backend: file" || bad "storage backend is '${storage}', expected 'file' (dev mode uses 'inmem')"
fi

# --- 2. the KV v2 engine is mounted ---------------------------------------------------------------
# `server -dev` auto-mounted this and a real server does not, so a missing mount is the first thing
# to check when a write fails with "no handler for route".
kv_version="$(v vault secrets list -format=json 2>/dev/null | jq -r ".\"${MOUNT}/\".options.version // empty")"
if [ "${kv_version}" = "2" ]; then
  ok "KV v2 engine mounted at ${MOUNT}/"
else
  note "KV v2 version at ${MOUNT}/ not readable with this token (expected with the scoped runtime"
  note "token, whose policy grants no sys/mounts access). The raw read below is authoritative --"
  note "it is the request the runtime actually makes."
fi

# --- 3. THE GATE: the canonical raw KV v2 read the provider makes ---------------------------------
# GET /v1/${MOUNT}/data/${KV_PATH} -- byte for byte the request VaultKvSecretProvider._load_kv()
# issues. Not `vault kv get`, whose CLI helper first calls sys/internal/ui/mounts and is therefore
# refused by a correctly-scoped runtime policy for reasons that have nothing to do with readiness.
raw_json="$(v vault read -format=json "${MOUNT}/data/${KV_PATH}" 2>/dev/null)"
names=""
if [ -n "${raw_json}" ]; then
  names="$(printf '%s' "${raw_json}" | jq -r '.data.data | keys[]' 2>/dev/null)"
fi

if [ -z "${names}" ]; then
  # Classify, do not swallow. The category is derived from Vault's own error text and is itself
  # value-free; the error text is never printed, because a Vault error can quote the request path
  # and there is no reason to widen what this script emits.
  read_err="$(v_err vault read -format=json "${MOUNT}/data/${KV_PATH}")"
  case "${read_err}" in
    *"permission denied"*|*"missing client token"*|*"403"*) diag=TOKEN_MISSING_OR_DENIED ;;
    *"no handler for route"*|*"unsupported path"*)          diag=NO_HANDLER_FOR_ROUTE ;;
    *"No value found at"*|*"404"*|"")                       diag=NO_VALUE_FOUND ;;
    *)                                                      diag=OTHER_READ_FAILURE ;;
  esac
  bad "runtime_canonical_read=FAIL -- ${MOUNT}/data/${KV_PATH} is not readable with this token"
  printf 'READINESS_DIAGNOSTIC: %s\n' "${diag}"
  case "${diag}" in
    TOKEN_MISSING_OR_DENIED) note "the token is expired, revoked, or carries a policy that does not cover this path" ;;
    NO_HANDLER_FOR_ROUTE)    note "no KV v2 engine is mounted at ${MOUNT}/ -- see step 4 of the runbook" ;;
    NO_VALUE_FOUND)          note "the mount exists but nothing is written at ${KV_PATH} -- see step 5 of the runbook" ;;
    OTHER_READ_FAILURE)      note "Vault is reachable and refused for none of the three known reasons; check container logs" ;;
  esac
  note "STOPPING BEFORE THE DENIAL CHECKS. A token that cannot read is refused everywhere,"
  note "including where refusal is the desired answer, so those checks would prove nothing."
  verdict
fi

ok "runtime_canonical_read=PASS"
printf '  --    field names present: %s\n' "$(printf '%s' "${names}" | tr '\n' ' ')"
if printf '%s\n' "${names}" | grep -qx "${FIELD}"; then
  ok "field=${FIELD} (NAME only -- the value is never read here)"
else
  bad "field name ${FIELD} absent"
fi

# --- 4. the runtime token is READ-ONLY ------------------------------------------------------------
# Each of these MUST be refused, and each is only meaningful because the read above succeeded.
if v vault kv patch -mount="${MOUNT}" "${KV_PATH}" READINESS_PROBE=deny-me >/dev/null 2>&1; then
  bad "write=ALLOWED -- the policy is too broad"
else
  ok "write=DENIED"
fi

if v vault kv metadata delete -mount="${MOUNT}" "${KV_PATH}" >/dev/null 2>&1; then
  bad "delete=ALLOWED -- the policy is too broad"
else
  ok "delete=DENIED"
fi

if v vault read "${MOUNT}/data/aiagents/some-other-secret" >/dev/null 2>&1; then
  bad "unrelated_path=ALLOWED -- the policy is not path-scoped"
else
  ok "unrelated_path=DENIED"
fi

if v vault read "${MOUNT}/metadata/${KV_PATH}" >/dev/null 2>&1; then
  bad "metadata_path=ALLOWED -- the provider never reads metadata; the grant is unused privilege"
else
  ok "metadata_path=DENIED"
fi

if v vault read sys/policy >/dev/null 2>&1; then
  bad "sys_policy=ALLOWED -- the token has administrative reach"
else
  ok "sys_policy=DENIED"
fi

# --- 5. the token is not root ---------------------------------------------------------------------
if policies="$(v vault token lookup -format=json 2>/dev/null | jq -r '.data.policies | join(",")')"; then
  case ",${policies}," in
    *,root,*) bad "the supplied token carries the ROOT policy -- never inject root into a runtime" ;;
    *)        ok "token policies: ${policies}" ;;
  esac
else
  note "token self-lookup refused (expected with -no-default-policy; not a defect)"
fi

verdict
