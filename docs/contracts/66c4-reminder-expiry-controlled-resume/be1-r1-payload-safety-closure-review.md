# Step 66C.4-BE1-R1-R — M-1 Payload Safety Closure Review

> Independent closure review of finding **M-1** (payload validation bypass). Judged from the
> allowlist in `shared/sdk/tasks/lifecycle_outbox.py` at `0bb9944` and the reviewer's own
> independently executed bypass probes.

## Finding under review

M-1 (MEDIUM, security, from `f5417f4`): the BE1 payload guard inspected only top-level keys against
an exact-match deny list, so a nested `{"meta": {"answer": ...}}` or a near-miss key name
(`answer_body`, `question_text`) was accepted, and a raw clarification body could be smuggled into
the outbox payload.

## Remediation inspected

The deny list is replaced by a POSITIVE per-event-type allowlist (`assert_safe_outbox_payload`):

- `ALLOWED_PAYLOAD_KEYS_BY_EVENT_TYPE` maps each canonical dotted event name
  (`clarification.reminder_due`, `.reminder_recorded`, `.expired`, `.resume_eligible`,
  `.resume_requested`, `.resume_authorized`) to the exact set of permitted keys
  (common keys `event_id`/`occurred_at`/`reason` plus event-specific timestamp keys).
- An unknown `event_type` is rejected before any key is examined.
- Each key is normalized (`strip().lower()`); a key owned by a dedicated column
  (`COLUMN_OWNED_PAYLOAD_KEYS`) is rejected; a key not in the allowlist is rejected.
- `_assert_safe_payload_value` permits only bounded scalars (`None`, `bool`, `int`, `str ≤ 500`);
  any `dict`, `list`, `float`, or other object is rejected — nesting (the smuggling vector) cannot
  pass.
- Total serialized payload is bounded to `MAX_PAYLOAD_BYTES = 2000`.
- Error messages name the offending KEY only, never the value.

## Independently executed bypass probes (reviewer's own)

All probes below were run by the reviewer against the real `assert_safe_outbox_payload`. `leak`
checks whether the raw value text appears in the error message.

```text
{"meta":{"answer":"raw"}}       => rejected  key='meta'            leak=False  ("key is not allowed")
{"items":[{"token":"secret"}]}  => rejected  key='items'           leak=False  ("key is not allowed")
{"answer_body":"raw"}           => rejected  key='answer_body'     leak=False  ("key is not allowed")
{"question_text":"raw"}         => rejected  key='question_text'   leak=False  ("key is not allowed")
{"TOKEN":"secret"}              => rejected  key='TOKEN'           leak=False  ("key is not allowed")
{"unknown_key":"value"}         => rejected  key='unknown_key'     leak=False  ("key is not allowed")
{"due_at":{"nested":1}}         => rejected  value must be a bounded scalar    leak=False
{"reason":"x"*600}              => rejected  value exceeds max length          leak=False
{"reason":1.5}                  => rejected  value must be a bounded scalar    leak=False (float)
{"reason":[1,2]}                => rejected  value must be a bounded scalar    leak=False (list)
{"clarification_id":"dup"}      => rejected  column-owned key                  leak=False
event_type="clarification.made_up"  => rejected  "unknown lifecycle outbox event_type"
legit payload (event_id, occurred_at, due_at, expired_at, reason) => ACCEPTED
```

Every required probe rejects: nested dict, list, float, oversized scalar, oversized total payload
(2000-byte bound), unknown dotted/underscored event name, near-miss body key names, case-variant
secret key (`TOKEN`), column-owned duplication (`clarification_id`), and raw
body/question/answer/message keys. The legitimate canonical payload is accepted. No error message
echoes a raw value.

## Observations (non-blocking)

- The stored payload retains original-case keys (the allowlist check lowercases only for comparison).
  This is cosmetic, not a safety gap: an accepted key is by definition an allowlisted, scalar-valued,
  bounded key. Recorded as informational; not a closure blocker.

## Verdict

**M-1: CLOSED.** The positive allowlist plus scalar-only value rule closes every bypass the original
review demonstrated and every additional probe the reviewer ran, without leaking raw values in
errors.

_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
