# Security Scan — Non-Production Limitations (Step 54.2)

This stage delivers a **local, offline** scan baseline. The following are explicitly not done
and not production-ready.

## Not performed this stage

- No external scanner upload; no SaaS scanner; no GitHub Advanced Security; no GitHub write / PR.
- No external CVE database lookup (pip-audit / npm-audit / osv-scanner are network-dependent).
- No SBOM generation; no image vulnerability scan; no image push / registry login; no signing.
- No production release gate / deployment gate; no Kubernetes deploy / ArgoCD sync / Helm install.
- No full regression.

## Baseline limitations (honestly recorded, not hidden)

- **Secret scan** is a custom baseline, not a full secret scanner; keyword/format heuristics
  (GUID, `secret`-named vars) are low-confidence review items. Strict committed-secret prevention
  remains Step 53's `SECRET_NO_INLINE_VALUES_VERIFY`.
- **SAST** is `custom_static_checks` — pattern-based, no dataflow/taint analysis; bandit/semgrep
  are runtime-detected and reported `tool_unavailable` when absent.
- **Dependency scan** is manifest-policy only (missing lockfile, unpinned deps); **no CVE
  verdict** is produced. A missing CVE check is never reported as clean.
- A `tool_unavailable` scan is never `passed`; a missing scan is never `clean`.

## Deferred

- **Step 54.3** — SBOM generation, image digest enforcement, container image vulnerability
  baseline, image signing / attestation, registry credential usage.
- **Step 54.4** — threat model generation, release risk summary, security evidence package,
  integrated Step 54 verification, full regression.

**Claude Code must not decide Production readiness.**
