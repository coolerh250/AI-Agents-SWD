from fastapi import FastAPI
from pydantic import BaseModel

from shared.sdk.observability.metrics import install_metrics_endpoint
from shared.sdk.observability.tracing import setup_tracing
from shared.sdk.policy.client import RESTRICTED_ACTIONS

setup_tracing("policy-engine")
app = FastAPI(title="policy-engine")
install_metrics_endpoint(app)


class PolicyEvaluateRequest(BaseModel):
    action: str


@app.get("/health")
def health() -> dict:
    return {"service": "policy-engine", "status": "ok"}


@app.post("/policy/evaluate")
def evaluate(payload: PolicyEvaluateRequest) -> dict:
    restricted = payload.action in RESTRICTED_ACTIONS
    return {
        "allowed": not restricted,
        "approval_required": restricted,
        "risk_level": "high" if restricted else "low",
        "reason": "restricted action" if restricted else "no policy restriction",
    }
