"""Shared interfaces between the pipeline (Omkar) and detection/verification (Danish).

Status: PROPOSED. These follow section 2 of the two-person plan. Fields marked
"ADDITION" are not in the plan; both owners must approve them before relying on them.

Nothing in these objects may be logged or serialized outside the release itself.
Raw values in FieldNode and IdentityEvidence stay in memory only.
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
KEEP = "KEEP"                          # protected value, informational only
REDACT = "REDACT"                      # replace with a typed placeholder
PSEUDONYMIZE = "PSEUDONYMIZE"          # replace with the record's pseudonym (else placeholder)
SHIFT_DATE = "SHIFT_DATE"              # privacy layer shifts the date
GENERALIZE_AGE = "GENERALIZE_AGE"      # privacy layer bands the age
GENERALIZE_LOCATION = "GENERALIZE_LOCATION"  # privacy layer lifts village to tehsil/district
GENERALIZE_PIN = "GENERALIZE_PIN"      # privacy layer reduces the PIN
REENCODE = "REENCODE"                  # use ResolvedSpan.replacement (sanitized payload)
ACTIONS = (KEEP, REDACT, PSEUDONYMIZE, SHIFT_DATE, GENERALIZE_AGE, GENERALIZE_LOCATION,
           GENERALIZE_PIN, REENCODE)

# --------------------------------------------------------------------------- categories
PATIENT_NAME = "PATIENT_NAME"
RELATIVE_NAME = "RELATIVE_NAME"
PERSON_NAME = "PERSON_NAME"            # a person whose role is unknown
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
PAYLOAD = "PAYLOAD"                    # an encoded payload that contained PII

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


# --------------------------------------------------------------------------- Omkar -> Danish
@dataclass
class FieldNode:
    path: str
    value: object
    value_type: str               # "str" | "int" | "float" | "bool" | "null"
    channel: str = CONTENT
    role_hint: str | None = None  # CSV header text or JSON key


@dataclass
class RecordEnvelope:
    record_id: str
    file_sha256: str
    locator: str                  # row:N, RFC 6901 pointer, doc, or "@file" (file-level channels)
    format: str                   # csv | tsv | json | fhir | text
    fields: list[FieldNode] = field(default_factory=list)
    free_text: str | None = None
    rendering_metadata: dict = field(default_factory=dict)


@dataclass
class FileEnvelope:
    input_sha256: str
    relative_path: str
    detected_format: str
    detected_encoding: str | None
    size_bytes: int
    records: list[RecordEnvelope] = field(default_factory=list)
    terminal_status: str | None = None


# --------------------------------------------------------------------------- Danish -> Omkar
@dataclass
class SpanCandidate:
    start: int
    end: int
    category: str
    role: str | None
    confidence: float
    tier: int
    source: str
    proposed_action: str


@dataclass
class ResolvedSpan:
    start: int
    end: int
    category: str
    action: str
    reason_code: str
    field_path: str = ""                       # ADDITION: which FieldNode the offsets refer to
    replacement: str | None = None             # ADDITION: precomputed value for REENCODE
    attrs: dict = field(default_factory=dict)  # ADDITION: non-PII hints (date format, primary name)


@dataclass
class ScopedIdentifier:                         # ADDITION: referenced by the plan, never defined
    scope: str                                  # hospital or ID-system prefix, normalized
    kind: str                                   # MRN | INSURANCE_ID | OTHER_ID
    value: str                                  # normalized value (digit core for MRNs)


@dataclass
class IdentityEvidence:
    record_id: str
    patient_names: list[str] = field(default_factory=list)
    relative_names: list[str] = field(default_factory=list)
    doctor_names: list[str] = field(default_factory=list)
    national_ids: dict[str, str] = field(default_factory=dict)
    scoped_ids: list[ScopedIdentifier] = field(default_factory=list)
    phones: list[str] = field(default_factory=list)
    date_of_birth: str | None = None
    age: int | None = None
    gender: str | None = None
    village: str | None = None
    tehsil: str | None = None
    district: str | None = None
    hospital: str | None = None


# --------------------------------------------------------------------------- Omkar's objects
@dataclass
class ClusterAssignment:
    record_id: str
    cluster_key: str | None
    decision: str                 # MUST_LINK | PROBABLE_LINK | UNRESOLVED | CANNOT_LINK
    evidence_codes: list[str] = field(default_factory=list)


@dataclass
class FieldTransformation:                      # ADDITION: placeholder for Omkar to define
    field_path: str
    action: str
    params: dict = field(default_factory=dict)


@dataclass
class TransformPlan:
    record_id: str
    pseudonym: str | None
    date_offset_days: int
    resolved_spans: list[ResolvedSpan] = field(default_factory=list)
    field_transformations: list[FieldTransformation] = field(default_factory=list)
    status: str = "sanitized"


# --------------------------------------------------------------------------- verification
RELEASE = "RELEASE"
RESCRUB = "RESCRUB"
QUARANTINE = "QUARANTINE"
ABORT_RELEASE = "ABORT_RELEASE"


@dataclass
class LeakFinding:                              # ADDITION: position and kind, never the value
    start: int
    end: int
    category: str
    channel: str = CONTENT


@dataclass
class VerificationResult:
    passed: bool
    safe_reason_codes: list[str] = field(default_factory=list)
    retry_allowed: bool = False
    terminal_action: str = RELEASE
    findings: list[LeakFinding] = field(default_factory=list)  # ADDITION
