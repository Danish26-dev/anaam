"""O3: format detection by content, not by extension.

The extension is used only as a weak hint; content sniffing always wins. This is what
catches traps like a JSON file saved with a ".csv" extension.
"""
from __future__ import annotations

import csv
import io
import json

SUPPORTED_FORMATS = ("csv", "tsv", "json", "fhir", "text")


def _printable_ratio(text: str) -> float:
    if not text:
        return 0.0
    printable = sum(1 for ch in text if ch.isprintable() or ch in "\n\r\t")
    return printable / len(text)


def _try_json(text: str) -> object | None:
    try:
        return json.loads(text)
    except (json.JSONDecodeError, RecursionError):
        return None


def _looks_like_delimited(text: str, delimiter: str) -> bool:
    """A file counts as CSV/TSV only if several lines share a consistent column count."""
    sample = "\n".join(text.splitlines()[:20])
    if not sample.strip():
        return False
    try:
        rows = list(csv.reader(io.StringIO(sample), delimiter=delimiter))
    except csv.Error:
        return False
    rows = [r for r in rows if r]
    if len(rows) < 2:
        return False
    widths = [len(r) for r in rows]
    if widths[0] <= 1:
        return False
    # Allow some ragged rows but most should match the header width.
    matching = sum(1 for w in widths if w == widths[0])
    return matching / len(widths) >= 0.6


def detect_format(text: str, extension: str) -> str:
    """Return one of SUPPORTED_FORMATS, or "unsupported" / "undecodable_as_text".

    Content sniffing order: JSON (incl. FHIR) -> CSV -> TSV -> plain text, falling back
    to the extension only to disambiguate CSV vs TSV when both look plausible.
    """
    stripped = text.strip()
    if not stripped:
        return "unsupported"  # caller distinguishes "empty_file" before calling this

    ext = extension.lower().lstrip(".")
    if stripped[0] in "{[":
        data = _try_json(text)
        if data is not None:
            if isinstance(data, dict) and data.get("resourceType") == "Bundle":
                return "fhir"
            return "json"
        # Text messages commonly begin with a bracketed timestamp. A failed JSON parse
        # is conclusive only when the declared extension is JSON/tabular; .txt falls
        # through to printable-text detection.
        if ext != "txt":
            return "unsupported"

    if _looks_like_delimited(text, ","):
        return "csv"
    if _looks_like_delimited(text, "\t"):
        return "tsv"
    if ext in ("csv", "tsv") and _printable_ratio(text) > 0.95:
        # Single-column or oddly shaped but still clearly tabular text-ish file.
        return "csv" if ext == "csv" else "tsv"

    if _printable_ratio(text) < 0.85:
        return "undecodable_as_text"

    return "text"
