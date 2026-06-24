# Container Image Inventory (Step 54.3)

Source: [infra/security/container-image-inventory.yaml](../../infra/security/container-image-inventory.yaml).

Normalized inventory of every image referenced by compose / Helm / Dockerfiles / jobs, reflecting
the actual repo. 20 first-party images (`aiagents/*:step-51-1-placeholder`, base
`python:3.12-slim`), the batch-job image (reuses orchestrator; lacks `pg_dump`/`psql`), and
third-party images (postgres:16, redis:7, hashicorp/vault:1.17, prom/*, grafana/*).

**No digest is pinned** (digests empty; no image was pulled to resolve them) and **no `:latest`
tag** is used. Per-image blockers record the digest/placeholder/root gaps. No image is falsely
marked `digestPinned`. Verified by `scripts/verify_container_image_inventory.py`
(`CONTAINER_IMAGE_INVENTORY_VERIFY`).
