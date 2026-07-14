<!--
See docs/process/branch-pr-naming-standard.md for the full standard this template implements.
See .agents/README.md and docs/process/context-guard-protocol.md for the Shared Context /
Authorization / Evidence sections below (Step 66GOV.1 Stage Gate & Context Guard Skill Pack).
-->

## Shared Context

- [ ] Pulled latest main
- [ ] Read `.agents/skills/shared-context/SKILL.md`
- [ ] Read `.agents/skills/stage-gate/SKILL.md`
- [ ] Read `.agents/skills/security-governance/SKILL.md`
- [ ] Read stage manifest, if present
- [ ] Reviewed `source/progress.md`
- [ ] Reviewed relevant design / contract / frontend / handoff docs
- [ ] Reviewed related PRs / branches

## Summary

<!-- One or two sentences on what changed and why -->

## Scope

<!-- Exactly what files/areas this PR touches -->

Stage:
Owner:
Task type:
Allowed paths:
Forbidden paths:
Files changed:

## Owner role

<!-- Operator / ChatGPT / Claude Code / Codex / Claude Design -- see
docs/process/role-responsibility-matrix.md -->

## Related stage

<!-- e.g. 66d-delivery-inbox -->

## Design reference

<!-- Link to docs/design/<stage>/... if applicable, else "N/A" -->

## Contract reference

<!-- Link to docs/contracts/<stage>/... if applicable, else "N/A" -->

## Authorization

Product Owner authorization:
Codex authorized:
Merge authorization:
Deployment authorization:

## Safety impact

- Workflow dispatch: no
- Workflow resume: no
- External action: no
- Production action: no

Backend changed:
API changed:
Database changed:
Secrets/internal identifiers:
Client-side-only RBAC:
Audit/safety evidence impact:

## RBAC impact

<!-- Describe, or "none" -->

## Audit impact

<!-- Describe, or "none" -->

## Evidence

Context receipt:
Stage gate report:
Tests:
Build:
Verifier:
Secret scan:
Known gaps:

## Tests

<!-- What was added/run, and the result -->

## Screenshots or evidence

<!-- Required for frontend/design PRs -->

## Known gaps

<!-- Anything explicitly deferred, non-blocking -->

## No production action statement

No production action. No production deploy. No production secret exposure.

<!--
Masking rule: do not include internal IP addresses, SSH aliases, private hostnames, real tokens,
credentials, private URLs, or environment secrets in this PR description, its comments, or attached
screenshots. Use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo".
-->
