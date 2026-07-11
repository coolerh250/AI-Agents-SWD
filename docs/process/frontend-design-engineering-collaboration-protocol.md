# Frontend / Design / Engineering Collaboration Protocol

> **Process documentation only. No backend/frontend runtime change. No workflow dispatch. No
> workflow resume. No external action. No production action.**

This protocol defines the standard flow for turning product direction into an operator-validated
Admin Console feature, across Zachary, ChatGPT, Claude Design, Codex, and Claude Code. See
`docs/process/role-responsibility-matrix.md` for what each role owns.

## Standard flow

1. **Product direction from Operator.** Zachary states a goal or priority.
2. **PM/Architect stage prompt from ChatGPT.** Translated into a concrete stage spec (scope, out of
   scope, safety constraints, required docs, PASS criteria) — the same format used for every prior
   Step 66 sub-stage.
3. **Claude Design creates the design brief / flow / component spec.** Written into
   `docs/design/<stage>/` using the templates in `docs/design/templates/`. No runtime code.
4. **Claude Code creates the API/frontend contract.** Written into `docs/contracts/<stage>/` using
   the templates in `docs/contracts/templates/` — the allowed fields, forbidden fields, RBAC rules,
   and safety fields the frontend must respect (e.g. `dispatch_enabled`/`resume_dispatch_enabled`
   always `false`, never a raw body).
5. **Codex implements the frontend** based on the design brief and the contract. Written into
   `docs/frontend/<stage>/` using the templates in `docs/frontend/templates/`. Codex does not
   change the contract or the backend.
6. **Claude Code reviews, integrates, tests, and deploys** the frontend PR against the contract and
   the project's standing safety/security constraints (plain-text rendering, no
   `dangerouslySetInnerHTML`, server-side RBAC, no workflow dispatch/resume), then deploys to the
   test runtime only.
7. **Operator validates in Admin Console.** Zachary walks through the deployed feature and responds
   with the standard verdict values (see `docs/process/operator-validation-standard.md`).
8. **Validation record is committed.** The operator's response is recorded verbatim in
   `docs/test/<stage>-operator-validation-record.md` (or the handoff-index equivalent under
   `docs/handoffs/<stage>/`) and `source/progress.md` is updated.

## Binding rules

- **Design does not equal implementation.** A design brief, wireframe, or component spec from
  Claude Design is a specification, not working code — it does not ship until Codex implements it
  against a contract and Claude Code integrates it.
- **Frontend does not change backend contract.** Codex builds against the contract Claude Code
  published; if the frontend needs a different API shape, that requires a new or updated contract
  from Claude Code first, not an ad-hoc frontend workaround.
- **Backend/API changes go through Claude Code.** Database, migration, workflow, policy, and
  infrastructure changes are Claude Code's responsibility; Codex and Claude Design do not touch
  them.
- **Operator is the only final product acceptance authority.** Every other role's output is a
  technical report (implementation PASS, design ready, frontend build pass) — never a product
  acceptance decision.

## Statement

Documentation only. No backend/frontend runtime change occurred. No workflow dispatch occurred. No
workflow resume occurred. No external action occurred. No production action occurred.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets in docs, examples, screenshots, or validation evidence — use neutral labels such as "test
host", "internal test runtime", "admin console local tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
