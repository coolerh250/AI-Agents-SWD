// Stage 50 -- typed read-only Admin Console API surface. GET only.

import { apiGet } from "./client";
import type {
  LatestDeliveryState,
  Overview,
  ProjectDetail,
  ProjectsResponse,
  RegressionSummary,
  SafetySummary,
} from "./types";

const BASE = "/operations/admin-console";

export const getOverview = () => apiGet<Overview>(`${BASE}/overview`);
export const getProjects = () => apiGet<ProjectsResponse>(`${BASE}/projects`);
export const getProjectDetail = (id: string) =>
  apiGet<ProjectDetail>(`${BASE}/projects/${encodeURIComponent(id)}`);
export const getLatestDeliveryState = () =>
  apiGet<LatestDeliveryState>(`${BASE}/latest-delivery-state`);
export const getSafetySummary = () => apiGet<SafetySummary>(`${BASE}/safety-summary`);
export const getRegressionSummary = () => apiGet<RegressionSummary>(`${BASE}/regression-summary`);

// Step 51.4 -- read-only Kubernetes/Helm/GitOps runtime baseline (GET only).
export const getRuntimeReport = () =>
  apiGet<Record<string, unknown>>(`/operations/runtime/report`);

// Step 52.4 -- read-only identity posture (GET only; no mutation client method).
export const getIdentityReport = () =>
  apiGet<Record<string, unknown>>(`/operations/identity/report`);

// Step 55 -- read-only non-production runtime smoke posture (GET only; no deploy /
// helm-install / cleanup / exec / sync client method).
export const getNonprodSmokeReadiness = () =>
  apiGet<Record<string, unknown>>(`/operations/runtime/nonprod-smoke/readiness`);
export const getNonprodSmokePreflight = () =>
  apiGet<Record<string, unknown>>(`/operations/runtime/nonprod-smoke/preflight`);
export const getNonprodSmokeReport = () =>
  apiGet<Record<string, unknown>>(`/operations/runtime/nonprod-smoke/report`);

// Step 56 -- read-only non-production ArgoCD manual-sync posture (GET only).
export const getNonprodArgocdSync = () =>
  apiGet<Record<string, unknown>>(`/operations/gitops/nonprod-argocd/sync`);
export const getNonprodArgocdSafety = () =>
  apiGet<Record<string, unknown>>(`/operations/gitops/nonprod-argocd/safety`);
export const getNonprodArgocdApplication = () =>
  apiGet<Record<string, unknown>>(`/operations/gitops/nonprod-argocd/application`);
export const getNonprodArgocdReadiness = () =>
  apiGet<Record<string, unknown>>(`/operations/gitops/nonprod-argocd/readiness`);

// Step 57 -- multi-project delivery + work-item dispatch (GET reads only).
export const getDeliveryProjects = () =>
  apiGet<Record<string, unknown>>(`/operations/delivery/projects`);
export const getDeliveryProject = (id: string) =>
  apiGet<Record<string, unknown>>(`/operations/delivery/projects/${id}`);
export const getDeliveryWorkItems = (id: string) =>
  apiGet<Record<string, unknown>>(`/operations/delivery/projects/${id}/work-items`);
export const getDeliveryWorkItem = (id: string) =>
  apiGet<Record<string, unknown>>(`/operations/delivery/work-items/${id}`);
export const getDeliveryWorkItemEvents = (id: string) =>
  apiGet<Record<string, unknown>>(`/operations/delivery/work-items/${id}/events`);
export const getDeliveryWorkItemDispatches = (id: string) =>
  apiGet<Record<string, unknown>>(`/operations/delivery/work-items/${id}/dispatches`);
export const getProjectDeliveryState = (id: string) =>
  apiGet<Record<string, unknown>>(`/operations/delivery/projects/${id}/delivery-state`);

// Step 53 -- read-only secret management foundation (GET only).
export const getSecretReport = () =>
  apiGet<Record<string, unknown>>(`/operations/secrets/report`);

// Step 54.1 -- read-only application security & supply chain (GET only).
export const getSecurityReport = () =>
  apiGet<Record<string, unknown>>(`/operations/security/report`);

// Step 54.2 -- read-only local scan toolchain status (GET only; no run-scan).
export const getSecurityScanStatus = () =>
  apiGet<Record<string, unknown>>(`/operations/security/scans/status`);

// Step 54.3 -- read-only SBOM / container security posture (GET only).
export const getSbomStatus = () =>
  apiGet<Record<string, unknown>>(`/operations/security/sbom/status`);
export const getImageReadiness = () =>
  apiGet<Record<string, unknown>>(`/operations/security/images/readiness`);

// Step 54.4 -- read-only integrated security (threat model / release risk /
// evidence / readiness). GET only; no generate / approve / gate / deploy method.
export const getSecurityStep54Status = () =>
  apiGet<Record<string, unknown>>(`/operations/security/step54/status`);
export const getReleaseRiskSummary = () =>
  apiGet<Record<string, unknown>>(`/operations/security/release-risk/summary`);
export const getSecurityEvidencePackage = () =>
  apiGet<Record<string, unknown>>(`/operations/security/evidence/package`);
export const getSecurityReadinessReport = () =>
  apiGet<Record<string, unknown>>(`/operations/security/readiness/report`);
