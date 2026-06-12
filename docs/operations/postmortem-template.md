# Postmortem Template

## Incident ID

<!-- incident_id from incident_records -->

## Severity

<!-- SEV1_CRITICAL / SEV2_HIGH / SEV3_MEDIUM -->

## Summary

<!-- 1-2 sentence description of what happened and the impact -->

## Customer / Internal Impact

- [ ] Customer-facing impact: <!-- yes/no and scope -->
- [ ] Internal systems impacted: <!-- list affected services -->
- [ ] Data integrity affected: <!-- yes/no -->
- [ ] Duration of impact: <!-- start → end -->

## Detection

- How was the incident detected? <!-- alert / monitoring / user report / operator observation -->
- Time to detection: <!-- minutes/hours from incident start -->
- Alert that fired (if any): <!-- alert name + severity -->

## Timeline

| Time (UTC) | Event |
|---|---|
| <!-- 2026-06-01 00:00 --> | Incident started |
| <!-- --> | Alert fired |
| <!-- --> | Incident acknowledged |
| <!-- --> | Investigation began |
| <!-- --> | Root cause identified |
| <!-- --> | Mitigation applied |
| <!-- --> | Incident resolved |
| <!-- --> | Postmortem started |

## Root Cause

<!-- Detailed technical root cause. What was the underlying failure? -->

## Contributing Factors

1. <!-- Factor 1 -->
2. <!-- Factor 2 -->

## What Went Well

- <!-- Detection was fast -->
- <!-- Runbook was accurate -->

## What Went Wrong

- <!-- Alert threshold was too high -->
- <!-- No runbook for this failure mode -->

## Corrective Actions

| Action | Owner | Due Date | Status |
|---|---|---|---|
| <!-- Fix the root cause --> | <!-- owner --> | <!-- 2026-07-01 --> | Open |
| <!-- Add monitoring --> | <!-- owner --> | <!-- --> | Open |

## Owners

- Primary: <!-- name / team -->
- Review: <!-- name / team -->

## Due Date

<!-- Date postmortem must be completed by -->

## Follow-up Verification

- [ ] Corrective actions implemented and tested
- [ ] New monitoring / alerting in place
- [ ] Runbook updated
- [ ] Postmortem reviewed by team lead

---

*AI Agents SWD Platform — Stage 40 Postmortem Template*
