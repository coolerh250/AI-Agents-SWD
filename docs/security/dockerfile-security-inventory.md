# Dockerfile Security Inventory (Step 54.3)

Source: [infra/security/dockerfile-security-inventory.yaml](../../infra/security/dockerfile-security-inventory.yaml).

Evidence-backed per-Dockerfile security surface (USER / root default / base image / exposed ports
/ ADD / curl-pipe-shell / secret copy / healthcheck / multi-stage). Reflects the actual repo;
Dockerfiles are **not** modified this stage.

Findings: all 20 first-party Dockerfiles use `python:3.12-slim`, declare **no USER** (run as
root), have no HEALTHCHECK, use COPY (not ADD), no curl-pipe-shell, no secret copy, single-stage.
The root gap is recorded as a blocker; non-root readiness is **not** claimed. Verified by
`scripts/verify_dockerfile_security_inventory.py` (`DOCKERFILE_SECURITY_INVENTORY_VERIFY`), which
cross-checks the count against `git ls-files`.
