import { AsyncView } from "../components/AsyncView";
import { KeyValueTable } from "../components/KeyValueTable";
import { getSecurityReport } from "../api/operations";

// Step 54.1 -- read-only application security & supply chain posture. GET-only;
// this page renders NO run-scan / upload-source / connect-scanner / configure-
// scanner / create-PR / push-image / production-gate control, and no mutation
// action. Security scans, SBOM, image supply chain, and release gate are never
// "production-ready".
export function SecurityPosture() {
  return (
    <AsyncView load={getSecurityReport}>
      {(d) => {
        const data = d as Record<string, unknown>;
        const f = (data.foundation as Record<string, unknown>) || {};
        const limits = (f.limitations as string[]) || [];
        const next = (f.nextRequiredSteps as string[]) || [];
        return (
          <>
            <h2>Application Security &amp; Supply Chain Baseline</h2>
            <p className="note">
              Read-only security posture — application security and supply chain baseline is
              modeled, NOT enforced for production. No scanner run, no SBOM generated, no image
              pushed, no GitHub write, no production gate. This view provides NO run-scan /
              upload-source / connect-scanner / configure-scanner / create-PR / push-image /
              production-gate control.
            </p>
            <KeyValueTable
              data={{
                foundation_status: data.status,
                production_ready: data.productionReady,
                sast_configured: f.sastConfigured,
                dependency_scan_configured: f.dependencyScanConfigured,
                secret_scan_configured: f.secretScanConfigured,
                sbom_configured: f.sbomConfigured,
                image_digest_policy_defined: f.imageDigestPolicyDefined,
                image_vulnerability_policy_defined: f.imageVulnerabilityPolicyDefined,
                threat_model_required: f.threatModelRequired,
                release_risk_summary_required: f.releaseRiskSummaryRequired,
                evidence_model_defined: f.evidenceModelDefined,
                finding_taxonomy_defined: f.findingTaxonomyDefined,
                gate_fail_closed_policy_defined: f.gateFailClosedPolicyDefined,
                github_write_enabled: f.githubWriteEnabled,
                pr_creation_enabled: f.prCreationEnabled,
                image_push_enabled: f.imagePushEnabled,
                registry_login_enabled: f.registryLoginEnabled,
                external_scanner_upload_enabled: f.externalScannerUploadEnabled,
                assets_inventoried: f.assetCount,
                production_relevant_assets: f.productionRelevantAssetCount,
              }}
            />
            <h2 style={{ marginTop: 20 }}>Production readiness caveat</h2>
            <p className="note">
              Security scans are NOT production-ready. SBOM is NOT generated. Image supply chain
              is NOT production-ready. The release gate is NOT production-ready. Step 54.2 (scan
              toolchain), Step 54.3 (SBOM / image digest / container security), and Step 54.4
              (threat model / release risk / integrated verification) are still required.
            </p>
            <h2 style={{ marginTop: 20 }}>Limitations / next required steps</h2>
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
