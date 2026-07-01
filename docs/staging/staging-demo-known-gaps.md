# Staging Demo Known Gaps (Step 64D)

> **Staging only — non-production only. No production action. No production secret. No external write.**

Known gaps from the Step 64D demo on the staging runtime (`10.0.1.32`). Overall result is
**PASS_WITH_GAPS**. None is a production readiness sign-off; **Claude Code does not decide
production readiness.**

## 1. communication-gateway image missing PyYAML
`POST /intake/mock/project-work-item` on the communication-gateway returns HTTP 500 —
`ModuleNotFoundError: No module named 'yaml'`. The gateway image does not bundle PyYAML, but
the mock-intake path imports the project/work-item SDK which loads YAML policy. **Workaround:**
the demo seed (`scripts/staging_seed_demo_workflow.py`) ran the same SDK inside the
**orchestrator** container (which has PyYAML). Fix for a later stage: add `PyYAML` to the
communication-gateway image dependencies and rebuild that image.

## 2. Delivery package / release candidate not produced (gated)
The governed work-item **dispatch** (`POST /operations/delivery/work-items/{id}/dispatch`)
requires operator auth + CSRF, and operator actions are disabled in staging
(`operator_actions_disabled`). So no delivery package or release candidate was generated; the
work item stays at `created` / `not_started`. See
[staging-demo-delivery-evidence.md](staging-demo-delivery-evidence.md).

## 3. LLM interactions = 0
No LLM interactions were recorded because live LLM calls are disabled/mocked in staging. This
is the intended safety posture, not a defect.

## 4. Two representations of the work item
The demo produced both a **delivery-domain** work item (`WI-0001`, lifecycle `created`) and
**workflow-domain** mock workflows (`demo-crud-userapi` / `demo-crud-001`) whose agent pipeline
completed. They are not linked; the mock workflow (`run_mock_workflow`) is a separate demo path
from the governed delivery lifecycle. Both are non-production.

## 5. No committed screenshots
Page reachability + demo data are evidenced by host-local `curl` values recorded in the demo
docs. A gitignored `runtime_evidence/staging/demo-workflow/` path is reserved for optional
local, non-secret screenshots.

## Not done in this stage
- No production deploy / sync / secret / external write; no GitHub merge / image push; no live
  Slack/GitHub/LLM call. `production_executed_true_count=0`.

---
_Staging only — non-production only. No production action. No production secret. No external write._

<!-- staging-safety: staging-only=true non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false live-integrations=disabled demo-workflow-executed=true -->
