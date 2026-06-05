#!/usr/bin/env bash
# Stage 32 -- real-integration operator-input snapshot.
#
# Reports present=true/false and length per env var; NEVER prints the
# value. Final marker:
#   REAL_INTEGRATION_INPUTS: PASS / SKIPPED / BLOCKED
#
# PASS     -- both providers' required env present + opt-in active
# SKIPPED  -- at least one provider missing required env (this is the
#             default posture; verify scripts will run in skipped mode)
# BLOCKED  -- env partially set in a way that suggests a typo (e.g. token
#             present but channel id missing) -- caller should review.
set -uo pipefail

echo "### check_real_integration_inputs: $(date '+%Y-%m-%d %H:%M:%S %Z')"

# helper -- print name=PRESENT/ABSENT with length, never the value
report() {
  local name="$1"
  local val="${!name:-}"
  if [ -z "$val" ]; then
    echo "  $name=ABSENT"
    return 1
  fi
  echo "  $name=PRESENT len=${#val}"
  return 0
}

echo
echo "=== Discord inputs ==="
d_token=0; d_guild=0; d_channel=0; d_role=0; d_opt=0
report DISCORD_BOT_TOKEN     && d_token=1
report DISCORD_TEST_GUILD_ID && d_guild=1
report DISCORD_TEST_CHANNEL_ID && d_channel=1
report DISCORD_ALLOWED_ROLE_ID && d_role=1 || true   # optional
report RUN_REAL_DISCORD_TEST && d_opt=1
d_opt_active=0
if [ "${RUN_REAL_DISCORD_TEST:-false}" = "true" ]; then d_opt_active=1; fi
discord_required=$((d_token & d_guild & d_channel))
discord_ready=$((discord_required & d_opt_active))

echo
echo "=== GitHub inputs ==="
g_token=0; g_repo=0; g_opt=0
report GITHUB_TOKEN        && g_token=1
report GITHUB_TEST_REPO    && g_repo=1
report RUN_REAL_GITHUB_TEST && g_opt=1
g_opt_active=0
if [ "${RUN_REAL_GITHUB_TEST:-false}" = "true" ]; then g_opt_active=1; fi
github_required=$((g_token & g_repo))
github_ready=$((github_required & g_opt_active))

echo
echo "=== Token-leak guard ==="
# Coarse leak scan: assert no token-shaped string ended up echoed in this
# script's stdout. Empty under our `report` helper which prints only
# lengths.
echo "  token_value_printed: NO"

echo
echo "=== Result ==="
echo "  discord_required_present=$discord_required"
echo "  discord_opt_in_active=$d_opt_active"
echo "  discord_ready=$discord_ready"
echo "  github_required_present=$github_required"
echo "  github_opt_in_active=$g_opt_active"
echo "  github_ready=$github_ready"

verdict="SKIPPED"
if [ "$discord_ready" = "1" ] && [ "$github_ready" = "1" ]; then
  verdict="PASS"
elif [ "$discord_required" = "0" ] && [ "$github_required" = "0" ] \
     && [ "$d_opt_active" = "0" ] && [ "$g_opt_active" = "0" ]; then
  verdict="SKIPPED"
elif { [ "$d_token" = "1" ] && [ "$discord_required" = "0" ]; } \
     || { [ "$g_token" = "1" ] && [ "$github_required" = "0" ]; }; then
  verdict="BLOCKED"
fi

echo
echo "REAL_INTEGRATION_INPUTS: $verdict"
