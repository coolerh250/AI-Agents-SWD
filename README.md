# AI Agents SWD Platform

## Project Name

AI Agents SWD Platform

## Purpose

A monorepo for an AI-agent-driven software-development platform. It hosts the
orchestration services, the individual AI agents, shared libraries, and the
infrastructure definitions used to build, test, and govern the platform.

## Repository Structure

```
apps/                      Core platform services
  orchestrator/              Coordinates agents and workflows
  communication-gateway/     Internal/external communication entry point
  approval-engine/           Human-in-the-loop approval handling
  policy-engine/             Policy evaluation and enforcement
  audit-service/             Audit logging and traceability
agents/                    Individual AI agents
  intake-agent/              Intake and triage of incoming requests
  requirement-agent/         Requirement analysis
  frontend-agent/            Frontend implementation
  backend-agent/             Backend implementation
  qa-agent/                  Testing and quality assurance
  devops-agent/              Build, deployment, and operations
shared/                    Shared libraries and assets
  sdk/                       Common SDK
  models/                    Shared data models
  prompts/                   Prompt templates
  utils/                     Utility helpers
  observability/             Logging, metrics, and tracing helpers
  governance/                Governance and compliance helpers
infra/                     Infrastructure definitions
  docker-compose/            Local/test Docker Compose definitions
  kubernetes/                Kubernetes manifests
  helm/                      Helm charts
  argocd/                    Argo CD application definitions
  vault/                     Vault configuration (no secret values committed)
migrations/                Database migrations
scripts/                   Operational and helper scripts
tests/                     Cross-cutting / integration tests
source/                    Project progress log and source notes
```

## Local / Test Deployment Principle

- All build, test, and deployment activity runs **only on the test server `10.0.1.31`**.
- The test server pulls the latest code from GitHub (`git clone` / `git pull`)
  before any deployment.
- No automated deployment to Production is performed.

## Test Server

- Host: `10.0.1.31`
- Access: SSH with key-based authentication.

## Production Restriction

**No production deployment is performed without explicit human approval.**
Automation must not create, modify, or deploy production resources.

## Secrets

**No secrets are stored in this repository.** API keys, tokens, passwords, and
other credentials must be supplied via environment variables or a secrets
manager — never committed. See `.gitignore`.
