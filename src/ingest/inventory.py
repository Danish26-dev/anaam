"""O2: file inventory and hashing.

Builds one FileEnvelope per input path, in stable sorted order, with a streamed SHA-256
over each file's bytes. Two files with identical bytes (e.g. the practice kit's
"sanjeevani_registration (1).csv" duplicate) remain two separate inventory entries: the
report must account for both paths even though their hashes match.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from core.errors import IngestError
from core.interfaces import FileEnvelope
from .path_safety import is_unsafe_symlink, iter_files_sorted

_CHUNK = 1024 * 1024  # 1 MiB streaming reads, so huge files do not blow up memory


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            chunk = f.read(_CHUNK)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


@dataclass
class InventoryEntry:
    path: Path  # absolute path on disk
    relative_path: str  # posix-style, relative to input root
    sha256: str
    size_bytes: int


def build_inventory(input_root: Path) -> list[InventoryEntry]:
    """Walk input_root and return one InventoryEntry per file, in deterministic order.

    Raises IngestError("unsafe_symlink_in_input") if any file escapes the input root via
    a symlink. Duplicate content is kept as separate entries (dedup happens nowhere here).
    """
    entries: list[InventoryEntry] = []
    for path in iter_files_sorted(input_root):
        if is_unsafe_symlink(path, input_root):
            raise IngestError("unsafe_symlink_in_input")
        rel = path.relative_to(input_root).as_posix()
        entries.append(
            InventoryEntry(
                path=path,
                relative_path=rel,
                sha256=sha256_file(path),
                size_bytes=path.stat().st_size,
            )
        )
    return entries


def to_file_envelope(entry: InventoryEntry, detected_format: str, detected_encoding: str | None) -> FileEnvelope:
    return FileEnvelope(
        input_sha256=entry.sha256,
        relative_path=entry.relative_path,
        detected_format=detected_format,
        detected_encoding=detected_encoding,
        size_bytes=entry.size_bytes,
        records=[],
        terminal_status=None,
    )
