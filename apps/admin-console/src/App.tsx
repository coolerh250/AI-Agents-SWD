import { Routes, Route } from "react-router-dom";
import { Layout } from "./components/Layout";
import { ExecutiveOverview } from "./pages/ExecutiveOverview";
import { Projects } from "./pages/Projects";
import { ProjectDetail } from "./pages/ProjectDetail";
import { TaskGraph } from "./pages/TaskGraph";
import { DesignReview } from "./pages/DesignReview";
import { WorkspaceExecution } from "./pages/WorkspaceExecution";
import { MiniDeliveryPilot } from "./pages/MiniDeliveryPilot";
import { DeliveryPackage } from "./pages/DeliveryPackage";
import { SafetyCenter } from "./pages/SafetyCenter";
import { RegressionStatus } from "./pages/RegressionStatus";
import { CostLlmGovernance } from "./pages/CostLlmGovernance";
import { Incidents } from "./pages/Incidents";
import { OperatorConsole } from "./pages/OperatorConsole";
import { RuntimeBaseline } from "./pages/RuntimeBaseline";
import { IdentityPosture } from "./pages/IdentityPosture";
import { SecretPosture } from "./pages/SecretPosture";
import { SecurityPosture } from "./pages/SecurityPosture";
import { MultiProjectDelivery } from "./pages/MultiProjectDelivery";
import { OperationalMetrics } from "./pages/OperationalMetrics";
import { SandboxGithub } from "./pages/SandboxGithub";
import { ReleaseGovernance } from "./pages/ReleaseGovernance";

export function App() {
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<ExecutiveOverview />} />
        <Route path="/projects" element={<Projects />} />
        <Route path="/projects/:projectId" element={<ProjectDetail />} />
        <Route path="/task-graph" element={<TaskGraph />} />
        <Route path="/design-review" element={<DesignReview />} />
        <Route path="/workspace" element={<WorkspaceExecution />} />
        <Route path="/mini-delivery" element={<MiniDeliveryPilot />} />
        <Route path="/delivery-package" element={<DeliveryPackage />} />
        <Route path="/safety" element={<SafetyCenter />} />
        <Route path="/regression" element={<RegressionStatus />} />
        <Route path="/cost-llm" element={<CostLlmGovernance />} />
        <Route path="/incidents" element={<Incidents />} />
        <Route path="/operator" element={<OperatorConsole />} />
        <Route path="/runtime" element={<RuntimeBaseline />} />
        <Route path="/identity" element={<IdentityPosture />} />
        <Route path="/secrets" element={<SecretPosture />} />
        <Route path="/security" element={<SecurityPosture />} />
        <Route path="/delivery" element={<MultiProjectDelivery />} />
        <Route path="/metrics" element={<OperationalMetrics />} />
        <Route path="/sandbox-github" element={<SandboxGithub />} />
        <Route path="/release-governance" element={<ReleaseGovernance />} />
      </Routes>
    </Layout>
  );
}
