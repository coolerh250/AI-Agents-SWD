from fastapi import FastAPI

from shared.sdk.policy.client import PolicyClient
from workflow import run_mock_workflow, workflow_state_schema

app = FastAPI(title="orchestrator")
_policy = PolicyClient()


@app.get("/health")
def health():
    return {"service": "orchestrator", "status": "ok"}


@app.post("/workflow/test")
async def workflow_test(payload: dict):
    return await run_mock_workflow(payload)


@app.post("/workflow/policy-test")
def workflow_policy_test(action: dict):
    return _policy.evaluate_policy(action)


@app.get("/workflow/schema")
def workflow_schema():
    return workflow_state_schema()
