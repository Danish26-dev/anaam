"""D6 helper: Devanagari to Latin transliteration and phonetic name keys.

`to_latin("ईश्वर्या मंडल")` gives a readable form ("reena nishaad").
`name_key(token)` gives a consonant skeleton that is equal across scripts and common
spelling variants: Mohammad / Muhammad / Mohd / Md / मोहम्मद -> "md",
Harish / Hareesh / हरीश -> "hrs", Nishad / निषाद -> "nsd".
`loose_form(token)` keeps vowels but folds long/short spellings (Reena == Rina).

Keys are for comparison only. Short keys collide easily, so callers decide how much
evidence a key match is worth (see identity_lexicon).
"""
from __future__ import annotations

import re
import unicodedata
from functools import lru_cache

from .normalization import TextView, is_devanagari

_CONS = {
    "क": "k", "ख": "kh", "ग": "g", "घ": "gh", "ङ": "n", "च": "ch", "छ": "chh", "ज": "j",
    "झ": "jh", "ञ": "n", "ट": "t", "ठ": "th", "ड": "d", "ढ": "dh", "ण": "n", "त": "t",
    "थ": "th", "द": "d", "ध": "dh", "न": "n", "ऩ": "n", "प": "p", "फ": "ph", "ब": "b",
    "भ": "bh", "म": "m", "य": "y", "र": "r", "ऱ": "r", "ल": "l", "ळ": "l", "ऴ": "l",
    "व": "v", "श": "sh", "ष": "sh", "स": "s", "ह": "h",
    # precomposed nukta forms
    "क़": "q", "ख़": "kh", "ग़": "g", "ज़": "z", "ड़": "r", "ढ़": "rh", "फ़": "f", "य़": "y",
}
_NUKTA_OF = {"क": "q", "ख": "kh", "ग": "g", "ज": "z", "ड": "r", "ढ": "rh", "फ": "f", "य": "y"}
_VOWELS = {
    "अ": "a", "आ": "aa", "इ": "i", "ई": "ee", "उ": "u", "ऊ": "oo", "ऋ": "ri", "ॠ": "ri",
    "ए": "e", "ऐ": "ai", "ओ": "o", "औ": "au", "ऍ": "e", "ऑ": "o", "ऎ": "e", "ऒ": "o",
}
_MATRAS = {
    "ा": "aa", "ि": "i", "ी": "ee", "ु": "u", "ू": "oo", "ृ": "ri", "ॄ": "ri", "े": "e",
    "ै": "ai", "ो": "o", "ौ": "au", "ॅ": "e", "ॉ": "o", "ॆ": "e", "ॊ": "o",
}
_NUKTA = "\u093c"
_VIRAMA = "\u094d"
_SIGNS = {"ं": "n", "ँ": "n", "ः": "h", "ऽ": ""}


def _translit_word(word: str) -> str:
    chars = unicodedata.normalize("NFC", word)
    # NFC decomposes some nukta letters; recombine consonant + nukta through _NUKTA_OF
    out: list[str] = []
    i = 0
    n = len(chars)
    while i < n:
        c = chars[i]
        if c in _CONS:
            cons = _CONS[c]
            j = i + 1
            if j < n and chars[j] == _NUKTA:
                cons = _NUKTA_OF.get(c, cons)
                j += 1
            out.append(cons)
            if j < n and chars[j] in _MATRAS:
                out.append(_MATRAS[chars[j]])
                j += 1
            elif j < n and chars[j] == _VIRAMA:
                j += 1
            else:
                # inherent vowel; dropped at word end (schwa deletion)
                at_end = j >= n or not ("\u0900" <= chars[j] <= "\u097f")
                if not at_end:
                    out.append("a")
            i = j
            continue
        if c in _VOWELS:
            out.append(_VOWELS[c])
        elif c in _SIGNS:
            out.append(_SIGNS[c])
        elif c in _MATRAS:
            out.append(_MATRAS[c])
        elif c in (_NUKTA, _VIRAMA):
            pass
        else:
            out.append(c)
        i += 1
    return "".join(out)


_DEVA_RUN = re.compile(r"[\u0900-\u0963\u0971-\u097f]+")


@lru_cache(maxsize=65536)
def to_latin(text: str) -> str:
    """Readable Latin form of any Devanagari runs; other text is returned unchanged."""
    if not is_devanagari(text):
        return text
    return _DEVA_RUN.sub(lambda m: _translit_word(m.group(0)), text)


def _ascii_lower(token: str) -> str:
    t = to_latin(TextView.of(token).text).casefold()
    return "".join(c for c in t if "a" <= c <= "z")


_KEY_REPLACEMENTS = [
    ("chh", "C"), ("ch", "C"), ("ksh", "ks"), ("x", "ks"), ("ph", "f"), ("ck", "k"),
    ("q", "k"), ("w", "v"), ("z", "j"), ("bh", "b"), ("dh", "d"), ("th", "t"),
    ("kh", "k"), ("gh", "g"), ("jh", "j"), ("sh", "s"), ("ngh", "nh"), ("c", "k"), ("C", "c"),
]


@lru_cache(maxsize=65536)
def name_key(token: str) -> str:
    """Consonant skeleton used to compare name tokens across scripts and spellings."""
    s = _ascii_lower(token)
    if not s:
        return ""
    for a, b in _KEY_REPLACEMENTS:
        s = s.replace(a, b)
    if s.endswith("ng") and len(s) > 3:
        s = s[:-1]
    first, rest = s[0], s[1:]
    rest = "".join(c for c in rest if c not in "aeiouyh")
    out = [first]
    for c in rest:
        if c != out[-1]:
            out.append(c)
    return "".join(out)


_LOOSE_REPLACEMENTS = [
    ("chh", "ch"), ("ph", "f"), ("w", "v"), ("th", "t"), ("dh", "d"), ("bh", "b"),
    ("kh", "k"), ("gh", "g"), ("q", "k"), ("z", "j"), ("ee", "i"), ("ii", "i"),
    ("oo", "u"), ("uu", "u"), ("aa", "a"), ("ey", "e"), ("ay", "ai"),
]


@lru_cache(maxsize=65536)
def loose_form(token: str) -> str:
    """Vowel-preserving folded spelling: Reena/Rina/रीना -> 'rina'."""
    s = _ascii_lower(token)
    for a, b in _LOOSE_REPLACEMENTS:
        s = s.replace(a, b)
    out: list[str] = []
    for c in s:
        if not out or c != out[-1]:
            out.append(c)
    s = "".join(out)
    if len(s) > 3 and s.endswith("h"):
        s = s[:-1]
    if len(s) > 3 and s[-1] == "a" and s[-2] not in "aeiou":
        # final schwa is often dropped in transliteration: Kamla / Kamal stay distinct,
        # but Rina / Reena / रीना all end the same way
        pass
    return s
