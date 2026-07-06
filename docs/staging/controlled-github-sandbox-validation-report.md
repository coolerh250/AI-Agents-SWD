# Controlled GitHub Sandbox Validation Report (Step 65D)

> **Staging only — non-production only. No production action. No production secret. No production repo write.**
> **A single controlled sandbox draft-PR write occurred (non-production sandbox repo). No merge, no production action.**

Records the **real** (not mock) controlled GitHub sandbox validation on staging `10.0.1.32`,
under operator authorization: a live draft PR was created in the operator's **non-production**
sandbox repo `coolerh250/AI-Agents-SWD-sandbox` through the full controlled path.

## Overall result
- Overall result: **PASS** — a genuine draft PR (`#15`) with a real commit was created in the
  sandbox repo via the platform's controlled flow (operator auth + CSRF → policy → allowlist → live
  gate → real GitHub API). `production_executed_true_count=0`; no merge; staging reset to safe.

## What was validated (all real)
- **Control path:** operator test-login + CSRF, sandbox draft-PR policy, repository allowlist
  (retargeted to the sandbox repo), live-mode gate, and the sandbox credential.
- **Real GitHub write:** branch `sandbox/ai-agents/prj-saas-user-management-module-15f51d/wi-0001/…`
  created; a non-production **sandbox evidence file** committed; a **draft** PR opened.
- **Result:** `status=created`, **PR #15**
  (`https://github.com/coolerh250/AI-Agents-SWD-sandbox/pull/15`), `draft=true`, `commits=1`,
  `changed_files=1`, base `main`.

## Changes required to make it work (committed)
1. **Allowlist retarget** (`022b518`): `infra/github/sandbox-repository-allowlist.yaml`
   `repo: AI-Agents-SWD` → `AI-Agents-SWD-sandbox` (was pointing at the main repo).
2. **Compose env wiring** (`38e4fcd`): pass `SANDBOX_GITHUB_LIVE` / `SANDBOX_GITHUB_TOKEN` +
   test-local operator-auth flags through to the orchestrator container (safe defaults).
3. **Flow fix** (`ea52208`): the Step 59 live flow created a branch with **no commit**, so GitHub
   rejected the PR ("no commits between base and head"). Fixed `_create_live` to commit a
   non-production evidence file before opening the draft PR (+ audit event + client test).

## Findings resolved during validation
- The provided fine-grained token initially lacked git access (403); operator granted
  **Contents (RW) + Pull requests (RW)** → branch creation succeeded.
- First real attempt failed at PR creation (empty branch); the flow fix (evidence commit) resolved
  it → PR #15 created.
- The stray empty branch from the first attempt was deleted (HTTP 204).

## Safety
- `production_executed_true_count=0`; the sandbox draft-PR safety shows `created_count=1`,
  `merge_enabled=false`. Only the **sandbox** repo was written; the main/production repo was never
  touched. Live mode + operator-auth were enabled only for the validation window and **reset to
  safe** afterwards (`SANDBOX_GITHUB_LIVE=false`, operator actions disabled). No secret value was
  printed or committed.

## Consolidation (Step 65D-C)
Consolidated with Step 65C in
[step65c-65d-integration-status-consolidation.md](step65c-65d-integration-status-consolidation.md):
GitHub sandbox integration **VALIDATED**; the 65C GitHub sandbox token gap is **RESOLVED_BY_65D**.
No new external write occurred in the consolidation stage. `production_executed_true_count=0`.

## Status
- Step 65D: **PASS** (real draft PR validated). Step 65E (notification) / 65F (LLM) still pending
  their own authorization. This is not production readiness.

---
_Staging only — non-production only. No production action. No production secret. No production repo write._

<!-- staging-safety: staging-only=true non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=sandbox-controlled github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled-at-rest -->
