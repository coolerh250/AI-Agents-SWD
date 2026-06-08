# Real Discord Delivery Policy

Stage 33 closes the autospam blocker that surfaced during Step 31R: when
real Discord credentials were present in the `notification-worker`
container, the worker's `stream.notifications` consumer routed **every**
platform event to the test channel — 128 messages landed there within
one hour.

The fix is a stream-side policy that mirrors the Stage 32 per-endpoint
guard. The endpoint guard already enforces channel + mode +
`production_executed=false` on the explicit `/discord/real/*` routes;
the policy now enforces the same intent on the stream consumer.

## Why we cannot just send everything

Internal events (`workflow.*`, `qa.*`, `code.*`, `github.*`, `task.*`,
`llm.*`, `approval.*`, `audit.*`, `incident.*`, `retry.*`) are produced
in normal platform operation at sustained rates that would saturate any
operator channel. They also leak operational context that should stay
inside the audit + operations surfaces, not Discord. The policy
**defaults to deny** so a producer cannot accidentally promote a new
internal event to Discord by setting a flag in the wrong place.

## Decision order

```
classify_real_delivery(payload, policy)
  1. policy.real_mode_enabled is False   -> simulated  (sandbox)
  2. policy.test_channel_id missing      -> skipped    (token_missing)
  3. payload.target_channel != configured-> real_blocked (wrong_channel)
  4. production_executed == True         -> real_blocked (production_executed_not_false)
  5. event matches denylist              -> real_blocked (event_type_denied)
  6. event matches allowlist OR
     allow_marker AND real_delivery=true -> real_allowed
  7. otherwise                           -> real_blocked (missing_real_delivery_marker)
```

**Denylist beats allowlist.** A producer cannot promote a `github.*` event
to real Discord by setting `metadata.real_delivery=true`; the denylist
match always wins.

## Default policy

```
allowlist:
  - discord.real_test_sent
  - discord.real_task_received

denylist:
  - workflow.*
  - qa.*
  - code.*
  - github.*
  - task.*
  - llm.*
  - approval.*
  - audit.*
  - incident.*
  - retry.*

allow_marker: true   # an unknown event may opt in with metadata.real_delivery=true
```

## Environment knobs

| Variable | Default | Purpose |
|---|---|---|
| `REAL_DISCORD_ALLOWLIST` | (defaults above) | comma-separated event patterns; `foo.*` is a prefix match |
| `REAL_DISCORD_DENYLIST` | (defaults above) | comma-separated event patterns; matches BEAT allowlist |
| `REAL_DISCORD_ALLOW_MARKER` | `true` | when `false`, only explicit allowlist entries may go real |
| `DISCORD_BOT_TOKEN` / `DISCORD_TEST_CHANNEL_ID` / `RUN_REAL_DISCORD_TEST` | — | the existing Stage 22/32 opt-in gate; none of these is changed by Stage 33 |

The token value is read only from the env var and never written into
audit, notifications, operations responses, logs, or any other
artifact.

## Per-event markers

A producer that needs to send a NEW event type to real Discord can set
either of:

```json
{"metadata": {"real_delivery": true, "production_executed": false}}
```

```json
{"real_delivery": true}
```

Both are accepted by the policy, but the denylist always wins. The
`production_executed` slot is checked separately — if it is the
literal `true` (or string `"true"`), the policy fails the event with
`production_executed_not_false`.

## Decision result + audit

Every classification returns a `RealDeliveryDecision`:

| field | values |
|---|---|
| `delivery_decision` | `simulated` / `real_allowed` / `real_blocked` / `skipped` / `failed` |
| `blocked_reason`    | one of `real_mode_disabled` / `missing_real_delivery_marker` / `event_type_not_allowed` / `event_type_denied` / `wrong_channel` / `production_executed_not_false` / `token_missing` |
| `event_type`        | the event_type from the payload |
| `target_channel`    | the configured `DISCORD_TEST_CHANNEL_ID` (never the payload's request) |
| `sandbox`           | `True` when no external attempt is made |
| `external_sent`     | only ever `True` when the real API actually accepted the message |

The worker writes the decision into `notification_deliveries.metadata`
under `delivery_decision` / `blocked_reason` / `event_type` and emits
matching audit rows:

* `discord_real_delivery_blocked` (`result=blocked`) — policy refused a
  real send.
* `discord_real_delivery_skipped` (`result=skipped`) — real mode was
  disabled before the event was even considered for the wire.
* `discord_real_test_sent` (`result=delivered`) — the allowlisted path
  that actually called the Discord API.

## No notification loop

The blocked-event audit goes onto `stream.audit` only. The worker MUST
NOT publish a notification event in response to a blocked notification
event — otherwise a single internal event would create an audit row
that itself becomes a notification, which would create another audit
row, etc. The Stage 33 implementation never calls
`publish_notification` from the blocked / skipped paths, and the
`verify_real_discord_delivery_filter.sh` script asserts this by
checking `stream.notifications` XLEN does not grow beyond the events
the script itself published.

## Operations surfaces

`/operations/safety` (orchestrator) adds:

```
real_discord_stream_delivery_default_blocked: true
real_discord_stream_delivery_policy_enforced: true
```

`/operations/real-integrations` (orchestrator) adds the
`notification_worker_real_delivery_policy` block, mirroring the worker
`/status` fields:

```
real_delivery_enabled
real_delivery_allowlist
real_delivery_denylist
real_delivery_allow_marker
real_delivery_allowed_count
real_delivery_blocked_count
real_delivery_skipped_count
last_real_delivery_decision
last_real_delivery_block_reason
```

## How to verify

```bash
# Pure-policy unit tests
pytest tests/test_notification_real_delivery_policy.py
pytest tests/test_notification_worker_real_delivery_filter.py
pytest tests/test_real_discord_delivery_no_autospam.py
pytest tests/test_operations_real_delivery_policy.py

# Runtime smoke
./scripts/verify_real_discord_delivery_filter.sh
./scripts/check_runtime_state.sh | grep -E 'REAL_DISCORD_(DELIVERY|AUTOSPAM|ALLOWED|DENYLIST|POLICY)'
```

The verify script is fail-closed: without real Discord env it asserts
`SKIPPED: PASS` for the scenarios that require the API, and runs the
policy-only checks against the in-process worker view.

## How to safely enable more event types

1. Decide whether the event is an operator-visible signal or a
   high-frequency internal stream. If high-frequency, do not enable
   it — keep it inside the operations + audit surfaces.
2. Check the denylist first. If the event matches a denied prefix
   (e.g. `workflow.completed` matches `workflow.*`), removing the
   denylist entry would re-create the autospam blast radius — instead,
   rename the event under a non-denied prefix or accept the block.
3. Add the new event_type to `REAL_DISCORD_ALLOWLIST` (or set
   `metadata.real_delivery=true` on the producer side).
4. Run `verify_real_discord_delivery_filter.sh` and confirm the
   allowed-count rose by the expected number.
5. Audit the channel for the next 24 hours to make sure the rate is
   what you expected.

## Cleanup history

After Step 31R, the test channel had 128 autospam messages. They were
left in place because they contained no secret content and were
prefixed with `[AI-Agents-SWD sandbox]`. Stage 33 prevents this from
happening again; if you re-enable real env in `notification-worker`,
the policy keeps the per-event blast radius at zero internal events.
