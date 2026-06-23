# Security & Supply Chain — Non-Production Limitations (Step 54.1)

This stage models policy and inventory only. The following are explicitly **not** done and
**not** production-ready.

## Not performed this stage

- No SAST / dependency / secret / image vulnerability scan executed.
- No SBOM generated; no attestation; no signing / Cosign key.
- No image build, push, scan, or registry login.
- No external scanner connection or source upload.
- No GitHub Advanced Security integration; no GitHub write; no PR creation; no workflow secret.
- No production release gate; no deployment gate; no Kubernetes deploy / ArgoCD sync / Helm install.
- No external secret store connection; no secret value read.
- No full regression.

## Recorded blockers / gaps (modeled, not fixed)

- **Container images not digest-pinned** — Helm values carry empty digest fields; first-party
  images use a placeholder tag.
- **Dockerfiles run as root** — none of the 20 first-party Dockerfiles declare a non-root `USER`.
- **Python dependencies unpinned** — 21 `requirements.txt` files list package names without
  versions/hashes; no lockfile. (Node has `package-lock.json`.)
- **No cluster runtime smoke** — first-party images and the migration/backup/restore jobs
  (`pg_dump` / `psql`) still require a non-production cluster runtime smoke (Step 51 observation).

These are inventoried and modeled here; no Dockerfile, Helm value, or dependency file was
modified by this stage (inventory/policy only).

## Deferred to later sub-stages

- **Step 54.2** — actual secret scan / SAST / dependency scan toolchain + local execution +
  scan result normalization.
- **Step 54.3** — SBOM generation, image digest policy enforcement, container image
  vulnerability baseline, image signing / attestation model.
- **Step 54.4** — threat model generation, release risk summary, security evidence package,
  integrated Step 54 verification, full regression.

**Claude Code must not decide Production readiness.**
