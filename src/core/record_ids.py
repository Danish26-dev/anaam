"""Opaque internal record IDs and duplicate-insensitive content anchors.

Inventory paths are distinct even when two files have identical bytes. Identity resolution
therefore needs a unique execution ID for every (input path, record locator), while HMAC
pseudonyms and linked-patient date offsets must not change merely because an exact duplicate
file was added. These helpers keep those two concepts separate:

* ``make_record_id`` includes a digest of the relative input path, so duplicate paths do
  not overwrite one another in ``evidence_by_record``.
* ``content_anchor`` removes that path component and retains only file SHA-256 + locator.
  Exact duplicate files therefore contribute one canonical anchor to a cluster fingerprint.

Record IDs are internal only. They must never be written to report.json or logs because the
relative path used to derive them may contain PII.
"""
from __future__ import annotations

import hashlib
from urllib.parse import quote, unquote

_RECORD_VERSION = "rec-v1"
_CONTENT_VERSION = "content-v1"


def make_record_id(file_sha256: str, relative_path: str, locator: str) -> str:
    """Return a deterministic ID unique to one input path and record locator."""
    path_digest = hashlib.sha256(relative_path.encode("utf-8")).hexdigest()
    encoded_locator = quote(locator, safe="")
    return f"{_RECORD_VERSION}|{file_sha256}|{path_digest}|{encoded_locator}"


def content_anchor(record_id: str) -> str:
    """Return the duplicate-insensitive content identity represented by ``record_id``.

    Legacy IDs are returned unchanged so development fixtures written before ``rec-v1``
    remain usable. New pipeline IDs always use the versioned format above.
    """
    parts = record_id.split("|", 3)
    if len(parts) != 4 or parts[0] != _RECORD_VERSION:
        return record_id
    _, file_sha256, _path_digest, encoded_locator = parts
    return f"{_CONTENT_VERSION}|{file_sha256}|{quote(unquote(encoded_locator), safe='')}"


def stable_content_fingerprint(record_ids: list[str]) -> bytes:
    """Hash the sorted, deduplicated content anchors for a cluster."""
    anchors = sorted({content_anchor(record_id) for record_id in record_ids})
    joined = "\x1f".join(anchors)
    return hashlib.sha256(joined.encode("utf-8")).digest()
