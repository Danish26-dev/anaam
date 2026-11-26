"""Compatibility shim: `src.contracts` re-exports the reconciled shared contract.

Omkar's pipeline and Danish's detection/verification engine were built in parallel and
each independently drafted a version of the shared dataclasses and vocabulary (Omkar's
`src/core/interfaces.py`, Danish's proposed `src/contracts.py`). Once both halves existed,
the two were reconciled into a single source of truth at `src/core/interfaces.py` (see
that module's docstring for exactly what changed and why).

Danish's detection and verification modules, and their tests, import this module as
`from .. import contracts as c` / `from src import contracts as c` and reference dozens of
names via `c.X`. Rather than rewrite every one of those call sites, this module re-exports
the reconciled contract under the same name, so `c.ResolvedSpan`, `c.ScopedIdentifier`,
`c.PATIENT_NAME`, etc. all resolve to the single real definition in `core.interfaces`.

Do not add new definitions here. Add them to `core/interfaces.py` and they will appear
here automatically via the star import.
"""
from __future__ import annotations

import sys
from pathlib import Path

# This module is reachable two ways depending on which half of the team imported it:
#   * Omkar's pipeline adds `src/` itself to sys.path, so `core.interfaces` resolves
#     directly as a top-level package.
#   * Danish's tests put the repo ROOT on sys.path and import this as `src.contracts`,
#     so `src/` is never on sys.path and a plain `from core.interfaces import ...` fails.
# Ensuring `src/`'s parent... no: ensuring `src/` itself is on sys.path here makes both
# import styles resolve to the exact same module object (no duplicate class definitions,
# so isinstance/dataclass identity checks keep working either way).
_SRC_DIR = Path(__file__).resolve().parent
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

from core.interfaces import *  # noqa: F401,F403,E402
from core.interfaces import (  # noqa: F401,E402
    ABHA_ADDRESS,
    ABHA_NUMBER,
    AADHAAR,
    AADHAAR_MASKED,
    ABORT_RELEASE,
    ACTIONS,
    ADDRESS,
    AGE,
    BASE64,
    CHANNELS,
    CLINICAL_CONTEXT,
    COMPLAINT,
    CONTENT,
    DATE,
    DEPARTMENT,
    DIAGNOSIS,
    DIAGNOSIS_CODE,
    DISTRICT,
    DOB,
    DOCTOR,
    DOSE,
    DURATION,
    EMAIL,
    EPONYM,
    FHIR_NARRATIVE,
    FILENAME,
    FREQUENCY,
    GENDER,
    GENERALIZE_AGE,
    GENERALIZE_LOCATION,
    GENERALIZE_PIN,
    HEADER,
    HISTORY,
    HOUSE,
    INSURANCE_ID,
    KEEP,
    KEY,
    LAB,
    LAB_RANGE,
    LANDMARK,
    LOCALITY,
    MEDICATION,
    METADATA,
    MRN,
    NAME_CATEGORIES,
    ORGANIZATION,
    OTHER_ID,
    PAN,
    PATIENT_NAME,
    PAYLOAD,
    PERSON_NAME,
    PHONE,
    PHONE_MASKED,
    PII_CATEGORIES,
    PIN,
    PROCEDURE,
    PROTECTED_CATEGORIES,
    PSEUDONYMIZE,
    QI_CATEGORIES,
    REDACT,
    REENCODE,
    RELATIVE_NAME,
    RELEASE,
    RESCRUB,
    QUARANTINE,
    SHIFT_DATE,
    TEHSIL,
    TIER_DIRECT_ID,
    TIER_EXPLICIT_IDENTITY,
    TIER_PROTECTED,
    TIER_QUASI,
    TIER_WEAK,
    VILLAGE,
    VITAL,
    WARD,
    ClusterAssignment,
    FieldNode,
    FieldTransformation,
    FileEnvelope,
    IdentityEvidence,
    LeakFinding,
    RecordEnvelope,
    ResolvedSpan,
    ScopedIdentifier,
    SpanCandidate,
    TransformPlan,
    VerificationResult,
)
