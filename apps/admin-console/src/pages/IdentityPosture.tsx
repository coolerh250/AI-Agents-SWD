import { AsyncView } from "../components/AsyncView";
import { KeyValueTable } from "../components/KeyValueTable";
import { getIdentityReport } from "../api/operations";

// Step 52.4 -- read-only identity posture view. GET-only; this page renders NO
// OIDC login / connect / configure, NO production auth toggle, NO role-mapping
// editor, NO break-glass button, NO token/secret display, NO mutation control.
// Production identity is never "ready".
export function IdentityPosture() {
  return (
    <AsyncView load={getIdentityReport}>
      {(d) => {
        const data = d as Record<string, unknown>;
        const posture = (data.posture as Record<string, unknown>) || {};
        const oidc = (data.oidc as Record<string, unknown>) || {};
        const sess = (data.session as Record<string, unknown>) || {};
        const rm = (data.roleMapping as Record<string, unknown>) || {};
        const bg = (data.breakGlass as Record<string, unknown>) || {};
        const az = (data.authorization as Record<string, unknown>) || {};
        const limits = (data.limitations as string[]) || [];
        const next = (data.nextRequiredSteps as string[]) || [];
        return (
          <>
            <h2>Production Identity & OIDC Foundation</h2>
            <p className="note">
              Read-only identity posture — production identity is NOT enabled. No real IdP, no
              OIDC discovery/JWKS fetch, no callback, no token exchange, no production login. This
              view provides NO login / connect / configure / role-mapping / break-glass / mutation
              control.
            </p>
            <KeyValueTable
              data={{
                posture_status: data.status,
                production_identity_ready: data.productionIdentityReady,
                production_auth_enabled: posture.productionAuthEnabled,
                test_local_enabled: posture.testLocalEnabled,
                oidc_abstraction_enabled: oidc.abstractionEnabled,
                oidc_enabled: oidc.enabled,
                oidc_configured: oidc.configured,
                oidc_discovery_fetched: oidc.discoveryFetched,
                oidc_jwks_fetched: oidc.jwksFetched,
                oidc_callback_enabled: oidc.callbackEnabled,
                oidc_token_exchange_enabled: oidc.tokenExchangeEnabled,
                session_hardened: sess.hardened,
                session_raw_token_persisted: sess.rawTokenPersisted,
                session_cleanup_available: sess.cleanupAvailable,
                session_concurrency_enforced: sess.concurrencyEnforced,
                session_forced_logout_supported: sess.forcedLogoutSupported,
                session_key_rotation_ready: sess.keyRotationProductionReady,
                role_mapping_engine: rm.enginePresent,
                role_mapping_configured: rm.configured,
                unknown_user_behavior: rm.unknownUserBehavior,
                default_role: rm.defaultRole,
                platform_admin_auto_grant: rm.platformAdminAutoGrant,
                break_glass_enabled: bg.enabled,
                platform_admin_infrastructure_authority: az.platformAdminInfrastructureAuthority,
                human_acceptance_is_deployment: az.humanAcceptanceIsDeployment,
              }}
            />
            <h2 style={{ marginTop: 20 }}>Production identity caveat</h2>
            <p className="note">
              Production identity is NOT ready. Real enablement still requires a production secret
              store (Step 53), a configured production OIDC provider + real group→role mapping, a
              production session key rotation backend, and a production approval identity chain
              (Step 60). Break-glass is disabled. platform_admin has no infrastructure authority.
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
