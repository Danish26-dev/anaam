"""O5: deterministic JSON candidate serialization.

Every top-level array of objects is treated as a record collection. Each element receives
its own pseudonym and date offset keyed by its RFC 6901 input locator. String keys and
values pass through the detection seam without changing non-string value types.
"""
from __future__ import annotations

import copy
import json

from export.text_writer import render_text
from ingest.json_adapter import pointer_escape, record_arrays
from privacy.date_shift import shift_date_string

_DATE_KEYS = {
    "visit_date", "admission_date", "discharge_date", "date", "reg_date",
    "registered", "collected", "collected_on", "reported_on", "report_date", "dob",
}
_IDENTITY_KEY_PRIORITY = (
    "patient_ref", "patient_id", "patientid", "uhid", "mrn", "hospital_uhid",
    "patient", "patient_name", "name",
)


def _normalized_key(value: object) -> str:
    return str(value).strip().lower().replace(" ", "_").replace("-", "_")


def _identity_path(value: object, prefix: tuple[object, ...] = ()) -> tuple[object, ...] | None:
    if not isinstance(value, dict):
        return None
    by_normalized = {_normalized_key(key): key for key in value}
    for candidate in _IDENTITY_KEY_PRIORITY:
        raw_key = by_normalized.get(candidate)
        if raw_key is not None and isinstance(value[raw_key], str):
            return (*prefix, raw_key)
    for raw_key, child in value.items():
        if isinstance(child, dict):
            nested = _identity_path(child, (*prefix, raw_key))
            if nested is not None:
                return nested
    return None


def can_embed_pseudonym(value: object) -> bool:
    return _identity_path(value) is not None


def _embed_pseudonym(value: dict, pseudonym: str) -> bool:
    path = _identity_path(value)
    if path is None:
        return False
    node: dict = value
    for token in path[:-1]:
        node = node[token]
    node[path[-1]] = pseudonym
    return True


def _insert_unique(target: dict, key: str, value: object) -> None:
    """Insert without losing data when two sanitized source keys collide."""
    if key not in target:
        target[key] = value
        return
    suffix = 2
    candidate = f"{key}__{suffix}"
    while candidate in target:
        suffix += 1
        candidate = f"{key}__{suffix}"
    target[candidate] = value


def _clean_value(value: object, stats: dict[str, int], offset_days: int = 0) -> object:
    if isinstance(value, str):
        # Passing offset_days here lets any embedded free-text date inside an ordinary
        # string value (not just a recognized date-typed key) get shifted too, matching
        # the whole-document free-text behaviour in text_writer.render_text_document.
        cleaned, count = render_text(value, offset_days)
        stats["redacted"] += count
        return cleaned
    if isinstance(value, list):
        return [_clean_value(item, stats, offset_days) for item in value]
    if isinstance(value, dict):
        cleaned: dict = {}
        for raw_key, raw_value in value.items():
            cleaned_key, count = render_text(raw_key)
            stats["redacted"] += count

            cleaned_value: object
            if offset_days and raw_key.strip().lower() in _DATE_KEYS and isinstance(raw_value, str):
                shifted = shift_date_string(raw_value, offset_days, date_hint="dmy")
                if shifted is not None:
                    cleaned_value = shifted
                else:
                    # A malformed declared-date value still receives ordinary sanitation.
                    stats["unshiftable_dates"] += 1
                    cleaned_value = _clean_value(raw_value, stats, offset_days)
            else:
                cleaned_value = _clean_value(raw_value, stats, offset_days)
            _insert_unique(cleaned, cleaned_key, cleaned_value)
        return cleaned
    return value  # numbers, booleans and null keep their original JSON types


def render_json_doc(
    data: object,
    date_offset_days: int = 0,
    pseudonym: str | None = None,
) -> tuple[str, int]:
    stats = {"redacted": 0, "unshiftable_dates": 0}
    source = copy.deepcopy(data)
    if pseudonym is not None and isinstance(source, dict):
        _embed_pseudonym(source, pseudonym)
    cleaned = _clean_value(source, stats, date_offset_days)
    return json.dumps(cleaned, ensure_ascii=False, indent=2) + "\n", stats["redacted"]


def render_json_records(
    data: dict,
    pseudonyms_by_locator: dict[str, str | None],
    date_offsets_by_locator: dict[str, int] | None = None,
) -> tuple[str, int]:
    """Clean every top-level record array using per-locator release decisions."""
    stats = {"redacted": 0, "unshiftable_dates": 0}
    date_offsets_by_locator = date_offsets_by_locator or {}
    cleaned: dict = {}
    selected_array_keys = {key for key, _array in record_arrays(data)}

    for raw_key, raw_value in data.items():
        cleaned_key, count = render_text(raw_key)
        stats["redacted"] += count

        if raw_key in selected_array_keys and isinstance(raw_value, list):
            escaped_key = pointer_escape(raw_key)
            cleaned_array = []
            for index, item in enumerate(raw_value):
                locator = f"/{escaped_key}/{index}"
                offset = date_offsets_by_locator.get(locator, 0)
                source_item = copy.deepcopy(item)
                pseudonym = pseudonyms_by_locator.get(locator)
                if pseudonym is not None:
                    _embed_pseudonym(source_item, pseudonym)
                cleaned_item = _clean_value(source_item, stats, offset)
                cleaned_array.append(cleaned_item)
            cleaned_value = cleaned_array
        else:
            # File-level metadata is not assigned a patient offset. Patient-bearing
            # metadata still passes through detection and hidden-channel sanitation.
            cleaned_value = _clean_value(raw_value, stats, 0)

        _insert_unique(cleaned, cleaned_key, cleaned_value)

    return json.dumps(cleaned, ensure_ascii=False, indent=2) + "\n", stats["redacted"]
