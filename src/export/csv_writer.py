"""O5: format-preserving CSV/TSV candidate serialization."""
from __future__ import annotations

import csv
import io

from core.header_roles import (
    declared_date_hint,
    find_patient_identity_column,
    role_for_header,
)
from detection.api import identity_column as engine_identity_column
from detection.api import sanitize_header
from export.text_writer import render_text
from privacy.date_shift import shift_date_string


def _find_identity_column(header: list[str], input_sha256: str | None) -> int | None:
    """The header-name table first (core.header_roles); if that finds nothing and the
    file has been through prepare() (input_sha256 given), fall back to the engine's
    field classifier, which identifies a patient-identity column (NAME_PATIENT/MRN) from
    its own values even when the header text itself is one this table has never seen --
    the gap that left unseen-format CSV/TSV records with no pseudonym at all.
    """
    found = find_patient_identity_column(header)
    if found is not None or input_sha256 is None:
        return found
    return engine_identity_column(input_sha256, header)


def embeddable_pseudonyms(
    header: list[str],
    rows: list[list[str]],
    pseudonyms_by_row: dict[int, str | None],
    input_sha256: str | None = None,
) -> dict[int, str | None]:
    """Drop claims that cannot be embedded without adding/repairing CSV columns."""
    identity_col = _find_identity_column(header, input_sha256)
    if identity_col is None:
        return {row_index: None for row_index in range(len(rows))}
    return {
        row_index: (
            pseudonyms_by_row.get(row_index)
            if identity_col < len(row)
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
    input_sha256: str | None = None,
) -> tuple[str, int]:
    """Render the original schema; never append a pseudonym column.

    With `record_ids_by_row`, each cell is cleaned with the detection engine's spans for that
    record field, and header cells that hold PII are renamed (detection.api.sanitize_header).
    `input_sha256` lets the identity column fall back to the engine's field classifier when
    the header-name table (core.header_roles) does not recognise this file's header text."""
    date_offsets_by_row = date_offsets_by_row or {}
    record_ids_by_row = record_ids_by_row or {}
    patient_column = _find_identity_column(header, input_sha256)
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
