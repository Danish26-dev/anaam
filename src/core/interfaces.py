"""Shared data contracts between Omkar's pipeline and Danish's detection/verification code.

This module is the single source of truth for every dataclass listed in the team plan's
"Shared internal interfaces" section. Both halves of the pipeline import from here so the
contract cannot drift between the two of us.

Reconciled from two independently-drafted versions (Omkar's `src/core/interfaces.py` and
Danish's proposed `src/contracts.py`) once both the pipeline and the detection/verification
engine existed. Differences and how they were resolved:
  * `ScopedIdentifier` now uses Danish's richer (scope, kind, value) shape instead of
    Omkar's (system, value) -- `kind` distinguishes MRN/INSURANCE_ID/OTHER_ID, which the
    detector already produces and the identity resolver can use directly.
  * `ResolvedSpan` gained `field_path`, `replacement` and `attrs`, used by the span
    resolver and writers to know exactly which field an offset range refers to and what
    sanitized value to substitute for a REENCODE action.
  * `FieldTransformation` keeps Omkar's (path, action, replacement) shape: Danish's
    version was an explicit placeholder ("ADDITION: placeholder for Omkar to define")
    never constructed by his code, so there was nothing to reconcile here.
  * `VerificationResult` gained `findings: list[LeakFinding]` so a verifier can report
    *where* a problem was found (position + category + channel) without ever including
    the matched value itself.
  * The channel/action/category/tier string vocabulary from Danish's `src/contracts.py`
    is adopted here as the single source of truth for those constants, replacing the
    ad-hoc inline string literals previously scattered across both sides' code.

Rules that apply across this whole file:
  * Nothing here stores RAKSHA_SECRET.
  * `IdentityEvidence` and `FieldNode.value` may carry raw PII in memory -- never log or
    repr() them, and never let them reach stdout/stderr/report.json.
  * Everything else (ResolvedSpan, ClusterAssignment, VerificationResult, LeakFinding...)
    must be safe to log: no raw personal values, only categories, positions and codes.
"""
from __future__ import annotations

from dataclasses import dataclass, field

# --------------------------------------------------------------------------- channels
CONTENT = "content"
HEADER = "header"
KEY = "key"
METADATA = "metadata"
FILENAME = "filename"
BASE64 = "base64"
FHIR_NARRATIVE = "fhir_narrative"
CHANNELS = (CONTENT, HEADER, KEY, METADATA, FILENAME, BASE64, FHIR_NARRATIVE)

# --------------------------------------------------------------------------- span actions
KEEP = "KEEP"                                  # protected value, informational only
REDACT = "REDACT"                              # replace with a typed placeholder
PSEUDONYMIZE = "PSEUDONYMIZE"                  # replace with the record's pseudonym (else placeholder)
SHIFT_DATE = "SHIFT_DATE"                      # privacy layer shifts the date
GENERALIZE_AGE = "GENERALIZE_AGE"              # privacy layer bands the age
GENERALIZE_LOCATION = "GENERALIZE_LOCATION"    # privacy layer lifts village to tehsil/district
GENERALIZE_PIN = "GENERALIZE_PIN"              # privacy layer reduces the PIN
REENCODE = "REENCODE"                          # use ResolvedSpan.replacement (sanitized payload)
ACTIONS = (
    KEEP, REDACT, PSEUDONYMIZE, SHIFT_DATE, GENERALIZE_AGE, GENERALIZE_LOCATION,
    GENERALIZE_PIN, REENCODE,
)

# --------------------------------------------------------------------------- categories
PATIENT_NAME = "PATIENT_NAME"
RELATIVE_NAME = "RELATIVE_NAME"
PERSON_NAME = "PERSON_NAME"                    # a person whose role is unknown
PHONE = "PHONE"
PHONE_MASKED = "PHONE_MASKED"
EMAIL = "EMAIL"
AADHAAR = "AADHAAR"
AADHAAR_MASKED = "AADHAAR_MASKED"
ABHA_NUMBER = "ABHA_NUMBER"
ABHA_ADDRESS = "ABHA_ADDRESS"
PAN = "PAN"
MRN = "MRN"
INSURANCE_ID = "INSURANCE_ID"
OTHER_ID = "OTHER_ID"
DOB = "DOB"
ADDRESS = "ADDRESS"
HOUSE = "HOUSE"
LOCALITY = "LOCALITY"
LANDMARK = "LANDMARK"
VILLAGE = "VILLAGE"
PIN = "PIN"
PAYLOAD = "PAYLOAD"                            # an encoded payload that contained PII

PII_CATEGORIES = frozenset({
    PATIENT_NAME, RELATIVE_NAME, PERSON_NAME, PHONE, PHONE_MASKED, EMAIL, AADHAAR,
    AADHAAR_MASKED, ABHA_NUMBER, ABHA_ADDRESS, PAN, MRN, INSURANCE_ID, OTHER_ID, DOB,
    ADDRESS, HOUSE, LOCALITY, LANDMARK, VILLAGE, PIN, PAYLOAD,
})
NAME_CATEGORIES = frozenset({PATIENT_NAME, RELATIVE_NAME, PERSON_NAME})

# quasi-identifiers that are transformed, not removed, by default
DATE = "DATE"
AGE = "AGE"
GENDER = "GENDER"
TEHSIL = "TEHSIL"
DISTRICT = "DISTRICT"
QI_CATEGORIES = frozenset({DATE, AGE, GENDER, TEHSIL, DISTRICT})

# protected clinical and context values
MEDICATION = "MEDICATION"
DOSE = "DOSE"
FREQUENCY = "FREQUENCY"
DURATION = "DURATION"
VITAL = "VITAL"
LAB = "LAB"
LAB_RANGE = "LAB_RANGE"
DIAGNOSIS = "DIAGNOSIS"
DIAGNOSIS_CODE = "DIAGNOSIS_CODE"
PROCEDURE = "PROCEDURE"
COMPLAINT = "COMPLAINT"
HISTORY = "HISTORY"
EPONYM = "EPONYM"
DOCTOR = "DOCTOR"
WARD = "WARD"
DEPARTMENT = "DEPARTMENT"
ORGANIZATION = "ORGANIZATION"
CLINICAL_CONTEXT = "CLINICAL_CONTEXT"
PROTECTED_CATEGORIES = frozenset({
    MEDICATION, DOSE, FREQUENCY, DURATION, VITAL, LAB, LAB_RANGE, DIAGNOSIS, DIAGNOSIS_CODE,
    PROCEDURE, COMPLAINT, HISTORY, EPONYM, DOCTOR, WARD, DEPARTMENT, ORGANIZATION,
    CLINICAL_CONTEXT,
})

# span tiers, lower wins (plan section D3)
TIER_DIRECT_ID = 1
TIER_EXPLICIT_IDENTITY = 2
TIER_QUASI = 3          # dates and ages: beat weak names, lose to clinical protection
TIER_PROTECTED = 4
TIER_WEAK = 5

# release decisions (verifier terminal actions)
RELEASE = "RELEASE"
RESCRUB = "RESCRUB"
QUARANTINE = "QUARANTINE"
ABORT_RELEASE = "ABORT_RELEASE"


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
    action: str  # one of the ACTIONS constants above
    reason_code: str
    field_path: str = ""  # which FieldNode these offsets refer to
    replacement: str | None = None  # precomputed value for a REENCODE action
    attrs: dict = field(default_factory=dict)  # non-PII hints, e.g. detected date format


# --------------------------------------------------------------------------- identity
@dataclass
class ScopedIdentifier:
    """An identifier that is only unique within one system/hospital (e.g. an MRN)."""

    scope: str  # hospital or ID-system prefix, normalized (e.g. "hospital:snj")
    kind: str  # MRN | INSURANCE_ID | OTHER_ID
    value: str  # normalized value (digit core for MRNs)


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
class LeakFinding:
    """One thing the verifier found wrong with a candidate release. Position and
    category only -- never the matched text.
    """

    start: int
    end: int
    category: str
    channel: str = CONTENT


@dataclass
class VerificationResult:
    """Danish's independent judgement on whether a candidate release is safe to publish."""

    passed: bool
    safe_reason_codes: list[str] = field(default_factory=list)
    retry_allowed: bool = True
    terminal_action: str = RELEASE  # RELEASE | RESCRUB | QUARANTINE | ABORT_RELEASE
    findings: list[LeakFinding] = field(default_factory=list)
