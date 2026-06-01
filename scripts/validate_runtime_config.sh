#!/usr/bin/env bash
# Thin bash wrapper around scripts/validate_runtime_config.py so the
# Stage 24 verify scripts and operator runbook can call a familiar
# `.sh` instead of remembering the Python entrypoint. Forwards every
# argument verbatim.
set -uo pipefail
exec python3 "$(dirname "$0")/validate_runtime_config.py" "$@"
