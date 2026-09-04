"""Step AT-M3.1 -- the reasoning service: request -> durable claim -> provider -> safety -> outcome.

The layer that turns the vendor-neutral provider protocol and the plain store into one call a
discussion loop (AT-M3.3) or a planner (AT-M3.4) can use without knowing which provider answered,
how the result got persisted, or whether this particular call was the first to use its
correlation_id.

Pipeline:

    request -> resolve provider -> ATOMICALLY CLAIM correlation_id (durable 'started' row with an
    ownership lease, BEFORE any provider call) -> [only the claim's owner reaches further] invoke
    verb -> validate artifact type -> content-safety check -> atomically persist terminal outcome
    AND ITS ARTIFACT -> return (artifact, invocation, disposition)

The claim is what stops a provider being invoked by a caller that did not win it. AT-M3.4's
rebaseline added the two things the claim alone could not provide:

**A succeeded call is replayable.** The terminal outcome and the structured artifact are written
by one UPDATE to one row, so a caller arriving later gets the real artifact back instead of
``None``. Before this, an invocation could be durably 'succeeded' while its artifact existed only
in the memory of a process that had since died -- terminal, so never re-invokable, and empty, so
never recoverable. That is the defect this module was rebaselined around.

**A dead owner does not own forever.** Ownership is bounded by a database-clock lease. A caller
that finds an expired lease takes it over and makes a genuine new attempt, rather than being told
'in_progress' by a worker that will never return.

AT-M3.6B.1's remediation added the third thing neither of those covers:

**A transient provider failure is retried, here, immediately.** ``provider_timeout``,
``rate_limited`` and ``provider_unavailable`` were declared retryable and behaved terminally -- the
first one wrote a FAILED row and every later call replayed it. This service now advances the SAME
invocation to its next attempt and calls the provider again, inside the same ``invoke``. It is the
ONLY retry authority: no scheduler, no queue, no daemon, no caller-side loop, and no retry inside
the adapter or its HTTP transport, so N attempts is exactly N provider calls. Lease takeover stays
what it always was -- recovery for a worker nobody has heard from -- and is not asked to stand in
for an answer the provider already gave.

WHAT A CALLER IS PROMISED. Exactly one canonical artifact per correlation_id. NOT exactly one
provider call: a process can die after the wire response and before the commit, so an external
provider may be asked twice for one correlation_id. At-least-once attempts, exactly-once canonical
result -- said plainly, because the alternative is the guarantee that was assumed and was not true.
"""

from __future__ import annotations

import inspect
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, cast

from shared.sdk.agent_reasoning import events as reasoning_events
from shared.sdk.agent_reasoning.models import (
    ARTIFACT_TYPE_FOR_VERB,
    _StrictArtifact,
    PROVIDER_MODE_LIVE,
    RETRYABLE_FAILURE_CATEGORIES,
    CritiqueArtifact,
    DecisionSummaryArtifact,
    ExecutionDisposition,
    PlanDraftArtifact,
    ProposalArtifact,
    ReasoningRequest,
    assert_artifact_within_size,
    sanitize_failure_reason,
)
from shared.sdk.agent_reasoning.provider import (
    AttemptContext,
    LiveProviderError,
    ProviderResult,
    ProviderUsage,
    ReasoningProvider,
    ReasoningProviderError,
    get_reasoning_provider,
)
from shared.sdk.agent_reasoning.store import DEFAULT_MAX_ATTEMPTS, ReasoningInvocationStore

ReasoningArtifact = (
    ProposalArtifact | CritiqueArtifact | DecisionSummaryArtifact | PlanDraftArtifact
)

# Provider modes for which a model identity is meaningful. `mock` and `disabled` never use a real
# model, so model_name is nulled out server-side regardless of what a caller supplied -- a row must
# never read provider_mode='mock' next to a live-model-looking model_name. AT-M3.6B.1 adds `live`
# here explicitly, as this constant was always designed to be extended rather than inferred from.
#
# AND THE MODEL NAME COMES FROM THE PROVIDER, NOT FROM THE REQUEST. `ReasoningRequest.model_name` is
# caller-supplied; honouring it in live mode would let a request choose which model is billed and
# then have that choice recorded as fact on an immutable row. The resolved provider is asked what it
# will actually use, and the request's opinion is kept only as `requested_provider_name`.
_MODES_WITH_REAL_MODEL_IDENTITY: frozenset[str] = frozenset({PROVIDER_MODE_LIVE})


def _unwrap(raw: Any) -> tuple[Any, ProviderUsage | None]:
    """Separate a verb's return value into its artifact and its call metadata.

    An AT-M3.1 provider returns the artifact itself and has nothing to report; a provider that
    actually called somebody returns a ``ProviderResult`` carrying what the call consumed. Accepting
    both is what let the usage channel be added without breaking a single existing provider.
    """
    if isinstance(raw, ProviderResult):
        return raw.artifact, raw.usage
    return raw, None


@dataclass
class _AttemptOutcome:
    """What ONE attempt produced. Not a public type -- the loop's working state, named.

    A tuple would have done the same job and would have made "which of these six is the artifact
    payload" a positional question at every call site. Six positions is where that stops being
    readable.
    """

    status: str = "failed"
    failure_category: str | None = None
    failure_reason: str | None = None
    artifact: Any | None = None
    artifact_payload: dict[str, Any] | None = None
    usage: ProviderUsage | None = None


class ReasoningPersistenceError(RuntimeError):
    """The provider ran and produced a terminal outcome, but that outcome could not be durably
    recorded (e.g. a dropped DB connection during the terminal write).

    A durable 'started' row already exists for this correlation_id -- inserted BEFORE the provider
    was called -- so the attempt is not evidence-less; it is left non-terminal. The artifact is
    deliberately NOT attached to this exception and NOT returned to the caller as a successful
    result: a persistence failure must never look like success.

    Unlike the pre-rebaseline contract, this is now RECOVERABLE rather than final. The row's lease
    will expire, a later caller will take the attempt over, and the provider will be asked again.
    Nothing is stranded by it.
    """

    def __init__(self, *, invocation_id: str, correlation_id: str, cause: Exception) -> None:
        self.invocation_id = invocation_id
        self.correlation_id = correlation_id
        super().__init__(
            f"reasoning invocation {invocation_id} (correlation_id={correlation_id}) ran but its "
            f"terminal outcome could not be persisted: {type(cause).__name__}. A durable "
            "'started' row exists for this correlation_id and its lease is recoverable."
        )


class ReasoningArtifactCorruptError(RuntimeError):
    """A stored artifact exists but no longer parses as the type its verb declares.

    Raised rather than degraded to "no artifact", deliberately. Returning ``None`` here would
    reproduce exactly the state this rebaseline removed -- a succeeded invocation that hands back
    nothing -- while hiding a real schema or data defect behind it. Unreachable through normal
    writes: migration 040 constrains ``artifact_type`` to agree with ``reasoning_verb`` and the
    payload to be a JSON object, and the artifact is validated before it is ever stored.
    """


@dataclass
class ReasoningResult:
    """One call's outcome, plus the execution provenance a caller MUST check before trusting it.

    ``artifact`` is populated whenever the invocation is terminally succeeded AND its durable
    artifact is present -- which, after AT-M3.4's rebaseline, is every succeeded invocation
    written under the current contract, whether this caller produced it (``fresh``) or recovered
    it (``replay``). Two cases still carry no artifact, and both are honest:

    * ``in_progress`` -- somebody else holds a live lease; there is no outcome yet.
    * a LEGACY succeeded row written before migration 040, which recorded metadata only. There is
      genuinely nothing to return, and fabricating something would be worse than saying so.

    ``disposition`` remains the provenance answer -- did THIS call invoke a provider -- and is no
    longer a proxy for "is there an artifact". Callers that need to know whether a provider ran
    (for cost, rate limiting or attempt accounting) read ``disposition``; callers that need the
    result read ``artifact``.
    """

    artifact: ReasoningArtifact | None
    invocation: dict[str, Any]
    disposition: ExecutionDisposition

    @property
    def succeeded(self) -> bool:
        """The underlying invocation's recorded OUTCOME -- NOT whether ``artifact`` is populated.
        A legacy pre-040 replay is ``succeeded=True`` with ``artifact=None``."""
        return self.invocation.get("status") == "succeeded"

    @property
    def attempt(self) -> int:
        """How many attempts this correlation_id has taken, including this one."""
        return int(self.invocation.get("attempt") or 1)


class ReasoningService:
    def __init__(
        self,
        store: Any | None = None,
        audit_client: Any | None = None,
    ) -> None:
        self.store = store if store is not None else ReasoningInvocationStore()
        self.audit_client = audit_client

    async def _audit(
        self, decision_type: str, summary: str, result: str, refs: dict[str, Any]
    ) -> str | None:
        if self.audit_client is None:
            return None
        try:
            event = self.audit_client.build_audit_event(
                agent="reasoning-runtime",
                decision_type=decision_type,
                summary=summary,
                result=result,
                artifact_refs=refs,
            )
            return await self.audit_client.write_audit_event(event)
        except Exception:
            return None

    # --- recovery ---------------------------------------------------------------------------

    @staticmethod
    def rehydrate(row: dict[str, Any]) -> ReasoningArtifact | None:
        """The durable artifact of a terminal row, rebuilt through the model its verb declares.

        Parsed rather than trusted: the payload goes back through the same Pydantic model that
        validated it on the way in, so a caller receives a typed artifact with the same guarantees
        a fresh one has -- closed schema included.
        """
        if row.get("status") != "succeeded":
            return None
        payload = row.get("artifact")
        if not payload:
            return None  # a legacy pre-040 metadata-only success
        artifact_type = ARTIFACT_TYPE_FOR_VERB.get(str(row.get("reasoning_verb")))
        if artifact_type is None:
            raise ReasoningArtifactCorruptError(
                f"invocation {row.get('invocation_id')} records verb "
                f"{row.get('reasoning_verb')!r}, which has no artifact type"
            )
        try:
            return cast(ReasoningArtifact, artifact_type.model_validate(payload))
        except Exception as exc:
            raise ReasoningArtifactCorruptError(
                f"invocation {row.get('invocation_id')} carries an artifact that no longer parses "
                f"as {artifact_type.__name__}: {type(exc).__name__}"
            ) from exc

    def _settled(self, row: dict[str, Any]) -> ReasoningResult:
        """Describe a row this caller does not own."""
        if row.get("status") == "started":
            return ReasoningResult(artifact=None, invocation=row, disposition="in_progress")
        return ReasoningResult(artifact=self.rehydrate(row), invocation=row, disposition="replay")

    async def _replayed(
        self, request: ReasoningRequest, result: ReasoningResult
    ) -> ReasoningResult:
        """Audit a replay and hand it back. A no-op for any other disposition.

        Deliberately NOT ``reasoning_invoked``: a replay invoked nothing, and counting it as a
        success would inflate the number of reasoning calls the system believes it made -- which,
        once a provider bills per call, is the difference between the audit trail and the invoice.
        """
        if result.disposition != "replay":
            return result
        await self._audit(
            reasoning_events.AUDIT_REASONING_REPLAYED,
            f"{request.verb}: replayed the terminal outcome of invocation "
            f"{result.invocation.get('invocation_id')}",
            str(result.invocation.get("status")),
            {
                "verb": request.verb,
                "correlation_id": str(request.correlation_id),
                "invocation_id": str(result.invocation.get("invocation_id")),
                "attempt": result.invocation.get("attempt"),
                "artifact_recovered": result.artifact is not None,
            },
        )
        return result

    @staticmethod
    async def _preflight(
        provider: ReasoningProvider, request: ReasoningRequest
    ) -> LiveProviderError | None:
        """Ask a provider to refuse now, if it can refuse for free. Returns the refusal, if any.

        Optional: only the live adapter implements ``preflight``, and a provider without one is
        simply not asked. Nothing here raises -- the refusal is returned so the caller can record it
        against a claimed attempt instead of throwing a new exception type at services that have
        never had to catch one.
        """
        preflight = getattr(provider, "preflight", None)
        if preflight is None:
            return None
        try:
            outcome = preflight(request)
            if inspect.isawaitable(outcome):
                await outcome
        except LiveProviderError as exc:
            return exc
        except ReasoningProviderError as exc:
            return LiveProviderError(str(exc), failure_category="provider_unauthorized")
        except Exception as exc:
            # Same rule as an unknown provider exception anywhere else: the class name is safe to
            # keep, the message is not.
            return LiveProviderError(
                f"unexpected_provider_preflight_error:{type(exc).__name__}",
                failure_category="provider_unavailable",
            )
        return None

    @staticmethod
    def _bound(provider: ReasoningProvider, invocation_id: Any, attempt: Any) -> ReasoningProvider:
        """Tell a provider WHICH durable attempt it is about to make, if it wants to know.

        Only a provider that spends money needs this, and only so the spend can be reserved against
        an identity that survives a failed ledger write. Optional in exactly the way ``preflight``
        is: a provider without the hook is never asked, and the mock and disabled providers are
        untouched. The hook returns a NEW bound provider rather than mutating the shared instance,
        because one adapter serves concurrent invocations and per-attempt state on it would be a
        race between two discussions.
        """
        bind = getattr(provider, "for_attempt", None)
        if bind is None:
            return provider
        return cast(
            ReasoningProvider,
            bind(AttemptContext(invocation_id=str(invocation_id), attempt=int(attempt or 1))),
        )

    async def _attempt(
        self,
        provider: ReasoningProvider,
        request: ReasoningRequest,
        expected_type: type[_StrictArtifact],
        row: dict[str, Any],
        preflight_error: LiveProviderError | None,
    ) -> _AttemptOutcome:
        """Run ONE attempt against ``provider`` and classify what came back.

        Extracted from ``invoke`` unchanged in behaviour so the retry loop has a body to call more
        than once. Every classification below is exactly the one it was before; what is new is that
        the caller now decides whether the classification means "try again".
        """
        outcome = _AttemptOutcome()

        if preflight_error is not None:
            # Refused before ownership. No provider call happened, so there is nothing to await,
            # nothing to parse and nothing billable -- but the attempt was claimed and is recorded.
            outcome.failure_category = preflight_error.failure_category
            outcome.failure_reason = str(preflight_error)
            outcome.usage = preflight_error.usage
            return outcome

        bound = self._bound(provider, row.get("invocation_id"), row.get("attempt"))
        verb_method = getattr(bound, request.verb, None)
        if verb_method is None:
            outcome.failure_category = "provider_unavailable"
            outcome.failure_reason = f"provider has no {request.verb!r} verb"
            return outcome

        try:
            raw = verb_method(request)
            if inspect.isawaitable(raw):
                # A provider that performs real I/O returns an awaitable. Awaiting it here --
                # rather than letting an adapter block inside a synchronous verb -- is what
                # keeps one slow reasoning call from stalling every other request the process
                # is serving.
                raw = await raw
            raw, outcome.usage = _unwrap(raw)
        except LiveProviderError as exc:
            # The raiser already classified this. Trusting its category rather than re-deriving
            # one from an exception message is the difference between knowing a call timed out
            # and guessing that it did -- and, since AT-M3.6B.1's remediation, the difference
            # between another attempt happening and not.
            outcome.failure_reason = str(exc)
            outcome.failure_category = exc.failure_category
            outcome.usage = exc.usage
        except ReasoningProviderError as exc:
            # Our own controlled exception type -- still routed through the store's
            # sanitize_failure_reason before persistence (defense-in-depth: its message can
            # embed a caller-supplied provider_name).
            outcome.failure_reason = str(exc)
            outcome.failure_category = (
                "provider_disabled"
                if getattr(provider, "name", "") == "disabled"
                else "provider_unauthorized"
            )
        except Exception as exc:  # a misbehaving provider must not crash the caller
            # UNTRUSTED: an unknown exception's message can contain anything a misbehaving or
            # adversarial provider put there, including echoed wire content. Only the
            # exception's CLASS name is safe to persist as-is; the message itself is dropped
            # rather than pattern-matched, because "probably safe after redaction" is not the
            # bar here.
            outcome.failure_reason = f"unexpected_provider_error:{type(exc).__name__}"
            outcome.failure_category = "provider_unavailable"
        else:
            if not isinstance(raw, expected_type):
                outcome.failure_category = "malformed_output"
                outcome.failure_reason = (
                    f"expected {expected_type.__name__}, got {type(raw).__name__}"
                )
            else:
                try:
                    # The same screen a TeamMessage passes -- and now also the exact payload
                    # that gets stored, so nothing can be persisted that was not screened.
                    outcome.artifact_payload = raw.as_safe_dict()
                    # AT-M3.6B.1: and the same payload is measured. A live adapter checks this
                    # too, but the check belongs on the write path as well: this is the only
                    # place every artifact passes through, whoever produced it.
                    assert_artifact_within_size(outcome.artifact_payload)
                except ValueError as exc:
                    outcome.artifact_payload = None
                    outcome.failure_category = (
                        "malformed_output" if "exceeds" in str(exc) else "content_safety_rejected"
                    )
                    outcome.failure_reason = str(exc)
                else:
                    outcome.artifact = raw
                    outcome.status = "succeeded"
        return outcome

    async def _recover(self, row: dict[str, Any]) -> dict[str, Any] | ReasoningResult:
        """Resolve a correlation_id this caller did not claim.

        Returns a row when this caller successfully TOOK OVER an expired attempt and may now
        invoke the provider; returns a finished :class:`ReasoningResult` otherwise.
        """
        if row.get("status") != "started":
            return self._settled(row)

        taken = await self.store.try_take_over_invocation(row["correlation_id"])
        if taken is not None:
            await self._audit(
                reasoning_events.AUDIT_REASONING_ATTEMPT_SUPERSEDED,
                f"attempt {row.get('attempt')} lease expired; attempt {taken.get('attempt')} "
                f"took over invocation {taken.get('invocation_id')}",
                "superseded",
                {
                    "correlation_id": str(row.get("correlation_id")),
                    "invocation_id": str(row.get("invocation_id")),
                    "superseded_attempt": row.get("attempt"),
                    "attempt": taken.get("attempt"),
                },
            )
            return taken

        # Takeover did not happen. Three different reasons, distinguished from the row itself
        # rather than from a local clock -- ownership is the database's answer, not ours.
        current = await self.store.get_by_correlation_id(str(row["correlation_id"])) or row
        if current.get("status") != "started":
            return self._settled(current)

        max_attempts = getattr(self.store, "max_attempts", DEFAULT_MAX_ATTEMPTS)
        if int(current.get("attempt") or 1) >= max_attempts:
            # The budget is spent and the lease is expired: every owner this attempt ever had is
            # gone. Terminalize it as a truthful failure instead of leaving it 'started' forever,
            # which is the state migration 040 exists to make unreachable. fail_exhausted_invocation
            # re-checks lease expiry in SQL, so a row that was re-leased in the meantime is
            # untouched and simply reports back as in_progress.
            exhausted = await self.store.fail_exhausted_invocation(
                current["invocation_id"],
                terminal={
                    "failure_category": "provider_unavailable",
                    "failure_reason": (
                        f"attempt budget exhausted after {current.get('attempt')} attempt(s); "
                        "every owner's lease expired without a terminal outcome"
                    ),
                    "completed_at": datetime.now(timezone.utc),
                },
            )
            return self._settled(exhausted or current)

        # Somebody else took it over first, or the lease is still live. Either way this caller
        # invokes nothing.
        return ReasoningResult(artifact=None, invocation=current, disposition="in_progress")

    # --- the call ------------------------------------------------------------------------------

    async def invoke(
        self,
        request: ReasoningRequest,
        provider: ReasoningProvider | None = None,
    ) -> ReasoningResult:
        """Run one reasoning call under an atomically-claimed, lease-bounded durable invocation.

        Raises :class:`ReasoningPersistenceError` if the provider produced a terminal outcome that
        could not be durably recorded. Unlike before the rebaseline, that is recoverable: the
        row's lease expires and a later caller re-attempts it.
        """
        expected_type = ARTIFACT_TYPE_FOR_VERB[request.verb]

        # REPLAY FIRST, before a provider is even resolved.
        #
        # A terminal correlation_id already has its answer, and returning it must not depend on the
        # runtime's CURRENT posture. Resolving the provider first -- as this method used to -- was
        # harmless while every provider was in-process, but under AT-M3.6B.1 it would make the
        # replay of a historical artifact depend on live configuration being valid, the network gate
        # being open and a credential being resolvable. Work that was already done and already paid
        # for must stay recoverable when the live path is switched off, which in this slice it always
        # is. The claim below remains the atomic authority; this read only short-circuits a question
        # that is already settled.
        existing = await self.store.get_by_correlation_id(str(request.correlation_id))
        if existing is not None and existing.get("status") != "started":
            return await self._replayed(request, self._settled(existing))

        resolved_provider = (
            provider if provider is not None else get_reasoning_provider(request.provider_name)
        )
        model_name = (
            getattr(resolved_provider, "model_name", None)
            if resolved_provider.mode in _MODES_WITH_REAL_MODEL_IDENTITY
            else None
        )

        # PRE-FLIGHT, before the attempt is claimed.
        #
        # A provider that can refuse for free says so here: the network gate is closed, the model is
        # not allowlisted, the outbound context is oversized or carries an unapproved field, no
        # budget policy is active. Reaching those answers before ownership means a refusal costs no
        # provider call, no credential read and no spend. The refusal is still RECORDED -- it is
        # carried down to the terminal write below rather than raised -- because a claimed-and-
        # refused attempt is evidence, and because that is exactly the shape the `disabled` provider
        # has always had. Raising instead would hand callers a new exception path for what is, to
        # them, an ordinary terminal failure with no artifact.
        preflight_error = await self._preflight(resolved_provider, request)

        started_at = datetime.now(timezone.utc)
        clock_start = time.monotonic()

        owned, row = await self.store.try_begin_invocation(
            {
                "project_id": request.project_id,
                "thread_id": request.thread_id,
                "requested_by_principal_id": request.requested_by_principal_id,
                "reasoning_verb": request.verb,
                "requested_provider_name": request.provider_name or resolved_provider.name,
                "provider_mode": resolved_provider.mode,
                "model_name": model_name,
                "round_number": request.round_number,
                "correlation_id": request.correlation_id,
                "started_at": started_at,
            }
        )

        if not owned:
            recovered = await self._recover(row)
            if isinstance(recovered, ReasoningResult):
                return await self._replayed(request, recovered)
            # A takeover: this caller now owns a genuine new attempt of the same invocation.
            row = recovered
            clock_start = time.monotonic()

        invocation_id = row["invocation_id"]
        attempt_token = row["attempt_token"]
        max_attempts = int(getattr(self.store, "max_attempts", DEFAULT_MAX_ATTEMPTS))

        # THE RETRY LOOP -- the one authoritative retry layer in this architecture.
        #
        # AT-M3.6B.1 Independent Validation 1 found that `provider_timeout`, `rate_limited` and
        # `provider_unavailable` were declared retryable and behaved terminally: the first transient
        # failure wrote a FAILED row, and the next call for that correlation_id replayed it. The
        # takeover path could not stand in for this, and should not: takeover recovers a worker that
        # has gone SILENT, and a provider that answered "429" has not gone silent. Waiting out a
        # 120s lease for an answer already in hand would also make every transient blip cost two
        # minutes of a discussion's wall clock.
        #
        # So a KNOWN transient outcome advances the attempt here and immediately -- same invocation,
        # same row, same correlation_id, new attempt number, new attempt_token, new database-clock
        # lease -- and the loop runs the next attempt. Crash recovery is unchanged and still belongs
        # to the lease. Nothing polls, nothing is scheduled, no daemon exists, and no caller is
        # asked to retry: the call that owns the attempt is the call that makes the next one.
        outcome = _AttemptOutcome()
        while True:
            await self._audit(
                reasoning_events.AUDIT_REASONING_ATTEMPT_STARTED,
                f"{request.verb} via {resolved_provider.name} ({resolved_provider.mode}): attempt "
                f"{row.get('attempt')} claimed",
                "started",
                {
                    "verb": request.verb,
                    "provider_name": resolved_provider.name,
                    "provider_mode": resolved_provider.mode,
                    "correlation_id": str(request.correlation_id),
                    "invocation_id": str(invocation_id),
                    "attempt": row.get("attempt"),
                },
            )

            outcome = await self._attempt(
                resolved_provider, request, expected_type, row, preflight_error
            )

            if outcome.status == "succeeded":
                break
            if preflight_error is not None:
                # A pre-flight refusal is a determination about CONFIGURATION, AUTHORIZATION or
                # BUDGET, reached without asking anybody. Re-running it would produce the same
                # answer, so it is terminal whatever its category happens to be.
                break
            if outcome.failure_category not in RETRYABLE_FAILURE_CATEGORIES:
                break
            if int(row.get("attempt") or 1) >= max_attempts:
                # Budget spent. The recorded failure is the FINAL attempt's own outcome, which is
                # the truthful account of why this invocation ended.
                break

            advanced = await self.store.advance_retryable_attempt(
                invocation_id,
                attempt_token=attempt_token,
                failure_category=str(outcome.failure_category),
            )
            if advanced is None:
                # This attempt no longer owns the invocation -- its lease expired and somebody took
                # it over while the provider was answering. Fall through to the terminal write,
                # which detects the zombie on the token guard and returns the canonical row.
                break

            await self._audit(
                reasoning_events.AUDIT_REASONING_ATTEMPT_RETRIED,
                f"{request.verb}: attempt {row.get('attempt')} failed with "
                f"{outcome.failure_category}; advancing invocation {invocation_id} to attempt "
                f"{advanced.get('attempt')}",
                "retried",
                {
                    "verb": request.verb,
                    "provider_name": resolved_provider.name,
                    "provider_mode": resolved_provider.mode,
                    "correlation_id": str(request.correlation_id),
                    "invocation_id": str(invocation_id),
                    "attempt": row.get("attempt"),
                    "next_attempt": advanced.get("attempt"),
                    "failure_category": outcome.failure_category,
                    "failure_reason": sanitize_failure_reason(outcome.failure_reason),
                    "model_name": model_name,
                    # A failed transient attempt is still billable-shaped. Its tokens and its
                    # reservation are named here so the attempt that is about to be discarded is
                    # not the only place they were ever written down.
                    "input_tokens": outcome.usage.input_tokens if outcome.usage else None,
                    "output_tokens": outcome.usage.output_tokens if outcome.usage else None,
                    "estimated_cost_usd": (
                        outcome.usage.estimated_cost_usd if outcome.usage else None
                    ),
                    "budget_reservation_key": (
                        outcome.usage.reservation_key if outcome.usage else None
                    ),
                    "provider_call_occurred": (
                        bool(outcome.usage.call_occurred) if outcome.usage else False
                    ),
                },
            )

            row = advanced
            attempt_token = row["attempt_token"]
            # Reset, so latency_ms describes the attempt that actually produced the recorded
            # outcome rather than the sum of every attempt that led to it.
            clock_start = time.monotonic()

        status = outcome.status
        failure_category = outcome.failure_category
        failure_reason = outcome.failure_reason
        artifact = outcome.artifact
        artifact_payload = outcome.artifact_payload
        usage = outcome.usage

        latency_ms = int((time.monotonic() - clock_start) * 1000)
        completed_at = datetime.now(timezone.utc)

        audit_ref = await self._audit(
            reasoning_events.AUDIT_REASONING_INVOKED,
            f"{request.verb} via {resolved_provider.name} ({resolved_provider.mode}): {status}",
            status,
            {
                "verb": request.verb,
                "provider_name": resolved_provider.name,
                "provider_mode": resolved_provider.mode,
                "project_id": request.project_id,
                "thread_id": request.thread_id,
                "round_number": request.round_number,
                "failure_category": failure_category,
                "correlation_id": request.correlation_id,
                "invocation_id": str(invocation_id),
                "attempt": row.get("attempt"),
                "artifact_type": expected_type.__name__ if status == "succeeded" else None,
                # AT-M3.6B.1 safe live metadata. Counts, money and an opaque provider identifier --
                # never a prompt, a completion, an artifact body or a credential.
                "model_name": model_name,
                "input_tokens": usage.input_tokens if usage else None,
                "output_tokens": usage.output_tokens if usage else None,
                "estimated_cost_usd": usage.estimated_cost_usd if usage else None,
                "provider_request_id": usage.provider_request_id if usage else None,
                "provider_call_occurred": bool(usage.call_occurred) if usage else False,
                # AT-M3.6B.1 remediation. The reservation is what makes a paid call countable even
                # when its settlement failed, so the trail names it -- and says plainly when the
                # ledger is still holding the conservative estimate rather than the actual charge.
                # `estimated_cost_usd` above remains the pre-flight ESTIMATE that gated the spend;
                # this does not claim actual-cost precision the ledger does not yet have.
                "budget_reservation_key": usage.reservation_key if usage else None,
                "budget_reserved_cost_usd": usage.reserved_cost_usd if usage else None,
                "usage_settlement_pending": (
                    bool(usage.call_occurred and not usage.settled) if usage else False
                ),
            },
        )

        try:
            completed = await self.store.complete_invocation(
                invocation_id,
                attempt_token=attempt_token,
                terminal={
                    "status": status,
                    "failure_category": failure_category,
                    "failure_reason": failure_reason,
                    "latency_ms": latency_ms,
                    "audit_ref": audit_ref,
                    "completed_at": completed_at,
                    "artifact_type": expected_type.__name__ if status == "succeeded" else None,
                    "artifact": artifact_payload if status == "succeeded" else None,
                    # Written on BOTH outcomes. A call that reached the provider consumed tokens
                    # whether or not its output turned out to be usable, and a failed row that
                    # dropped them would make the audit trail cheaper than the invoice.
                    # `estimated_cost_usd` keeps the meaning 037 gave it -- the pre-flight ESTIMATE
                    # that gated the spend. The ACTUAL cost lives in the llm_budget usage ledger,
                    # which is where this project already records actuals.
                    "input_tokens": usage.input_tokens if usage else None,
                    "output_tokens": usage.output_tokens if usage else None,
                    "estimated_cost_usd": usage.estimated_cost_usd if usage else None,
                },
            )
        except Exception as exc:
            # The provider already ran; the durable 'started' row (inserted before the provider
            # was called) already exists. Only the terminal write failed -- never substitute the
            # artifact as an authoritative success, and never silently retry here. The lease is
            # what makes this recoverable rather than terminal.
            raise ReasoningPersistenceError(
                invocation_id=str(invocation_id),
                correlation_id=str(request.correlation_id),
                cause=exc,
            ) from exc

        if completed is None:
            # The row this call itself just inserted cannot legitimately vanish; treat it the
            # same as any other terminal-persistence anomaly rather than fabricate a result.
            raise ReasoningPersistenceError(
                invocation_id=str(invocation_id),
                correlation_id=str(request.correlation_id),
                cause=RuntimeError("complete_invocation returned no row for a known invocation_id"),
            )

        if str(completed.get("attempt_token")) != str(attempt_token):
            # ZOMBIE. This attempt's lease expired while the provider was running, another worker
            # took the invocation over, and the token guard refused this write. This attempt's
            # result is discarded -- not because it is wrong, but because exactly one artifact can
            # be canonical and this one did not win. The canonical row is returned instead, so the
            # caller still gets the real answer rather than an error.
            await self._audit(
                reasoning_events.AUDIT_REASONING_ATTEMPT_SUPERSEDED,
                f"{request.verb}: this attempt's result was discarded; invocation "
                f"{invocation_id} is owned by a later attempt",
                "superseded",
                {
                    "verb": request.verb,
                    "correlation_id": str(request.correlation_id),
                    "invocation_id": str(invocation_id),
                    "attempt": row.get("attempt"),
                    "current_attempt": completed.get("attempt"),
                },
            )
            return self._settled(completed)

        return ReasoningResult(artifact=artifact, invocation=completed, disposition="fresh")


__all__ = [
    "ReasoningArtifact",
    "ReasoningArtifactCorruptError",
    "ReasoningPersistenceError",
    "ReasoningResult",
    "ReasoningService",
]
