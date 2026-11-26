"""Safe error handling.

Every error that can surface to stdout/stderr/report.json must carry only a reason CODE,
never a file path, never a value, never a stack trace that could echo input content.
"""
from __future__ import annotations


class SafeError(Exception):
    """Base class for all errors raised by Anaam's pipeline.

    `reason_code` is the only thing allowed to be printed, logged, or written to
    report.json. Never pass raw file content, PII, or RAKSHA_SECRET into the message.
    """

    def __init__(self, reason_code: str, detail: str | None = None):
        # `detail` is for developers reading a local traceback during testing; it is never
        # emitted by the top-level handler installed in preflight.py.
        super().__init__(reason_code)
        self.reason_code = reason_code
        self.detail = detail


class ConfigError(SafeError):
    """Bad invocation: missing/invalid CLI args, missing secret, unsafe paths."""


class IngestError(SafeError):
    """A single file could not be safely ingested. Callers should quarantine, not crash."""


class NetworkBlocked(SafeError):
    """Raised by the network guard when code tries to open a socket during `run`."""

    def __init__(self):
        super().__init__("network_access_blocked")


def safe_reason(exc: BaseException) -> str:
    """Reduce any exception to a reason code that is safe to print or store.

    Known SafeError subclasses report their own code. Anything else is reduced to its
    exception class name only -- never str(exc), which might contain file content.
    """
    if isinstance(exc, SafeError):
        return exc.reason_code
    return type(exc).__name__
