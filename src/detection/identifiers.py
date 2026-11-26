"""D4: direct identifiers in free text and field values.

All patterns run on a normalized TextView (ASCII digits, no zero-width characters).
No checksum is required: the data is synthetic.

Hospital identifiers (UHID, MRN, IPD, registration numbers) are found three ways:
  1. a label in front of them ("UHID:", "Reg No", "पंजीकरण सं."),
  2. a generic ID shape (letters + separators + 5..8 digits, uppercase in content),
  3. templates learned at run time from structured ID columns (see `id_template`),
     so an unseen hospital's ID format is still caught in free text.
"""
from __future__ import annotations

import re
from functools import lru_cache

try:
    from .. import contracts as c
except ImportError:  # loaded as a top-level `detection` package (Omkar's sys.path layout)
    import contracts as c

_B = r"(?<![A-Za-z0-9+])(?<!\d[ \t\-.])"      # not inside a longer token or digit run
_E = r"(?![ \t\-.]?\d)(?![A-Za-z0-9])"

PHONE = re.compile(
    _B + r"(?:(?:\+|00)[ \t]?91[ \t\-.]?|91[ \t\-]|0)?\(?[6-9](?:[ \t\-.)]?\d){9}" + _E)
PHONE_LABELLED = re.compile(
    r"(?:\bMob(?:ile)?|\bPh(?:one)?|\bTel(?:ephone)?|\bContact|\bCell|\bWhatsApp|\bCallback|"
    r"\bcall(?:ed)?(?:\s+on)?|मोबाइल|मो\.|फ़ोन|फोन|संपर्क)\.?[ \t]*(?:No\.?|Number|#)?[ \t]*[:\-]?[ \t]*"
    r"(\+?\(?\d[\d \t\-().]{7,18}\d)(?![\d])",
    re.IGNORECASE,
)
PHONE_MASKED = re.compile(
    r"(?<![A-Za-z0-9])(?:\+?91[\s\-]?)?[6-9][\dXx*]{1,4}[Xx*]{3,8}[\dXx*]{0,4}\d(?![A-Za-z0-9])")
AADHAAR = re.compile(_B + r"[2-9]\d{3}([ \t\-.]?)\d{4}\1\d{4}" + _E)
AADHAAR_MASKED = re.compile(
    r"(?<![A-Za-z0-9])[Xx*]{4}[\s\-]?[Xx*]{4}[\s\-]?\d{4}(?![A-Za-z0-9])"
    r"|(?<![A-Za-z0-9])[Xx*]{8}\d{4}(?![A-Za-z0-9])")
ABHA = re.compile(_B + r"\d{2}([ \t\-]?)\d{4}\1\d{4}\1\d{4}" + _E)
ABHA_ADDRESS = re.compile(r"(?<![\w.])[A-Za-z0-9._]{3,40}@(?:abdm|sbx|ndhm|abha)\b", re.IGNORECASE)
EMAIL = re.compile(r"(?<![\w.+\-])[A-Za-z0-9._%+\-]{1,64}@[A-Za-z0-9\-]+(?:\.[A-Za-z0-9\-]+)*\.[A-Za-z]{2,}")
PAN = re.compile(r"(?<![A-Za-z0-9])[A-Z]{5}\d{4}[A-Z](?![A-Za-z0-9])")
INSURANCE = re.compile(
    r"(?<![A-Za-z0-9])PM[\s\-]?JAY[\s\-/]?(?:[A-Z]{2}[\s\-/]?)?\d{6,14}(?![A-Za-z0-9])"
    r"|(?<![A-Za-z0-9])(?:POL|POLICY|INS|CLM|AB-?PMJAY|ABPMJAY|ESIC?|CGHS)[\s\-/]?(?:\d{1,4}[\-/])?\d{5,14}(?![A-Za-z0-9])",
    re.IGNORECASE,
)
INSURANCE_LABELLED = re.compile(
    r"(?:Policy|Insurance|Insurer|Member|Beneficiary|Ayushman|PMJAY|Card|Claim\s?ID|TPA)\s*"
    r"(?:No\.?|Number|ID|Id|#)\s*[:\-]?\s*([A-Za-z0-9][A-Za-z0-9/\-]{4,30})",
    re.IGNORECASE,
)

_ID_TAIL = r"(?![A-Za-z0-9])(?![/\-]\d)"
HOSPITAL_ID = re.compile(
    r"(?<![A-Za-z0-9/\-])(?:"
    r"[A-Z]{2,6}[/\-]\d{2,4}[/\-]\d{4,8}"          # SNJ/26/052715, IPD-2026-00243
    r"|[A-Z]{2,6}\d{2,4}[/\-]\d{4,8}"               # DHH2026-018208
    r"|[A-Z]{2,6}[/\-][A-Z]{2,4}[/\-]\d{4,8}"       # DHH-IPD-00162
    r"|[A-Z]{2,6}[/\-]?\d{5,8}"                     # JJH-0006739, ADM000524
    r")" + _ID_TAIL
)
HOSPITAL_ID_CI = re.compile(HOSPITAL_ID.pattern, re.IGNORECASE)  # for filenames and paths
ID_LABEL = re.compile(
    r"(?:\bUHID|\bMRN|\bMR\s?No|\bCR\s?No|\bReg(?:istration)?\.?\s?(?:No|Number|#|ID)|\bIPD\s?(?:No|Number|#)|"
    r"\bIP\s?No|\bAdm(?:ission)?\.?\s?(?:No|Number|ID)|\bPatient\s?(?:ID|Id|No|#)|\bHosp(?:ital)?\.?\s?(?:No|ID|Id)|"
    r"\bCase\s?No|\bFile\s?No|\bPID|पंजीकरण\s?(?:सं|संख्या|नं)|आईपीडी\s?(?:सं|संख्या|नं)|भर्ती\s?(?:सं|संख्या)|"
    r"रजिस्ट्रेशन\s?(?:नं|सं))\.?\s*[:#\-]?\s*"
    r"([A-Za-z0-9][A-Za-z0-9/\-]{2,24}[0-9])(?![A-Za-z0-9/\-])"
)


def _cand(s, e, category, source, confidence=0.95, action=c.REDACT, role="patient"):
    return c.SpanCandidate(s, e, category, role, confidence, c.TIER_DIRECT_ID, source, action)


def _digit_count(s: str) -> int:
    return sum(ch.isdigit() for ch in s)


def detect_identifiers(text: str, templates: "IdTemplates | None" = None,
                       case_insensitive_ids: bool = False) -> list[c.SpanCandidate]:
    out: list[c.SpanCandidate] = []
    for m in EMAIL.finditer(text):
        out.append(_cand(m.start(), m.end(), c.EMAIL, "email"))
    for m in ABHA_ADDRESS.finditer(text):
        out.append(_cand(m.start(), m.end(), c.ABHA_ADDRESS, "abha_address"))
    for m in ABHA.finditer(text):
        out.append(_cand(m.start(), m.end(), c.ABHA_NUMBER, "abha", 0.9))
    for m in AADHAAR.finditer(text):
        out.append(_cand(m.start(), m.end(), c.AADHAAR, "aadhaar", 0.9))
    for m in AADHAAR_MASKED.finditer(text):
        out.append(_cand(m.start(), m.end(), c.AADHAAR_MASKED, "aadhaar_masked", 0.9))
    for m in PHONE.finditer(text):
        out.append(_cand(m.start(), m.end(), c.PHONE, "phone"))
    for m in PHONE_LABELLED.finditer(text):
        n = _digit_count(m.group(1))
        if 10 <= n <= 13:
            out.append(_cand(m.start(1), m.end(1), c.PHONE, "phone_label"))
    for m in PHONE_MASKED.finditer(text):
        tok = m.group(0)
        if sum(ch in "Xx*" for ch in tok) >= 3 and 10 <= len(re.sub(r"[\s\-+]", "", tok)) <= 12:
            out.append(_cand(m.start(), m.end(), c.PHONE_MASKED, "phone_masked", 0.85))
    for m in PAN.finditer(text):
        out.append(_cand(m.start(), m.end(), c.PAN, "pan", 0.9))
    for m in INSURANCE.finditer(text):
        out.append(_cand(m.start(), m.end(), c.INSURANCE_ID, "insurance"))
    for m in INSURANCE_LABELLED.finditer(text):
        if _digit_count(m.group(1)) >= 4:
            out.append(_cand(m.start(1), m.end(1), c.INSURANCE_ID, "insurance_label", 0.85))
    for m in ID_LABEL.finditer(text):
        if _digit_count(m.group(1)) >= 3:
            out.append(_cand(m.start(1), m.end(1), c.MRN, "id_label"))
    rx = HOSPITAL_ID_CI if case_insensitive_ids else HOSPITAL_ID
    for m in rx.finditer(text):
        out.append(_cand(m.start(), m.end(), c.MRN, "id_shape", 0.8))
    if templates is not None:
        for s, e in templates.find(text, case_insensitive_ids):
            out.append(_cand(s, e, c.MRN, "id_template", 0.95))
    return out


# --------------------------------------------------------------------------- learned templates
_TPL_PART = re.compile(r"[A-Za-z]+|\d+|[^A-Za-z\d]+")


@lru_cache(maxsize=4096)
def id_template(value: str) -> str | None:
    """Regex template for an ID value seen in a structured ID column.

    Letters are kept literally, digit runs become \\d{n-1,n+1}, separators are kept.
    Returns None for values that are too generic to learn (no letters, or too short).
    """
    v = value.strip()
    if not v or len(v) > 32 or not re.search(r"\d", v):
        return None
    parts = _TPL_PART.findall(v)
    if not any(p.isalpha() for p in parts) or sum(len(p) for p in parts if p.isdigit()) < 4:
        return None
    out = []
    for p in parts:
        if p.isdigit():
            n = len(p)
            out.append(rf"\d{{{max(1, n - 1)},{n + 1}}}")
        elif p.isalpha():
            out.append(re.escape(p.upper()))
        else:
            out.append(re.escape(p))
    return "".join(out)


class IdTemplates:
    """A set of learned ID templates, compiled into one alternation."""

    def __init__(self) -> None:
        self._templates: set[str] = set()
        self._rx: re.Pattern | None = None
        self._rx_ci: re.Pattern | None = None

    def add(self, value: str) -> bool:
        tpl = id_template(value)
        if tpl and tpl not in self._templates:
            self._templates.add(tpl)
            self._rx = self._rx_ci = None
            return True
        return False

    def __len__(self) -> int:
        return len(self._templates)

    def _compile(self, ci: bool) -> re.Pattern | None:
        if not self._templates:
            return None
        body = "|".join(sorted(self._templates, key=lambda t: (-len(t), t)))
        pat = r"(?<![A-Za-z0-9])(?:" + body + r")(?![A-Za-z0-9])"
        return re.compile(pat, re.IGNORECASE if ci else 0)

    def find(self, text: str, ci: bool = False) -> list[tuple[int, int]]:
        if ci:
            if self._rx_ci is None:
                self._rx_ci = self._compile(True)
            rx = self._rx_ci
        else:
            if self._rx is None:
                self._rx = self._compile(False)
            rx = self._rx
        return [(m.start(), m.end()) for m in rx.finditer(text)] if rx else []


def id_digit_core(value: str) -> str:
    """Digit core used by the scorer: the last digit run of a hospital ID ("052715")."""
    runs = re.findall(r"\d+", value)
    return runs[-1] if runs else ""


def id_scope(value: str) -> str:
    """Hospital or ID-system prefix of an identifier ("SNJ", "JJH", "IP")."""
    m = re.match(r"\s*([A-Za-z]+)", value)
    return m.group(1).upper() if m else ""
