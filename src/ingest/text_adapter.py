"""O4: plain-text adapter.

Treats the whole document as one record (locator "doc"), preserving line structure in
free_text so Danish's line-oriented context rules (e.g. "Name:", "नाम:", "S/o") can work
with real line boundaries instead of a flattened blob.
"""
from __future__ import annotations

from core.interfaces import RecordEnvelope
from core.record_ids import make_record_id


def build_record(text: str, file_sha256: str, relative_path: str) -> RecordEnvelope:
    return RecordEnvelope(
        record_id=make_record_id(file_sha256, relative_path, "doc"),
        file_sha256=file_sha256,
        locator="doc",
        format="text",
        fields=[],
        free_text=text,
        rendering_metadata={"line_count": text.count("\n") + 1},
    )
