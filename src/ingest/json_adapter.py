"""O4: JSON adapter.

Builds RecordEnvelope objects from a parsed JSON document:
  * if the top level has one or more arrays-of-objects, each array element becomes a
    record with an RFC 6901 pointer locator (e.g. "/visits/3");
  * otherwise the whole document is one record with locator "doc" (covers single-object
    exports and FHIR Bundles, which the fhir_adapter specializes further).

Every scalar leaf becomes a FieldNode with its JSON-pointer path; dict keys are exposed as
their own FieldNode (channel="key") so Danish can flag a PII-bearing key (e.g. a dict keyed
by patient name) even when the key never appears as a value.
"""
from __future__ import annotations

import json

from core.errors import IngestError
from core.interfaces import FieldNode, RecordEnvelope
from core.record_ids import make_record_id

MAX_DEPTH = 200  # guards the "1,500-level-deep JSON" trap without a brittle exact cutoff


def parse_json(text: str) -> object:
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise IngestError("json_parse_error", detail=str(exc)) from exc
    if _depth(data) > MAX_DEPTH:
        raise IngestError("json_nesting_too_deep")
    return data


def _depth(obj, current: int = 0) -> int:
    if current > MAX_DEPTH:
        return current
    if isinstance(obj, dict):
        return max((_depth(v, current + 1) for v in obj.values()), default=current)
    if isinstance(obj, list):
        return max((_depth(v, current + 1) for v in obj), default=current)
    return current


def pointer_escape(token: str) -> str:
    return token.replace("~", "~0").replace("/", "~1")


def _collect_fields(obj, pointer: str, out: list[FieldNode]) -> None:
    if isinstance(obj, dict):
        for k, v in obj.items():
            out.append(FieldNode(path=f"{pointer}/{pointer_escape(k)}:key", value=k, value_type="str", channel="key"))
            _collect_fields(v, f"{pointer}/{pointer_escape(k)}", out)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            _collect_fields(v, f"{pointer}/{i}", out)
    else:
        vtype = "null" if obj is None else type(obj).__name__
        out.append(FieldNode(path=pointer, value=obj, value_type=vtype, channel="content"))


_EXPLICIT_PATIENT_KEYS = {
    "patient", "patient_ref", "patient_id", "patient_name", "uhid", "mrn",
    "hospital_uhid", "beneficiary_id",
}
_SUPPORTING_IDENTITY_KEYS = {
    "dob", "birth_date", "age", "gender", "sex", "phone", "mobile", "contact",
    "address", "guardian", "relative", "ids",
}


def _normalized_keys(value: dict) -> set[str]:
    return {
        str(key).strip().lower().replace(" ", "_").replace("-", "_")
        for key in value
    }


def _looks_like_patient_record(value: object) -> bool:
    if not isinstance(value, dict):
        return False
    keys = _normalized_keys(value)
    if keys & _EXPLICIT_PATIENT_KEYS:
        return True
    return bool(keys & {"name", "full_name"}) and bool(keys & _SUPPORTING_IDENTITY_KEYS)


def record_arrays(data: object) -> list[tuple[str, list[dict]]]:
    """Return top-level arrays whose elements structurally represent patient records."""
    if not isinstance(data, dict) or data.get("resourceType") == "Bundle":
        return []
    result: list[tuple[str, list[dict]]] = []
    for key, value in data.items():
        if (
            isinstance(value, list)
            and value
            and all(isinstance(item, dict) for item in value)
            and all(_looks_like_patient_record(item) for item in value)
        ):
            result.append((key, value))
    return result


def build_records(data: object, file_sha256: str, relative_path: str) -> list[RecordEnvelope]:
    """Mirrors the starter's doc-vs-array heuristic, generalized: a top-level dict whose
    own fields are scalars/sub-objects (not record arrays) is a single "doc" record; a
    top-level dict containing one or more record arrays yields one record per array item,
    across ALL such arrays (not just the first), each with its own JSON-pointer locator.
    """
    is_fhir_bundle = isinstance(data, dict) and data.get("resourceType") == "Bundle"
    if is_fhir_bundle:
        return []  # fhir_adapter.py owns Bundle record construction

    arrays = record_arrays(data)

    if not arrays:
        fields: list[FieldNode] = []
        _collect_fields(data, "", fields)
        return [
            RecordEnvelope(
                record_id=make_record_id(file_sha256, relative_path, "doc"),
                file_sha256=file_sha256,
                locator="doc",
                format="json",
                fields=fields,
                free_text=None,
                rendering_metadata={},
            )
        ]

    records: list[RecordEnvelope] = []
    for key, array in arrays:
        esc_key = pointer_escape(key)
        for i, item in enumerate(array):
            fields = []
            _collect_fields(item, "", fields)
            locator = f"/{esc_key}/{i}"
            records.append(
                RecordEnvelope(
                    record_id=make_record_id(file_sha256, relative_path, locator),
                    file_sha256=file_sha256,
                    locator=locator,
                    format="json",
                    fields=fields,
                    free_text=None,
                    rendering_metadata={"array_key": key},
                )
            )
    return records
