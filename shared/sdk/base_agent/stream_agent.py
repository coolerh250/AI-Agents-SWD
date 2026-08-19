import asyncio
import time
from abc import abstractmethod

from shared.sdk.agent_execution.store import AgentExecutionStore
from shared.sdk.agent_team.context import team_context_of, with_team_context
from shared.sdk.agent_team.events import STREAM_TEAM_BLOCKED
from shared.sdk.agent_team.service import TeamService
from shared.sdk.audit.client import AuditClient
from shared.sdk.base_agent.base import BaseAgent
from shared.sdk.event_bus.redis_streams import (
    RedisStreamEventBus,
    is_retry_exhausted,
    with_incremented_retry,
)
from shared.sdk.notifications.client import send_notification
from shared.sdk.observability.correlation import correlation_payload
from shared.sdk.observability.metrics import (
    AGENT_EXECUTION_FAILURES_TOTAL,
    AGENT_EXECUTION_TOTAL,
    AGENT_LATENCY_SECONDS,
)
from shared.sdk.observability.tracing import start_span


class StreamAgent(BaseAgent):
    """A BaseAgent that consumes one Redis stream and transforms each message.

    For every message it records an agent_executions row (started -> completed
    or failed), writes an audit event, and publishes a notification. Concrete
    agents implement handle(); they make no LLM / GitHub / Slack / Kubernetes /
    cloud calls and execute no production actions.
    """

    input_stream: str = ""
    output_stream: str = ""
    group: str = ""
    consumer: str = ""

    # AT-M2-TEAM-CORE. What this agent can take, and what the NEXT worker must be able to do.
    # The agent states the NEED; the router decides who fills it. ``output_stream`` above is
    # transport for the legacy task pipeline and is no longer the routing authority on the
    # autonomous path.
    declared_capabilities: tuple[str, ...] = ()
    successor_capability: str = ""
    # Class-level so the routing seam is safe on an instance built without __init__.
    team_service: object | None = None
    _team_context: dict | None = None
    last_routing_decision = None

    def __init__(
        self,
        event_bus: RedisStreamEventBus | None = None,
        team_service: object | None = None,
    ) -> None:
        bus = event_bus or RedisStreamEventBus()
        super().__init__(audit_client=AuditClient(event_bus=bus))
        self.bus = bus
        self.execution_store = AgentExecutionStore()
        self.processed_count = 0
        self.failed_count = 0
        self.dead_letter_count = 0
        self.last_task_id: str | None = None
        self.running = False
        # Deployed agents are constructed with no arguments, so the router has to be the default
        # rather than something a caller opts into -- otherwise the autonomous path would exist
        # only in tests. Constructing it opens no connection; like every other store here it
        # resolves DATABASE_URL lazily and degrades if the database is unreachable.
        self.team_service = (
            team_service
            if team_service is not None
            else TeamService(event_bus=bus, audit_client=self.audit_client)
        )
        self._team_context: dict | None = None
        self.last_routing_decision = None

    @staticmethod
    def correlation_ids(payload: dict) -> dict:
        """Build the {task_id, workflow_id, trace_id, span_id} block carried by
        every pipeline message.

        The trace_id is propagated from the inbound payload (so the whole
        workflow shares one trace) and a fresh span_id is generated for the
        outbound stage. Receivers see the same trace_id and a new span_id per
        hop.
        """
        return correlation_payload(payload, inject_new_span=True)

    # BaseAgent abstract methods — stream agents transform inside handle().
    async def receive_task(self, task: dict) -> dict:
        return dict(task)

    async def analyze(self, context: dict) -> dict:
        return dict(context)

    async def execute(self, plan: dict) -> dict:
        return dict(plan)

    @abstractmethod
    async def handle(self, payload: dict) -> dict:
        """Transform one message and (optionally) publish to the output stream.

        Returns a descriptor dict with: task_id, decision_type, summary, result,
        artifact_refs, event_type, message, and optional execution_metadata.
        """

    async def resolve_publish_target(
        self,
        message: dict,
        capability: str = "",
        default_stream: str | None = None,
    ) -> tuple[str, dict | None]:
        """Where this message goes next, and the routing evidence for that choice.

        On the AUTONOMOUS path -- a message carrying a team context, with a router available and
        a stated capability need -- the router decides, from the team's declared capabilities as
        they are right now. On the legacy task pipeline the compile-time stream is still the
        transport.

        When the router finds nobody eligible the message goes to the team blocked stream. It is
        deliberately NOT sent to the compile-time stream instead: silently falling back would
        restore exactly the behaviour this milestone removes, and would do it precisely when the
        team is least able to handle the work.
        """
        fallback = self.output_stream if default_stream is None else default_stream
        wanted = capability or self.successor_capability
        context = self._team_context
        if context is None or self.team_service is None or not wanted:
            return fallback, None
        decision, _record = await self.team_service.decide_route(
            project_id=context["project_id"],
            capability=wanted,
            workflow_stage=str(message.get("stage") or context.get("workflow_stage") or ""),
            work_item_id=context.get("work_item_id"),
            task_id=str(message.get("task_id") or "") or None,
            workflow_id=str(message.get("workflow_id") or "") or None,
        )
        self.last_routing_decision = decision
        if decision.selected and decision.selected_stream:
            return decision.selected_stream, decision.as_record()
        return STREAM_TEAM_BLOCKED, decision.as_record()

    async def _publish_resolved(
        self, message: dict, capability: str = "", default_stream: str | None = None
    ) -> str:
        stream, routing = await self.resolve_publish_target(
            message, capability=capability, default_stream=default_stream
        )
        if routing is not None:
            message = {**with_team_context(message, self._team_context), "routing": routing}
        with start_span(
            "agent.publish_next",
            **{
                "service.name": self.name,
                "agent": self.name,
                "stream": stream,
                "task_id": str(message.get("task_id", "")),
                "workflow_id": str(message.get("workflow_id", "")),
                "event_type": str(message.get("event", "")),
            },
        ):
            return await self.bus.publish_event(stream, message)

    async def publish_next(self, message: dict) -> str:
        """Publish ``message`` to its resolved target inside an ``agent.publish_next`` span.

        Concrete handle() implementations use this instead of calling ``bus.publish_event``
        directly so the per-agent custom span is always emitted.
        """
        return await self._publish_resolved(message)

    async def publish_for_capability(
        self, message: dict, capability: str, default_stream: str | None = None
    ) -> str:
        """Send work that needs a SPECIFIC capability, which may not be this agent's successor.

        The QA repair loop uses this: QA's normal successor handles deployment planning, but a
        blocking auto-fixable finding needs whoever can fix defects, and on a team that may not
        be the agent that wrote the code.
        """
        return await self._publish_resolved(
            message, capability=capability, default_stream=default_stream
        )

    async def process(self, payload: dict) -> dict:
        # The inbound team context, if any, decides whether this hop is on the autonomous path
        # and is carried forward onto whatever handle() publishes.
        self._team_context = team_context_of(payload)
        self.last_routing_decision = None
        task_id = str(payload.get("task_id", "unknown"))
        workflow_id = str(payload.get("workflow_id", ""))
        parent_trace_id = str(payload.get("trace_id", ""))
        parent_span_id = str(payload.get("span_id", ""))
        span_attrs = {
            "service.name": self.name,
            "agent": self.name,
            "task_id": task_id,
            "workflow_id": workflow_id,
            "stream": self.input_stream,
            "event_type": str(payload.get("event", "")),
        }
        # agent.receive adopts the upstream trace context so every span this
        # process() emits shares one trace_id with the orchestrator and the
        # upstream agents.
        with start_span(
            "agent.receive",
            parent_trace_id=parent_trace_id,
            parent_span_id=parent_span_id,
            **span_attrs,
        ):
            execution_id = await self._start_execution(task_id)
            started = time.perf_counter()
            try:
                with start_span("agent.execute", **span_attrs):
                    with start_span("agent.analyze", **span_attrs):
                        pass
                    result = await self.handle(payload)
            except Exception as exc:
                self.failed_count += 1
                AGENT_EXECUTION_TOTAL.labels(agent=self.name, status="failed").inc()
                AGENT_EXECUTION_FAILURES_TOTAL.labels(agent=self.name).inc()
                AGENT_LATENCY_SECONDS.labels(agent=self.name).observe(time.perf_counter() - started)
                await self._fail_execution(execution_id, str(exc))
                raise
            self.processed_count += 1
            self.last_task_id = task_id
            AGENT_EXECUTION_TOTAL.labels(agent=self.name, status="completed").inc()
            AGENT_LATENCY_SECONDS.labels(agent=self.name).observe(time.perf_counter() - started)
            await self._complete_execution(execution_id, result)
            with start_span("agent.write_audit", **span_attrs):
                await self.write_audit(
                    {
                        "decision_type": result.get("decision_type", self.name),
                        "summary": result.get("summary", ""),
                        "result": result.get("result", ""),
                        "task_id": task_id,
                        "artifact_refs": result.get("artifact_refs", {}),
                    }
                )
            with start_span("agent.publish_notification", **span_attrs):
                await send_notification(
                    task_id,
                    result.get("event_type", f"{self.name}.completed"),
                    result.get("message", result.get("summary", "")),
                )
            return result

    async def run_consumer(self, stop_event: asyncio.Event) -> None:
        """Consume the input stream until stop_event is set (Redis consumer group)."""
        self.running = True
        try:
            while not stop_event.is_set():
                try:
                    events = await self.bus.consume_events(
                        self.input_stream, self.group, self.consumer, count=10, block_ms=2000
                    )
                    for event in events:
                        payload = event["event"]
                        try:
                            await self.process(payload)
                        except Exception as exc:
                            await self._handle_failure(payload, exc)
                        await self.bus.ack_event(self.input_stream, self.group, event["id"])
                except asyncio.CancelledError:
                    break
                except Exception:
                    await asyncio.sleep(1)
        finally:
            self.running = False

    async def _handle_failure(self, payload: dict, exc: Exception) -> None:
        """Retry a failed message; dead-letter it once its retries are exhausted.

        This is the retry / dead-letter foundation — there is no separate retry
        scheduler. A failed message is re-published to the input stream with an
        incremented retry_count; once retry_count reaches max_retries it goes to
        stream.deadletter instead.
        """
        attempted = with_incremented_retry(payload)
        try:
            if is_retry_exhausted(attempted):
                await self.bus.publish_dead_letter(
                    self.input_stream,
                    attempted,
                    failure_reason=str(exc),
                    retry_after_seconds=1.0,
                )
                self.dead_letter_count += 1
            else:
                await self.bus.publish_event(self.input_stream, attempted)
        except Exception:
            pass  # a transient Redis error must not stop the consumer loop

    def status(self) -> dict:
        return {
            "agent": self.name,
            "running": self.running,
            "input_stream": self.input_stream,
            "output_stream": self.output_stream,
            "declared_capabilities": list(self.declared_capabilities),
            "successor_capability": self.successor_capability,
            "group": self.group,
            "processed_count": self.processed_count,
            "failed_count": self.failed_count,
            "dead_letter_count": self.dead_letter_count,
            "last_task_id": self.last_task_id,
        }

    async def close(self) -> None:
        await self.bus.close()

    async def _start_execution(self, task_id: str) -> str | None:
        try:
            execution = await self.execution_store.create_execution(task_id, self.name)
            return str(execution["execution_id"])
        except Exception:
            return None

    async def _complete_execution(self, execution_id: str | None, result: dict) -> None:
        if execution_id is None:
            return
        metadata = result.get("execution_metadata") or {"summary": result.get("summary", "")}
        try:
            await self.execution_store.complete_execution(execution_id, metadata=metadata)
        except Exception:
            pass

    async def _fail_execution(self, execution_id: str | None, error: str) -> None:
        if execution_id is None:
            return
        try:
            await self.execution_store.fail_execution(execution_id, error)
        except Exception:
            pass
