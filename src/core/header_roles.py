"""Single shared table for CSV/TSV header-name role detection.

This exists so "which header means age / village / PIN / date / patient-identity" is
defined in exactly ONE place. Before this module, the same decision was duplicated with
slightly different literal sets in main.py, privacy/apply_generalization.py and
export/csv_writer.py -- a header recognized by one and missed by another silently broke
generalization or pseudonym embedding for that column.

This is still a conservative, exact-match (after normalization) heuristic, not real field
classification. Danish's field classifier (D5) is the long-term source of truth via
`FieldNode.role_hint`; this table is only the fallback used until that lands, and it is
intentionally narrow so it never guesses on a genuinely ambiguous header.

Normalization: lowercase, declared date-format suffix like "(MM/DD/YYYY)" stripped,
whitespace/underscore/hyphen runs collapsed to a single space. This means "Patient_Name",
"patient-name" and "Patient Name" all normalize to "patient name" and compare equal.
"""
from __future__ import annotations

import re

_DECLARED_DATE_FORMAT_RE = re.compile(
    r"\(\s*(MM|DD)\s*[/.-]\s*(DD|MM)\s*[/.-]\s*YYYY\s*\)", re.IGNORECASE
)

AGE_HEADERS = {
    "age", "age (yrs)", "age yrs", "patient age", "age in years",
    # "Umar" (Hindi/Hinglish for age) is the practice data's actual header in
    # registration/jeevanjyoti_patients.tsv. Deliberately only adding the term
    # confirmed from real data here, not the wider set of synonyms Danish's
    # detection.field_classifier recognizes (e.g. "umr", "aayu") -- this table is a
    # blunt exact-match fallback used wherever a header name alone must decide a
    # column's role (e.g. CSV generalization), and test_unrecognised_village_column_is_
    # redacted shows an unfamiliar header deliberately falling through to the engine's
    # own value-based detection is a real, relied-upon behaviour, not a gap to close
    # speculatively.
    "umar", "आयु", "उम्र",
}

VILLAGE_HEADERS = {
    "village/mohalla", "village", "mohalla", "gram", "gram/mohalla",
    "gram panchayat", "gaon", "village name",
    "ग्राम", "गाँव", "गांव",
}

TEHSIL_HEADERS = {"tehsil", "taluka", "block", "तहसील"}

DISTRICT_HEADERS = {"district", "zila", "jila", "जिला"}

PIN_HEADERS = {"pin", "pincode", "pin code", "postal code", "zip", "zip code"}

DATE_HEADERS = {
    "reg date", "registered", "dob", "date of birth", "admission date",
    "discharge date", "visit date", "collected on", "reported on", "report date",
    "bill date", "claim date",
    # "Janm Tithi" (Hindi for date of birth) is the practice data's actual header in
    # registration/jeevanjyoti_patients.tsv -- without this, that column's DOB values
    # were neither shifted nor redacted, a real, measured 20.7% DOB leak confirmed by
    # the organiser's own check_dev.py before this fix, 0.0% after.
    "janm tithi", "janm", "जन्म तिथि", "जन्म",
}

# Ordered from strongest reference/identifier columns to name-like identity locations;
# the first match wins, so a scoped identifier column is preferred over a bare "name".
PATIENT_IDENTITY_HEADERS = (
    "patient ref", "patient id", "patientid", "uhid", "mrn", "patient",
    "patient name", "patient's name", "name",
)


def normalize_header(header: str) -> str:
    without_format = _DECLARED_DATE_FORMAT_RE.sub("", header)
    return re.sub(r"[\s_-]+", " ", without_format).strip().lower()


def declared_date_hint(header: str) -> str | None:
    """Return "mdy"/"dmy" if the header itself declares a date order, else None."""
    match = _DECLARED_DATE_FORMAT_RE.search(header)
    if not match:
        return None
    return "mdy" if match.group(1).upper() == "MM" else "dmy"


def role_for_header(header: str) -> str | None:
    """Return "age" | "village" | "tehsil" | "district" | "pin" | "date" | None."""
    normalized = normalize_header(header)
    if normalized in AGE_HEADERS:
        return "age"
    if normalized in VILLAGE_HEADERS:
        return "village"
    if normalized in TEHSIL_HEADERS:
        return "tehsil"
    if normalized in DISTRICT_HEADERS:
        return "district"
    if normalized in PIN_HEADERS:
        return "pin"
    if normalized in DATE_HEADERS:
        return "date"
    return None


def find_column(header: list[str], role: str) -> int | None:
    """Return the first column index in `header` whose normalized name has `role`."""
    for index, value in enumerate(header):
        if role_for_header(value) == role:
            return index
    return None


def find_patient_identity_column(header: list[str]) -> int | None:
    normalized = [normalize_header(value) for value in header]
    for candidate in PATIENT_IDENTITY_HEADERS:
        if candidate in normalized:
            return normalized.index(candidate)
    return None
