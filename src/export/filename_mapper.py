"""O5: deterministic, keyed mapping for PII-bearing path components."""
from __future__ import annotations

import base64
import hashlib
import hmac
import re
from pathlib import PurePosixPath

# Full Indian mobile/identifier digit runs and common hospital-scoped identifier shapes.
# This is deliberately format-based rather than tuned to one hospital's exact prefix.
_LONG_DIGIT_RUN_RE = re.compile(r"\d{7,}")
_SCOPED_ID_RE = re.compile(
    r"(?:^|[_-])(?:[a-z]{2,6}[-_])?(?:uhid|mrn|ipd|ip|adm|snj|jjh|dhh)"
    r"[-_]?\d(?:[\d_-]*\d)?",
    re.IGNORECASE,
)


def looks_unsafe(component: str) -> bool:
    """Return true when a path component contains a direct/scoped identifier shape."""
    stem = PurePosixPath(component).stem
    return bool(_LONG_DIGIT_RUN_RE.search(stem) or _SCOPED_ID_RE.search(stem))


def _token(filename_key: bytes, purpose: bytes, value: str) -> str:
    digest = hmac.new(filename_key, purpose + value.encode("utf-8"), hashlib.sha256).digest()
    return base64.b32encode(digest).decode("ascii").rstrip("=")[:16].lower()


def safe_filename(filename_key: bytes, relative_path: str) -> str:
    """Map an unsafe filename while preserving only its extension."""
    path = PurePosixPath(relative_path)
    token = _token(filename_key, b"filename-v1|", relative_path)
    return str(path.with_name(f"file_{token}{path.suffix}").as_posix())


def resolve_output_relative_path(filename_key: bytes, relative_path: str) -> str:
    """Map every unsafe file or directory component without exposing its original text."""
    source = PurePosixPath(relative_path)
    parts = list(source.parts)
    mapped: list[str] = []

    for index, component in enumerate(parts):
        if not looks_unsafe(component):
            mapped.append(component)
            continue

        component_context = "/".join(parts[: index + 1])
        token = _token(filename_key, b"path-component-v1|", component_context)
        if index == len(parts) - 1:
            suffix = PurePosixPath(component).suffix
            mapped.append(f"file_{token}{suffix}")
        else:
            mapped.append(f"dir_{token}")

    return PurePosixPath(*mapped).as_posix()
