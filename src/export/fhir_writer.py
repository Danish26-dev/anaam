"""O5/O9: safe FHIR R4 Bundle candidate serialization.

The pipeline currently accepts document Bundles containing exactly one Patient resource.
That patient receives the record pseudonym, every resolvable reference to the old Patient
identity is rewritten, direct patient identity blocks are removed, and all clinical dates
move by the same patient-specific offset.
"""
from __future__ import annotations

import copy
import json

from export.text_writer import render_text
from ingest.fhir_adapter import FhirPatientIndex
from privacy.date_shift import shift_date_string

_DATE_KEYS = {
    "date", "birthDate", "deceasedDateTime", "recordedDate", "authoredOn",
    "effectiveDateTime", "issued", "performedDateTime", "occurrenceDateTime",
    "start", "end", "lastUpdated", "timestamp",
}
_PATIENT_IDENTITY_KEYS = {
    "identifier", "telecom", "address", "name", "birthDate", "contact", "photo", "link",
}


def _tokens(pointer: str) -> list[str]:
    return [
        token.replace("~1", "/").replace("~0", "~")
        for token in pointer.strip("/").split("/")
    ] if pointer else []


def _value_at_pointer(root: object, pointer: str) -> object | None:
    node = root
    for token in _tokens(pointer):
        try:
            node = node[int(token)] if isinstance(node, list) else node[token]
        except (KeyError, IndexError, TypeError, ValueError):
            return None
    return node


def _set_at_pointer(root: object, pointer: str, value: object) -> bool:
    parts = _tokens(pointer)
    if not parts:
        return False
    node = root
    try:
        for token in parts[:-1]:
            node = node[int(token)] if isinstance(node, list) else node[token]
        last = parts[-1]
        if isinstance(node, list):
            node[int(last)] = value
        else:
            node[last] = value
        return True
    except (KeyError, IndexError, TypeError, ValueError):
        return False


def _shift_dates_in_place(node: object, offset_days: int) -> int:
    """Shift recognized clinical/audit dates while preserving syntax and intervals."""
    shifted_count = 0
    if isinstance(node, dict):
        for key, value in list(node.items()):
            if key in _DATE_KEYS and isinstance(value, str):
                # FHIR date/dateTime values use ISO syntax.
                shifted = shift_date_string(value, offset_days, date_hint="dmy")
                if shifted is not None:
                    node[key] = shifted
                    shifted_count += 1
            else:
                shifted_count += _shift_dates_in_place(value, offset_days)
    elif isinstance(node, list):
        for item in node:
            shifted_count += _shift_dates_in_place(item, offset_days)
    return shifted_count


def _rewrite_patient_references(
    node: object,
    old_patient_id: str | None,
    old_full_url: str | None,
    new_patient_id: str,
    new_full_url: str | None,
) -> int:
    """Rewrite Patient references at any nesting depth and replace patient displays."""
    changes = 0
    if isinstance(node, dict):
        reference = node.get("reference")
        if isinstance(reference, str):
            replacement: str | None = None
            if old_full_url and reference == old_full_url:
                replacement = new_full_url or f"Patient/{new_patient_id}"
            elif old_patient_id and reference == f"Patient/{old_patient_id}":
                replacement = f"Patient/{new_patient_id}"
            elif old_patient_id and reference.endswith(f"/Patient/{old_patient_id}"):
                replacement = reference[: -len(old_patient_id)] + new_patient_id

            if replacement is not None:
                node["reference"] = replacement
                changes += 1
                if "display" in node:
                    node["display"] = new_patient_id
                    changes += 1

        for value in node.values():
            changes += _rewrite_patient_references(
                value, old_patient_id, old_full_url, new_patient_id, new_full_url
            )
    elif isinstance(node, list):
        for value in node:
            changes += _rewrite_patient_references(
                value, old_patient_id, old_full_url, new_patient_id, new_full_url
            )
    return changes


def _drop_meta_sources(node: object) -> int:
    """Remove metadata source strings, which commonly embed MRNs or source paths."""
    removed = 0
    if isinstance(node, dict):
        meta = node.get("meta")
        if isinstance(meta, dict) and "source" in meta:
            del meta["source"]
            removed += 1
        for value in node.values():
            removed += _drop_meta_sources(value)
    elif isinstance(node, list):
        for value in node:
            removed += _drop_meta_sources(value)
    return removed


# Values under these keys are structure the Bundle needs to stay resolvable and valid.
_STRUCTURAL_KEYS = {"reference", "fullUrl", "id", "resourceType", "system", "url", "status"}


def _clean_strings(
    node: object, pointer: str, record_id: str | None, skip: set[str], counter: list[int]
) -> object:
    """Run every non-structural string through the detection seam (with record context)."""
    if isinstance(node, dict):
        for key in list(node):
            child = f"{pointer}/{str(key).replace('~', '~0').replace('/', '~1')}"
            if key in _STRUCTURAL_KEYS or child in skip:
                continue
            node[key] = _clean_strings(node[key], child, record_id, skip, counter)
        return node
    if isinstance(node, list):
        return [
            _clean_strings(item, f"{pointer}/{i}", record_id, skip, counter)
            for i, item in enumerate(node)
        ]
    if isinstance(node, str):
        cleaned, count = render_text(node, 0, record_id, pointer)
        counter[0] += count
        return cleaned
    return node


def render_fhir_bundle(
    bundle: dict, index: FhirPatientIndex, pseudonym: str | None, date_offset_days: int = 0,
    record_id: str | None = None,
) -> tuple[str, int]:
    doc = copy.deepcopy(bundle)
    redacted = 0
    new_patient_id = pseudonym or "ANON"

    patient_entries = [
        entry
        for entry in doc.get("entry", [])
        if isinstance(entry, dict)
        and isinstance(entry.get("resource"), dict)
        and entry["resource"].get("resourceType") == "Patient"
    ]
    if len(patient_entries) != 1:
        raise ValueError("fhir_requires_exactly_one_patient")

    patient_entry = patient_entries[0]
    patient_resource = patient_entry["resource"]
    old_patient_id = str(patient_resource.get("id")) if patient_resource.get("id") is not None else None
    old_full_url = patient_entry.get("fullUrl") if isinstance(patient_entry.get("fullUrl"), str) else None

    # Opaque urn:uuid fullUrls contain no patient values and remain resolvable when kept.
    # Relative/absolute Patient URLs can embed the old resource id and must be replaced.
    new_full_url = old_full_url
    if old_full_url and not old_full_url.startswith("urn:uuid:"):
        new_full_url = f"Patient/{new_patient_id}"
        patient_entry["fullUrl"] = new_full_url
        redacted += 1

    patient_resource["id"] = new_patient_id
    if old_patient_id != new_patient_id:
        redacted += 1
    for key in _PATIENT_IDENTITY_KEYS:
        if key in patient_resource:
            del patient_resource[key]
            redacted += 1

    redacted += _rewrite_patient_references(
        doc, old_patient_id, old_full_url, new_patient_id, new_full_url
    )
    redacted += _drop_meta_sources(doc)

    for pointer in index.narrative_pointers:
        narrative = _value_at_pointer(doc, pointer)
        if isinstance(narrative, str):
            # Narrative is free-text prose (e.g. a rendered discharge paragraph), so an
            # inline date mention is shifted the same way whole free-text documents are.
            cleaned, count = render_text(narrative, date_offset_days, record_id, pointer if record_id else None)
            if _set_at_pointer(doc, pointer, cleaned):
                redacted += count

    if record_id is not None:
        counter = [0]
        _clean_strings(doc, "", record_id, set(index.narrative_pointers), counter)
        redacted += counter[0]

    if date_offset_days:
        _shift_dates_in_place(doc, date_offset_days)

    return json.dumps(doc, ensure_ascii=False, indent=2) + "\n", redacted
