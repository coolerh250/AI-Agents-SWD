# Operator Validation Standard

> **Process documentation only. No backend/frontend runtime change. No workflow dispatch. No
> workflow resume. No external action. No production action.**

## Response values

**UI-visibility validation** (does the operator see what was built, in the Admin Console):

```
VISIBLE
PARTIAL_WITH_GAPS
NOT_VISIBLE
```

**Implementation-completion validation** (does a stage's technical work meet its PASS criteria):

```
PASS
PASS_WITH_GAPS
FAIL
```

A stage typically collects both: an implementation report from Claude Code stating a technical
`PASS`/`PASS_WITH_GAPS`/`FAIL`, followed by an operator validation request that Zachary answers with
`VISIBLE`/`NOT_VISIBLE`/`PARTIAL_WITH_GAPS` after using the deployed feature in the Admin Console.

## Who may give which verdict

**Claude Code, Codex, and Claude Design must not decide final product acceptance.** They may report:

- Claude Code: technical `PASS` / `PASS_WITH_GAPS` / `FAIL` for implementation completeness against
  a stage's stated criteria.
- Codex: frontend build pass/fail, frontend test pass/fail.
- Claude Design: design ready / design needs revision.

**Only Zachary gives `VISIBLE` / `NOT_VISIBLE` / `PARTIAL_WITH_GAPS`** after actually using the
deployed feature, and only Zachary's response determines whether a stage's product acceptance is
final. If `PARTIAL_WITH_GAPS` or `NOT_VISIBLE` is returned, the responsible role (per
`docs/process/role-responsibility-matrix.md`) remediates and a new validation request is issued —
this project's established recurring pattern (see `docs/test/step66c2-remediation-*.md` for a worked
example: an initial `NOT_VISIBLE`, a remediation stage, then `VISIBLE`).

## Recording the result

The operator's response is recorded verbatim (not summarized or reinterpreted) in a
`*-operator-validation-record.md` document, plus a status update in `source/progress.md`. Every
prior stage's status line follows this convention already — do not deviate from it.

## Statement

Documentation only. No backend/frontend runtime change occurred. No workflow dispatch occurred. No
workflow resume occurred. No external action occurred. No production action occurred.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets in docs, examples, screenshots, or validation evidence — use neutral labels such as "test
host", "internal test runtime", "admin console local tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
