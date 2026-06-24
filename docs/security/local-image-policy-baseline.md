# Local Image Policy Baseline (Step 54.3)

Runner: `scripts/run_local_image_policy_scan.py`. Local-only; no registry login, no image
pull/push, no CVE lookup.

Reads the committed container image inventory + Dockerfile security inventory and emits
normalized policy findings: `IMG-NO-DIGEST` (medium), `IMG-LATEST-TAG` (high),
`IMG-DOCKERFILE-ROOT` (medium), `IMG-JOB-NO-PGCLIENT` (medium),
`IMG-REGISTRY-CRED-UNBOUNDED` (low). Output redacted to `--json-report` (default
`.runtime/security/images/image-policy-report.json`, never committed); `productionReady=false`.
A missing/unavailable CVE scan is never reported as clean. Verified by
`scripts/verify_local_image_policy_baseline.py` (`LOCAL_IMAGE_POLICY_BASELINE_VERIFY`).
