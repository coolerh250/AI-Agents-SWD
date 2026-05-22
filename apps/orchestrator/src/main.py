from fastapi import FastAPI

from shared.sdk.http_clients.policy_http_client import PolicyHttpClient
from workflow import run_mock_workflow, workflow_state_schema

app = FastAPI(title="orchestrator")


@app.get("/health")
def health():
    return {"service": "orchestrator", "status": "ok"}


@app.post("/workflow/test")
async def workflow_test(payload: dict):
    return await run_mock_workflow(payload)


@app.post("/workflow/policy-test")
async def workflow_policy_test(action: dict):
    return await PolicyHttpClient().evaluate(action.get("type", ""))


@app.get("/workflow/schema")
def workflow_schema():
    return workflow_state_schema()
