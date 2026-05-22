import json
import os

import asyncpg

from shared.sdk.base_agent.stream_agent import StreamAgent

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://postgres@localhost:5432/aiagents")


class DevOpsAgent(StreamAgent):
    """Consumes test reports from stream.deployments and produces a mock
    deployment record. It writes a dev/test deployment row to deployment_records,
    records an agent execution, an audit event, and a notification.

    Mock-safe: it never deploys to production and makes no Kubernetes / cloud /
    GitHub calls. It is the final stage of the pipeline (no output stream).
    """

    name = "devops-agent"
    input_stream = "stream.deployments"
    output_stream = ""
    group = "devops-agent-group"
    consumer = "devops-agent-1"

    def build_deployment_record(self, payload: dict) -> dict:
        """Produce a mock dev/test deployment record (no production deploy)."""
        task_id = str(payload.get("task_id", "unknown"))
        return {
            "artifact_type": "deployment_record",
            "task_id": task_id,
            "environment": "test",
            "status": "simulated",
            "production_executed": False,
            "produced_by": self.name,
            "mock": True,
        }

    async def _persist_deployment_record(self, record: dict) -> None:
        """Best-effort write of a mock deployment record to deployment_records."""
        try:
            conn = await asyncpg.connect(dsn=DATABASE_URL, timeout=5)
        except Exception:
            return
        try:
            await conn.execute(
                "INSERT INTO deployment_records (task_id, environment, status, metadata) "
                "VALUES ($1, $2, $3, $4::jsonb)",
                record["task_id"],
                record["environment"],
                record["status"],
                json.dumps(record),
            )
        except Exception:
            pass
        finally:
            await conn.close()

    async def handle(self, payload: dict) -> dict:
        record = self.build_deployment_record(payload)
        task_id = record["task_id"]
        await self._persist_deployment_record(record)
        return {
            "task_id": task_id,
            "decision_type": "deployment",
            "summary": f"devops-agent simulated a test deployment for {task_id}",
            "result": "deployment.simulated",
            "artifact_refs": {"environment": "test", "production_executed": False},
            "event_type": "devops.deployment_simulated",
            "message": f"devops-agent simulated a test deployment for {task_id}",
            "execution_metadata": record,
        }
