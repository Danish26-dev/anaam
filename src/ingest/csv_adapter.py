"""O4: CSV/TSV adapter.

Produces one RecordEnvelope per data row (locator "row:N", 0-based, header excluded), with
one FieldNode per cell addressed by its header name ("col:<Header>"). Also emits FieldNode
entries for the header row itself (channel="header") so Danish's field classifier and
channel detector can flag a PII-bearing header for renaming.
"""
from __future__ import annotations

import csv
import io
from dataclasses import dataclass

from core.errors import IngestError
from core.interfaces import FieldNode, RecordEnvelope
from core.record_ids import make_record_id


@dataclass
class CsvTable:
    delimiter: str
    header: list[str]
    rows: list[list[str]]  # original row shape, including ragged rows
    ragged_row_indices: list[int]


def sniff_delimiter(sample_text: str, fallback: str) -> str:
    try:
        dialect = csv.Sniffer().sniff(sample_text, delimiters=",\t;|")
        return dialect.delimiter
    except csv.Error:
        return fallback


def parse_csv(text: str, delimiter: str) -> CsvTable:
    try:
        rows = list(csv.reader(io.StringIO(text, newline=""), delimiter=delimiter))
    except csv.Error as exc:
        raise IngestError("csv_parse_error", detail=str(exc)) from exc
    rows = [r for r in rows if r]  # drop fully-blank lines
    if not rows:
        raise IngestError("csv_empty_after_parse")
    header, body = rows[0], rows[1:]
    ragged = [i for i, r in enumerate(body) if len(r) != len(header)]
    return CsvTable(delimiter=delimiter, header=header, rows=body, ragged_row_indices=ragged)


def build_records(
    table: CsvTable,
    file_sha256: str,
    relative_path: str,
    format_name: str = "csv",
) -> list[RecordEnvelope]:
    """Build one RecordEnvelope per row. Ragged rows are kept as-is (no aggressive repair);
    extra/missing cells just get positional "col:N" paths instead of a header name.
    """
    records: list[RecordEnvelope] = []
    for i, row in enumerate(table.rows):
        fields: list[FieldNode] = []
        for j, cell in enumerate(row):
            header_name = table.header[j] if j < len(table.header) else f"col:{j}"
            path = header_name if header_name.startswith("col:") else f"col:{header_name}"
            fields.append(FieldNode(path=path, value=cell, value_type="str", channel="content"))
        # Header cells themselves: exposed once per file would be enough, but attaching to
        # every record keeps the contract simple -- Danish's classifier just checks path.
        records.append(
            RecordEnvelope(
                record_id=make_record_id(file_sha256, relative_path, f"row:{i}"),
                file_sha256=file_sha256,
                locator=f"row:{i}",
                format=format_name,
                fields=fields,
                free_text=None,
                rendering_metadata={"ragged": i in table.ragged_row_indices},
            )
        )
    return records


def header_field_nodes(table: CsvTable) -> list[FieldNode]:
    """One FieldNode per header cell, channel="header", for PII-in-header detection."""
    return [
        FieldNode(path=f"header:{i}", value=h, value_type="str", channel="header")
        for i, h in enumerate(table.header)
    ]
