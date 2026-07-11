# Decision Records (ADRs)

> **Process documentation only. No backend/frontend runtime change. No production action.**

Architectural/process decisions that outlive a single Step 66 sub-stage live here, not in a stage's
`docs/test/` folder. Use `adr-template.md` for each new decision. Number sequentially
(`0001-<slug>.md`, `0002-<slug>.md`, ...).

## Index

_No ADRs recorded yet under this structure as of Step 66TEAM.1 — prior project-wide decisions (e.g.
the test-only header role simulation standing in for a real session until 66S, the
`operator_clarification_requests` naming to avoid the pre-existing `clarification_requests` table
collision) remain recorded in their original stage docs under `docs/test/` rather than being
retroactively migrated here. New cross-stage decisions from this point forward should use this
directory._

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
