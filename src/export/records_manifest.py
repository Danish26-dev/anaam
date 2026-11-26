"""O12: records.jsonl builder.

One line per patient-bearing record actually exported. Records whose file ended up
quarantined must never appear here -- the writer filters by the set of exported output
paths before serializing, matching the starter's existing safeguard.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass
class RecordManifestEntry:
    file: str  # output path, relative to {output}
    loc: str  # input locator: row:N / JSON pointer / "doc"
    patient: str | None
    out: str | None = None  # output locator, only if it differs from loc
    status: str | None = None  # "sanitized" | "generalized" | "suppressed"

    def to_json_dict(self) -> dict:
        d = {"file": self.file, "loc": self.loc, "patient": self.patient}
        if self.out is not None:
            d["out"] = self.out
        if self.status is not None:
            d["status"] = self.status
        return d


def write_records_jsonl(output_dir: Path, entries: list[RecordManifestEntry], exported_files: set[str]) -> None:
    """Writes records.jsonl, silently dropping any entry whose `file` is not in
    exported_files (i.e. its file ended up quarantined after the record was queued).
    """
    kept = [entry for entry in entries if entry.file in exported_files]
    content = "".join(
        json.dumps(entry.to_json_dict(), ensure_ascii=False, sort_keys=True) + "\n"
        for entry in kept
    )
    destination = output_dir / "records.jsonl"
    temporary = output_dir / ".records.jsonl.tmp"
    try:
        temporary.write_text(content, encoding="utf-8", newline="")
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)
