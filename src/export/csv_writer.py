"""O5: format-preserving CSV/TSV candidate serialization."""
from __future__ import annotations

import csv
import io

from core.header_roles import (
    declared_date_hint,
    find_patient_identity_column,
    role_for_header,
)
from detection.api import sanitize_header
from export.text_writer import render_text
from privacy.date_shift import shift_date_string


def embeddable_pseudonyms(
    header: list[str], rows: list[list[str]], pseudonyms_by_row: dict[int, str | None]
) -> dict[int, str | None]:
    """Drop claims that cannot be embedded without adding/repairing CSV columns."""
    identity_column = find_patient_identity_column(header)
    if identity_column is None:
        return {row_index: None for row_index in range(len(rows))}
    return {
        row_index: (
            pseudonyms_by_row.get(row_index)
            if identity_column < len(row)
            else None
        )
        for row_index, row in enumerate(rows)
    }


def _find_date_columns(header: list[str]) -> dict[int, str]:
    result: dict[int, str] = {}
    for index, raw_header in enumerate(header):
        declared = declared_date_hint(raw_header)
        if declared is not None:
            result[index] = declared
        elif role_for_header(raw_header) == "date":
            result[index] = "dmy"
    return result


def render_csv(
    header: list[str],
    rows: list[list[str]],
    delimiter: str,
    pseudonyms_by_row: dict[int, str | None],
    date_offsets_by_row: dict[int, int] | None = None,
    record_ids_by_row: dict[int, str] | None = None,
) -> tuple[str, int]:
    """Render the original schema; never append a pseudonym column.

    With `record_ids_by_row`, each cell is cleaned with the detection engine's spans for that
    record field, and header cells that hold PII are renamed (detection.api.sanitize_header)."""
    date_offsets_by_row = date_offsets_by_row or {}
    record_ids_by_row = record_ids_by_row or {}
    patient_column = find_patient_identity_column(header)
    date_columns = _find_date_columns(header)

    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter=delimiter, lineterminator="\n")
    out_header = sanitize_header(header) if record_ids_by_row else header
    writer.writerow(out_header)

    total_redacted = 0
    for row_index, row in enumerate(rows):
        offset = date_offsets_by_row.get(row_index, 0)
        cleaned_row: list[str] = []
        for column_index, cell in enumerate(row):
            if offset and column_index in date_columns and cell.strip():
                shifted = shift_date_string(
                    cell, offset, date_hint=date_columns[column_index]
                )
                if shifted is not None:
                    cleaned_row.append(shifted)
                    continue
                # A malformed declared-date cell still falls through to render_text
                # below, so it is at least checked for an embedded free-text date and
                # sanitized like any other cell, rather than silently passing through.
            header_name = header[column_index] if column_index < len(header) else f"col:{column_index}"
            path = header_name if header_name.startswith("col:") else f"col:{header_name}"
            cleaned, count = render_text(cell, offset, record_ids_by_row.get(row_index), path)
            cleaned_row.append(cleaned)
            total_redacted += count

        pseudonym = pseudonyms_by_row.get(row_index)
        if (
            pseudonym is not None
            and patient_column is not None
            and patient_column < len(cleaned_row)
        ):
            cleaned_row[patient_column] = pseudonym

        writer.writerow(cleaned_row)

    return buffer.getvalue(), total_redacted
