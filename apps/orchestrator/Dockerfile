FROM python:3.12-slim

WORKDIR /app

COPY apps/orchestrator/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY shared/ ./shared/
COPY apps/orchestrator/src/ ./
# Stage 50 -- Admin Console v0 read-only static UI (zero-build fallback served
# at /admin). A built Vite bundle (admin_console_static/dist) is preferred when
# present; the committed static/ fallback guarantees /admin responds.
COPY apps/admin-console/static/ ./admin_console_static/
# Stage 52 -- allowlisted verification scripts (path-resolution for the
# governed operator verification rerun). The runner uses realpath containment to
# the scripts/ dir and shell=False with fixed argv; heavy docker-dependent
# verifications still require a runner with docker access (documented limitation).
COPY scripts/ ./scripts/
COPY migrations/ ./migrations/
# Stage 53G (Step 51.4) / Stage 57A (Step 55) -- committed read-only runtime baseline
# summary + non-production runtime smoke plans consumed by the /operations/runtime/*
# read-only API + /operations/safety. Non-sensitive (booleans/enums/counts/names/plan
# metadata only); no rendered manifests, no kubeconfig, no secrets.
COPY infra/kubernetes/ ./infra/kubernetes/
# Stage 58A (Step 56) -- committed read-only non-production ArgoCD manual-sync
# summary / plan / boundary / project policy + manifests consumed by the
# /operations/gitops/nonprod-argocd/* read-only API + /operations/safety.
# Non-sensitive (statuses/enums/names/public git revision only); no kubeconfig,
# token, admin password, secret, or rendered manifest.
COPY infra/gitops/ ./infra/gitops/
# Stage 60A (Step 58) -- committed read-only operational metrics model + source
# inventory + delivery policies consumed by the read-only /operations/metrics/* API.
# Non-sensitive (model/enums/source descriptors only); no secret/token/kubeconfig.
COPY infra/operations/ ./infra/operations/
# Stage 59A (Step 57) -- committed multi-project / work-item delivery policies consumed
# by the work_items + projects SDK (lifecycle / dispatch / decomposition / assignment /
# delivery-state / linkage / audit / notification) + /operations/safety. Non-sensitive
# (deterministic policy metadata only); no secret, token, or customer data.
COPY infra/delivery/ ./infra/delivery/
# Stage 61A (Step 59) -- committed sandbox GitHub draft-PR policies consumed by the
# sandbox_github SDK (policy / allowlist / branch / metadata / credential boundary /
# audit mapping) + /operations/safety. Non-sensitive (deterministic policy metadata
# only); NO token, secret, or credential -- the sandbox token comes from the env only.
COPY infra/github/ ./infra/github/
# Stage 54D (Step 52.4) -- committed read-only identity posture summary consumed
# by the /operations/identity/* read-only API + /operations/safety. Non-sensitive
# (booleans/enums/statuses only); no token, secret, raw email, or real group ID.
COPY infra/identity/identity-posture-summary.yaml ./infra/identity/identity-posture-summary.yaml
# Stage 55A (Step 53) -- committed read-only secret management foundation catalogs
# consumed by the /operations/secrets/* read-only API + /operations/safety.
# References/metadata only (store=disabled); NO secret value, token, or key.
COPY infra/secrets/ ./infra/secrets/
# Stage 56A (Step 54.1) -- committed read-only application security & supply chain
# catalogs consumed by the /operations/security/* read-only API + /operations/safety.
# Inventory/policy metadata only; modeled_not_enforced; NO secret, token, or key.
COPY infra/security/ ./infra/security/

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
