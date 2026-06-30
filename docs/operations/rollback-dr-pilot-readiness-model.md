# Rollback / DR Pilot Readiness Model (Step 63A)

Source: [`infra/readiness/rollback-dr-pilot-readiness-model.yaml`](../../infra/readiness/rollback-dr-pilot-readiness-model.yaml).

References the Step 60 release-governance rollback requirement and the Step 61
backup/restore/DR baseline. A Step 61 PASS is explicitly **NOT** production DR ready
(`step61_pass_is_production_dr_ready: false`). No restore / failover is executed
(`executes_restore: false`, `executes_failover: false`). Production rollback / restore /
failover are not validated → status `insufficient`, contributing to `no_go` /
`conditional_go`.
