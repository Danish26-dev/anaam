"""D1: text normalization with a map back to original offsets.

Detectors run on `TextView.text`, which has:
  * per-character NFKC (fullwidth forms, ligatures),
  * zero-width and bidi control characters removed,
  * common Cyrillic/Greek homoglyphs folded to Latin,
  * every Unicode decimal digit (Devanagari, Arabic-Indic, ...) turned into ASCII,
  * Latin combining diacritics (U+0300-U+036F) stripped.
Case is preserved because capitalization is a useful name signal; match case-insensitively
with regex flags or `str.casefold()` where needed.

`TextView.span_to_original(start, end)` converts a match in the view to the original string,
so redaction always replaces the original characters (including hidden zero-width ones).
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from functools import lru_cache

ZERO_WIDTH = frozenset(
    [0x00AD, 0x034F, 0x061C, 0x180E, 0x200B, 0x200C, 0x200D, 0x200E, 0x200F, 0x2060,
     0x2061, 0x2062, 0x2063, 0x2064, 0xFEFF]
    + list(range(0x202A, 0x202F))
    + list(range(0x2066, 0x206A))
)

HOMOGLYPHS = {
    # Cyrillic
    "А": "A", "В": "B", "Е": "E", "К": "K", "М": "M", "Н": "H", "О": "O", "Р": "P",
    "С": "C", "Т": "T", "Х": "X", "У": "Y", "І": "I", "Ј": "J", "Ѕ": "S", "Ү": "Y",
    "а": "a", "е": "e", "о": "o", "р": "p", "с": "c", "у": "y", "х": "x", "і": "i",
    "ј": "j", "ѕ": "s", "һ": "h", "ԁ": "d", "ԛ": "q", "ԝ": "w", "ү": "y", "ѵ": "v",
    # Greek
    "Α": "A", "Β": "B", "Ε": "E", "Ζ": "Z", "Η": "H", "Ι": "I", "Κ": "K", "Μ": "M",
    "Ν": "N", "Ο": "O", "Ρ": "P", "Τ": "T", "Υ": "Y", "Χ": "X", "ο": "o", "ι": "i",
    "κ": "k", "ρ": "p", "υ": "u", "χ": "x", "ν": "v", "α": "a", "τ": "t",
}


@lru_cache(maxsize=4096)
def _fold_char(ch: str) -> str:
    """Normalize one original character into zero or more view characters."""
    cp = ord(ch)
    if cp in ZERO_WIDTH:
        return ""
    if cp < 128:
        return ch
    out = []
    for c in unicodedata.normalize("NFKC", ch):
        if ord(c) in ZERO_WIDTH:
            continue
        c = HOMOGLYPHS.get(c, c)
        if c.isdigit() and not c.isascii():
            d = unicodedata.decimal(c, None)
            out.append(str(d) if d is not None else c)
            continue
        if not c.isascii() and _is_latin(c):
            base = "".join(x for x in unicodedata.normalize("NFD", c) if not 0x300 <= ord(x) <= 0x36F)
            out.append(base)
            continue
        if 0x300 <= ord(c) <= 0x36F:
            continue
        out.append(c)
    return "".join(out)


def _is_latin(c: str) -> bool:
    try:
        return "LATIN" in unicodedata.name(c)
    except ValueError:
        return False


@dataclass
class TextView:
    """A normalized view of `original` plus an index map back to it."""

    original: str
    text: str
    _map: list[int]

    @classmethod
    def of(cls, original: str) -> "TextView":
        if original.isascii() and "\x00" not in original:
            return cls(original, original, list(range(len(original))))
        chars: list[str] = []
        idx: list[int] = []
        for i, ch in enumerate(original):
            n = _fold_char(ch)
            for c in n:
                chars.append(c)
                idx.append(i)
        return cls(original, "".join(chars), idx)

    def span_to_original(self, start: int, end: int) -> tuple[int, int]:
        """Map a half-open view span to a half-open original span."""
        if not self._map or start >= end:
            return (0, 0)
        start = max(0, min(start, len(self._map) - 1))
        end = max(start + 1, min(end, len(self._map)))
        o_start = self._map[start]
        o_end = self._map[end - 1] + 1
        # absorb hidden characters (zero-width) that sit inside the original span
        return (o_start, o_end)

    def original_slice(self, start: int, end: int) -> str:
        a, b = self.span_to_original(start, end)
        return self.original[a:b]


_WS = re.compile(r"\s+")


@lru_cache(maxsize=65536)
def normalize_key(s: str) -> str:
    """Comparison key: the view normalization plus casefold and whitespace collapse."""
    return _WS.sub(" ", TextView.of(s).text.casefold()).strip()


def digits_only(s: str) -> str:
    return "".join(c for c in TextView.of(s).text if c.isdigit() and c.isascii())


# --------------------------------------------------------------------------- tokens
DEVANAGARI_LETTERS = "\u0900-\u0963\u0971-\u097F"
_TOKEN = re.compile(
    rf"[A-Za-z]+(?:['\u2019][A-Za-z]+)?|[{DEVANAGARI_LETTERS}]+|[0-9]+"
)


@dataclass(frozen=True)
class Token:
    start: int
    end: int
    text: str
    script: str  # latin | deva | digit


def tokenize(text: str) -> list[Token]:
    """Tokenize already-normalized text (a TextView.text)."""
    out = []
    for m in _TOKEN.finditer(text):
        t = m.group(0)
        c = t[0]
        script = "digit" if c.isdigit() else ("latin" if c.isascii() else "deva")
        out.append(Token(m.start(), m.end(), t, script))
    return out


def is_devanagari(s: str) -> bool:
    return any("\u0900" <= c <= "\u097F" for c in s)


def script_of(s: str) -> str:
    has_deva = is_devanagari(s)
    has_latin = any(c.isascii() and c.isalpha() for c in s)
    if has_deva and has_latin:
        return "mixed"
    if has_deva:
        return "deva"
    return "latin"
