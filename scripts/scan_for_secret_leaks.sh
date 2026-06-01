#!/usr/bin/env bash
# Stage 26 secret-leak scanner.
#
# Sweeps the committed file set (docs, README, source/progress.md,
# infra/runtime/*.example, docker-compose templates, scripts/) plus the
# generated runtime-health logs for substrings that look like a real
# token. A small list of LITERAL substrings (placeholders, env-var
# references, the redaction token) are allowed; any match that doesn't
# contain one is a leak.
#
# Two files are deliberately skipped — they legitimately carry the
# forbidden regex patterns as DOCUMENTATION:
#   * scripts/scan_for_secret_leaks.sh — the scanner itself
#   * docs/operations/secrets-management.md — runbook quoting the regexes
#   * tests/test_secret_leak_scanner.py — fixture text
#
# Exit code:
#   0   SECRET_LEAK_SCAN: PASS
#   1   SECRET_LEAK_SCAN: FAIL — printed lines redact the matched text
set -uo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

# Scan targets — globbed individually so a missing path doesn't break
# the whole sweep.
TARGETS=(
  "$REPO_ROOT/README.md"
  "$REPO_ROOT/docs"
  "$REPO_ROOT/source/progress.md"
  "$REPO_ROOT/source/runtime-health.log"
  "$REPO_ROOT/source/runtime-health-staging.log"
  "$REPO_ROOT/infra/runtime"
  "$REPO_ROOT/infra/docker-compose"
  "$REPO_ROOT/scripts"
)

# Patterns the scanner refuses. Each is POSIX ERE — works on every
# grep we deploy on (Linux gnu grep + git-bash on Windows). ``\b`` and
# ``\s`` are not portable so we use explicit word boundaries via
# anchored char classes.
FORBIDDEN_PATTERNS=(
  'ghp_[A-Za-z0-9_]{16,}'
  'github_pat_[A-Za-z0-9_]{16,}'
  'xoxb-[A-Za-z0-9-]{8,}'
  '(^|[^A-Za-z0-9])Bot [A-Za-z0-9._-]{20,}'
  '(^|[^A-Za-z0-9])Bearer [A-Za-z0-9._-]{30,}'
  '(^|[^A-Za-z0-9])sk-[A-Za-z0-9]{20,}'
)

# Literal substrings that, when present on a matching line, whitelist
# the match. These are EXACT substrings (ERE-escaped where needed) —
# they don't share the structure of any forbidden token.
ALLOW_LITERAL_SUBSTRINGS=(
  'PLACEHOLDER_DO_NOT_COMMIT_REAL_VALUE'
  '\*\*\*REDACTED\*\*\*'
  '\$\{GITHUB_TOKEN'
  '\$\{DISCORD_BOT_TOKEN'
  '\$\{VAULT_TOKEN'
  '\$\{POSTGRES_PASSWORD'
  '\$\{ALERTMANAGER_WEBHOOK_URL'
  # Pre-existing mnemonic fixtures that read like tokens but aren't.
  'ghp_REAL_OR_FINE_GRAINED'
  'ghp_TEST_NOT_REAL'
  'ghp_REPLACE_ME'
  'ghp_NEVER_LEAK_THIS_VALUE'
  'ghp_NEVER_LEAK'
  # Pragma any future fixture / docs example can carry on the same
  # line to mark the match as intentional.
  'leak-scan: allow'
)

# Files the scanner deliberately skips (documentation of the regexes).
SKIP_BASENAMES=(
  "scan_for_secret_leaks.sh"
  "secrets-management.md"
  "test_secret_leak_scanner.py"
)

echo "### scan_for_secret_leaks: $(date '+%Y-%m-%d %H:%M:%S %Z')"

leaks=0

_skip_basename() {
  local f="$1"
  local base
  base=$(basename "$f")
  for s in "${SKIP_BASENAMES[@]}"; do
    if [ "$base" = "$s" ]; then
      return 0
    fi
  done
  return 1
}

scan_file() {
  local f="$1"
  if [ ! -f "$f" ]; then
    return 0
  fi
  if _skip_basename "$f"; then
    return 0
  fi
  for pat in "${FORBIDDEN_PATTERNS[@]}"; do
    while IFS= read -r line; do
      [ -z "$line" ] && continue
      local content="${line#*:}"
      local allowed=0
      for allow in "${ALLOW_LITERAL_SUBSTRINGS[@]}"; do
        if echo "$content" | grep -Eq "$allow" 2>/dev/null; then
          allowed=1
          break
        fi
      done
      if [ "$allowed" = "0" ]; then
        leaks=$((leaks+1))
        local lineno="${line%%:*}"
        printf '  LEAK in %s:%s  pattern=%s\n' "$f" "$lineno" "$pat"
      fi
    done < <(grep -En "$pat" "$f" 2>/dev/null || true)
  done
}

scan_path() {
  local p="$1"
  if [ -f "$p" ]; then
    scan_file "$p"
  elif [ -d "$p" ]; then
    while IFS= read -r -d '' f; do
      scan_file "$f"
    done < <(find "$p" -type f \
        \( -name '*.md' -o -name '*.yml' -o -name '*.yaml' \
        -o -name '*.json' -o -name '*.sh' -o -name '*.py' \
        -o -name '*.log' -o -name '*.example' -o -name '*.sample' \) \
        -print0 2>/dev/null)
  fi
}

for t in "${TARGETS[@]}"; do
  scan_path "$t"
done

echo
echo "  scan complete. leak hits: $leaks"
if [ "$leaks" -eq 0 ]; then
  echo "SECRET_LEAK_SCAN: PASS"
  exit 0
else
  echo "SECRET_LEAK_SCAN: FAIL"
  exit 1
fi
