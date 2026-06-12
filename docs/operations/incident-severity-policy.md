# Incident Severity Policy

Stage 40 — AI Agents SWD Platform

## SEV Definitions

| Level | Name | Criteria | Response Target |
|---|---|---|---|
| SEV1 | CRITICAL | Platform down, data loss risk, complete function unavailable, production-impacting audit/integrity breach | Immediate |
| SEV2 | HIGH | Major feature degraded, significant user impact, partial data unavailability | < 15 min |
| SEV3 | MEDIUM | Non-critical feature degraded, workaround available, limited user impact | < 1 hour |
| SEV4 | LOW | Minor issue, cosmetic, minimal user impact, can be planned | Next business day |
| SEV5 | INFO | Informational alerts, capacity planning, trend anomaly | No SLA |

## Alertmanager Severity Mapping

| Alertmanager label | Normalized severity |
|---|---|
| critical | SEV1_CRITICAL |
| warning | SEV3_MEDIUM |
| info | SEV5_INFO |
| (unknown / missing) | SEV4_LOW |

## Postmortem Requirement

- **SEV1 and SEV2**: postmortem required after resolution.
- SEV3–SEV5: postmortem optional; recommended for recurring incidents.

## Escalation Policy (Dry-run Only — Stage 40)

All escalation is `dry_run=true`. No real pager/Slack/OpsGenie message is sent.

| Severity | Targets (placeholder) | Delay | Repeat |
|---|---|---|---|
| SEV1_CRITICAL | oncall-primary-placeholder, engineering-lead-placeholder | 0 min | 15 min |
| SEV2_HIGH | oncall-primary-placeholder | 5 min | 30 min |
| SEV3_MEDIUM | team-channel-placeholder | 30 min | 120 min |
| SEV4_LOW | (none) | 60 min | 480 min |
| SEV5_INFO | (none) | 120 min | 1440 min |

## Production Blockers

- Real pager/Slack integration requires secret store + production approval.
- Kubernetes / Helm deployment baseline not yet configured.
- Off-host backup storage not yet configured.

## Claude Code Note

Claude Code reports observations only. It does not decide production readiness.
