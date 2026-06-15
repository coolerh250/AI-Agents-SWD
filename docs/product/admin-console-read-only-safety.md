# Admin Console v0 — Read-only Safety (Stage 50)

Admin Console v0 is read-only by construction. These are the invariants and how
they are enforced / tested.

## Invariants

- **No write API calls.** The typed API client (`src/api/client.ts`) exposes
  `apiGet` only — there is no post/put/patch/delete method anywhere. The static
  fallback page uses `fetch(..., { method: "GET" })` exclusively.
- **No operator actions.** No approve / reject / request-changes / accept.
- **No approval actions.** The console never calls the approval API.
- **No delivery acceptance action.** Human acceptance is displayed `pending` and
  cannot be changed from the UI.
- **No deploy.** No deploy / devops trigger.
- **No GitHub write.** No PR creation, no branch push, no repo write.
- **No secret exposure.** Responses + raw JSON panels are redacted before
  display.

## Redaction rules

`src/utils/safety.ts` (`redact`) deep-walks every rendered object and:

- replaces values whose key contains `token`, `secret`, `password`, `api_key`,
  `apikey`, `hmac`, `private_key`, or `webhook` with `***REDACTED***`;
- drops keys containing `chain_of_thought`, `raw_prompt`, or `transcript`
  entirely (chain-of-thought is never displayed).

The zero-build static fallback implements the same redaction in-page. No
sensitive data is written to `localStorage`. No token is stored in the bundle.

## Enforcement / tests

- `src/__tests__/readOnlyGuard.test.ts` scans the whole frontend source tree and
  asserts no mutating HTTP method and no operator/approve/deploy action call.
- `src/__tests__/redaction.test.ts` asserts secret-key redaction and
  chain-of-thought stripping.
- `src/__tests__/apiClient.test.ts` asserts GET-only behaviour.
- Backend `tests/test_admin_console_no_side_effects.py` arms tripwires on every
  store write method and asserts the aggregate endpoints never write; it also
  asserts the router exposes only GET/HEAD routes.
- `tests/test_admin_console_no_secret_leak.py` asserts responses + the static
  bundle carry no secrets / chain-of-thought.
- `/operations/safety` exposes `admin_console_read_only=true`,
  `admin_console_operator_actions_enabled=false`,
  `admin_console_write_api_enabled=false`,
  `admin_console_secret_redaction_enabled=true`.
- `check_runtime_state.sh` smokes 230–242 + `verify_admin_console_v0.sh`
  (Scenario C/E) re-check the read-only / redaction guards at runtime.
