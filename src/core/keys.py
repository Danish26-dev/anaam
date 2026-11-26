"""Key derivation from RAKSHA_SECRET.

RAKSHA_SECRET itself must never be logged, printed, written to any file, or stored on any
dataclass that could be serialized. This module derives purpose-scoped subkeys with HKDF-like
HMAC derivation so that, for example, leaking the date-shift key (which we never do, but
defense in depth) does not also expose the pseudonym key.
"""
from __future__ import annotations

import hashlib
import hmac
import os


class MissingSecretError(Exception):
    """Raised when RAKSHA_SECRET is absent or empty. Carries no sensitive detail."""


def _derive(secret: bytes, label: str) -> bytes:
    """HMAC-SHA256(secret, label) -- a simple, deterministic, purpose-scoped subkey."""
    return hmac.new(secret, label.encode("utf-8"), hashlib.sha256).digest()


class KeySet:
    """Holds purpose-scoped subkeys derived from RAKSHA_SECRET.

    The raw secret is kept only inside this object (as `_secret`), for deriving further
    subkeys on demand. Nothing on this object has a safe __repr__; never print an instance.
    """

    __slots__ = ("_secret", "pseudonym_key", "date_shift_key", "filename_key", "temp_key")

    def __init__(self, secret: bytes):
        self._secret = secret
        self.pseudonym_key = _derive(secret, "anaam:pseudonym:v1")
        self.date_shift_key = _derive(secret, "anaam:date-shift:v1")
        self.filename_key = _derive(secret, "anaam:filename:v1")
        self.temp_key = _derive(secret, "anaam:temp-encryption:v1")

    def __repr__(self) -> str:  # defense in depth: never let repr() leak key material
        return "KeySet(***)"

    def __str__(self) -> str:
        return "KeySet(***)"


def load_keyset(env: dict | None = None) -> KeySet:
    """Read RAKSHA_SECRET from the environment and derive the KeySet.

    Raises MissingSecretError if the secret is absent or blank. Never log `env`.
    """
    env = env if env is not None else os.environ
    secret = env.get("RAKSHA_SECRET", "")
    if not secret.strip():
        raise MissingSecretError("RAKSHA_SECRET is missing or empty")
    return KeySet(secret.encode("utf-8"))
