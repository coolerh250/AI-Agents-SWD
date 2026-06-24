import { AsyncView } from "../components/AsyncView";
import { KeyValueTable } from "../components/KeyValueTable";
import {
  getImageReadiness,
  getSbomStatus,
  getSecurityReport,
  getSecurityScanStatus,
} from "../api/operations";

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
            <ScanPosture />
            <ContainerPosture />
          </>
        );
      }}
    </AsyncView>
  );
}

// Step 54.3 -- read-only SBOM / container security posture. NO generate-SBOM /
// scan-image / registry-login / image-push / sign / attest control; status only.
function ContainerPosture() {
  return (
    <AsyncView load={async () => ({ sbom: await getSbomStatus(), images: await getImageReadiness() })}>
      {(d) => {
        const data = d as { sbom: Record<string, unknown>; images: Record<string, unknown> };
        const sbom = data.sbom || {};
        const images = data.images || {};
        const blockers = (images.blockers as string[]) || [];
        const latest = (sbom.latest as Record<string, unknown>) || {};
        return (
          <>
            <h2 style={{ marginTop: 20 }}>SBOM / Image Digest / Container Security (Step 54.3)</h2>
            <p className="note">
              Read-only SBOM + container security baseline — local-only, modeled and locally
              verifiable, NOT production-enforced. No registry login, no image pull/push, no
              signing, no attestation, no SBOM upload, no production gate. This view provides NO
              generate-SBOM / scan-image / login-registry / push-image / sign / attest control.
              Runtime SBOM / image-policy reports are never committed (status not_run here).
            </p>
            <KeyValueTable
              data={{
                sbom_baseline_enabled: sbom.baselineEnabled,
                sbom_local_only: sbom.localOnly,
                sbom_external_upload_enabled: sbom.externalUploadEnabled,
                sbom_runtime_reports_committed: sbom.runtimeReportsCommitted,
                sbom_latest_status: latest.status ?? "not_run",
                container_production_ready: images.productionReady,
                container_production_gate_enabled: images.productionGateEnabled,
              }}
            />
            <h2 style={{ marginTop: 20 }}>Production readiness caveat / blockers</h2>
            <p className="note">
              Production SBOM, production image supply chain, and the production image
              vulnerability gate are NOT ready. Digest pinning, non-root images, an external CVE
              scan, signing/attestation, and a non-production cluster smoke (Step 55) are still
              required.
            </p>
            <ul>
              {blockers.map((b) => (
                <li key={b}>{b}</li>
              ))}
            </ul>
          </>
        );
      }}
    </AsyncView>
  );
}

// Step 54.2 -- read-only local scan toolchain posture. NO run-scan / upload /
// connect / configure control; status only, degrades to not_run when no local
// scan has been run in this environment.
function ScanPosture() {
  return (
    <AsyncView load={getSecurityScanStatus}>
      {(d) => {
        const data = d as Record<string, unknown>;
        const bc = (data.baselineConfiguration as Record<string, unknown>) || {};
        const sev = (k: string) =>
          ((data[k] as Record<string, unknown>) || {}).status ?? "not_run";
        return (
          <>
            <h2 style={{ marginTop: 20 }}>Local Scan Toolchain Baseline (Step 54.2)</h2>
            <p className="note">
              Local-only scan baseline — no external scanner, no source upload, no token, no
              network, no run-scan control. Runtime scan reports are never committed; live
              status is not_run when no local scan has run in this environment. Scans are NOT
              production-enforced.
            </p>
            <KeyValueTable
              data={{
                local_scan_baseline_enabled: bc.localScanBaselineEnabled,
                secret_scan_configured: bc.secretScanConfigured,
                sast_configured: bc.sastConfigured,
                dependency_scan_configured: bc.dependencyScanConfigured,
                external_upload_enabled: bc.externalUploadEnabled,
                network_enabled: bc.networkEnabled,
                token_required: bc.tokenRequired,
                result_normalization_enabled: bc.resultNormalizationEnabled,
                reports_committed: bc.reportsCommitted,
                production_gate_enabled: bc.productionGateEnabled,
                production_ready: data.productionReady,
                secret_scan_last_status: sev("secret"),
                sast_last_status: sev("sast"),
                dependency_scan_last_status: sev("dependency"),
              }}
            />
          </>
        );
      }}
    </AsyncView>
  );
}
