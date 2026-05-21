from abc import ABC, abstractmethod

from shared.sdk.audit.client import AuditClient
from shared.sdk.policy.client import PolicyClient


class BaseAgent(ABC):
    """Abstract base class for all platform agents.

    Concrete agents implement receive_task / analyze / execute. The base class
    provides approval, audit, and reporting helpers. It performs no LLM calls,
    no production operations, and reads or writes no secrets.
    """

    name: str = "base-agent"
    allowed_tools: list[str] = []

    def __init__(
        self,
        name: str | None = None,
        allowed_tools: list[str] | None = None,
        policy_client: PolicyClient | None = None,
        audit_client: AuditClient | None = None,
    ) -> None:
        if name is not None:
            self.name = name
        if allowed_tools is not None:
            self.allowed_tools = list(allowed_tools)
        self.policy_client = policy_client or PolicyClient()
        self.audit_client = audit_client or AuditClient()
        self.last_report: dict | None = None

    @abstractmethod
    async def receive_task(self, task: dict) -> dict: ...

    @abstractmethod
    async def analyze(self, context: dict) -> dict: ...

    @abstractmethod
    async def execute(self, plan: dict) -> dict: ...

    async def request_approval(self, action: dict) -> dict:
        decision = self.policy_client.evaluate_policy(action)
        return {
            "agent": self.name,
            "action": action,
            "allowed": decision["allowed"],
            "approval_required": decision["approval_required"],
        }

    async def write_audit(self, event: dict) -> None:
        audit_event = self.audit_client.build_audit_event(
            agent=self.name,
            decision_type=event.get("decision_type", "unspecified"),
            summary=event.get("summary", ""),
            result=event.get("result", ""),
            task_id=event.get("task_id"),
            artifact_refs=event.get("artifact_refs", {}),
        )
        await self.audit_client.write_audit_event(audit_event)

    async def report(self, result: dict) -> None:
        self.last_report = result
