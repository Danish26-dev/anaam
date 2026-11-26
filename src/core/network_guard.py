"""Python-level network guard.

The evaluator already runs `run` inside an empty network namespace, so every real
connection fails there. This guard is defense in depth: it makes any attempt to open a
socket fail fast and loudly (with a safe reason code) instead of hanging on a DNS lookup
or a dropped-packet timeout, which would burn the wall-clock budget.
"""
from __future__ import annotations

import socket

from .errors import NetworkBlocked

_ORIGINAL_SOCKET = socket.socket
_ORIGINAL_GETADDRINFO = socket.getaddrinfo
_installed = False


class _GuardedSocket(_ORIGINAL_SOCKET):
    def connect(self, *args, **kwargs):  # noqa: D102 - thin guard, not a real socket impl
        raise NetworkBlocked()

    def connect_ex(self, *args, **kwargs):
        raise NetworkBlocked()

    def sendto(self, *args, **kwargs):
        # UDP can transmit without connect(), so it needs an explicit guard.
        raise NetworkBlocked()

    def sendmsg(self, *args, **kwargs):
        raise NetworkBlocked()


def _blocked_getaddrinfo(*args, **kwargs):
    # DNS resolution may itself leave the process even before socket.connect().
    raise NetworkBlocked()


def install_network_guard() -> None:
    """Replace socket.socket so any outbound connection attempt raises NetworkBlocked.

    Idempotent: safe to call more than once.
    """
    global _installed
    if _installed:
        return
    socket.socket = _GuardedSocket  # type: ignore[assignment]
    socket.getaddrinfo = _blocked_getaddrinfo  # type: ignore[assignment]
    _installed = True


def uninstall_network_guard() -> None:
    """Restore the real socket.socket. Mainly for tests."""
    global _installed
    socket.socket = _ORIGINAL_SOCKET  # type: ignore[assignment]
    socket.getaddrinfo = _ORIGINAL_GETADDRINFO  # type: ignore[assignment]
    _installed = False
