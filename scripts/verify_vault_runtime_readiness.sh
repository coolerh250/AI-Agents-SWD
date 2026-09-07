#!/usr/bin/env bash
# AT-M3.6B.2 readiness -- value-free verification of the test-runtime Vault rail.
#
# Prints booleans, names and Vault status fields. It NEVER prints a secret value, a prefix or a
# length -- not the Anthropic key, not the runtime token, not the root token. Its output is safe to
# paste into a report.
#
# Usage, from the compose directory or the repo root:
#
#     scripts/verify_vault_runtime_readiness.sh
#
# Reads VAULT_TOKEN from the environment when checking runtime-token behaviour. Run it with the
# RUNTIME token, not the root token -- the point of the last three checks is that a read-only token
# is actually read-only, and a root token would pass them by being allowed to do everything.

set -uo pipefail

MOUNT="${VAULT_KV_MOUNT:-secret}"
PATH_="${VAULT_KV_PATH:-aiagents/test-runtime}"
FIELD="ANTHROPIC_API_KEY"
COMPOSE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../infra/docker-compose" && pwd)"

pass=0
fail=0

ok()   { printf '  ok    %s\n' "$1"; pass=$((pass + 1)); }
bad()  { printf '  FAIL  %s\n' "$1"; fail=$((fail + 1)); }
note() { printf '  --    %s\n' "$1"; }

# Run a vault command inside the compose vault container. stdout is captured by the caller; we
# never echo a captured value, only decide on it.
v() { docker compose -f "${COMPOSE_DIR}/docker-compose.yml" exec -T -e VAULT_TOKEN vault "$@"; }

echo "AT-M3.6B.2 VAULT RUNTIME READINESS -- value-free checks"
echo "mount=${MOUNT} path=${PATH_} field=${FIELD}"
echo

# --- 1. server posture ---------------------------------------------------------------------
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

# --- 2. the secret exists, and only its FIELD NAMES are read ---------------------------------
if names="$(v vault kv get -mount="${MOUNT}" -format=json "${PATH_}" 2>/dev/null | jq -r '.data.data | keys[]' 2>/dev/null)"; then
  if [ -n "${names}" ]; then
    ok "secret ${MOUNT}/${PATH_} exists"
    printf '  --    field names present: %s\n' "$(printf '%s' "${names}" | tr '\n' ' ')"
    if printf '%s\n' "${names}" | grep -qx "${FIELD}"; then
      ok "field name ${FIELD} present (NAME only -- value never read here)"
    else
      bad "field name ${FIELD} absent"
    fi
  else
    bad "secret ${MOUNT}/${PATH_} has no fields"
  fi
else
  note "kv get refused -- expected when running with the RUNTIME token, whose policy"
  note "deliberately omits the sys/internal/ui/mounts preflight the KV v2 CLI helper needs."
  note "Falling back to the raw v2 data path, which is the request the provider actually makes."
  if names="$(v vault read -format=json "${MOUNT}/data/${PATH_}" 2>/dev/null | jq -r '.data.data | keys[]' 2>/dev/null)"; then
    ok "runtime token can READ ${MOUNT}/data/${PATH_}"
    printf '  --    field names present: %s\n' "$(printf '%s' "${names}" | tr '\n' ' ')"
    printf '%s\n' "${names}" | grep -qx "${FIELD}" \
      && ok "field name ${FIELD} present (NAME only)" \
      || bad "field name ${FIELD} absent"
  else
    bad "cannot read ${MOUNT}/data/${PATH_} with the supplied token"
  fi
fi

# --- 3. the runtime token is READ-ONLY -------------------------------------------------------
# Each of these MUST be refused. A success here is a privilege the runtime should not have.
if v vault kv patch -mount="${MOUNT}" "${PATH_}" READINESS_PROBE=deny-me >/dev/null 2>&1; then
  bad "runtime token was allowed to WRITE -- the policy is too broad"
else
  ok "write refused"
fi

if v vault kv metadata delete -mount="${MOUNT}" "${PATH_}" >/dev/null 2>&1; then
  bad "runtime token was allowed to DELETE -- the policy is too broad"
else
  ok "delete refused"
fi

if v vault read "${MOUNT}/data/aiagents/some-other-secret" >/dev/null 2>&1; then
  bad "runtime token could read an UNRELATED path -- the policy is not path-scoped"
else
  ok "unrelated path refused"
fi

if v vault read sys/policy >/dev/null 2>&1; then
  bad "runtime token could read sys/policy -- it has administrative reach"
else
  ok "sys/policy refused"
fi

# --- 4. the token is not root ------------------------------------------------------------------
if policies="$(v vault token lookup -format=json 2>/dev/null | jq -r '.data.policies | join(",")')"; then
  case ",${policies}," in
    *,root,*) bad "the supplied token carries the ROOT policy -- never inject root into a runtime" ;;
    *)        ok "token policies: ${policies}" ;;
  esac
else
  note "token self-lookup refused (expected with -no-default-policy; not a defect)"
fi

echo
printf 'READINESS_CHECKS passed=%s failed=%s\n' "${pass}" "${fail}"
[ "${fail}" -eq 0 ] && echo "VAULT_RUNTIME_READINESS: PASS" || echo "VAULT_RUNTIME_READINESS: FAIL"
exit $((fail > 0))
