# SBOM / Container Security — Non-Production Limitations (Step 54.3)

This stage delivers a **local, offline** SBOM + container security baseline. The following are
explicitly not done and not production-ready.

## Not performed this stage

- No registry login; no image pull-with-credential; no image push.
- No image signing; no Cosign key generation; no production attestation; no external attestation
  / SBOM upload.
- No external image vulnerability scan; no private registry scan; **no CVE verdict**.
- No Kubernetes deploy / ArgoCD sync / Helm install; no GitHub write / PR; no production gate.
- No full regression.

## Baseline limitations (honestly recorded, not hidden)

- **SBOM** is a custom manifest baseline (no transitive resolution, no image layer
  introspection) — **not** a production SBOM.
- **Image inventory** records empty digests (no image pulled to resolve them) and the
  non-deployable placeholder tag on first-party images.
- **Dockerfiles** all run as root (no USER) — non-root readiness is **not** claimed; it requires
  a non-production cluster smoke (Step 55).
- **Image policy scan** produces policy findings only (digest/root/job gaps); a missing or
  unavailable CVE scan is never reported as clean.
- **Job image** reuses the orchestrator image and lacks `pg_dump`/`psql` — runtime smoke required.
- **Signing/attestation** is model-only and disabled; no key is committed.

## Deferred

- **Step 54.4** — threat model generation, release risk summary, security evidence package,
  integrated Step 54 verification, full regression.
- **Step 55** — non-production cluster smoke: runtime non-root validation, PVC / NetworkPolicy
  runtime validation, `pg_dump` / `psql` job runtime smoke.

**Claude Code must not decide Production readiness.**
