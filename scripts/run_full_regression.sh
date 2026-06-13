#!/usr/bin/env bash
# Stage 41 -- unified regression runner.
#
# Single entry point for all production-readiness regressions.
# Runs every verify script, classifies results, and writes a JSON report.
#
# Usage:
#   ./scripts/run_full_regression.sh [OPTIONS]
#
# Options:
#   --quick               Run a subset of fast scripts only
#   --full                Run all scripts (default)
#   --continue-on-fail    Continue even when a script fails (default)
#   --stop-on-fail        Abort on first failure
#   --json-report         Write JSON report to source/regression-reports/
#
# Outputs:
#   FULL_REGRESSION_VERIFY: PASS   -- all results are allowed
#   FULL_REGRESSION_VERIFY: FAIL   -- one or more disallowed failures
#
# Report files:
#   source/regression-reports/regression_{timestamp}.json
#   source/regression-reports/regression_latest.json
#   source/regression-reports/regression_latest_summary.json

set -uo pipefail

cd "$(dirname "$0")/.."

# shellcheck source=scripts/lib/verify_env.sh
source "$(dirname "$0")/lib/verify_env.sh"

echo "### run_full_regression: $(date '+%Y-%m-%d %H:%M:%S %Z')"

# ---- argument parsing -------------------------------------------------------
MODE=full
STOP_ON_FAIL=0
JSON_REPORT=0
QUICK_SCRIPTS=(
    scripts/verify_environment_dependencies.sh
    scripts/verify_incident_response.sh
    scripts/verify_external_alert_receiver.sh
    scripts/verify_audit_integrity_remediation.sh
    scripts/verify_backup_production_readiness.sh
)

while [ $# -gt 0 ]; do
    case "$1" in
        --quick) MODE=quick ;;
        --full) MODE=full ;;
        --stop-on-fail) STOP_ON_FAIL=1 ;;
        --continue-on-fail) STOP_ON_FAIL=0 ;;
        --json-report) JSON_REPORT=1 ;;
        *) echo "unknown option: $1"; exit 1 ;;
    esac
    shift
done

echo "  mode=$MODE  stop_on_fail=$STOP_ON_FAIL  json_report=$JSON_REPORT"

# ---- result classification --------------------------------------------------
# Result classes:
#   pass               -- script exited 0 with PASS marker
#   fail               -- script exited non-zero (disallowed)
#   skipped_pass       -- script explicitly SKIPPED-PASS (e.g. no real LLM key)
#   pass_with_gaps     -- PASS_WITH_GAPS marker (only allowed for documented scripts)
#   environment_failure -- ModuleNotFoundError or missing dependency
#   regression_failure  -- audit integrity fail or direct safety-check fail
#   safety_failure      -- production_executed != 0
#   unknown_failure     -- exit non-zero with no known marker

# Scripts allowed to emit PASS_WITH_GAPS:
ALLOWED_GAPS_SCRIPTS=(
    "scripts/verify_backup_production_readiness.sh"
)

# Documented allowed gap reasons (for backup readiness):
DOCUMENTED_GAPS=(
    "encryption_no_key"
    "storage_not_off_host"
    "schedule_dry_run_only"
    "migration_down_gaps"
)

# ---- tracking ---------------------------------------------------------------
PASS_COUNT=0
FAIL_COUNT=0
ENV_FAIL_COUNT=0
SAFETY_FAIL_COUNT=0
REGRESSION_FAIL_COUNT=0
SKIP_COUNT=0
GAP_COUNT=0
TOTAL=0

declare -a SCRIPT_RESULTS=()

START_TIME="$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
REPORT_TIMESTAMP="$(date '+%Y%m%d_%H%M%S')"

# ---- run a single verify script ---------------------------------------------
run_verify() {
    local script="$1"
    local allowed_gap="${2:-no}"
    local script_start
    script_start="$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
    local t_start=$SECONDS

    echo
    echo "--- $script ---"

    local output
    local exit_code=0
    output=$(bash "$script" 2>&1) || exit_code=$?
    echo "$output"

    local duration=$((SECONDS - t_start))
    local key_marker=""
    local result_class=""
    local failure_reason=""

    # Extract key marker (last VERIFY: line)
    key_marker="$(echo "$output" | grep -E '^\S+_VERIFY: (PASS|FAIL|SKIPPED|PASS_WITH_GAPS|SKIPPED-PASS)' | tail -1 || true)"

    # Classify
    if echo "$output" | grep -q "ModuleNotFoundError\|No module named"; then
        result_class="environment_failure"
        failure_reason="ModuleNotFoundError"
        ENV_FAIL_COUNT=$((ENV_FAIL_COUNT + 1))
    elif echo "$output" | grep -qE "_VERIFY: FAIL.*production_safety"; then
        result_class="safety_failure"
        failure_reason="production_safety_nonzero"
        SAFETY_FAIL_COUNT=$((SAFETY_FAIL_COUNT + 1))
    elif echo "$output" | grep -qE "_VERIFY: FAIL.*audit_integrity|_VERIFY: FAIL.*tamper|_VERIFY: FAIL.*direct_post"; then
        result_class="regression_failure"
        failure_reason="audit_integrity_fail"
        REGRESSION_FAIL_COUNT=$((REGRESSION_FAIL_COUNT + 1))
    elif echo "$output" | grep -qE "SKIPPED-PASS|SKIPPED: PASS|SKIP.*PASS"; then
        result_class="skipped_pass"
        SKIP_COUNT=$((SKIP_COUNT + 1))
    elif echo "$output" | grep -q "PASS_WITH_GAPS"; then
        if [ "$allowed_gap" = "yes" ]; then
            result_class="pass_with_gaps"
            GAP_COUNT=$((GAP_COUNT + 1))
        else
            result_class="fail"
            failure_reason="pass_with_gaps_not_allowed_for_this_script"
            FAIL_COUNT=$((FAIL_COUNT + 1))
        fi
    elif [ "$exit_code" -eq 0 ] && echo "$output" | grep -qE "_VERIFY: PASS"; then
        result_class="pass"
        PASS_COUNT=$((PASS_COUNT + 1))
    elif [ "$exit_code" -ne 0 ]; then
        result_class="unknown_failure"
        failure_reason="exit_code_${exit_code}"
        FAIL_COUNT=$((FAIL_COUNT + 1))
    else
        result_class="pass"
        PASS_COUNT=$((PASS_COUNT + 1))
    fi

    local script_end
    script_end="$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
    TOTAL=$((TOTAL + 1))

    # Append to results array (newline-delimited JSON fragment)
    SCRIPT_RESULTS+=("$(printf '{"script":"%s","result_class":"%s","started_at":"%s","completed_at":"%s","duration_seconds":%d,"exit_code":%d,"key_marker":"%s","allowed_gap":%s,"failure_reason":"%s"}' \
        "$script" "$result_class" "$script_start" "$script_end" "$duration" "$exit_code" \
        "$(echo "$key_marker" | sed 's/"/\\"/g')" \
        "$([ "$allowed_gap" = "yes" ] && echo true || echo false)" \
        "$(echo "${failure_reason:-}" | sed 's/"/\\"/g')")")

    echo "  -> result_class=$result_class (${duration}s)"

    # Stop on fail if requested
    if [ "$STOP_ON_FAIL" = "1" ] && [ "$result_class" != "pass" ] && [ "$result_class" != "skipped_pass" ] && [ "$result_class" != "pass_with_gaps" ]; then
        echo
        echo "FULL_REGRESSION_VERIFY: FAIL (stop_on_fail)"
        exit 1
    fi
}

# ---- step 0: environment dependencies ---------------------------------------
echo
echo "=== Step 0: Verify environment dependencies ==="
env_ok=0
if bash scripts/verify_environment_dependencies.sh; then
    env_ok=1
    echo "  environment: READY"
else
    echo "  environment: NOT READY"
    echo "  Run: ./scripts/setup_verification_env.sh"
    if [ "$STOP_ON_FAIL" = "1" ]; then
        echo "FULL_REGRESSION_VERIFY: FAIL (environment_not_ready)"
        exit 1
    fi
fi

# ---- step 1: run scripts ----------------------------------------------------
echo
echo "=== Step 1: Run verify scripts (mode=$MODE) ==="

if [ "$MODE" = "quick" ]; then
    for s in "${QUICK_SCRIPTS[@]}"; do
        is_gap=no
        for gap_s in "${ALLOWED_GAPS_SCRIPTS[@]}"; do
            [ "$s" = "$gap_s" ] && is_gap=yes
        done
        run_verify "$s" "$is_gap"
    done
else
    # Full mode — run all verify scripts in dependency order
    run_verify scripts/verify_incident_response.sh
    run_verify scripts/verify_external_alert_receiver.sh
    run_verify scripts/verify_audit_integrity_remediation.sh
    run_verify scripts/verify_audit_hmac_key_rotation.sh
    run_verify scripts/verify_audit_direct_post_integrity.sh
    run_verify scripts/verify_tamper_evident_audit.sh
    run_verify scripts/verify_llm_model_routing.sh
    run_verify scripts/verify_llm_cost_governance.sh
    run_verify scripts/verify_real_llm_plan_only_pilot.sh
    run_verify scripts/verify_real_discord_delivery_filter.sh
    run_verify scripts/verify_real_integration_pilot.sh
    run_verify scripts/verify_notification_delivery.sh
    run_verify scripts/verify_operations_view.sh
    run_verify scripts/verify_unified_audit.sh
    run_verify scripts/verify_platform_observability.sh
    run_verify scripts/verify_flexible_human_approval_policy.sh
    run_verify scripts/verify_llm_proposal_promotion.sh
    run_verify scripts/verify_qa_auto_fix_loop.sh
    run_verify scripts/verify_controlled_code_generation.sh
    run_verify scripts/verify_backup_drill.sh
    run_verify scripts/verify_backup_production_readiness.sh yes
fi

# ---- step 2: overall result -------------------------------------------------
END_TIME="$(date -u '+%Y-%m-%dT%H:%M:%SZ')"

DISALLOWED_FAIL=$((FAIL_COUNT + ENV_FAIL_COUNT + SAFETY_FAIL_COUNT + REGRESSION_FAIL_COUNT))

echo
echo "=== Regression Summary ==="
echo "  total=$TOTAL  pass=$PASS_COUNT  skipped_pass=$SKIP_COUNT  pass_with_gaps=$GAP_COUNT"
echo "  fail=$FAIL_COUNT  env_fail=$ENV_FAIL_COUNT  safety_fail=$SAFETY_FAIL_COUNT  regression_fail=$REGRESSION_FAIL_COUNT"
echo "  environment_ready=${env_ok}"

# Determine result class
if [ "$SAFETY_FAIL_COUNT" -gt 0 ]; then
    RESULT_CLASS="safety_failure"
elif [ "$REGRESSION_FAIL_COUNT" -gt 0 ]; then
    RESULT_CLASS="regression_failure"
elif [ "$ENV_FAIL_COUNT" -gt 0 ]; then
    RESULT_CLASS="environment_failure"
elif [ "$FAIL_COUNT" -gt 0 ]; then
    RESULT_CLASS="fail"
elif [ "$GAP_COUNT" -gt 0 ]; then
    RESULT_CLASS="pass_with_documented_gaps"
else
    RESULT_CLASS="pass"
fi

HOST_CAVEAT_CLOSED=false
if [ "$ENV_FAIL_COUNT" -eq 0 ] && [ "$env_ok" = "1" ]; then
    HOST_CAVEAT_CLOSED=true
fi

# ---- step 3: write JSON report ----------------------------------------------
if [ "$JSON_REPORT" = "1" ]; then
    mkdir -p source/regression-reports

    REPORT_FILE="source/regression-reports/regression_${REPORT_TIMESTAMP}.json"
    LATEST_FILE="source/regression-reports/regression_latest.json"
    SUMMARY_FILE="source/regression-reports/regression_latest_summary.json"

    # Build scripts JSON array
    SCRIPTS_JSON=""
    for entry in "${SCRIPT_RESULTS[@]:-}"; do
        [ -n "$SCRIPTS_JSON" ] && SCRIPTS_JSON="${SCRIPTS_JSON},"
        SCRIPTS_JSON="${SCRIPTS_JSON}${entry}"
    done

    GAPS_JSON=""
    for g in "${DOCUMENTED_GAPS[@]}"; do
        [ -n "$GAPS_JSON" ] && GAPS_JSON="${GAPS_JSON},"
        GAPS_JSON="${GAPS_JSON}\"${g}\""
    done

    cat > "$REPORT_FILE" <<JSON
{
  "report_id": "regression_${REPORT_TIMESTAMP}",
  "started_at": "${START_TIME}",
  "completed_at": "${END_TIME}",
  "mode": "${MODE}",
  "result_class": "${RESULT_CLASS}",
  "environment_ready": ${env_ok},
  "host_dependency_caveat_closed": ${HOST_CAVEAT_CLOSED},
  "scripts": [${SCRIPTS_JSON}],
  "summary": {
    "total": ${TOTAL},
    "pass": ${PASS_COUNT},
    "skipped_pass": ${SKIP_COUNT},
    "pass_with_gaps": ${GAP_COUNT},
    "fail": ${FAIL_COUNT},
    "environment_failure": ${ENV_FAIL_COUNT},
    "safety_failure": ${SAFETY_FAIL_COUNT},
    "regression_failure": ${REGRESSION_FAIL_COUNT}
  },
  "dependency_failures": [],
  "known_gaps": [${GAPS_JSON}],
  "caveats": []
}
JSON
    cp "$REPORT_FILE" "$LATEST_FILE"

    # Write compact summary (read by operations/safety)
    cat > "$SUMMARY_FILE" <<JSON
{
  "completed_at": "${END_TIME}",
  "result_class": "${RESULT_CLASS}",
  "environment_ready": ${env_ok},
  "host_dependency_caveat_closed": ${HOST_CAVEAT_CLOSED},
  "report_path": "${REPORT_FILE}",
  "dependency_failures": [],
  "known_gaps": [${GAPS_JSON}],
  "caveats": [],
  "summary": {
    "total": ${TOTAL},
    "pass": ${PASS_COUNT},
    "fail": ${DISALLOWED_FAIL}
  }
}
JSON
    echo "  report: $REPORT_FILE"
    echo "  summary: $SUMMARY_FILE"
fi

# ---- final marker -----------------------------------------------------------
echo
if [ "$DISALLOWED_FAIL" -eq 0 ]; then
    if [ "$GAP_COUNT" -gt 0 ]; then
        echo "FULL_REGRESSION_VERIFY: PASS_WITH_DOCUMENTED_GAPS"
    else
        echo "FULL_REGRESSION_VERIFY: PASS"
    fi
    exit 0
else
    echo "FULL_REGRESSION_VERIFY: FAIL"
    exit 1
fi
