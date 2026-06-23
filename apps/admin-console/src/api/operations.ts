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

// Step 53 -- read-only secret management foundation (GET only).
export const getSecretReport = () =>
  apiGet<Record<string, unknown>>(`/operations/secrets/report`);

// Step 54.1 -- read-only application security & supply chain (GET only).
export const getSecurityReport = () =>
  apiGet<Record<string, unknown>>(`/operations/security/report`);
