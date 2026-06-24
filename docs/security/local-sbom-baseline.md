# Local SBOM Baseline (Step 54.3)

Runner: `scripts/run_local_sbom_baseline.py`. Local-only, no network, no registry, no image pull.

Builds an internal manifest-based SBOM from `requirements.txt` files, `package.json` /
`package-lock.json`, and the container image inventory (Dockerfile base images + image refs). It
does **not** resolve transitive trees or introspect image layers — the custom baseline is
**limited**, not a production SBOM. Records the Python lockfile gap and unpinned-digest
limitation. Output redacted to `--json-report` (default
`.runtime/security/sbom/local-sbom-baseline.json`, never committed); `productionReady=false`.
Verified by `scripts/verify_local_sbom_baseline.py` (`LOCAL_SBOM_BASELINE_VERIFY`).
