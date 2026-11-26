"""D2: compiled regular expressions for the Clinical Shield."""
from __future__ import annotations

import re

from . import clinical_lexicon as lx


def _alt(words, escape=True) -> str:
    items = sorted({w for w in words if w}, key=lambda w: (-len(w), w))
    return "|".join(re.escape(w) if escape else w for w in items)


_DOSE_UNIT = _alt(lx.DOSE_UNITS)
_LAB_UNIT = _alt(lx.LAB_UNITS)
_NUM = r"\d+(?:\.\d+)?"

DOSE = re.compile(
    # `-[0-9a-f]{4}` after the unit: the start of a UUID such as "81cc-7d1e-...", not a dose
    rf"(?<![\w.]){_NUM}(?:\s?/\s?{_NUM})?\s?(?:{_DOSE_UNIT})(?![A-Za-z]|-[0-9a-fA-F]{{4}})"
    rf"(?:\s?\+\s?{_NUM}\s?(?:{_DOSE_UNIT})(?![A-Za-z]))*"
)
FREQ_PATTERN = re.compile(r"(?<![\d/\-.])[0-2](?:\s?-\s?[0-2]){2,3}(?![\d/\-])")
FREQ_WORD = re.compile(rf"\b(?:{_alt(lx.FREQUENCY_WORDS)})\b")
DURATION = re.compile(
    r"\b(?:x|X|×|for)\s?\d+\s?(?:days?|d|wks?|weeks?|months?|mths?|month|yrs?|years?)\b"
    r"|\d+\s?(?:दिन|सप्ताह|महीने)"
)
ROUTE = re.compile(r"\b(?:IV|IM|SC|PO|SL|stat|STAT)\b")

DRUG = re.compile(rf"\b(?:{_alt(lx.DRUGS)})\b", re.IGNORECASE)
FORM = re.compile(rf"\b(?:{_alt(lx.DOSAGE_FORMS)})\.?(?=\s)", re.IGNORECASE)

VITAL = re.compile(
    r"\bBP\s*[:\-]?\s*\d{2,3}\s?/\s?\d{2,3}(?:\s?mm\s?Hg)?"
    r"|\b(?:Pulse|PR|HR|Heart rate|pulse)\s*[:\-]?\s*\d{2,3}(?:\s?(?:/min|bpm|/minute))?"
    r"|\b(?:Temp(?:erature)?|temp|Bukhar|bukhar|Fever|fever)\s*[:\-]?\s*\d{2,3}(?:\.\d)?\s?°?\s?[FC]\b"
    r"|\bSpO2\s*[:\-]?\s*\d{2,3}\s?%"
    r"|\b(?:RR|Resp(?:iratory)? rate)\s*[:\-]?\s*\d{1,2}(?:\s?/min)?"
    r"|\b(?:Weight|Wt|weight)\s*[:\-]?\s*\d{1,3}(?:\.\d)?\s?kg"
    r"|\bबुखार\s*\d{2,3}"
)
# Short all-caps test abbreviations match case-sensitively: lower-case "pt" is Hinglish for
# patient ("pt ka BP") and "pt-422" is a FHIR patient id, not prothrombin time.
_LAB_ABBR = [t for t in lx.LAB_TESTS if t.isupper() and len(t) <= 5]
_LAB_WORDS = [t for t in lx.LAB_TESTS if t not in _LAB_ABBR]
_LAB_TEST = rf"(?:(?i:{_alt(_LAB_WORDS)})|{_alt(_LAB_ABBR)})"
LAB = re.compile(rf"\b{_LAB_TEST}\b\s*[:\-=]?\s*{_NUM}(?:\s?(?i:{_LAB_UNIT}))?")
LAB_GENERIC = re.compile(rf"\b[A-Za-z][A-Za-z ]{{2,30}}?\s{_NUM}\s?(?:{_LAB_UNIT})(?![A-Za-z])")
LAB_NAME = re.compile(rf"\b{_LAB_TEST}\b")
LAB_RANGE_CTX = re.compile(
    rf"(?:range|ref\.?|normal|bio\.? ref\.?)\s*[:\-]?\s*({_NUM}\s?-\s?{_NUM})", re.IGNORECASE)
RANGE_VALUE = re.compile(rf"^\s*{_NUM}\s?-\s?{_NUM}\s*$")

ICD10 = re.compile(r"(?<![A-Za-z0-9/\-.])[A-TV-Z][0-9]{2}(?:\.[0-9A-Z]{1,4})?(?![A-Za-z0-9/\-])")
LOINC_CTX = re.compile(r"\bLOINC\b\s*[:\-]?\s*(\d{3,6}-\d)", re.IGNORECASE)

DISEASE = re.compile(rf"\b(?:{_alt(lx.DISEASES)})\b", re.IGNORECASE)
EPONYM = re.compile(
    rf"\b[A-Za-z][a-z]+['\u2019]s\s+(?:{_alt(lx.EPONYM_HEADS)})\b"
    rf"|\b[A-Z][a-z]{{3,}}\s+(?:disease|syndrome|palsy)\b",
    re.IGNORECASE,
)
PROCEDURE = re.compile(rf"\b(?:{_alt(lx.PROCEDURES)})\b", re.IGNORECASE)

COMPLAINT_HEAD = re.compile(r"\bC\s?/\s?O\b\s*[:\-]?\s*", re.IGNORECASE)
HISTORY_HEAD = re.compile(
    r"\b(?:K\s?/\s?C\s?/\s?O|H\s?/\s?O|known case of|history of|h/o|k/c/o)\b\s*[:\-]?\s*",
    re.IGNORECASE,
)
COMPLAINT_LABEL = re.compile(
    r"\b(?:Presenting complaints?|Chief complaints?|Complaints?)\s*[:\-]\s*", re.IGNORECASE)
CLAUSE_END = re.compile(r"\n|\.\s|\.$|;|\|")

_DEGREES = _alt(lx.DEGREES)
DOCTOR = re.compile(
    r"\b(?:Dr|DR|Doctor|dr)\.?\s+"
    r"((?:[A-Z]\.\s?){0,2}(?:[A-Z][a-zA-Z'\-]+|[A-Z]{2,})(?:\s+(?:[A-Z]\.\s?)?(?:[A-Z][a-zA-Z'\-]+|[A-Z]{2,})){0,3})"
    r"(?:\s*\((?:[^()\n]{1,60})\)|,?\s+(?:" + _DEGREES + r")\b(?:\s*\([^()\n]{1,40}\))?)?"
)
DOCTOR_DEVA = re.compile(r"(?:डॉ|डा|डॉक्टर)\.?\s*([\u0900-\u097F]+(?:\s+[\u0900-\u097F]+){0,2})")

WARD = re.compile(r"\bWard\s*(?:No\.?\s*)?\d+[A-Z]?(?:\s*\(\s*[A-Za-z &]+\s*\))?", re.IGNORECASE)
BED = re.compile(r"\bBed\s*(?:No\.?\s*)?\d+\b", re.IGNORECASE)
DEPARTMENT = re.compile(rf"\b(?:{_alt(lx.DEPARTMENTS)})\b")

_ORG_SUFFIX = _alt(lx.ORG_SUFFIXES)
ORGANIZATION = re.compile(
    rf"\b(?:(?:[A-Z][a-zA-Z]+|[A-Z]{{2,}})\s+){{1,5}}(?:{_ORG_SUFFIX})\b"
    rf"|\b(?:(?:[A-Z]{{2,}})\s+){{1,5}}(?:{_ORG_SUFFIX.upper()})\b"
)
CONTEXT = re.compile(rf"\b(?:{_alt(lx.CONTEXT_PHRASES)})\b")
