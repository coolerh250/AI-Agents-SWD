# Risk Register — Step 66ALIGN.1-CC

> **Analysis and documentation only. No implementation, merge, deployment, or runtime modification
> performed by this document.**

Ranked by (impact if ignored) x (likelihood of being ignored given current execution pattern).

## Top risks

| # | Risk | Impact | Likelihood | Mitigation |
| --- | --- | --- | --- | --- |
| 1 | **Continued cosmetic (FE.1D-S2 and beyond) investment while 66C.4/66D remain unstarted, silently extending time-to-value of the entire critical path.** | High — the project's actual product goal (a working human-agent delivery loop) does not advance while polish work continues. | High — this is the pattern observed over the last several completed stages (FE.1A through FE.1D-S1 all shipped in sequence while 66C.4 sat READY_TO_START). | Explicit Product Owner decision to pause further Admin-Console-only cosmetic work until 66C.4 (and ideally 66D) land; recommended-next-stages.md proposes 66C.4 as stage 1. |
| 2 | **Building 66D's UI before its data model/API contract is frozen**, repeating a mistake this project has otherwise been careful to avoid (every FE.1x stage to date used a Claude-Code-owned contract doc before Codex implemented). | High — a delivery/acceptance data model is far more consequential to get wrong than a nav-label choice; retrofitting it after UI exists is expensive. | Medium — no evidence this is already happening, but the risk rises the moment 66D UI design starts without an explicit architecture-direction stage first. | Require an explicit Claude-Code-owned `docs/contracts/66d-delivery-lifecycle/` data-model/API contract stage before any 66D UI implementation is authorized (see alignment-statement.md's direct answer). |
| 3 | **Backup/DR gaps (`encryption_no_key`, `storage_not_off_host`, `schedule_dry_run_only`, `migration_down_gaps`) have been open and undisturbed since at least Stage 38** and have never been on any stage's execution list since. | High for M6/M7 (these are hard blockers for real production readiness) but currently Low for M1-M5 (test-only environment, no real data at risk). | Medium — nothing forces revisiting them until M6 explicitly requires it; without this alignment stage naming them, they could remain silently deferred indefinitely. | Explicitly gate M6 entry on closing all four; do not allow M6 to be declared "started" while any remains open (security-runtime-gates.md M6 section). |
| 4 | **Conflating the Stage 60–63A non-production "kind"/ArgoCD dry-run rehearsal with real production-readiness progress.** | High if misread by a future stage or a future Product Owner review as "K8s/ArgoCD already done" — it is not; no real cluster, no real sync, ever performed. | Medium — the dry-run work is well-documented as non-production, but its sheer volume (multiple stages, many docs) creates a plausible-sounding but incorrect impression of readiness if skimmed. | This document and technical-critical-path.md state explicitly: dry-run rehearsal is valuable preparation for M6, not M6 itself. Any future stage citing Stage 60–63A as evidence of production K8s/ArgoCD readiness should be treated as a red flag requiring correction. |
| 5 | **Stale host reference checkout (64 commits behind `origin/main` at time of writing) being mistaken for the deployment source by a future stage that doesn't re-derive the established disposable-clone pattern from scratch.** | Medium — would deploy a stale build if a future operator "just `git pull`s and builds in place" instead of following the established pattern. | Low-Medium — every deployment stage to date has correctly used a disposable clone, but the pattern lives in institutional practice/prior completion reports, not in a single canonical runbook doc. | Recommend a short, explicit "how we deploy to test runtime" runbook doc be created (candidate for the next 5 stages list, or folded into M0 closure) so the pattern is discoverable without needing this session's full history. |
| 6 | **Vault dev-mode / Postgres `trust` auth becoming taken-for-granted** and not actually replaced when M6 arrives, because they have "always worked fine" in test. | High for M6/M7. | Low-Medium — explicitly named in every relevant stage's safety statement so far, which is a good sign, but the habit of writing "local/test-only, never production" without a concrete remediation plan attached is itself a risk if it continues unchanged into M6 planning. | M6 entry criteria (security-runtime-gates.md) explicitly require both closed before M6 can be considered started. |
| 7 | **FE.1D's three unmerged branches (design, technical-readiness review, Codex-implementation-boundary) drifting further from `main` the longer they sit unmerged**, increasing future merge-conflict risk if `main` continues to move (e.g. via 66C.4/66D work touching files these branches also reference, like `App.tsx` route additions). | Medium — a merge-conflict cost, not a correctness risk, since none of these branches touch runtime code themselves. | Medium — will only grow as 66C.4/66D land and touch `App.tsx`/`Nav.tsx`-adjacent files. | Recommend a Product Owner decision soon on whether to merge these three documentation-only branches (low risk, since they contain no runtime code) independent of any FE.1D-S2 authorization decision. |

## Known gaps carried forward (not new findings — confirmed still open)

```text
Team RBAC UI (Step 66S) -- blueprinted, not implemented.
DLQ/Retry operator UI -- backend service running, no product UI (Step 66D).
Approvals operator UI -- same status.
Governed web-research connector -- flagged missing at discovery time (66A.1), still missing.
Multi-channel intake (Slack/Telegram) -- not built.
Notifications / Action Center -- not built.
Admin Console SPA deep-link/hard-refresh fallback -- known backend gap
  (docs/frontend/admin-console-spa-deep-link-fallback-known-gap.md), accepted as non-blocking for
  every UI stage to date, but will need remediation before M7 (a real production operator hitting
  a 404 on a bookmarked/refreshed deep link is a real support-burden risk, not just a test-
  environment curiosity).
```

## Statement

Analysis and documentation only. No implementation, merge, deployment, or runtime modification
performed by this document.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._
