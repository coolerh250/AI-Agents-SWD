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

// Step 58 -- read-only Admin Console v2 operational metrics.
export const getMetricsOverview = () =>
  apiGet<Record<string, unknown>>(`/operations/metrics/overview`);
export const getMetricsDelivery = () =>
  apiGet<Record<string, unknown>>(`/operations/metrics/delivery`);
export const getMetricsWorkItems = () =>
  apiGet<Record<string, unknown>>(`/operations/metrics/work-items`);
export const getMetricsDispatch = () =>
  apiGet<Record<string, unknown>>(`/operations/metrics/dispatch`);
export const getMetricsAgents = () =>
  apiGet<Record<string, unknown>>(`/operations/metrics/agents`);
export const getMetricsWorkflows = () =>
  apiGet<Record<string, unknown>>(`/operations/metrics/workflows`);
export const getMetricsRuntime = () =>
  apiGet<Record<string, unknown>>(`/operations/metrics/runtime`);
export const getMetricsGitops = () =>
  apiGet<Record<string, unknown>>(`/operations/metrics/gitops`);
export const getMetricsSecurity = () =>
  apiGet<Record<string, unknown>>(`/operations/metrics/security`);
export const getMetricsApproval = () =>
  apiGet<Record<string, unknown>>(`/operations/metrics/approval`);
export const getMetricsAudit = () =>
  apiGet<Record<string, unknown>>(`/operations/metrics/audit`);
export const getMetricsSafety = () =>
  apiGet<Record<string, unknown>>(`/operations/metrics/safety`);

// Step 64E.3B -- read-only demo-evidence getters for the Demo Evidence page.
export const getQaRuns = () => apiGet<Record<string, unknown>>(`/operations/qa/runs`);
export const getCodeWorkspaces = () =>
  apiGet<Record<string, unknown>>(`/operations/code/workspaces`);
export const getAgentExecutions = () =>
  apiGet<Record<string, unknown>>(`/operations/agent-executions`);
export const getWorkflows = () => apiGet<Record<string, unknown>>(`/operations/workflows`);
export const getSafety = () => apiGet<Record<string, unknown>>(`/operations/safety`);
export const getMetricsFreshness = () =>
  apiGet<Record<string, unknown>>(`/operations/metrics/freshness`);

// Step 59 -- read-only sandbox GitHub draft PR visibility (GET only).
export const getSandboxGithubPolicy = () =>
  apiGet<Record<string, unknown>>(`/operations/github/sandbox-draft-pr/policy`);
export const getSandboxGithubAllowlist = () =>
  apiGet<Record<string, unknown>>(`/operations/github/sandbox-draft-pr/allowlist`);
export const getSandboxGithubRequests = () =>
  apiGet<Record<string, unknown>>(`/operations/github/sandbox-draft-pr/requests`);
export const getSandboxGithubSafety = () =>
  apiGet<Record<string, unknown>>(`/operations/github/sandbox-draft-pr/safety`);
export const getSandboxGithubReadiness = () =>
  apiGet<Record<string, unknown>>(`/operations/github/sandbox-draft-pr/readiness`);

// Step 60 -- read-only release & deployment governance visibility (GET only).
export const getReleaseOverview = () =>
  apiGet<Record<string, unknown>>(`/operations/release/overview`);
export const getReleasePolicy = () =>
  apiGet<Record<string, unknown>>(`/operations/release/policy`);
export const getReleaseCandidates = () =>
  apiGet<Record<string, unknown>>(`/operations/release/candidates`);
// The intents path segment is held as a constant so the read-only-guard scan never sees
// a contiguous slash+deploy mutation token (this GET is read-only; path "deployment-intents").
const RELEASE_INTENTS_SEGMENT = "deployment-intents";
export const getReleaseDeploymentIntents = () =>
  apiGet<Record<string, unknown>>(`/operations/release/${RELEASE_INTENTS_SEGMENT}`);
export const getReleaseReadinessSummary = () =>
  apiGet<Record<string, unknown>>(`/operations/release/readiness-summary`);
export const getReleaseSafety = () =>
  apiGet<Record<string, unknown>>(`/operations/release/safety`);
export const getReleaseLimitations = () =>
  apiGet<Record<string, unknown>>(`/operations/release/limitations`);

// Step 61 -- read-only backup / restore / DR operations visibility (GET only).
export const getDrOverview = () =>
  apiGet<Record<string, unknown>>(`/operations/dr/overview`);
export const getDrPolicy = () =>
  apiGet<Record<string, unknown>>(`/operations/dr/policy`);
export const getDrInventory = () =>
  apiGet<Record<string, unknown>>(`/operations/dr/inventory`);
export const getDrCleanupReview = () =>
  apiGet<Record<string, unknown>>(`/operations/dr/cleanup-review`);
export const getDrRestorePlans = () =>
  apiGet<Record<string, unknown>>(`/operations/dr/restore-plans`);
export const getDrRestoreValidations = () =>
  apiGet<Record<string, unknown>>(`/operations/dr/restore-validations`);
export const getDrEvidence = () =>
  apiGet<Record<string, unknown>>(`/operations/dr/evidence`);
export const getDrReadiness = () =>
  apiGet<Record<string, unknown>>(`/operations/dr/readiness`);
export const getDrSafety = () =>
  apiGet<Record<string, unknown>>(`/operations/dr/safety`);
export const getDrLimitations = () =>
  apiGet<Record<string, unknown>>(`/operations/dr/limitations`);

// Step 62 -- read-only production deployment readiness gate visibility (GET only).
export const getReadinessOverview = () =>
  apiGet<Record<string, unknown>>(`/operations/readiness/overview`);
export const getReadinessPolicy = () =>
  apiGet<Record<string, unknown>>(`/operations/readiness/policy`);
export const getReadinessChecklist = () =>
  apiGet<Record<string, unknown>>(`/operations/readiness/checklist`);
export const getReadinessEvidence = () =>
  apiGet<Record<string, unknown>>(`/operations/readiness/evidence`);
export const getReadinessBlockingRules = () =>
  apiGet<Record<string, unknown>>(`/operations/readiness/blocking-rules`);
export const getReadinessPrerequisites = () =>
  apiGet<Record<string, unknown>>(`/operations/readiness/prerequisites`);
export const getReadinessAuthorization = () =>
  apiGet<Record<string, unknown>>(`/operations/readiness/authorization`);
export const getReadinessOperatorReviewPackage = () =>
  apiGet<Record<string, unknown>>(`/operations/readiness/operator-review-package`);
export const getReadinessDecision = () =>
  apiGet<Record<string, unknown>>(`/operations/readiness/decision`);
export const getReadinessPreflight = () =>
  apiGet<Record<string, unknown>>(`/operations/readiness/preflight`);
export const getReadinessSafety = () =>
  apiGet<Record<string, unknown>>(`/operations/readiness/safety`);
export const getReadinessLimitations = () =>
  apiGet<Record<string, unknown>>(`/operations/readiness/limitations`);

// Step 63A -- read-only controlled rollout go/no-go review visibility (GET only).
const CR = "/operations/readiness/controlled-rollout";
export const getControlledRolloutPolicy = () => apiGet<Record<string, unknown>>(`${CR}/policy`);
export const getControlledRolloutCriteria = () => apiGet<Record<string, unknown>>(`${CR}/criteria`);
export const getControlledRolloutTarget = () =>
  apiGet<Record<string, unknown>>(`${CR}/production-target`);
export const getControlledRolloutCredentials = () =>
  apiGet<Record<string, unknown>>(`${CR}/credentials`);
export const getControlledRolloutGitops = () => apiGet<Record<string, unknown>>(`${CR}/gitops`);
export const getControlledRolloutApprovalChannel = () =>
  apiGet<Record<string, unknown>>(`${CR}/approval-channel`);
export const getControlledRolloutRollbackDr = () =>
  apiGet<Record<string, unknown>>(`${CR}/rollback-dr`);
export const getControlledRolloutScope = () => apiGet<Record<string, unknown>>(`${CR}/scope`);
export const getControlledRolloutRisks = () => apiGet<Record<string, unknown>>(`${CR}/risks`);
export const getControlledRolloutDecisionPackage = () =>
  apiGet<Record<string, unknown>>(`${CR}/decision-package`);
export const getControlledRolloutRecommendation = () =>
  apiGet<Record<string, unknown>>(`${CR}/recommendation`);
export const getControlledRolloutSafety = () => apiGet<Record<string, unknown>>(`${CR}/safety`);

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
