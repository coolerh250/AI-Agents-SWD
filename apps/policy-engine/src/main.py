from fastapi import FastAPI
from pydantic import BaseModel

from shared.sdk.policy.client import RESTRICTED_ACTIONS

app = FastAPI(title="policy-engine")


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
