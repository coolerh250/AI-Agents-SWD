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
