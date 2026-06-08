"""Stage 34 -- no recursive audit / notification loop.

The audit-worker's integrity write hooks into the audit row insert, so
a key invariant is: the integrity write path itself does NOT call
``publish_audit_event`` or ``publish_notification``. Otherwise a single
audit row would trigger an audit-integrity audit row, which would
trigger another, etc.

We assert this by reading the source files and checking that:

* ``shared/sdk/audit_integrity/*`` never imports ``publish_audit_event``
  or ``publish_notification`` (no fanout from the integrity SDK).
* The audit-worker handler creates the integrity record AFTER the audit
  row insert and does NOT publish a notification event in the integrity
  branch.

Pair this with the runtime smoke ``AUDIT_INTEGRITY_NO_LOOP_SMOKE`` which
asserts the integrity-record count does not change across a verify-chain
call.
"""

from __future__ import annotations

from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]


def _read(path: str) -> str:
    return (_REPO_ROOT / path).read_text(encoding="utf-8")


def test_integrity_sdk_does_not_import_audit_publisher():
    for name in ("canonical.py", "hasher.py", "signer.py", "store.py", "verifier.py"):
        text = _read(f"shared/sdk/audit_integrity/{name}")
        assert (
            "publish_audit_event" not in text
        ), f"integrity SDK file {name} must not call publish_audit_event"
        assert (
            "publish_notification" not in text
        ), f"integrity SDK file {name} must not call publish_notification"


def test_audit_worker_does_not_publish_in_integrity_branch():
    text = _read("apps/audit-worker/src/worker.py")
    # The integrity span sits between the audit insert and the function
    # return. We assert there is no `publish_audit_event` call inside
    # the integrity persist span by checking the span name appears
    # exactly once + the publisher import is absent.
    assert text.count("audit_integrity.persist") == 1
    assert "from shared.sdk.audit.publisher" not in text
    # The integrity persist block must explicitly swallow errors so a
    # transient DB issue cannot crash-loop the consumer.
    assert "self.audit_integrity_degraded = True" in text
    assert "AUDIT_INTEGRITY_DEGRADED_TOTAL" in text


def test_orchestrator_verify_chain_endpoint_does_not_publish_notification():
    text = _read("apps/orchestrator/src/operations.py")
    # The verify-chain endpoint should record a verification run row
    # but MUST NOT call publish_notification (which would re-enter the
    # stream.notifications fanout).
    assert "operations_audit_verify_chain" in text
    # Find the function body and inspect it.
    block_start = text.index("async def operations_audit_verify_chain(")
    block_end = text.index("async def operations_audit_verify_chain_latest")
    block = text[block_start:block_end]
    assert "publish_notification" not in block
    assert "stream.notifications" not in block
