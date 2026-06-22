import { AsyncView } from "../components/AsyncView";
import { KeyValueTable } from "../components/KeyValueTable";
import { getSecretReport } from "../api/operations";

// Step 53 -- read-only secret management foundation view. GET-only; this page
// renders NO reveal / copy / upload / rotate / configure / test secret control,
// no production-ready toggle, and never displays a secret value. Production
// secret management is never "ready".
export function SecretPosture() {
  return (
    <AsyncView load={getSecretReport}>
      {(d) => {
        const data = d as Record<string, unknown>;
        const f = (data.foundation as Record<string, unknown>) || {};
        const limits = (f.limitations as string[]) || [];
        const next = (f.nextRequiredSteps as string[]) || [];
        const cats = (f.categoriesCovered as string[]) || [];
        return (
          <>
            <h2>Production Secret Management Foundation</h2>
            <p className="note">
              Read-only secret foundation — production secret management is NOT configured. No
              real secret store, no secret values, no read/write/rotate. This view provides NO
              reveal / copy / upload / rotate / configure / test control and never displays a
              secret value.
            </p>
            <KeyValueTable
              data={{
                foundation_status: data.status,
                production_ready: data.productionReady,
                production_store_configured: f.productionStoreConfigured,
                production_store_enabled: f.productionStoreEnabled,
                read_value_enabled: f.readValueEnabled,
                write_value_enabled: f.writeValueEnabled,
                rotation_enabled: f.rotationEnabled,
                inline_values_detected: f.inlineValuesDetected,
                redaction_policy_enabled: f.redactionPolicyEnabled,
                categories_covered: cats.length,
              }}
            />
            <h2 style={{ marginTop: 20 }}>Production secret readiness caveat</h2>
            <p className="note">
              Production secret management is NOT ready. A production secret store (this Step),
              production OIDC client secret, production session key rotation backend, and
              production backup key store are all still required. No secret value is stored in the
              repo or displayed here.
            </p>
            <h2 style={{ marginTop: 20 }}>Production blockers / next required steps</h2>
            <ul>
              {limits.map((l) => (
                <li key={l}>{l}</li>
              ))}
              {next.map((s) => (
                <li key={s}>{s}</li>
              ))}
            </ul>
          </>
        );
      }}
    </AsyncView>
  );
}
