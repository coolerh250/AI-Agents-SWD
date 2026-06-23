# Local Dependency Scan Baseline (Step 54.2)

Runner: `scripts/run_local_dependency_scan.py`. Local-only, **no external CVE lookup**.

Inspects local manifests / lockfiles only. It does **not** query an external CVE database, so it
never reports "clean" on the basis of a CVE check. pip-audit / npm-audit / osv-scanner are
network-dependent and recorded as `network_required` / unavailable.

Manifest-policy findings: missing Python lockfile across the `requirements.txt` files (medium),
unpinned Python dependencies (low), and Node `package-lock.json` status. Output redacted to
`--json-report` (default `.runtime/security/dependency-scan-report.json`, never committed);
`productionReady=false`.

Verified by `scripts/verify_local_dependency_scan_baseline.py`
(`LOCAL_DEPENDENCY_SCAN_BASELINE_VERIFY`).
