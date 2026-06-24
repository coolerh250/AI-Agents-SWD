# Per-run dedup guard for chained *_baseline.sh verifiers.
#
# The combined baseline shells re-verify their predecessor baselines, and those
# predecessors re-verify theirs. Because the chains overlap (e.g. scan_toolchain,
# supply_chain, secret_mgmt and identity_foundation all re-chain identity_foundation,
# which transitively drags the full platform regression), the same heavy baselines
# were re-executed many times in a single top-level run.
#
# This guard makes each baseline run fully exactly ONCE per top-level run. The first
# invocation (reached via the deepest chain) executes in full; later invocations
# reached via overlapping chains are skipped. A skip replays the first run's actual
# exit code, so a baseline that FAILED on its first run still fails its re-chains --
# dedup removes duplicate work, it never masks a failure. Strictness is preserved:
# every baseline still runs once, completely, and its real pass/fail propagates.
#
# Scope: keyed off BASELINE_GUARD_RUNDIR, exported by the first baseline that runs
# and inherited by all chained children. A baseline invoked standalone (no rundir
# in the environment) starts a fresh scope, so it always runs.

if [ -z "${BASELINE_GUARD_RUNDIR:-}" ]; then
  BASELINE_GUARD_RUNDIR="$(mktemp -d "${TMPDIR:-/tmp}/baseline_guard.XXXXXX")"
  export BASELINE_GUARD_RUNDIR
fi

# EXIT trap (registered for the first run only) records the script's real exit code.
_baseline_guard_record() {
  local ec=$?
  [ -n "${_BASELINE_GUARD_MARKER:-}" ] && printf '%s' "$ec" > "${_BASELINE_GUARD_MARKER}"
}

# baseline_run_once <key>
#   first invocation this run -> register the EXIT trap, return 0, caller proceeds.
#   later invocation         -> print a DEDUP line and EXIT with the first run's
#                               recorded exit code (RUNNING => cycle guard, exit 0).
baseline_run_once() {
  local key="$1"
  local marker="${BASELINE_GUARD_RUNDIR}/${key}.status"
  if [ -e "$marker" ]; then
    local prev
    prev="$(cat "$marker" 2>/dev/null || true)"
    if [ "$prev" = "RUNNING" ]; then
      echo "########## DEDUP: ${key} already in progress this run (cycle guard) -- skipping ##########"
      exit 0
    fi
    echo "########## DEDUP: ${key} already verified this run (exit ${prev}) -- skipping re-chain ##########"
    exit "${prev:-0}"
  fi
  printf 'RUNNING' > "$marker"
  _BASELINE_GUARD_MARKER="$marker"
  trap '_baseline_guard_record' EXIT
  return 0
}
