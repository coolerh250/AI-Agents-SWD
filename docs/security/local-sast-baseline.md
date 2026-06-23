# Local SAST Baseline (Step 54.2)

Runner: `scripts/run_local_sast_scan.py`. Local-only, no network, no source upload.

Runs bounded `custom_static_checks` over allowlisted Python targets. This is a **limited**
baseline, **not** a full SAST engine (no dataflow/taint analysis); bandit/semgrep are
runtime-detected and recorded as unavailable when absent. Rules detect: `eval`/`exec`,
shell-invoked subprocess, unsafe YAML load, disabled TLS verification (all high); subprocess
usage and bind-all (low); production-bypass TODO markers and broad exception swallowing in
security modules (medium).

Detection is proven against the intentional fixture
[tests/fixtures/sast_unsafe_samples.py](../../tests/fixtures/sast_unsafe_samples.py) (excluded
from the normal scan). Output redacted to `--json-report` (default
`.runtime/security/sast-scan-report.json`, never committed); limitations recorded;
`productionReady=false`.

Verified by `scripts/verify_local_sast_baseline.py` (`LOCAL_SAST_BASELINE_VERIFY`).
