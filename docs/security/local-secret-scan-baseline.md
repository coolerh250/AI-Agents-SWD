# Local Secret Scan Baseline (Step 54.2)

Runner: `scripts/run_local_secret_scan.py`. Local-only, no network, no token, no source upload.

Scans the allowlisted targets for committed inline secret/token shapes (reusing the Step 53
detector). Classification:

- **High-confidence credential shapes** (github/openai/aws token, JWT, private key, kubeconfig,
  DB URL with password, service-account token) outside reviewed fixtures → confirmed `critical`
  (production blocker).
- **Keyword/format heuristics** (GUID, `secret`-named variable, bearer, webhook, email) →
  low-confidence `low` review items.
- **Reviewed intentional fixtures** (tests/detector/docs) → `informational`.

Exit codes: `0` no confirmed finding · `1` confirmed finding / policy violation · `2` scanner
unavailable / config error. Output redacted to `--json-report` (default
`.runtime/security/secret-scan-report.json`, never committed). A `tool_unavailable` run is never
a PASS. The custom baseline is **not** a full secret scanner; strict committed-secret prevention
remains Step 53's `SECRET_NO_INLINE_VALUES_VERIFY`.

Verified by `scripts/verify_local_secret_scan_baseline.py` (`LOCAL_SECRET_SCAN_BASELINE_VERIFY`).
