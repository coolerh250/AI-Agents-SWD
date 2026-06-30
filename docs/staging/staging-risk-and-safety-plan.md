# Staging Risk & Safety Plan (Step 64A)

> **Staging only — non-production only. No production action. No production secret. No external write.**

Safety guardrails for the Step 64 staging mainline. **Staging target host: `10.0.1.32` ·
Access: SSH (interactive credentials, never stored).**

## Hard safety guarantees
- **No production action** — no production deploy / sync / restore / failover / rollout.
- **No secret exposure** — SSH credentials interactive-only, never stored/committed/printed;
  no `.env` / token / kubeconfig / private key committed; SSH key contents never printed
  (path existence only).
- **No external write** — GitHub merge / image push / registry login / Slack / external
  connector / LLM live all disabled by default.
- **No data deletion** — no cleanup execution; existing `10.0.1.31` test data and scheduled
  DR / regression artifacts are untouched.
- **No unapproved cost** — no cloud provider write, no paid external calls.
- **No staging-to-production confusion** — staging is never labelled production; a compose /
  kind stack is not production; non-production ArgoCD is not production ArgoCD.

## Credential handling (10.0.1.32)
SSH username + auth requested interactively at connect time. On failure only the error
*type* is reported, never the credential. No credential is ever written to a file, log,
script, `.env`, or commit.

## Risks & mitigations
| Risk | Mitigation |
|---|---|
| Port `18000` exposed on shared LAN | prefer SSH local port-forward; keep loopback binding |
| HTTP (no TLS) for first demo | acceptable for demo only; TLS is a future option |
| Vault dev mode | documented staging limitation; not production secret storage |
| Operator session for mutation pages | reuse existing auth + CSRF + audit; confirm in 64C |
| Confusing staging with production | explicit staging-only labelling on every doc + safety endpoint |
| Missing Docker on `10.0.1.32` | record as prerequisite gap; no auto-install in Step 64A |

## Safety endpoint checks (Step 64B+)
After bring-up verify `GET /operations/safety`: all `*_allow_production_*` / deploy / sync /
merge / image-push / restore / failover toggles false; readiness gate `production_ready=false`;
controlled rollout `recommendation` not an approval; `production_executed_true_count=0`.

## Audit checks
Audit integrity preserved; audit canonicalization unchanged; HARD_SAFETY_ACTIONS unmodified;
secret scan + verifier strictness unchanged.

---
_Staging only — non-production only. No production action. No production secret. No external write._

<!-- staging-safety: staging-only=true non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false -->
