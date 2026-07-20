# Planning Doc — Step 66UI.4-FE.1C.1-P: TaskList Query Param Filter Support

> **Planning document only. No frontend runtime code changed. No backend/API/database/workflow
> change. No new endpoint. No deployment. No production/external action. Codex implementation not
> authorized by this document. FE.1D not authorized.**

Executed by: Claude Code (Lead Engineer / Architecture Owner — see
`docs/process/role-responsibility-matrix.md`), per Product Owner explicit authorization:

```text
授權規劃 Step 66UI.4-FE.1C.1 — TaskList Query Param Filter Support；僅限 frontend-only，讓
/tasks?status=... 可套用既有 TaskList status filter；不得修改 backend/API/DB/workflow，不得新增
endpoint，不得授權 FE.1D。
```

## Background

Step 66UI.4-FE.1C's Overview Attention-first implementation (PR #10, merged to `main` at
`dee66c9`) added two attention tiles that link to `/tasks?status=clarification_needed` and
`/tasks?status=blocked` (`ExecutiveOverview.tsx` lines 215/222). This was flagged as a known,
non-blocking UX gap throughout the FE.1C review chain (Step 66UI.4-FE.1C-R finding #2, carried
through Step 66UI.4-FE.1C-VP and accepted by the Product Owner in Step 66UI.4-FE.1C-V): `TaskList`
does not read the URL query string, so clicking a tile lands on `/tasks` without the status filter
applied. This stage plans the fix; it does not implement it.

## 1. Current behavior analysis

### 1.1 How Overview currently constructs `/tasks?status=...` links

`ExecutiveOverview.tsx` renders two hardcoded `<Link>` elements:

```text
<Link to="/tasks?status=clarification_needed">...</Link>
<Link to="/tasks?status=blocked">...</Link>
```

These are static strings, not built from a shared query-building helper. The status values used
(`clarification_needed`, `blocked`) are both valid members of `TASK_STATUSES`
(`apps/admin-console/src/tasks/taskTypes.ts`).

### 1.2 How TaskList currently stores and applies its status filter

`TaskList.tsx` holds filter state entirely in local component state:

```text
const [filters, setFilters] = useState<TaskListFilters>({});
```

The `Status` field is one of six independent `<select>`/`<input>` controls (status, task_type,
priority, environment, owner, created_by), all reading from and writing to this same local
`filters` object. There is no `useSearchParams` call, no `window.location.search` read, and no
`history`/`navigate` call anywhere in this file. Filter changes trigger a `key={filterKey}` remount
of `<AsyncView>` (a documented existing pattern, since `AsyncView` only loads once per mount),
which re-runs `taskApi.list(filters)`.

### 1.3 Whether TaskList uses local state, URL state, or both

Local state only. No URL state exists today.

### 1.4 Whether existing status filter values match URL query values

Yes, by construction: the Overview tiles link to exactly the string values already present in
`TASK_STATUSES` (17 defined values, e.g. `draft`, `clarification_needed`, `blocked`, `failed`,
etc. -- see `taskTypes.ts`), which are the same values the `Status` `<select>` control iterates over
to build its `<option>` list. No value translation is required.

### 1.5 Whether invalid query values should be ignored or normalized

Ignored (recommended). A query value not present in `TASK_STATUSES` should be treated as if no
`status` query param were present at all -- the filter falls back to "(any)" and the page renders
normally. This avoids ever sending an unrecognized value to `taskApi.list()`, which would otherwise
surface as a raw backend error rather than a calm default state.

### 1.6 Whether query param should update the visible dropdown/control

Yes (recommended). On initial load, if `?status=<valid-value>` is present, the `Status` `<select>`
should render pre-selected to that value -- otherwise the deep link is invisible to the user (they
would see an unfiltered list with no visual indication a filter was ever intended), which is the
core of the currently-accepted gap.

### 1.7 Whether changing the dropdown should update URL query param

Optional, deferred to the future implementation's own source-of-truth review, not decided here (see
"Open question" below). Two-way sync (dropdown edits also update the URL) is a reasonable
enhancement but is not required to close the specific gap the Product Owner accepted -- the gap is
about deep links working, not about making every manual filter change bookmarkable. Recommending
this remain optional so the future implementation stays minimal unless explicitly requested.

### 1.8 Whether clearing filter should remove query param

Only relevant if 1.7 is implemented (two-way sync). If two-way sync is not implemented, this
question does not arise. If it is, clearing the `Status` dropdown back to "(any)" should remove the
`status` param from the URL (via `history.replace`, not `push`, to avoid polluting back/forward
history with every keystroke-equivalent dropdown change).

### 1.9 Whether browser back/forward should restore filter state

If two-way sync (1.7) is implemented via `useSearchParams`, this behavior comes for free from
`react-router-dom`'s history integration -- no extra code required. If two-way sync is not
implemented (read-once-on-load only), back/forward will simply reload the page fresh each time,
re-parsing the URL at that point, which is also acceptable and simpler.

### 1.10 Whether requester/admin RBAC role-scoping remains server-side and unchanged

Confirmed unaffected. Role-scoping (`requester` role sees only its own tasks) is enforced entirely
server-side in `apps/orchestrator/src/task_api.py` (`scope_created_by = ctx.actor if ctx.role ==
"requester" else created_by`, plus explicit ownership checks on task detail/submit). Reading a
`status` value from the URL and passing it into the existing `taskApi.list(filters)` call changes
only which `status` filter value is sent -- it does not touch, bypass, or duplicate any RBAC
decision, all of which remains server-side exactly as today.

### Root cause

`TaskList.tsx` was implemented in Step 66B.2, before Overview's attention tiles existed (Step
66UI.4-FE.1C). Nobody has since revisited `TaskList.tsx` to add query-string awareness, because
until FE.1C's Overview redesign, nothing in the product linked to `/tasks` with a pre-set filter
intent. This is a sequencing gap, not a defect introduced by any single stage.

## 2. Recommended future behavior

```text
1. Visiting /tasks?status=blocked preselects the existing Status filter = blocked.
2. Visiting /tasks?status=clarification_needed preselects the existing Status filter =
   clarification_needed.
3. The TaskList request continues to use the existing status-filtered API logic
   (taskApi.list(filters)) -- no new request shape, no new parameter.
4. An invalid/unrecognized status query value is ignored (treated as no filter), and does not throw,
   does not send an invalid value to the backend, and does not break the page.
5. No fake counts are introduced -- the page continues to render exactly what taskApi.list()
   returns.
6. No client-side-only RBAC is introduced or implied -- role-scoping remains exclusively
   server-side, unchanged.
7. No backend/API changes are required -- the existing GET /tasks?status=... contract already
   supports this.
```

Two-way URL sync (dropdown edits updating the URL, browser back/forward restoring state) is
recorded as an **optional enhancement**, not a requirement, deferred to the future implementation's
own scope decision -- see "Open question" below.

## 3. Open question for Product Owner / Codex readiness review

```text
Q1: Should the future implementation be read-only-on-load (query param sets initial filter, but
    manual dropdown changes do not update the URL), or full two-way sync (dropdown changes also
    push/replace the URL, enabling bookmarking and back/forward)?
    Recommendation: read-only-on-load is sufficient to close the accepted gap and is the minimal
    correct fix; two-way sync is a reasonable follow-up enhancement but should require its own
    explicit go-ahead rather than being bundled by default.
```

## 4. No new route / endpoint / status model required

```text
No new route: /tasks already exists and already accepts being visited with a query string; React
  Router does not require any route definition change to support query parameters.
No new endpoint: GET /tasks?status=... already exists and is already used by TaskList's own filter
  UI today.
No new task status model: TASK_STATUSES already contains every value Overview's tiles link to.
```

## Statement

Planning document only. No frontend runtime code changed. No backend/API/database/workflow change.
No new endpoint. No deployment. No production/external action. Codex implementation not authorized
by this document. FE.1D not authorized.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
