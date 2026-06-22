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
# Stage 53G (Step 51.4) -- committed read-only runtime baseline summary consumed
# by the /operations/runtime/* read-only API + /operations/safety. Non-sensitive
# (booleans/enums/counts/names only); no rendered manifests, no secrets.
COPY infra/kubernetes/runtime-baseline-summary.yaml ./infra/kubernetes/runtime-baseline-summary.yaml
# Stage 54D (Step 52.4) -- committed read-only identity posture summary consumed
# by the /operations/identity/* read-only API + /operations/safety. Non-sensitive
# (booleans/enums/statuses only); no token, secret, raw email, or real group ID.
COPY infra/identity/identity-posture-summary.yaml ./infra/identity/identity-posture-summary.yaml

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
