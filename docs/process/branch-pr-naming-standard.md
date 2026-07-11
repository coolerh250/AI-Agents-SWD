# Branch and Pull Request Naming Standard

> **Process documentation only. No backend/frontend runtime change. No workflow dispatch. No
> workflow resume. No external action. No production action.**

## Branch naming

`<type>/<stage>-<short-description>`, where `<type>` identifies which role/layer the branch belongs
to and `<stage>` matches the Step 66 sub-stage naming already used under `docs/test/`
(e.g. `66c3-workroom-audit-visibility`).

| Type | Owner | Example |
| --- | --- | --- |
| `design/` | Claude Design | `design/66d-delivery-inbox` |
| `contract/` | Claude Code | `contract/66d-delivery-api` |
| `frontend/` | Codex | `frontend/66d-delivery-inbox` |
| `backend/` | Claude Code | `backend/66d-delivery-api` |
| `docs/` | any role | `docs/66c3-operator-validation` |
| `fix/` | any role | `fix/66c3-ui-feedback` |

## Pull request requirements

Every PR description must include:

- **Summary** — one or two sentences on what changed and why.
- **Scope** — exactly what files/areas this PR touches.
- **Owner role** — which of the five roles authored this PR (see
  `docs/process/role-responsibility-matrix.md`).
- **Related stage** — the Step 66 sub-stage this PR belongs to.
- **Design reference** — link to the relevant `docs/design/<stage>/` doc, if applicable.
- **Contract reference** — link to the relevant `docs/contracts/<stage>/` doc, if applicable.
- **Safety impact** — workflow dispatch/resume, external action, production action: yes/no for each,
  expected `no` for every PR under this project's current scope.
- **RBAC impact** — any change to who can do what; `none` if unchanged.
- **Audit impact** — any new/changed audit event; `none` if unchanged.
- **Tests** — what was added/run, and the result.
- **Screenshots or evidence** — required for any frontend or design PR.
- **Known gaps** — anything explicitly deferred, non-blocking.
- **No production action statement** — an explicit line confirming no production action, no
  production deploy, no production secret exposure.

## Statement

Documentation only. No backend/frontend runtime change occurred. No workflow dispatch occurred. No
workflow resume occurred. No external action occurred. No production action occurred.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets in docs, examples, screenshots, or validation evidence — use neutral labels such as "test
host", "internal test runtime", "admin console local tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
