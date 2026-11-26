"""O6: canonicalization helpers for identity candidate generation.

These turn raw IdentityEvidence fields into comparable keys. Danish's normalization
(src/detection/normalization.py) handles script/Unicode-level normalization; this module
handles the identity-specific canonical forms (digits-only phone, name token sets, ...).
"""
from __future__ import annotations

import re

_DIGITS_RE = re.compile(r"\D+")


def canonical_digits(value: str) -> str:
    """Strip everything but digits -- for phone/Aadhaar/ABHA/PAN-ish comparisons."""
    return _DIGITS_RE.sub("", value or "")


def canonical_phone(value: str) -> str:
    """Last 10 digits, so +91 prefixes and separators do not create false distinctions."""
    digits = canonical_digits(value)
    return digits[-10:] if len(digits) >= 10 else digits


def canonical_name_tokens(name: str) -> tuple[str, ...]:
    """Lowercased, whitespace-split tokens, stripped of common honorifics.

    This is intentionally conservative: it does NOT do fuzzy/phonetic matching (that is a
    separate, lower-confidence candidate pass per O6). It only normalizes case/spacing/
    honorifics so "TARUN VELLAN" and "tarun vellan" compare equal.
    """
    honorifics = {"ji", "sahab", "didi", "shri", "smt", "mr", "mrs", "dr", "md"}
    tokens = re.split(r"[\s.]+", name.strip().lower())
    return tuple(t for t in tokens if t and t not in honorifics)


def canonical_dob(value: str) -> str | None:
    """Best-effort DOB normalization to ISO (YYYY-MM-DD). Returns None if unparseable.

    Accepts "DD/MM/YYYY" (the practice data's dominant format) and ISO input as-is.
    """
    if not value:
        return None
    value = value.strip()
    iso = re.match(r"^(\d{4})-(\d{2})-(\d{2})$", value)
    if iso:
        return value
    dmy = re.match(r"^(\d{1,2})/(\d{1,2})/(\d{4})$", value)
    if dmy:
        d, m, y = dmy.groups()
        return f"{y}-{int(m):02d}-{int(d):02d}"
    return None


def phonetic_name_key(name: str) -> str | None:
    """Return a conservative Soundex-style key for Latin name tokens.

    This key is used only for residual candidate generation. It never establishes a link
    by itself; scoring still requires exact canonical name evidence plus a supporting clue.
    Non-Latin names return ``None`` and rely on Danish's transliteration variants upstream.
    """
    tokens = canonical_name_tokens(name)
    if not tokens or any(not re.fullmatch(r"[a-z]+", token) for token in tokens):
        return None

    groups = {
        **{letter: "1" for letter in "bfpv"},
        **{letter: "2" for letter in "cgjkqsxz"},
        **{letter: "3" for letter in "dt"},
        **{letter: "4" for letter in "l"},
        **{letter: "5" for letter in "mn"},
        **{letter: "6" for letter in "r"},
    }

    def encode(token: str) -> str:
        first = token[0]
        digits: list[str] = []
        previous = groups.get(first, "")
        for letter in token[1:]:
            code = groups.get(letter, "")
            if code and code != previous:
                digits.append(code)
            previous = code
        return (first + "".join(digits) + "000")[:4]

    return "-".join(encode(token) for token in tokens)
