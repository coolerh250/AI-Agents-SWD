import { AsyncView } from "../components/AsyncView";
import { KeyValueTable } from "../components/KeyValueTable";
import {
  getNonprodSmokePreflight,
  getNonprodSmokeReadiness,
  getNonprodSmokeReport,
  getRuntimeReport,
} from "../api/operations";

// Step 51.4 -- read-only Kubernetes / Helm / GitOps runtime baseline view.
// GET-only; this page renders NO deploy / sync / apply / install control and no
// cluster credential / kubeconfig / token input. Production is never "ready".
export function RuntimeBaseline() {
  return (
    <AsyncView load={getRuntimeReport}>
      {(d) => {
        const data = d as Record<string, unknown>;
        const area = (data.areaStatus as Record<string, unknown>) || {};
        const prod = (data.productionSafety as Record<string, unknown>) || {};
        const facts = (data.safetyFacts as Record<string, unknown>) || {};
        const limits = (data.limitations as string[]) || [];
        const envs = (data.environments as Record<string, unknown>[]) || [];
        return (
          <>
            <h2>Kubernetes / Helm / GitOps Runtime Baseline</h2>
            <p className="note">
              Read-only static baseline — no cluster connected, no deploy, no Helm install, no
              ArgoCD sync. This view provides NO deploy / sync / apply / install control.
            </p>
            <KeyValueTable
              data={{
                runtime_status: data.status,
                production_ready: prod.productionReady,
                validated_not_deployed: prod.validatedNotDeployed,
                cluster_connected: data.clusterConnected,
                ...area,
                auto_sync_enabled: prod.autoSyncEnabled,
                production_application_enabled: prod.productionApplicationEnabled,
              }}
            />
            <h2 style={{ marginTop: 20 }}>Production safety caveat</h2>
            <p className="note">
              Production is NOT ready. Real rollout still requires ArgoCD install, real
              destination clusters, repo credentials, production OIDC, a secret store,
              image-digest pinning, a backup target, operator approval, and a runtime cluster
              smoke.
            </p>
            <h2 style={{ marginTop: 20 }}>Environments</h2>
            <KeyValueTable
              data={Object.fromEntries(
                envs.map((e) => [
                  String(e.name),
                  `active=${e.active} disabled=${e.disabled} production=${e.production}`,
                ]),
              )}
            />
            <h2 style={{ marginTop: 20 }}>Safety facts</h2>
            <KeyValueTable data={facts} />
            <h2 style={{ marginTop: 20 }}>Non-production limitations</h2>
            <ul>
              {limits.map((l) => (
                <li key={l}>{l}</li>
              ))}
            </ul>
            <NonprodRuntimeSmoke />
          </>
        );
      }}
    </AsyncView>
  );
}

// Step 55 -- read-only non-production Kubernetes runtime smoke posture. NO deploy /
// helm-install / cleanup / kubectl-exec / ArgoCD-sync control, no namespace / secret
// input, no production-ready toggle, no mutation action. Runtime smoke artifacts are
// never committed (status not_run here); when no safe cluster exists the smoke is
// blocked, never faked.
function NonprodRuntimeSmoke() {
  return (
    <AsyncView
      load={async () => ({
        readiness: await getNonprodSmokeReadiness(),
        preflight: await getNonprodSmokePreflight(),
        report: await getNonprodSmokeReport(),
      })}
    >
      {(d) => {
        const data = d as {
          readiness: Record<string, unknown>;
          preflight: Record<string, unknown>;
          report: Record<string, unknown>;
        };
        const readiness = data.readiness || {};
        const preflight = data.preflight || {};
        const report = data.report || {};
        const blockers = (readiness.blockers as string[]) || [];
        const nextSteps = (readiness.requiredNextSteps as string[]) || [];
        return (
          <>
            <h2 style={{ marginTop: 20 }}>Non-production Runtime Smoke (Step 55)</h2>
            <p className="note">
              Read-only non-production Kubernetes runtime smoke — framework ready, NOT
              production-enforced. No deploy, no Helm install, no cleanup, no kubectl exec, no
              ArgoCD sync control; no namespace / secret input; no production-ready toggle. When
              no safe non-production cluster exists the smoke is BLOCKED (never faked). Runtime
              smoke reports are never committed (status not_run here).
            </p>
            <KeyValueTable
              data={{
                smoke_status: readiness.status,
                cluster_access_detected: readiness.clusterAccessDetected,
                namespace: readiness.namespace,
                preflight_status: preflight.status ?? "not_run",
                preflight_blocked: preflight.blocked,
                helm_smoke_status: report.status ?? "not_run",
                pod_startup: report.status ?? "not_run",
                production_ready: readiness.productionReady,
              }}
            />
            <h2 style={{ marginTop: 16 }}>Blockers / Step 56 dependency</h2>
            <p className="note">
              Step 56 (real ArgoCD non-production manual sync) and Step 60 (production readiness
              review) are still required. Claude Code does not decide Production readiness.
            </p>
            <ul>
              {blockers.map((b) => (
                <li key={b}>{b}</li>
              ))}
              {nextSteps.map((s) => (
                <li key={s}>{s}</li>
              ))}
            </ul>
          </>
        );
      }}
    </AsyncView>
  );
}
