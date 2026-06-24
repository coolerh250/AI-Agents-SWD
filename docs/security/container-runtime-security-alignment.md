# Container Runtime Security Alignment (Step 54.3)

Source: [infra/security/container-runtime-security-alignment.yaml](../../infra/security/container-runtime-security-alignment.yaml).

Maps the Step 51 Helm securityContext baseline (runAsNonRoot 10001, readOnlyRootFilesystem,
allowPrivilegeEscalation=false, drop-all capabilities, RuntimeDefault seccomp,
automountServiceAccountToken=false, writable /tmp emptyDir) against the image reality.

Key point: **a static manifest securityContext is not image runtime compatibility.** The
first-party images run as root (no USER), so `runAsNonRoot` / read-only-root start cannot be
confirmed without a non-production cluster smoke (Step 55). Third-party exceptions (postgres /
redis / vault) and the job-image `pg_dump`/`psql` gap are recorded. `productionReady: false`.
Verified by `scripts/verify_container_runtime_security_alignment.py`
(`CONTAINER_RUNTIME_SECURITY_ALIGNMENT_VERIFY`).
