# GitHub Sandbox Integration Plan (Step 65B → 65D)

> **Staging only — non-production only. No production action. No production secret. No external write.**
> **Planning only — no GitHub write, no token use, no integration enabled in this stage.**

Plan for the controlled GitHub sandbox integration to be validated at Step 65D. Currently
dry-run/mock (`github_external_write_enabled=false`); the sandbox draft-PR endpoints
(`/operations/github/sandbox-draft-pr/*`) already exist.

## Sandbox resource
- **Repository:** `<SANDBOX_GITHUB_REPO>` placeholder — a **non-production** repo the operator
  supplies at 65D (never a production or customer repo).
- **Credential reference:** `GITHUB_TOKEN` (sandbox, minimal scope), stored in the staging secret
  backend only.

## Allowed conventions (for 65D)
- **Branch naming:** `staging/agents-sandbox/*` (staging-only prefix).
- **Draft PR creation:** allowed (draft only).
- **Allowed file paths:** generated artifact paths under a sandbox directory only.
- **Commit message prefix:** `[STAGING-SANDBOX]`.
- **Allowed labels:** `staging`, `sandbox`, `do-not-merge`.

## Allowed actions (later Step 65D)
- Create a staging-only branch in the sandbox repo.
- Commit a generated artifact to the sandbox repo.
- Open a **draft** PR.
- Read PR status.
- Record audit / evidence.

## Forbidden actions
- Merge a PR. Delete the repo. Push to a production repo. Push to a customer repo. Create a release.
  Create a tag. Modify a protected branch directly. Trigger a production deployment. Image push.

## Enable flags / kill switch
- Live only when `RUN_REAL_GITHUB_TEST=true` **and** `GITHUB_DRY_RUN=false` **and** a sandbox
  `GITHUB_TEST_REPO` + `GITHUB_TOKEN` are present.
- **Kill switch:** set `GITHUB_DRY_RUN=true` or `RUN_REAL_GITHUB_TEST=false`, or rotate/revoke the
  token → returns to dry-run/mock.

## Required audit / evidence
- Record branch/PR reference, action, and result (sanitized) per sandbox interaction.
- Surface in the Admin Console (e.g. sandbox draft-PR views / `/operations/github/sandbox-draft-pr/*`).
- Verify `production_executed_true_count=0` and that the target is the sandbox repo.

## Operator authorization
Required before 65D enables any write; the operator supplies the sandbox repo + token delivery
method (see [external-integration-user-input-checklist.md](external-integration-user-input-checklist.md)).

## Posture
Planning only. No GitHub write, no token use, no integration enabled, no external write, no runtime
change, no production action; `production_executed_true_count=0`.

---
_Staging only — non-production only. No production action. No production secret. No external write._

<!-- staging-safety: staging-only=true non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
