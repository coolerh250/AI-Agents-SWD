"""Input-authority tracer for the canonical governance measurement (Step PCP-V2.1-RM4).

Loaded by the measurement harness through PYTHONPATH, so it runs before the module under
measurement. It records every filesystem path and environment variable the module actually
touches, and whether the module's OWN code made the call.

Observation, not inspection. DEF-PCPE-01 escaped a static classifier because a path can be spelled
an unbounded number of ways -- a constant, an f-string, a loop variable, a helper's return value.
What a process opens is decidable regardless of spelling, so a verifier reading a non-canonical
input is caught without anyone having to anticipate the mechanism.

Attribution matters because the interpreter is noisy. Python reads COMSPEC, PATH and PATHEXT on
every subprocess call, APPDATA and USERPROFILE at startup, and imported libraries probe machine
paths of their own. Counting those as dependencies of the governance module made almost every
verifier look ambient and silently excluded three already-registered debt identities.

Emitted records:

    probe   header proving the tracer loaded at all
    path    a filesystem path touched by anyone in the process
    mpath   a filesystem path touched by the module's own frame
    env     an environment variable read by the module's own frame
    node    the pytest identity subsequent records belong to (written by the pytest plugin)
"""

import io
import os
import sys

_TRACE = os.environ.get("PCP_MEASUREMENT_TRACE")

PROBE_HEADER = "probe\tinput-authority-tracer/1"

if _TRACE:
    _sink = open(_TRACE, "a", encoding="utf-8", errors="replace")
    # Proves the module's inputs were actually observed. A trace without this line means the
    # tracer never loaded, and an unobserved module is UNKNOWN, never assumed deterministic.
    _sink.write(PROBE_HEADER + "\n")
    _sink.flush()

    _MEASURED_ROOT = os.path.normcase(os.path.abspath(os.environ.get("PCP_MEASUREMENT_ROOT", "")))

    def _from_measured_module(depth: int) -> bool:
        """True when the frame `depth` levels above the tracer wrapper is the module's own code."""
        if not _MEASURED_ROOT:
            return True
        try:
            filename = sys._getframe(depth + 1).f_code.co_filename
        except (ValueError, AttributeError):
            return False
        return os.path.normcase(os.path.abspath(filename)).startswith(_MEASURED_ROOT)

    def _emit(kind: str, value: object) -> None:
        try:
            value = os.fspath(value)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return
        if isinstance(value, bytes):
            value = value.decode("utf-8", "replace")
        _sink.write(f"{kind}\t{value}\n")
        _sink.flush()

    def _emit_path(value: object, depth: int) -> None:
        # Repository-relative authority is judged without attribution, so that a non-canonical
        # dependency reached through any depth of helper is still caught. Attribution only decides
        # whether an OUT-OF-repository read belongs to the module or to machinery beneath it.
        _emit("path", value)
        if _from_measured_module(depth + 1):
            _emit("mpath", value)

    def _trace_path(module: object, name: str) -> None:
        original = getattr(module, name)

        def traced(path, *args, **kwargs):  # type: ignore[no-untyped-def]
            _emit_path(path, 1)
            return original(path, *args, **kwargs)

        setattr(module, name, traced)

    for _name in ("stat", "lstat", "listdir", "scandir", "open", "readlink"):
        _trace_path(os, _name)
    _trace_path(os.path, "exists")
    _trace_path(os.path, "isfile")
    _trace_path(os.path, "isdir")

    _real_open = io.open

    def _traced_open(file, *args, **kwargs):  # type: ignore[no-untyped-def]
        _emit_path(file, 1)
        return _real_open(file, *args, **kwargs)

    io.open = _traced_open  # type: ignore[assignment]
    import builtins

    builtins.open = _traced_open  # type: ignore[assignment]

    def _emit_env(key: object, depth: int) -> None:
        if _from_measured_module(depth + 1):
            _emit("env", key)

    _real_getenv = os.getenv

    def _traced_getenv(key, default=None):  # type: ignore[no-untyped-def]
        _emit_env(key, 1)
        return _real_getenv(key, default)

    os.getenv = _traced_getenv  # type: ignore[assignment]

    _environ_class = type(os.environ)
    _real_getitem = _environ_class.__getitem__
    _real_get = _environ_class.get
    _real_contains = _environ_class.__contains__

    def _traced_getitem(self, key):  # type: ignore[no-untyped-def]
        _emit_env(key, 1)
        return _real_getitem(self, key)

    def _traced_get(self, key, default=None):  # type: ignore[no-untyped-def]
        _emit_env(key, 1)
        return _real_get(self, key, default)

    def _traced_contains(self, key):  # type: ignore[no-untyped-def]
        _emit_env(key, 1)
        return _real_contains(self, key)

    _environ_class.__getitem__ = _traced_getitem  # type: ignore[assignment]
    _environ_class.get = _traced_get  # type: ignore[assignment]
    _environ_class.__contains__ = _traced_contains  # type: ignore[assignment]
