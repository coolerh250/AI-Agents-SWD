"""Attributes traced inputs to the exact pytest node that touched them (Step PCP-V2.1-RM4).

The verifier domain gets one process per identity, so its trace needs no attribution. The test
domain runs in a single pytest process, so without a marker the tracer could only say "something in
this batch read a non-canonical input" -- which is not an exact identity, and exact identity is the
property the debt register depends on.
"""

import os


def _mark(nodeid: str) -> None:
    trace = os.environ.get("PCP_MEASUREMENT_TRACE")
    if not trace:
        return
    with open(trace, "a", encoding="utf-8", errors="replace") as sink:
        sink.write(f"node\t{nodeid}\n")


def pytest_collectstart(collector):  # type: ignore[no-untyped-def]
    # Import-time reads happen during collection, before any node starts. Attributing them to the
    # file lets them reach every identity in it instead of escaping attribution entirely.
    _mark(getattr(collector, "nodeid", "") or "")


def pytest_runtest_logstart(nodeid, location):  # type: ignore[no-untyped-def]
    _mark(nodeid)
