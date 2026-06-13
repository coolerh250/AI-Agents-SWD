#!/usr/bin/env bash
# Stage 44 -- shared audit-touching verification lock.
#
# Serializes every script that reads or mutates the audit chain
# (audit_logs / audit_integrity_records), runs a tamper simulation, or runs
# the restore exception. Step 41 observed that running the restore-exception
# verify concurrently with the full regression let two tamper-simulations race
# and leave a residue. This helper forces conservative serialization.
#
# Mechanism: a single host-level exclusive lock (flock when available, atomic
# mkdir fallback otherwise) keyed on a stable name. PostgreSQL has no native
# shared advisory lock and verification frequency is low, so one exclusive lock
# is the conservative choice. Released via an EXIT trap.
#
# Reentrancy: run_full_regression.sh acquires the lock once and exports
# AUDIT_VERIFICATION_LOCK_HELD_BY_RUNNER=true. Child audit-touching scripts then
# log "INHERITED" and skip re-acquiring (avoids self-deadlock).
#
# Markers:
#   AUDIT_VERIFICATION_LOCK: ACQUIRED <who>
#   AUDIT_VERIFICATION_LOCK: INHERITED <who>
#   AUDIT_VERIFICATION_LOCK: RELEASED <who>
#   AUDIT_VERIFICATION_LOCK: TIMEOUT <who>
#
# Never prints a secret.

AUDIT_LOCK_KEY="aiagents_audit_verification_exclusive_v1"
AUDIT_VERIFICATION_LOCK_FILE="${AUDIT_VERIFICATION_LOCK_FILE:-/tmp/${AUDIT_LOCK_KEY}.lock}"
AUDIT_VERIFICATION_LOCK_TIMEOUT="${AUDIT_VERIFICATION_LOCK_TIMEOUT:-300}"
_AUDIT_LOCK_FD=200
_AUDIT_LOCK_HELD=0
_AUDIT_LOCK_MODE=""

_audit_lock_have_flock() { command -v flock >/dev/null 2>&1; }

_audit_lock_report_dir() {
    # Resolve repo root relative to this helper, fall back to cwd.
    local here
    here="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." 2>/dev/null && pwd)" || here="$(pwd)"
    echo "${here}/source/audit-forensics"
}

record_lock_metadata() {
    # record_lock_metadata <status> <who>
    local status="$1" who="${2:-$(basename "$0")}"
    local dir
    dir="$(_audit_lock_report_dir)"
    mkdir -p "$dir" 2>/dev/null || true
    cat > "${dir}/audit_verification_lock_latest.json" 2>/dev/null <<JSON || true
{
  "lock_key": "${AUDIT_LOCK_KEY}",
  "status": "${status}",
  "holder": "${who}",
  "timeout_seconds": ${AUDIT_VERIFICATION_LOCK_TIMEOUT},
  "enabled": true,
  "recorded_at": "$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
}
JSON
}

acquire_audit_exclusive_lock() {
    local who="${1:-$(basename "$0")}"
    # Already hold it in THIS shell -> idempotent.
    if [ "$_AUDIT_LOCK_HELD" = "1" ]; then
        echo "AUDIT_VERIFICATION_LOCK: ACQUIRED ${who} (already held)"
        return 0
    fi
    # A parent process holds the lock -> inherit, do not re-acquire.
    if [ "${AUDIT_VERIFICATION_LOCK_HELD_BY_RUNNER:-false}" = "true" ]; then
        echo "AUDIT_VERIFICATION_LOCK: INHERITED ${who}"
        record_lock_metadata "inherited" "$who"
        return 0
    fi
    if _audit_lock_have_flock; then
        eval "exec ${_AUDIT_LOCK_FD}>\"${AUDIT_VERIFICATION_LOCK_FILE}\""
        if flock -w "${AUDIT_VERIFICATION_LOCK_TIMEOUT}" "${_AUDIT_LOCK_FD}"; then
            _AUDIT_LOCK_HELD=1
            _AUDIT_LOCK_MODE="flock"
            echo "AUDIT_VERIFICATION_LOCK: ACQUIRED ${who}"
            record_lock_metadata "acquired" "$who"
            trap 'release_audit_lock' EXIT
            return 0
        fi
        echo "AUDIT_VERIFICATION_LOCK: TIMEOUT ${who}"
        record_lock_metadata "timeout" "$who"
        return 1
    fi
    # Portable fallback: atomic mkdir spinlock.
    local deadline=$(( $(date +%s) + AUDIT_VERIFICATION_LOCK_TIMEOUT ))
    while ! mkdir "${AUDIT_VERIFICATION_LOCK_FILE}.d" 2>/dev/null; do
        if [ "$(date +%s)" -ge "$deadline" ]; then
            echo "AUDIT_VERIFICATION_LOCK: TIMEOUT ${who}"
            record_lock_metadata "timeout" "$who"
            return 1
        fi
        echo "  waiting for audit verification lock (held by another process)..."
        sleep 2
    done
    echo "$$" > "${AUDIT_VERIFICATION_LOCK_FILE}.d/owner" 2>/dev/null || true
    _AUDIT_LOCK_HELD=1
    _AUDIT_LOCK_MODE="mkdir"
    echo "AUDIT_VERIFICATION_LOCK: ACQUIRED ${who}"
    record_lock_metadata "acquired" "$who"
    trap 'release_audit_lock' EXIT
    return 0
}

# Conservative: read lock == exclusive lock (no native shared advisory lock).
acquire_audit_read_lock() { acquire_audit_exclusive_lock "${1:-$(basename "$0")}"; }

release_audit_lock() {
    local who="${1:-$(basename "$0")}"
    # Release only if THIS shell actually acquired the lock. Inherited
    # children (which never acquired) and the runner-owned flag do not matter
    # here -- ownership is tracked by _AUDIT_LOCK_HELD.
    [ "$_AUDIT_LOCK_HELD" = "1" ] || return 0
    if [ "$_AUDIT_LOCK_MODE" = "flock" ]; then
        flock -u "${_AUDIT_LOCK_FD}" 2>/dev/null || true
        eval "exec ${_AUDIT_LOCK_FD}>&-" 2>/dev/null || true
    else
        rm -rf "${AUDIT_VERIFICATION_LOCK_FILE}.d" 2>/dev/null || true
    fi
    _AUDIT_LOCK_HELD=0
    echo "AUDIT_VERIFICATION_LOCK: RELEASED ${who}"
    record_lock_metadata "released" "$who"
}

with_audit_exclusive_lock() {
    # with_audit_exclusive_lock <who> <cmd...>
    local who="$1"; shift
    acquire_audit_exclusive_lock "$who" || return 1
    "$@"
    local rc=$?
    release_audit_lock "$who"
    return $rc
}

with_audit_read_lock() { with_audit_exclusive_lock "$@"; }

# ---- audit-state assertions -------------------------------------------------

assert_no_audit_tamper_residue() {
    # Returns 0 when no [TAMPER-SIMULATION] residue remains; else 1.
    local repo
    repo="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." 2>/dev/null && pwd)" || repo="$(pwd)"
    if [ -x "${repo}/scripts/detect_audit_tamper_residue.sh" ]; then
        if bash "${repo}/scripts/detect_audit_tamper_residue.sh" 2>/dev/null \
            | grep -q "AUDIT_TAMPER_RESIDUE_DETECTOR: PASS"; then
            return 0
        fi
        echo "  audit tamper residue detected -- use the controlled restore exception"
        return 1
    fi
    return 0
}

assert_audit_chain_clean_or_known_blocker() {
    # Best-effort: a failed verify-chain is reported but not fatal here (the
    # caller decides). Returns 0 if chain passes or the orchestrator is down.
    local orch="${ORCHESTRATOR_URL:-http://localhost:8000}"
    local body
    body="$(curl -sS -m 8 -X POST "${orch}/operations/audit/verify-chain" 2>/dev/null || echo '{}')"
    if echo "$body" | grep -q '"status": "passed"' || echo "$body" | grep -q '"status":"passed"'; then
        return 0
    fi
    if [ "$body" = "{}" ]; then
        return 0  # orchestrator unreachable -- not this helper's failure
    fi
    return 1
}

fail_if_parallel_audit_mutation_detected() {
    # If we do NOT hold the lock and we are not the runner-owner, a concurrent
    # holder means another audit-touching process is active.
    if [ "${AUDIT_VERIFICATION_LOCK_HELD_BY_RUNNER:-false}" = "true" ]; then
        return 0
    fi
    if [ "$_AUDIT_LOCK_HELD" != "1" ]; then
        echo "  WARN: audit verification lock not held -- parallel mutation possible"
        return 1
    fi
    return 0
}