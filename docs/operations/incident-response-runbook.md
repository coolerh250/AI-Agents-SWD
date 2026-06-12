# Incident Response Runbook

AI Agents SWD Platform — Stage 40

## Incident Lifecycle

```
[ALERT RECEIVED] → [INCIDENT CREATED] → [ACKNOWLEDGED] → [INVESTIGATING]
     → [MITIGATED] → [RESOLVED] → [CLOSED]
                                        ↓ (SEV1/SEV2)
                                 [POSTMORTEM REQUIRED]
```

Reopen path: `[CLOSED/RESOLVED] → [REOPENED/OPEN]`

## SEV Definitions

See [incident-severity-policy.md](incident-severity-policy.md) for full definitions.

| Level | Short description |
|---|---|
| SEV1_CRITICAL | Platform down / data loss / integrity breach |
| SEV2_HIGH | Major feature degraded |
| SEV3_MEDIUM | Non-critical degradation, workaround available |
| SEV4_LOW | Minor issue |
| SEV5_INFO | Informational |

## Roles and Responsibilities

| Role | Responsibility |
|---|---|
| Operator / On-call | Acknowledge, investigate, drive to resolution |
| Team Lead | Escalation oversight, postmortem sign-off |
| Claude Code | Report observations only — NEVER decides production readiness |

## Alert Intake

1. Alert fires in Alertmanager → routed to null-receiver (test) or `aiagents-receiver` (production).
2. `POST /alerts/alertmanager` or `POST /alerts/generic` called.
3. Payload validated, redacted, deduped.
4. Incident created (or linked to existing).
5. Lifecycle event `incident_created` recorded.
6. Audit row written to `audit_logs`.
7. Notification event published (blocked by denylist in test mode).
8. SEV1/SEV2: dry-run escalation recorded.

## Triage Steps

1. Check `/operations/incidents` for open incidents.
2. Check `/operations/incidents/{incident_id}` for details.
3. Check `/operations/incidents/{incident_id}/timeline` for lifecycle events.
4. Check `/operations/incidents/{incident_id}/alerts` for linked alerts.
5. Determine severity and appropriate response.

## Acknowledge Procedure

```bash
curl -s -X POST http://localhost:8000/operations/incidents/{incident_id}/acknowledge \
  -H 'Content-Type: application/json' | python -m json.tool
```

- Records lifecycle event `incident_acknowledged`.
- Writes audit row `incident_acknowledged`.
- Publishes notification `incident.acknowledged` (blocked by denylist in test).

## Escalation Procedure (Dry-run Only — Stage 40)

- SEV1/SEV2 escalation is automatically triggered as dry-run on alert ingestion.
- No real pager/Slack/OpsGenie message is sent.
- Lifecycle event `incident_escalated` with `dry_run=true` is recorded.
- To see escalation policies: `GET /operations/incidents` (includes escalation records if implemented).

**Production escalation requires:**
- Secret store integration.
- Real pager/Slack target configuration.
- Operator approval.

## Mitigation Procedure

1. Identify root cause from alert + timeline.
2. Apply fix (outside this system — no auto-remediation).
3. Verify service recovery via `/operations/safety` and `/operations/audit/integrity`.
4. Do not use Claude Code to auto-apply production changes.

## Resolve / Close Procedure

```bash
# Resolve
curl -s -X POST http://localhost:8000/operations/incidents/{incident_id}/resolve | python -m json.tool

# Close (requires resolved status, or explicit reason)
curl -s -X POST http://localhost:8000/operations/incidents/{incident_id}/close \
  -H 'Content-Type: application/json' \
  -d '{"reason": "resolved and verified"}' | python -m json.tool
```

## Reopen Procedure

```bash
curl -s -X POST http://localhost:8000/operations/incidents/{incident_id}/reopen \
  -H 'Content-Type: application/json' \
  -d '{"reason": "issue recurred"}' | python -m json.tool
```

## Postmortem Procedure

Required for SEV1 and SEV2.

```bash
# Create postmortem draft
curl -s -X POST http://localhost:8000/operations/incidents/{incident_id}/postmortem \
  -H 'Content-Type: application/json' \
  -d '{"summary": "Host unreachable after deploy", "owner": "team-ops"}' | python -m json.tool

# List postmortems
curl -s http://localhost:8000/operations/incidents/postmortems | python -m json.tool
```

Complete the postmortem using [postmortem-template.md](postmortem-template.md).

## Communication Policy

- All incident events produce audit rows in `audit_logs` (tamper-evident chain).
- Notification events (`incident.*`) are blocked by `DEFAULT_REAL_DELIVERY_DENYLIST` in test mode.
- Real external notifications require explicit operator enablement via secret store.

## Stop-pilot / Disable External Integrations Procedure

1. Remove `ALERT_RECEIVER_SHARED_SECRET` env var.
2. Service reverts to `local_test_unsigned` mode.
3. Alertmanager continues to route to null-receiver.
4. No real escalation is possible without explicit target configuration.

## Production Constraints

- `production_executed` must remain 0.
- No auto-remediation.
- No direct model selection by agent.
- No real LLM patch generation.
- No GitHub production write.
- Discord real delivery blocked by default.

## No Auto-remediation Policy

Claude Code and the agent pipeline do NOT automatically remediate incidents. All remediation is operator-driven. Incidents only affect `incident_records`, `incident_alerts`, `incident_lifecycle_events` — never `deployment_records` or `workflow_states` with `production_executed=true`.

## Known Gaps (Stage 40)

- Real pager/Slack/OpsGenie escalation: not wired (dry-run only).
- Alertmanager null-receiver: must be changed to `aiagents-receiver` for real intake.
- ALERT_RECEIVER_SHARED_SECRET: not configured on test server.
- Kubernetes/Helm/ArgoCD runtime baseline: pending.
- Off-host backup storage: pending.
- Production secret store (Vault): pending.
