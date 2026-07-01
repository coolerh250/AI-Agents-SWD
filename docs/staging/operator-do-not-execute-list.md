# Operator Do-Not-Execute List (Step 64E)

> **Staging only — non-production only. No production action. No production secret. No external write.**

Actions the operator **must NOT** perform against the staging system. This is a staging
demonstration/inspection environment; none of the below is authorized here.

## Do NOT — production
- **Production deploy** — do not deploy anything to production.
- **Production sync** — do not run any production sync (ArgoCD / GitOps).
- **Production approval** — do not create or grant a production approval.
- **Production secret** — do not create or read any production secret.

## Do NOT — external integrations
- **Live GitHub write** — no live GitHub write / commit / PR merge.
- **GitHub merge / release / tag** — none.
- **Image push / registry login** — none.
- **Live Slack / Discord send** — no live external notification.
- **Live LLM call** — none (LLM disabled/mocked).
- **External connector write** — none.

## Do NOT — infrastructure
- **`kubectl apply` / `helm install` / `argocd sync`** — none.
- **`docker compose down -v`** — never (this deletes staging volumes/data).
- **Volume deletion** — do not delete any staging volume.
- **Manual DB mutation** — do not hand-edit the staging database.

## Do NOT — access / governance
- **Public port exposure** — do not expose port 18000 (or any port) publicly. Use the SSH
  tunnel only.
- **Operator auth bypass** — do not bypass operator auth / CSRF.
- **Delivery dispatch while operator auth disabled** — do not force the gated delivery dispatch.
- **Release candidate creation while gated** — do not force-create a release candidate.

## Do NOT — runtime changes (this stage)
- **communication-gateway image rebuild** — not in this stage.
- **Dependency installation inside runtime containers** — do not `pip install` inside a running
  container.

## If in doubt
Read-only inspection only. If an action is not explicitly listed as allowed in the
[operator-walkthrough-sop.md](operator-walkthrough-sop.md), do not perform it — record and
escalate instead.

`production_executed_true_count` must remain `0`.

---
_Staging only — non-production only. No production action. No production secret. No external write._

<!-- staging-safety: staging-only=true non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
