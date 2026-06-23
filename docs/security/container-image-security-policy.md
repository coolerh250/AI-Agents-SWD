# Container Image Security Policy (Step 54.1)

Source of truth: [infra/security/container-image-security-policy.yaml](../../infra/security/container-image-security-policy.yaml).

Models container image security requirements and records the **current gaps**. No Dockerfile
is modified, no image is built / pushed / scanned. `productionReady: false`.

## Requirements

Digest pinning required; `latest` prohibited before runtime smoke; non-root USER required;
read-only root filesystem alignment; minimal base image desired; image vulnerability scan
required; SBOM required; signature/attestation (future); registry credential via Step 53
secret refs; **no image push in this stage**.

## Current gaps

- `dockerfiles_missing_nonroot_user` (high) — all 20 first-party Dockerfiles run as root.
- `helm_images_not_digest_pinned` (high) — Helm values have empty digest fields.
- `first_party_images_placeholder_tag` (medium) — tag `step-51-1-placeholder`.
- `third_party_images_tag_only` (medium) — postgres:16 / redis:7 / vault:1.17.

## Step 51 observations carried forward

- First-party images require a non-root cluster smoke.
- Job images (`pg_dump` / `psql`) require a runtime smoke.

Enforcement deferred to **Step 54.3**.
