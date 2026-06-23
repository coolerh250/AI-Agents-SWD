# Scan Exclusion Policy (Step 54.2)

Source of truth: [infra/security/scan-exclusion-policy.yaml](../../infra/security/scan-exclusion-policy.yaml).

Every exclusion is explicit and carries a reason. Exclusions may **not** hide production code,
secret-like files, Dockerfiles, requirements/package files, Helm/GitOps manifests, or the
generated delivery package (unless separately scanned). Reviewed before any production gate.

## Secret fixture classification

Secret-shaped matches in reviewed intentional fixtures (`tests/**`, `docs/**`, detector /
redaction modules, the secret/security verifier scripts) are classified `informational` — they
are still **scanned and reported** (not hidden), but are not confirmed leaks. A high-confidence
credential shape in any other file is a confirmed `critical`. This mirrors the Step 53 scoping
and keeps the baseline honest while reflecting that the repo has no real committed secrets.

Covered by `tests/test_scan_exclusion_policy.py`.
