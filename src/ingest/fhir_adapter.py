"""O4: FHIR R4 Bundle adapter.

A Bundle is one record (locator "doc") for linkage/report purposes, but we also index:
  * every Patient resource (by its Bundle-local id / fullUrl),
  * every reference to a Patient resource (so the writer can rewrite them consistently),
  * narrative text (Composition.section text, Patient.text) for PII scanning,
  * identifiers and telecom blocks, which are exactly the fields O5's writer must drop.

This index is handed to the serializer (O5) alongside the RecordEnvelope so it can find
and rewrite every Patient-identifying field without re-walking the Bundle from scratch.
"""
from __future__ import annotations

from dataclasses import dataclass, field as dc_field

from core.interfaces import FieldNode, RecordEnvelope
from core.record_ids import make_record_id


@dataclass
class FhirPatientIndex:
    patient_resource_ids: set[str] = dc_field(default_factory=set)  # Bundle-local Patient.id
    patient_full_urls: set[str] = dc_field(default_factory=set)  # entry.fullUrl for Patients
    references_to_patient: list[str] = dc_field(default_factory=list)  # JSON pointers of refs
    narrative_pointers: list[str] = dc_field(default_factory=list)  # text.div, display strings


def _pointer_escape(token: str) -> str:
    return token.replace("~", "~0").replace("/", "~1")


def index_bundle(bundle: dict) -> FhirPatientIndex:
    idx = FhirPatientIndex()
    entries = bundle.get("entry", []) if isinstance(bundle, dict) else []

    for i, entry in enumerate(entries):
        resource = entry.get("resource", {}) if isinstance(entry, dict) else {}
        if resource.get("resourceType") == "Patient":
            if "id" in resource:
                idx.patient_resource_ids.add(str(resource["id"]))
            if "fullUrl" in entry:
                idx.patient_full_urls.add(entry["fullUrl"])

    seen_narrative_pointers: set[str] = set()

    def _add_narrative_pointer(pointer: str) -> None:
        if pointer not in seen_narrative_pointers:
            seen_narrative_pointers.add(pointer)
            idx.narrative_pointers.append(pointer)

    def walk(obj, pointer: str) -> None:
        if isinstance(obj, dict):
            ref = obj.get("reference")
            if isinstance(ref, str) and (
                ref.startswith("Patient/") or ref in idx.patient_full_urls
            ):
                idx.references_to_patient.append(pointer)

            # Two independent, non-overlapping narrative shapes: a `text: {div: "..."}`
            # block (FHIR's standard Narrative element, found on Composition/Patient/
            # etc.), and a bare `div` key one level below that same `text` object. Each
            # is checked exactly once per dict, keyed by its own specific shape, so the
            # same /text/div path can never be recorded twice via two different checks.
            text_value = obj.get("text")
            if isinstance(text_value, dict) and isinstance(text_value.get("div"), str):
                _add_narrative_pointer(f"{pointer}/text/div")
            elif isinstance(obj.get("div"), str) and "text" not in obj:
                _add_narrative_pointer(f"{pointer}/div")

            for k, v in obj.items():
                walk(v, f"{pointer}/{_pointer_escape(k)}")
        elif isinstance(obj, list):
            for i, v in enumerate(obj):
                walk(v, f"{pointer}/{i}")

    walk(bundle, "")
    return idx


def _collect_fhir_fields(
    value: object,
    pointer: str,
    fields: list[FieldNode],
    narrative_pointers: set[str],
) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            child_pointer = f"{pointer}/{_pointer_escape(key)}"
            fields.append(
                FieldNode(
                    path=f"{child_pointer}:key",
                    value=key,
                    value_type="str",
                    channel="key",
                )
            )
            _collect_fhir_fields(child, child_pointer, fields, narrative_pointers)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _collect_fhir_fields(child, f"{pointer}/{index}", fields, narrative_pointers)
    else:
        if pointer in narrative_pointers:
            channel = "fhir_narrative"
        elif "/meta/" in pointer or pointer.endswith("/meta/source"):
            channel = "metadata"
        else:
            channel = "content"
        value_type = "null" if value is None else type(value).__name__
        fields.append(
            FieldNode(path=pointer, value=value, value_type=value_type, channel=channel)
        )


def build_record(
    bundle: dict, file_sha256: str, relative_path: str
) -> tuple[RecordEnvelope, FhirPatientIndex]:
    idx = index_bundle(bundle)
    fields: list[FieldNode] = []
    _collect_fhir_fields(bundle, "", fields, set(idx.narrative_pointers))
    record = RecordEnvelope(
        record_id=make_record_id(file_sha256, relative_path, "doc"),
        file_sha256=file_sha256,
        locator="doc",
        format="fhir",
        fields=fields,
        free_text=None,
        rendering_metadata={"patient_count": len(idx.patient_resource_ids)},
    )
    return record, idx
