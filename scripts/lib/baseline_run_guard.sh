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
# reached via overlapping chains are skipped with a PASS exit. Strictness is
# preserved -- every baseline still runs once, completely; only redundant identical
# re-runs are removed.
#
# Scope: keyed off BASELINE_GUARD_RUNDIR, exported by the first baseline that runs
# and inherited by all chained children. A baseline invoked standalone (no rundir
# in the environment) starts a fresh scope, so it always runs.

if [ -z "${BASELINE_GUARD_RUNDIR:-}" ]; then
  BASELINE_GUARD_RUNDIR="$(mktemp -d "${TMPDIR:-/tmp}/baseline_guard.XXXXXX")"
  export BASELINE_GUARD_RUNDIR
fi

# baseline_run_once <key>
#   return 0 -> caller is the first to run this baseline; proceed.
#   return 1 -> already verified in this run; caller should skip (exit 0).
baseline_run_once() {
  local key="$1"
  local marker="$BASELINE_GUARD_RUNDIR/${key}.done"
  if [ -e "$marker" ]; then
    echo "########## DEDUP: ${key} already verified in this run -- skipping re-chain ##########"
    return 1
  fi
  : > "$marker"
  return 0
}
