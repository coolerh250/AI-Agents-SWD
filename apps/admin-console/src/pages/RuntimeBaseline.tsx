import { AsyncView } from "../components/AsyncView";
import { KeyValueTable } from "../components/KeyValueTable";
import { getRuntimeReport } from "../api/operations";

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
          </>
        );
      }}
    </AsyncView>
  );
}
