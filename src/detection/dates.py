"""D4 helper: dates, dates of birth and ages in free text.

Dates are quasi-identifiers (action SHIFT_DATE); a date right after a birth label is a DOB.
Ages cover only the number ("48" in "48/F") so the privacy layer can band it in place.
Durations such as "x 12 yrs" or "10 yrs back" are never ages.
"""
from __future__ import annotations

import datetime as dt
import re

try:
    from .. import contracts as c
except ImportError:  # loaded as a top-level `detection` package (Omkar's sys.path layout)
    import contracts as c
from .gazetteer_data import MONTHS, MONTHS_DEVA

_MON = "|".join(sorted(MONTHS, key=len, reverse=True))
_MON_DEVA = "|".join(sorted(MONTHS_DEVA, key=len, reverse=True))

NUMERIC = re.compile(
    r"(?<![\d/\-.:])(\d{1,2})([/\-.])(\d{1,2})\2(\d{4}|\d{2})(?![\d/\-]|\.\d)")
ISO = re.compile(r"(?<![\d\-])(\d{4})-(\d{2})-(\d{2})(?:[T ](\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?)(Z|[+\-]\d{2}:?\d{2})?)?(?![\d])")
TEXT_DMY = re.compile(rf"(?<![\w])(\d{{1,2}})(?:st|nd|rd|th)?[\s\-]+({_MON})\.?,?[\s\-]+(\d{{4}}|\d{{2}})(?![\d])", re.IGNORECASE)
TEXT_MDY = re.compile(rf"(?<![\w])({_MON})\.?\s+(\d{{1,2}})(?:st|nd|rd|th)?,?\s+(\d{{4}})(?![\d])", re.IGNORECASE)
# no year: only capitalized month names, so "1 may be repeated" is not a date
TEXT_DM = re.compile(
    r"(?<![\w])(\d{1,2})(?:st|nd|rd|th)?\s+((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*)\b"
    r"(?![\s\-.,]*\d)")
DEVA_DMY = re.compile(rf"(\d{{1,2}})\s+({_MON_DEVA})\s+(\d{{4}})")

DOB_LABEL = re.compile(
    r"(?:\bDOB|\bD\.\s?O\.\s?B\.?|\bDate of Birth|\bBirth\s?Date|\bBorn on|\bJanm\s?Tithi|"
    r"\bbirthDate|जन्म\s?तिथि|जन्मतिथि|जन्म दिनांक)\"?\s*[:\-=]?\s*\"?$",
    re.IGNORECASE,
)

AGE_PATTERNS = [
    re.compile(r"(?:\bAge|\bAGE|\bage|\bAged|\baged|\bUmar|\bumar|आयु|उम्र)(?:\s*/\s*(?:Sex|Gender|लिंग))?\s*[:\-]?\s*(\d{1,3})(?!\d|\.\d|/\d)"),
    re.compile(r"(?<![\w/.])(\d{1,3})\s?(?:Y|Yr|Yrs|Years|yrs|years|yr|y)\.?\s?/\s?(?:M|F|Male|Female|male|female)\b"),
    re.compile(r"(?<![\w/.])(\d{1,3})\s?/\s?(?:M|F)\b"),
    re.compile(r"(?<![\w/.])(\d{1,3})\s?(?:वर्ष|साल)\s*/\s*(?:महिला|पुरुष|स्त्री)"),
    re.compile(r"(?<![\w/.])(\d{1,3})[\s\-]?(?:year|yr)s?[\s\-]old\b", re.IGNORECASE),
    re.compile(r"(?<![\w/.])(\d{1,3})\s?(?:Y|Yrs|yrs|years|Years)\s*,\s*(?:male|female|M|F)\b", re.IGNORECASE),
]
_DURATION_BEFORE = re.compile(r"(?:\bx|×|\bfor|\bsince|\blast|\bpast)\s*$", re.IGNORECASE)
_DURATION_AFTER = re.compile(r"^\s*(?:yrs?|years?)?\s*(?:back|ago|se|से)\b", re.IGNORECASE)


def _valid(y: int, m: int, d: int) -> dt.date | None:
    try:
        return dt.date(y, m, d)
    except ValueError:
        return None


def _year(s: str) -> int:
    y = int(s)
    if len(s) == 2:
        y += 2000 if y <= 40 else 1900
    return y


def infer_order(texts) -> str | None:
    """'dmy' or 'mdy' from numeric dates whose first or second part exceeds 12."""
    dmy = mdy = 0
    for t in texts:
        for m in NUMERIC.finditer(t):
            a, b = int(m.group(1)), int(m.group(3))
            if a > 12 >= b:
                dmy += 1
            elif b > 12 >= a:
                mdy += 1
    if dmy > mdy:
        return "dmy"
    if mdy > dmy:
        return "mdy"
    return None


def parse_numeric(day_or_month: str, month_or_day: str, year: str, order: str) -> dt.date | None:
    a, b, y = int(day_or_month), int(month_or_day), _year(year)
    if order == "mdy":
        return _valid(y, a, b) or _valid(y, b, a)
    return _valid(y, b, a) or _valid(y, a, b)


def find_dates(text: str, order: str | None = None) -> list[tuple[int, int, dt.date | None, str]]:
    """(start, end, parsed date or None, format tag) for every date-like span."""
    order = order or "dmy"
    out = []
    taken: list[tuple[int, int]] = []

    def add(s, e, d, fmt):
        if any(s < te and ts < e for ts, te in taken):
            return
        taken.append((s, e))
        out.append((s, e, d, fmt))

    for m in ISO.finditer(text):
        add(m.start(), m.end(), _valid(int(m.group(1)), int(m.group(2)), int(m.group(3))), "iso")
    for m in NUMERIC.finditer(text):
        d = parse_numeric(m.group(1), m.group(3), m.group(4), order)
        if d:
            add(m.start(), m.end(), d, f"{order}{m.group(2)}")
    for m in TEXT_DMY.finditer(text):
        d = _valid(_year(m.group(3)), MONTHS[m.group(2).casefold()], int(m.group(1)))
        add(m.start(), m.end(), d, "text_dmy")
    for m in TEXT_MDY.finditer(text):
        d = _valid(int(m.group(3)), MONTHS[m.group(1).casefold()], int(m.group(2)))
        add(m.start(), m.end(), d, "text_mdy")
    for m in DEVA_DMY.finditer(text):
        d = _valid(int(m.group(3)), MONTHS_DEVA[m.group(2)], int(m.group(1)))
        add(m.start(), m.end(), d, "deva_dmy")
    for m in TEXT_DM.finditer(text):
        if m.group(2).casefold() in MONTHS:
            add(m.start(), m.end(), None, "text_dm")
    return sorted(out)


def detect_dates_and_ages(text: str, order: str | None = None) -> list[c.SpanCandidate]:
    out: list[c.SpanCandidate] = []
    for s, e, _d, fmt in find_dates(text, order):
        is_dob = bool(DOB_LABEL.search(text[max(0, s - 24):s]))
        if is_dob:
            out.append(c.SpanCandidate(s, e, c.DOB, "patient", 0.95, c.TIER_EXPLICIT_IDENTITY,
                                       f"dob:{fmt}", c.SHIFT_DATE))
        else:
            out.append(c.SpanCandidate(s, e, c.DATE, None, 0.9, c.TIER_QUASI, f"date:{fmt}",
                                       c.SHIFT_DATE))
    seen = set()
    for rx in AGE_PATTERNS:
        for m in rx.finditer(text):
            s, e = m.start(1), m.end(1)
            if (s, e) in seen:
                continue
            if _DURATION_BEFORE.search(text[max(0, s - 8):s]) or _DURATION_AFTER.match(text[e:e + 12]):
                continue
            age = int(m.group(1))
            if age > 120:
                continue
            seen.add((s, e))
            out.append(c.SpanCandidate(s, e, c.AGE, "patient", 0.9, c.TIER_QUASI, "age",
                                       c.GENERALIZE_AGE))
    return out
