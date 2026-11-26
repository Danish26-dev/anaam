"""Shared data contracts between Omkar's pipeline and Danish's detection/verification code.

This module is the single source of truth for every dataclass listed in the team plan's
"Shared internal interfaces" section. Both halves of the pipeline import from here so the
contract cannot drift between the two of us.

Rules that apply across this whole file:
  * Nothing here stores RAKSHA_SECRET.
  * `IdentityEvidence` and `FieldNode.value` may carry raw PII in memory -- never log or
    repr() them, and never let them reach stdout/stderr/report.json.
  * Everything else (ResolvedSpan, ClusterAssignment, VerificationResult, ...) must be
    safe to log, because they contain no raw personal values, only categories/decisions.
"""
from __future__ import annotations

from dataclasses import dataclass, field


# --------------------------------------------------------------------------- ingestion (Omkar)
@dataclass
class FieldNode:
    """One addressable piece of data inside a record (a CSV cell, a JSON value, a header,
    a filename fragment, ...). Created by Omkar's format adapters.
    """

    path: str  # e.g. "col:Mobile", "/visits/3/patient_ref", "header:Contact#", "filename"
    value: object
    value_type: str  # "str" | "int" | "float" | "bool" | "null"
    channel: str  # content | header | key | metadata | filename | base64 | fhir_narrative
    role_hint: str | None = None  # optional hint from the adapter, e.g. "patient_id"


@dataclass
class RecordEnvelope:
    """One record inside a file: a CSV row, a JSON array element, a whole document, a FHIR
    Bundle. Created by Omkar's adapters, consumed by Danish's detectors.
    """

    record_id: str
    file_sha256: str
    locator: str  # "row:12" | "/visits/3" | "doc"
    format: str  # "csv" | "tsv" | "json" | "text" | "fhir"
    fields: list[FieldNode] = field(default_factory=list)
    free_text: str | None = None
    rendering_metadata: dict = field(default_factory=dict)


@dataclass
class FileEnvelope:
    """One input file. Created by Omkar's ingestion stage."""

    input_sha256: str
    relative_path: str
    detected_format: str
    detected_encoding: str | None
    size_bytes: int
    records: list[RecordEnvelope] = field(default_factory=list)
    terminal_status: str | None = None  # "sanitized" | "quarantined" | "suppressed"


# --------------------------------------------------------------------------- detection (Danish)
@dataclass
class SpanCandidate:
    """A proposed PII/clinical span inside some text, before conflicts are resolved.
    Created by Danish's detectors (clinical shield, identifier regexes, name/context rules).
    """

    start: int
    end: int
    category: str  # e.g. PATIENT_NAME, PHONE, AADHAAR, MEDICINE, DOSE, DIAGNOSIS
    role: str | None  # patient | relative | doctor | None
    confidence: float
    tier: int  # priority tier used by the span resolver
    source: str  # which detector produced this, e.g. "clinical_patterns", "identifiers"
    proposed_action: str  # "redact" | "generalize" | "preserve"


@dataclass
class ResolvedSpan:
    """The final decision for one span after Danish's resolver merges/splits overlaps.
    Contains no raw PII -- safe to log and to store in TransformPlan.
    """

    start: int
    end: int
    category: str
    action: str  # "redact" | "generalize" | "preserve"
    reason_code: str


# --------------------------------------------------------------------------- identity
@dataclass
class ScopedIdentifier:
    """An identifier that is only unique within one system/hospital (e.g. an MRN)."""

    system: str  # e.g. "hospital:SNJ" or "system:ABHA"
    value: str


@dataclass
class IdentityEvidence:
    """Everything Danish's detectors found about who a record belongs to. Raw values stay
    in memory only -- never logged, never written to report.json or records.jsonl.
    Created by Danish, consumed by Omkar's identity resolution (O6/O7).
    """

    record_id: str
    patient_names: list[str] = field(default_factory=list)
    relative_names: list[str] = field(default_factory=list)
    doctor_names: list[str] = field(default_factory=list)
    national_ids: dict[str, str] = field(default_factory=dict)  # e.g. {"AADHAAR": "..."}
    scoped_ids: list[ScopedIdentifier] = field(default_factory=list)
    phones: list[str] = field(default_factory=list)
    date_of_birth: str | None = None
    age: int | None = None
    gender: str | None = None
    village: str | None = None
    tehsil: str | None = None
    district: str | None = None
    hospital: str | None = None


@dataclass
class ClusterAssignment:
    """Omkar's decision about which patient cluster a record belongs to."""

    record_id: str
    cluster_key: str | None
    decision: str  # MUST_LINK | PROBABLE_LINK | UNRESOLVED | CANNOT_LINK
    evidence_codes: list[str] = field(default_factory=list)


# --------------------------------------------------------------------------- transform & release
@dataclass
class FieldTransformation:
    """One concrete edit Omkar's writers must apply to a field before export."""

    path: str
    action: str  # "redact" | "replace" | "generalize" | "shift_date" | "preserve" | "suppress"
    replacement: object = None


@dataclass
class TransformPlan:
    """Everything needed to produce the sanitized candidate for one record. Created by
    Omkar using Danish's resolved spans plus Omkar's own clustering/date-shift output.
    """

    record_id: str
    pseudonym: str | None
    date_offset_days: int
    resolved_spans: list[ResolvedSpan] = field(default_factory=list)
    field_transformations: list[FieldTransformation] = field(default_factory=list)
    status: str = "sanitized"  # "sanitized" | "generalized" | "suppressed" | "quarantined"


@dataclass
class VerificationResult:
    """Danish's independent judgement on whether a candidate release is safe to publish."""

    passed: bool
    safe_reason_codes: list[str] = field(default_factory=list)
    retry_allowed: bool = True
    terminal_action: str = "RELEASE"  # RELEASE | RESCRUB | QUARANTINE | ABORT_RELEASE
